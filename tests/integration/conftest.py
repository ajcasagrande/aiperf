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
import os
import socket
import sys
import time
from collections.abc import AsyncGenerator
from pathlib import Path

import pytest


def is_port_in_use(port: int, host: str = "127.0.0.1") -> bool:
    """Check if a port is already in use."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind((host, port))
            return False
        except OSError:
            return True


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
    """Get an available port for mock server."""
    # Try a few common ports
    for port in range(39000, 40000):
        if not is_port_in_use(port):
            return port
    raise RuntimeError("No available ports found")


@pytest.fixture
async def mock_server(mock_server_port: int) -> AsyncGenerator[dict, None]:
    """Start fakeai mock server and return connection info.

    Yields:
        dict with 'host', 'port', 'url', 'process'
    """
    host = "127.0.0.1"
    url = f"http://{host}:{mock_server_port}"

    # Start fakeai server
    cmd = ["fakeai-server"]

    # Configure fakeai via environment variables
    env = {
        **dict(os.environ),
        "FAKEAI_HOST": host,
        "FAKEAI_PORT": str(mock_server_port),
        "FAKEAI_DEBUG": "false",
        "FAKEAI_RESPONSE_DELAY": "0.01",  # Small delay for realistic behavior
    }

    process = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env=env,
    )

    try:
        # Wait for server to be ready
        ready = await wait_for_server(host, mock_server_port, timeout=30.0)
        if not ready:
            raise RuntimeError(f"FakeAI server failed to start on {url}")

        # Give it a moment to fully initialize
        await asyncio.sleep(0.5)

        yield {
            "host": host,
            "port": mock_server_port,
            "url": url,
            "process": process,
        }

    finally:
        # Cleanup: Stop the server
        if process.returncode is None:
            process.terminate()
            try:
                await asyncio.wait_for(process.wait(), timeout=5.0)
            except asyncio.TimeoutError:
                process.kill()
                await process.wait()


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

        except asyncio.TimeoutError:
            # Kill the process on timeout
            try:
                process.kill()
                await process.wait()
            except:
                pass
            raise RuntimeError(f"AIPerf subprocess timed out after {timeout}s")
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

        except asyncio.TimeoutError:
            try:
                process.kill()
                await process.wait()
            except:
                pass
            raise RuntimeError(f"AIPerf subprocess timed out after {timeout}s")


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

    def validator(output_dir: Path) -> dict:
        """Validate AIPerf output and return results.

        Returns:
            dict with 'json_results', 'csv_results', 'log_file'
        """
        # AIPerf writes directly to the artifact directory
        # Look for JSON and CSV files
        json_files = list(output_dir.glob("**/*aiperf.json"))
        csv_files = list(output_dir.glob("**/*aiperf.csv"))
        log_files = list(output_dir.glob("**/logs/aiperf.log"))

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

        # Load CSV results
        with open(csv_file) as f:
            csv_content = f.read()

        return {
            "json_results": json_results,
            "csv_content": csv_content,
            "log_file": log_file,
            "actual_dir": json_file.parent,
        }

    return validator
