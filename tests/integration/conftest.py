# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""
Integration test fixtures for AIPerf.

Provides utilities to:
- Start and stop mock server
- Run AIPerf as subprocess
- Validate results
- Clean up resources
"""

import asyncio
import json
import socket
import sys
import time
from collections.abc import AsyncGenerator, Callable
from contextlib import suppress
from pathlib import Path

import pytest

# Test constants
DEFAULT_MODEL = "openai/gpt-oss-20b"
DEFAULT_CONCURRENCY = 2
DEFAULT_REQUEST_COUNT = 5
DEFAULT_UI = "simple"


async def wait_for_server(host: str, port: int, timeout: float = 30.0) -> bool:
    """Wait for server to be ready."""
    start = time.time()
    while time.time() - start < timeout:
        try:
            reader, writer = await asyncio.open_connection(host, port)
            writer.close()
            await writer.wait_closed()
            return True
        except (ConnectionRefusedError, OSError):
            await asyncio.sleep(0.1)
    return False


@pytest.fixture
async def mock_server_port() -> int:
    """Get an available port for mock server.

    Uses OS-assigned ephemeral port by binding to port 0,
    which is more reliable than random selection.
    """
    # Let OS pick a free port
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        s.listen(1)
        port = s.getsockname()[1]

    # Small window where port could be taken, but much better than random selection
    return port


@pytest.fixture
async def mock_server(mock_server_port: int) -> AsyncGenerator[dict, None]:
    """Start fakeai mock server and return connection info.

    Uses fakeai package from PyPI (version 0.0.5+) which provides
    an OpenAI-compatible API server for testing.

    Yields:
        dict with 'host', 'port', 'url', 'process'

    Note:
        Some flakiness may occur due to rapid server process creation/destruction
        in test suites. Run with `pytest -n 0` to disable parallel execution if needed.
    """
    host = "127.0.0.1"
    url = f"http://{host}:{mock_server_port}"

    # Start fakeai server using CLI flags (more reliable than env vars in subprocess)
    cmd = [
        "fakeai",
        "server",
        "--host",
        host,
        "--port",
        str(mock_server_port),
        "--response-delay",
        "0.01",  # Small delay for realistic behavior
    ]

    # Create server process with stdout/stderr redirected to DEVNULL
    # to avoid buffer blocking issues
    process = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.DEVNULL,
    )

    try:
        # Wait for server to be ready with TCP connection check
        ready = await wait_for_server(host, mock_server_port, timeout=30.0)
        if not ready:
            if process.returncode is None:
                process.terminate()
                with suppress(asyncio.TimeoutError):
                    await asyncio.wait_for(process.wait(), timeout=2.0)
            raise RuntimeError(f"FakeAI server failed to bind to {url}")

        # Verify server is responding to HTTP with retries
        import aiohttp

        # Give server extra time to fully initialize
        await asyncio.sleep(1.5)

        for attempt in range(30):
            # Check if process crashed
            if process.returncode is not None:
                raise RuntimeError(
                    f"FakeAI server process exited with code {process.returncode}"
                )

            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(
                        f"{url}/health", timeout=aiohttp.ClientTimeout(total=2)
                    ) as response:
                        if response.status == 200:
                            # Server is up and responding
                            break
            except (aiohttp.ClientError, asyncio.TimeoutError):
                if attempt == 29:
                    raise RuntimeError(
                        f"FakeAI server not responding after {attempt + 1} attempts at {url}/health"
                    )
                await asyncio.sleep(0.2)

        yield {
            "host": host,
            "port": mock_server_port,
            "url": url,
            "process": process,
        }

    finally:
        # Cleanup: Gracefully stop server
        if process.returncode is None:
            process.terminate()
            try:
                await asyncio.wait_for(process.wait(), timeout=5.0)
            except asyncio.TimeoutError:
                # Force kill if termination hangs
                process.kill()
                with suppress(Exception):
                    await process.wait()

        # Brief delay to allow port release
        await asyncio.sleep(0.1)


@pytest.fixture
def temp_output_dir(tmp_path: Path) -> Path:
    """Create temporary directory for AIPerf output."""
    output_dir = tmp_path / "aiperf_output"
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir


async def run_aiperf_subprocess(
    args: list[str],
    timeout: float = 60.0,
    cwd: Path | None = None,
    capture_output: bool = False,
) -> tuple[int, str, str]:
    """Run AIPerf as a subprocess.

    Args:
        args: Command-line arguments for aiperf
        timeout: Maximum time to wait
        cwd: Working directory
        capture_output: If False, output goes to terminal in real-time

    Returns:
        tuple of (returncode, stdout, stderr)
    """
    cmd = [sys.executable, "-m", "aiperf.cli"] + args

    if capture_output:
        # Capture for validation
        process = await asyncio.create_subprocess_exec(
            *cmd,
            cwd=str(cwd) if cwd else None,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        try:
            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                process.communicate(), timeout=timeout
            )
            stdout = stdout_bytes.decode("utf-8", errors="replace")
            stderr = stderr_bytes.decode("utf-8", errors="replace")
            return process.returncode, stdout, stderr

        except asyncio.TimeoutError as timeout_error:
            # Kill the process on timeout
            with suppress(Exception):
                process.kill()
                await process.wait()
            raise RuntimeError(
                f"AIPerf subprocess timed out after {timeout}s"
            ) from timeout_error
    else:
        # Stream output to terminal in real-time
        process = await asyncio.create_subprocess_exec(
            *cmd,
            cwd=str(cwd) if cwd else None,
            stdout=None,  # Inherit stdout
            stderr=None,  # Inherit stderr
        )

        try:
            await asyncio.wait_for(process.wait(), timeout=timeout)
            return process.returncode, "", ""

        except asyncio.TimeoutError as timeout_error:
            with suppress(Exception):
                process.kill()
                await process.wait()
            raise RuntimeError(
                f"AIPerf subprocess timed out after {timeout}s"
            ) from timeout_error


@pytest.fixture
async def aiperf_runner(temp_output_dir: Path):
    """Fixture to run AIPerf commands."""

    async def runner(
        args: list[str],
        timeout: float = 60.0,
        add_artifact_dir: bool = True,
        capture_output: bool = False,
    ) -> dict:
        """Run AIPerf and return results.

        Args:
            args: AIPerf command-line arguments
            timeout: Maximum execution time
            add_artifact_dir: Whether to add --artifact-dir
            capture_output: If False, stream output to terminal

        Returns:
            dict with 'returncode', 'stdout', 'stderr', 'output_dir'
        """
        # Add output directory unless disabled
        if add_artifact_dir:
            full_args = args + ["--artifact-dir", str(temp_output_dir)]
        else:
            full_args = args

        returncode, stdout, stderr = await run_aiperf_subprocess(
            full_args,
            timeout=timeout,
            capture_output=capture_output,
        )

        return {
            "returncode": returncode,
            "stdout": stdout,
            "stderr": stderr,
            "output_dir": temp_output_dir,
        }

    return runner


@pytest.fixture
def validate_aiperf_output():
    """Fixture to validate AIPerf output files."""

    def validator(output_dir: Path, check_inputs_json: bool = True) -> dict:
        """Validate AIPerf output and return results.

        Args:
            output_dir: Directory containing AIPerf output
            check_inputs_json: Whether to verify inputs.json was generated

        Returns:
            dict with comprehensive validation results including:
            - json_results: Parsed JSON output
            - csv_content: CSV file contents
            - log_file: Path to log file
            - actual_dir: Actual artifact directory
            - inputs_json: Parsed inputs.json (if exists)
        """
        # AIPerf writes directly to the artifact directory
        # Look for JSON and CSV files
        json_files = list(output_dir.glob("**/*aiperf.json"))
        csv_files = list(output_dir.glob("**/*aiperf.csv"))
        log_files = list(output_dir.glob("**/logs/aiperf.log"))
        inputs_json_files = list(output_dir.glob("**/inputs.json"))

        assert len(json_files) > 0, (
            f"No JSON results found in {output_dir}. Contents: {list(output_dir.rglob('*'))}"
        )
        assert len(csv_files) > 0, f"No CSV results found in {output_dir}"
        assert len(log_files) > 0, f"No log file found in {output_dir}"

        json_file = json_files[0]
        csv_file = csv_files[0]
        log_file = log_files[0]

        # Load and validate JSON results
        with open(json_file) as f:
            json_results = json.load(f)

        assert "records" in json_results, "JSON missing records"
        assert "input_config" in json_results, "JSON missing input_config"
        assert isinstance(json_results["records"], dict), "records should be dict"

        # Load CSV results
        with open(csv_file) as f:
            csv_content = f.read()

        # Validate CSV has header and content
        assert len(csv_content) > 0, "CSV file is empty"
        assert "Metric" in csv_content, "CSV missing header row"

        # Validate log file has content
        assert log_file.stat().st_size > 0, "Log file is empty"

        result = {
            "json_results": json_results,
            "csv_content": csv_content,
            "log_file": log_file,
            "actual_dir": json_file.parent,
            "json_file": json_file,
            "csv_file": csv_file,
        }

        # Check for inputs.json if requested
        if check_inputs_json and len(inputs_json_files) > 0:
            with open(inputs_json_files[0]) as f:
                inputs_json = json.load(f)
            assert "data" in inputs_json, "inputs.json missing data"
            result["inputs_json"] = inputs_json
            result["inputs_json_file"] = inputs_json_files[0]

        return result

    return validator


@pytest.fixture
def base_profile_args(mock_server) -> list[str]:
    """Provide base arguments for profile command."""
    return [
        "profile",
        "--model",
        DEFAULT_MODEL,
        "--url",
        mock_server["url"],
        "--ui",
        DEFAULT_UI,
    ]


@pytest.fixture
def create_rankings_dataset(tmp_path) -> Callable[[int], Path]:
    """Factory fixture to create rankings dataset files."""

    def _create_dataset(num_entries: int = 5) -> Path:
        """Create a rankings dataset with query and passages.

        Args:
            num_entries: Number of ranking entries to create

        Returns:
            Path to the created dataset file
        """
        dataset_path = tmp_path / "rankings.jsonl"
        with open(dataset_path, "w") as f:
            for i in range(num_entries):
                entry = {
                    "texts": [
                        {
                            "name": "query",
                            "contents": [f"What is artificial intelligence topic {i}?"],
                        },
                        {
                            "name": "passages",
                            "contents": [
                                f"AI is a branch of computer science {i}",
                                f"Machine learning is a subset of AI {i}",
                                f"Deep learning uses neural networks {i}",
                            ],
                        },
                    ]
                }
                f.write(json.dumps(entry) + "\n")
        return dataset_path

    return _create_dataset


def assert_basic_metrics(records: dict, *metric_names: str) -> None:
    """Assert that basic metrics exist in records.

    Args:
        records: The metrics records dictionary
        *metric_names: Variable number of metric names to check
    """
    assert isinstance(records, dict), "records should be a dict"
    for metric_name in metric_names:
        assert metric_name in records, f"Missing {metric_name} metric"


def assert_streaming_metrics(records: dict) -> None:
    """Assert that streaming-specific metrics exist and are valid.

    Args:
        records: The metrics records dictionary
    """
    assert_basic_metrics(records, "ttft", "inter_token_latency")
    assert records["ttft"]["avg"] > 0, "TTFT should be positive"


def assert_no_token_metrics(records: dict) -> None:
    """Assert that token-producing metrics are NOT present.

    Args:
        records: The metrics records dictionary
    """
    assert "ttft" not in records, "Should not have TTFT"
    assert "inter_token_latency" not in records, "Should not have ITL"
    assert "output_sequence_length" not in records, (
        "Should not have output_sequence_length"
    )
