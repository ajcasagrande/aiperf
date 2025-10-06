# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Seamless helpers for writing integration tests with minimal boilerplate."""

import shlex
from collections.abc import Callable

from .conftest import (
    run_and_validate_benchmark,
)
from .result_validators import BenchmarkResult


def parse_command(cmd: str) -> list[str]:
    """Parse multi-line command string into arguments.

    Args:
        cmd: Command string (with optional backslash line continuations)

    Returns:
        List of command arguments (without 'aiperf' prefix)

    Example:
        url = "http://localhost:8000"
        args = parse_command(f'''
            aiperf profile \
            --model Qwen/Qwen3-0.6B \
            --url {url} \
            --endpoint-type chat \
            --streaming
        ''')
    """
    cmd = cmd.strip().replace("\\\n", " ")
    args = shlex.split(cmd)

    if args and args[0] == "aiperf":
        args = args[1:]

    return args


def assert_streaming_metrics(result: BenchmarkResult) -> None:
    """Assert streaming metrics exist and are valid.

    Args:
        result: BenchmarkResult to validate

    Example:
        result = await run_chat_benchmark(..., streaming=True)
        assert_streaming_metrics(result)
    """
    assert "ttft" in result.metrics, "Missing TTFT metric"
    assert "inter_token_latency" in result.metrics, "Missing ITL metric"
    assert result.metrics["ttft"].avg > 0, "TTFT should be positive"


def assert_non_streaming_metrics(result: BenchmarkResult) -> None:
    """Assert non-streaming metrics exist.

    Args:
        result: BenchmarkResult to validate

    Example:
        result = await run_chat_benchmark(...)
        assert_non_streaming_metrics(result)
    """
    assert "request_latency" in result.metrics
    assert "output_sequence_length" in result.metrics


def assert_basic_metrics(result: BenchmarkResult) -> None:
    """Assert basic metrics that all endpoints should have.

    Args:
        result: BenchmarkResult to validate
    """
    assert "request_count" in result.metrics
    assert "request_latency" in result.metrics
    assert result.request_count > 0


class AIPerfCLI:
    """Pure CLI argument builder with full parameter control.

    Example:
        # Explicit parameters - full IDE autocomplete
        result = await cli.profile(ProfileCommand(
                endpoint_type=EndpointType.CHAT,
                streaming=True,
                request_count=10,
                concurrency=5,
                image_width_mean=64,
                image_height_mean=64,
            )
        )

        # Or raw args for complete control
        result = await cli.run("profile", "--model", "gpt-4", "--streaming")
    """

    def __init__(
        self,
        aiperf_runner: Callable,
        validate_aiperf_output: Callable,
        default_model: str = "openai/gpt-oss-20b",
        default_url: str | None = None,
    ):
        self._runner = aiperf_runner
        self._validator = validate_aiperf_output
        self._default_model = default_model
        self._default_url = default_url

    async def run(
        self,
        command: str,
        timeout: float = 60.0,
    ) -> BenchmarkResult:
        """Run aiperf from a multi-line command string.

        Args:
            command: Multi-line command string (backslash continuations supported)
            timeout: Subprocess timeout

        Example:
            result = await cli.run(f'''
                aiperf profile \
                    --model Qwen/Qwen3-0.6B \
                    --url {mock_server.url} \
                    --endpoint-type chat \
                    --streaming
            ''')
        """
        args = parse_command(command)

        output = await run_and_validate_benchmark(
            self._runner,
            self._validator,
            args,
            timeout=timeout,
        )

        return BenchmarkResult(output.artifact_dir)


class CLIArgs:
    def __init__(self):
        self._args: list[str | int | float] = []

    def add(self, flag: str, arg: str | int | float | None = None) -> "CLIArgs":
        self._args.append(flag)
        if arg is not None:
            self._args.append(arg)

    def build(self) -> list[str]:
        return self._args


__all__ = [
    "parse_command",
    "AIPerfCLI",
    "assert_streaming_metrics",
    "assert_non_streaming_metrics",
    "assert_basic_metrics",
]
