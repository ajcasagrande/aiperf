# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Seamless helpers for writing integration tests with minimal boilerplate.

Two main fixtures available:

1. **runner** - High-level helper methods (chat, benchmark, dashboard)
   ```python
   async def test_streaming_chat(runner):
       result = await runner.chat(streaming=True, images=True)
       assert "ttft" in result.metrics
   ```

2. **cli** - Direct kwargs-to-args conversion (most flexible)
   ```python
   async def test_custom_profile(cli, mock_server):
       result = await cli.profile(
           model="gpt-4",
           url=mock_server.url,
           endpoint_type=EndpointType.CHAT,
           streaming=True,
           request_count=10,
       )
       assert result.request_count >= 8
   ```
"""

from collections.abc import Callable

from aiperf.common.enums import EndpointType

from .conftest import (
    AUDIO_SHORT,
    DEFAULT_CONCURRENCY,
    DEFAULT_REQUEST_COUNT,
    IMAGE_64,
    run_and_validate_benchmark,
)
from .result_validators import BenchmarkResult


class BenchmarkRunner:
    """Provides clean methods to run benchmarks without passing fixtures repeatedly.

    All benchmark methods accept optional profile args and configuration, returning BenchmarkResult.
    Profile args default to those provided at initialization.

    Example:
        # Minimal usage with defaults
        result = await runner.chat(streaming=True, images=True)
        assert "ttft" in result.metrics

        # Override profile args per call if needed
        result = await runner.chat(custom_args, streaming=True)
    """

    def __init__(
        self,
        aiperf_runner: Callable,
        validate_aiperf_output: Callable,
        default_profile_args: list[str] | None = None,
        default_dashboard_args: list[str] | None = None,
    ):
        self._runner = aiperf_runner
        self._validator = validate_aiperf_output
        self._default_profile_args = default_profile_args or []
        self._default_dashboard_args = default_dashboard_args or []

    async def chat(
        self,
        profile_args: list[str] | None = None,
        *,
        streaming: bool = False,
        request_count: str = DEFAULT_REQUEST_COUNT,
        concurrency: str = DEFAULT_CONCURRENCY,
        images: bool = False,
        audio: bool = False,
        image_format: str = "png",
        audio_format: str = "wav",
        duration: str | None = None,
        min_requests: int | None = None,
        timeout: float = 60.0,
        extra_args: list[str] | None = None,
        **kwargs,
    ) -> BenchmarkResult:
        """Run a chat benchmark with sensible defaults.

        Args:
            profile_args: Profile arguments (uses defaults if not provided)
            streaming: Enable streaming
            request_count: Number of requests
            concurrency: Concurrency level
            images: Add synthetic images
            audio: Add synthetic audio
            image_format: Image format (png, jpeg)
            audio_format: Audio format (wav, mp3)
            duration: Benchmark duration instead of request count
            min_requests: Minimum expected requests
            timeout: Timeout in seconds
            extra_args: Additional CLI arguments
            **kwargs: Any other args passed to run_and_validate_benchmark

        Returns:
            BenchmarkResult ready for assertions
        """
        args = [
            *(profile_args if profile_args is not None else self._default_profile_args),
            "--endpoint-type",
            "chat",
        ]

        if streaming:
            args.append("--streaming")

        if duration:
            args.extend(["--benchmark-duration", duration])
        else:
            args.extend(["--request-count", request_count])

        args.extend(["--concurrency", concurrency])

        if images:
            args.extend([*IMAGE_64, "--image-format", image_format])

        if audio:
            args.extend([*AUDIO_SHORT, "--audio-format", audio_format])

        if extra_args:
            args.extend(extra_args)

        output = await run_and_validate_benchmark(
            self._runner,
            self._validator,
            args,
            timeout=timeout,
            min_requests=min_requests,
            **kwargs,
        )

        return BenchmarkResult(output.actual_dir)

    async def benchmark(
        self,
        endpoint: EndpointType,
        profile_args: list[str] | None = None,
        *,
        streaming: bool = False,
        request_count: str = DEFAULT_REQUEST_COUNT,
        concurrency: str = DEFAULT_CONCURRENCY,
        min_requests: int | None = None,
        timeout: float = 60.0,
        extra_args: list[str] | None = None,
        **kwargs,
    ) -> BenchmarkResult:
        """Run any endpoint benchmark.

        Args:
            endpoint: Endpoint type (chat, completions, embeddings, rankings, responses)
            profile_args: Profile arguments (uses defaults if not provided)
            streaming: Enable streaming
            request_count: Number of requests
            concurrency: Concurrency level
            min_requests: Minimum expected requests
            timeout: Timeout in seconds
            extra_args: Additional arguments
            **kwargs: Passed to run_and_validate_benchmark

        Returns:
            BenchmarkResult ready for assertions
        """
        args = [
            *(profile_args if profile_args is not None else self._default_profile_args),
            "--endpoint-type",
            endpoint,
            "--request-count",
            request_count,
            "--concurrency",
            concurrency,
        ]

        if streaming:
            args.append("--streaming")

        if extra_args:
            args.extend(extra_args)

        output = await run_and_validate_benchmark(
            self._runner,
            self._validator,
            args,
            timeout=timeout,
            min_requests=min_requests,
            **kwargs,
        )

        return BenchmarkResult(output.actual_dir)

    async def dashboard(
        self,
        dashboard_args: list[str] | None = None,
        *,
        request_count: str | None = None,
        duration: str | None = None,
        concurrency: str = DEFAULT_CONCURRENCY,
        streaming: bool = False,
        images: bool = False,
        audio: bool = False,
        min_requests: int | None = None,
        timeout: float = 60.0,
        **kwargs,
    ) -> BenchmarkResult:
        """Run a benchmark with dashboard UI.

        Args:
            dashboard_args: Dashboard arguments (uses defaults if not provided)
            request_count: Number of requests (or use duration)
            duration: Benchmark duration in seconds
            concurrency: Concurrency level
            streaming: Enable streaming
            images: Add synthetic images
            audio: Add synthetic audio
            min_requests: Minimum expected requests
            timeout: Timeout in seconds
            **kwargs: Passed to run_and_validate_benchmark

        Returns:
            BenchmarkResult ready for assertions
        """
        args = [
            *(
                dashboard_args
                if dashboard_args is not None
                else self._default_dashboard_args
            ),
            "--endpoint-type",
            "chat",
        ]

        if streaming:
            args.append("--streaming")

        if duration:
            args.extend(["--benchmark-duration", duration])
        elif request_count:
            args.extend(["--request-count", request_count])
        else:
            args.extend(["--request-count", "10"])

        args.extend(["--concurrency", concurrency])

        if images:
            args.extend(IMAGE_64)

        if audio:
            args.extend(AUDIO_SHORT)

        output = await run_and_validate_benchmark(
            self._runner,
            self._validator,
            args,
            timeout=timeout,
            min_requests=min_requests,
            **kwargs,
        )

        return BenchmarkResult(output.actual_dir)


# Convenient assertion helpers (complement Pythonic properties)


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
    """Clean Pythonic CLI wrapper with kwargs-to-args conversion.

    Example:
        # Simple kwargs interface - clean and Pythonic
        result = await cli.profile(
            model="gpt-4",
            url="http://localhost:8000",
            endpoint_type=EndpointType.CHAT,
            streaming=True,
            request_count=10,
            concurrency=5,
        )

        # Raw args when you need full control
        result = await cli.run("profile", "--model", "gpt-4", "--streaming")
    """

    def __init__(self, aiperf_runner: Callable, validate_aiperf_output: Callable):
        self._runner = aiperf_runner
        self._validator = validate_aiperf_output

    def _kwargs_to_args(self, **kwargs) -> list[str]:
        """Convert kwargs to CLI arguments.

        Rules:
        - snake_case → --kebab-case
        - bool True → --flag
        - bool False → omitted
        - Enum → value.name.lower()
        - list/tuple → repeated flags
        """
        args = []

        for key, value in kwargs.items():
            if value is None or value is False:
                continue

            flag = f"--{key.replace('_', '-')}"

            if isinstance(value, bool):
                args.append(flag)
            elif hasattr(value, "name"):  # Enum
                args.extend([flag, value.name.lower()])
            elif isinstance(value, (list, tuple)):
                for item in value:
                    args.extend([flag, str(item)])
            else:
                args.extend([flag, str(value)])

        return args

    async def profile(
        self,
        *,
        timeout: float = 60.0,
        min_requests: int | None = None,
        **kwargs,
    ) -> BenchmarkResult:
        """Run aiperf profile with kwargs converted to CLI args.

        Special kwargs (not converted to CLI args):
        - timeout: Subprocess timeout
        - min_requests: Minimum expected requests for validation

        All other kwargs become --flag-name arguments.

        Example:
            result = await cli.profile(
                model="gpt-4",
                url="http://localhost:8000",
                endpoint_type=EndpointType.CHAT,
                streaming=True,
                request_count=10,
                image_width_mean=64,
                image_height_mean=64,
            )
        """
        args = ["profile", *self._kwargs_to_args(**kwargs)]

        output = await run_and_validate_benchmark(
            self._runner,
            self._validator,
            args,
            timeout=timeout,
            min_requests=min_requests,
        )

        return BenchmarkResult(output.actual_dir)

    async def run(
        self,
        *args: str,
        timeout: float = 60.0,
        min_requests: int | None = None,
    ) -> BenchmarkResult:
        """Run aiperf with raw CLI arguments.

        Args:
            *args: Raw CLI arguments
            timeout: Subprocess timeout
            min_requests: Minimum expected requests

        Example:
            result = await cli.run(
                "profile",
                "--model", "gpt-4",
                "--endpoint-type", "chat",
                "--streaming",
            )
        """
        output = await run_and_validate_benchmark(
            self._runner,
            self._validator,
            list(args),
            timeout=timeout,
            min_requests=min_requests,
        )

        return BenchmarkResult(output.actual_dir)


__all__ = [
    "BenchmarkRunner",
    "AIPerfCLI",
    "assert_streaming_metrics",
    "assert_non_streaming_metrics",
    "assert_basic_metrics",
]
