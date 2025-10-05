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

from tests.integration.test_models import AIPerfRunResult, MockServerInfo, ValidatedOutput

# Test constants
DEFAULT_MODEL = "openai/gpt-oss-20b"
DEFAULT_CONCURRENCY = "2"
DEFAULT_REQUEST_COUNT = "5"
DEFAULT_UI = "simple"

# Common multi-modal flags
IMAGE_64 = ["--image-width-mean", "64", "--image-height-mean", "64"]
AUDIO_SHORT = ["--audio-length-mean", "0.1"]

# Limit workers for integration tests to avoid exhausting system resources
MAX_WORKERS = ["--workers-max", "2"]


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
async def mock_server(mock_server_port: int) -> AsyncGenerator[MockServerInfo, None]:
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

        yield MockServerInfo(
            host=host,
            port=mock_server_port,
            url=url,
            process=process,
        )

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
) -> AIPerfRunResult:
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
            return AIPerfRunResult(
                returncode=process.returncode or 0,
                stdout=stdout_bytes.decode("utf-8", errors="replace"),
                stderr=stderr_bytes.decode("utf-8", errors="replace"),
                output_dir=Path(),  # Not used in capture mode
            )

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
            return AIPerfRunResult(
                returncode=process.returncode or 0,
                stdout="",
                stderr="",
                output_dir=Path(),  # Not used
            )

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
    ) -> AIPerfRunResult:
        """Run AIPerf and return Pydantic result model."""
        full_args = args + ["--artifact-dir", str(temp_output_dir)] if add_artifact_dir else args

        result = await run_aiperf_subprocess(full_args, timeout=timeout, capture_output=capture_output)

        return AIPerfRunResult(
            returncode=result.returncode,
            stdout=result.stdout,
            stderr=result.stderr,
            output_dir=temp_output_dir,
        )

    return runner


@pytest.fixture
def validate_aiperf_output():
    """Validate AIPerf output and return Pydantic model."""

    def validator(output_dir: Path) -> ValidatedOutput:
        json_file = next(output_dir.glob("**/*aiperf.json"))
        csv_file = next(output_dir.glob("**/*aiperf.csv"))
        log_file = next(output_dir.glob("**/logs/aiperf.log"))

        json_results = json.loads(json_file.read_text())
        csv_content = csv_file.read_text()

        assert "records" in json_results and "input_config" in json_results
        assert "Metric" in csv_content and log_file.stat().st_size > 0

        return ValidatedOutput(
            json_results=json_results,
            csv_content=csv_content,
            actual_dir=json_file.parent,
            log_file=log_file,
            json_file=json_file,
            csv_file=csv_file,
        )

    return validator


@pytest.fixture
def base_profile_args(mock_server: MockServerInfo) -> list[str]:
    """Provide base arguments for profile command."""
    return [
        "profile",
        "--model",
        DEFAULT_MODEL,
        "--url",
        mock_server.url,
        "--ui",
        DEFAULT_UI,
    ]


@pytest.fixture
def dashboard_profile_args(mock_server: MockServerInfo) -> list[str]:
    """Provide base arguments with dashboard UI."""
    return [
        "profile",
        "--model",
        DEFAULT_MODEL,
        "--url",
        mock_server.url,
        "--ui",
        "dashboard",
    ]


async def run_and_validate_benchmark(
    aiperf_runner,
    validate_aiperf_output,
    args: list[str],
    timeout: float = 60.0,
    min_requests: int | None = None,
    limit_workers: bool = True,
) -> ValidatedOutput:
    """Run benchmark and validate, returning Pydantic model."""
    # Add worker limit for integration tests to avoid resource exhaustion during parallel runs
    if limit_workers and "--workers-max" not in args:
        args = [*args, *MAX_WORKERS]

    result: AIPerfRunResult = await aiperf_runner(args, timeout=timeout)

    if result.returncode != 0:
        print(f"\n=== STDOUT ===\n{result.stdout}")
        print(f"\n=== STDERR ===\n{result.stderr}")

    assert result.returncode == 0, f"Benchmark failed with returncode {result.returncode}"

    output: ValidatedOutput = validate_aiperf_output(result.output_dir)

    if min_requests is not None:
        from tests.integration.result_validators import BenchmarkResult
        validator = BenchmarkResult.from_directory(output.actual_dir)
        count_metric = validator.get_metric("request_count")
        assert count_metric.avg >= min_requests, f"Too few requests: {count_metric.avg} < {min_requests}"

    return output


@pytest.fixture
def create_rankings_dataset(tmp_path) -> Callable[[int], Path]:
    """Create rankings dataset files."""

    def _create_dataset(num_entries: int = 5) -> Path:
        dataset_path = tmp_path / "rankings.jsonl"
        with open(dataset_path, "w") as f:
            for i in range(num_entries):
                entry = {
                    "texts": [
                        {"name": "query", "contents": [f"What is AI topic {i}?"]},
                        {"name": "passages", "contents": [
                            f"AI is computer science {i}",
                            f"ML is subset of AI {i}",
                            f"DL uses neural networks {i}",
                        ]},
                    ]
                }
                f.write(json.dumps(entry) + "\n")
        return dataset_path

    return _create_dataset
