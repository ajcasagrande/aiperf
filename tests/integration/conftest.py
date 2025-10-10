# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
import asyncio
import shutil
import socket
import sys
from collections.abc import AsyncGenerator, Callable
from contextlib import suppress
from pathlib import Path

import aiohttp
import orjson
import pytest

from tests.integration.helpers import AIPerfCLI, AIPerfSubprocessResult, MockLLMServer


@pytest.fixture
async def mock_llm_server_port() -> int:
    """Get an available port."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    return port


@pytest.fixture
async def mock_llm_server(
    mock_llm_server_port: int,
) -> AsyncGenerator[MockLLMServer, None]:
    """Start mock-llm server, wait for it to be ready, and yield the server."""

    host = "127.0.0.1"
    url = f"http://{host}:{mock_llm_server_port}"

    # Use aiperf-mock-server from the same venv as the test runner
    mock_server_cmd = shutil.which("aiperf-mock-server")
    if not mock_server_cmd:
        # Fallback to finding it relative to sys.executable
        venv_bin = Path(sys.executable).parent
        mock_server_cmd = str(venv_bin / "aiperf-mock-server")

    process = await asyncio.create_subprocess_exec(
        mock_server_cmd,
        "--host",
        host,
        "--port",
        str(mock_llm_server_port),
        "--ttft",
        "10",
        "--itl",
        "5",
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.DEVNULL,
    )

    try:
        async with aiohttp.ClientSession() as session:
            for _ in range(30):
                try:
                    async with session.get(
                        f"{url}/health", timeout=aiohttp.ClientTimeout(total=2)
                    ) as resp:
                        if resp.status == 200:
                            break
                except (aiohttp.ClientError, asyncio.TimeoutError):
                    await asyncio.sleep(0.2)

        yield MockLLMServer(
            host=host, port=mock_llm_server_port, url=url, process=process
        )

    finally:
        if process.returncode is None:
            process.terminate()
            with suppress(asyncio.TimeoutError):
                await asyncio.wait_for(process.wait(), timeout=5.0)


@pytest.fixture
def temp_output_dir(tmp_path: Path) -> Path:
    """Temporary directory for AIPerf output."""
    output_dir = tmp_path / "aiperf_output"
    output_dir.mkdir()
    return output_dir


@pytest.fixture
async def aiperf_runner(
    temp_output_dir: Path,
) -> Callable[[list[str], float], AIPerfSubprocessResult]:
    """AIPerf subprocess runner."""

    async def runner(args: list[str], timeout: float = 60.0) -> AIPerfSubprocessResult:
        full_args = args + ["--artifact-dir", str(temp_output_dir)]
        cmd = [sys.executable, "-m", "aiperf.cli"] + full_args

        process = await asyncio.create_subprocess_exec(*cmd, stdout=None, stderr=None)

        try:
            await asyncio.wait_for(process.wait(), timeout=timeout)
        except asyncio.TimeoutError as e:
            process.kill()
            raise RuntimeError(f"AIPerf timed out after {timeout}s") from e

        return AIPerfSubprocessResult(
            exit_code=process.returncode or 0,
            stdout="",
            stderr="",
            output_dir=temp_output_dir,
        )

    return runner


@pytest.fixture
def cli(
    aiperf_runner: Callable[[list[str], float], AIPerfSubprocessResult],
    mock_llm_server: MockLLMServer,
) -> AIPerfCLI:
    """AIPerf CLI wrapper."""
    return AIPerfCLI(aiperf_runner)


@pytest.fixture
def create_rankings_dataset(tmp_path: Path) -> Callable[[int], Path]:
    """Rankings dataset creator."""

    def _create_dataset(num_entries: int = 5) -> Path:
        dataset_path = tmp_path / "rankings.jsonl"
        with open(dataset_path, "w") as f:
            for i in range(num_entries):
                entry = {
                    "texts": [
                        {"name": "query", "contents": [f"What is AI topic {i}?"]},
                        {"name": "passages", "contents": [f"AI passage {i}"]},
                    ]
                }
                f.write(orjson.dumps(entry).decode("utf-8") + "\n")
        return dataset_path

    return _create_dataset
