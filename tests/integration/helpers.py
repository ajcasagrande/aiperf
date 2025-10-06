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

from aiperf.common.enums import AIPerfUIType, AudioFormat, EndpointType, ImageFormat

from .conftest import (
    run_and_validate_benchmark,
)
from .result_validators import BenchmarkResult

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
    """Pure CLI argument builder with full parameter control.

    Example:
        # Explicit parameters - full IDE autocomplete
        result = await cli.profile(
            endpoint_type=EndpointType.CHAT,
            streaming=True,
            request_count=10,
            concurrency=5,
            image_width_mean=64,
            image_height_mean=64,
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
        # Core
        model: str | None = "openai/gpt-oss-20b",
        url: str | None = None,
        endpoint_type: EndpointType = EndpointType.CHAT,
        ui: AIPerfUIType = AIPerfUIType.SIMPLE,
        # Request config
        streaming: bool = False,
        request_count: int | None = 10,
        concurrency: int | None = 2,
        benchmark_duration: str | None = None,
        # Multi-modal
        image_width_mean: int | None = None,
        image_height_mean: int | None = None,
        image_format: ImageFormat | str | None = ImageFormat.PNG,
        audio_length_mean: float | None = None,
        audio_format: AudioFormat | str | None = AudioFormat.WAV,
        # Advanced
        random_seed: int | None = None,
        workers_max: int | None = 2,
        request_cancellation_rate: float | None = None,
        request_cancellation_delay: float | None = None,
        # Test control
        timeout: float = 60.0,
        min_requests: int | None = 8,
        **kwargs,
    ) -> BenchmarkResult:
        """Pure CLI argument builder - all parameters explicit.

        Every parameter maps directly to a CLI flag. No magic, no defaults.

        Args:
            model: Model name (uses fixture default if None)
            url: Endpoint URL (uses fixture default if None)
            endpoint_type: Endpoint type
            ui: UI type
            streaming: Enable streaming
            request_count: Number of requests
            concurrency: Concurrency level
            benchmark_duration: Duration instead of request count
            image_width_mean: Image width
            image_height_mean: Image height
            image_format: Image format
            audio_length_mean: Audio length
            audio_format: Audio format
            random_seed: Random seed
            workers_max: Maximum workers
            request_cancellation_rate: Cancellation rate
            request_cancellation_delay: Cancellation delay
            timeout: Subprocess timeout
            min_requests: Minimum expected requests
            **kwargs: Any other CLI args

        Example:
            result = await cli.profile(
                endpoint_type=EndpointType.CHAT,
                streaming=True,
                request_count=10,
                concurrency=5,
                image_width_mean=64,
                image_height_mean=64,
            )
        """
        cli_args = {
            "model": model or self._default_model,
            "url": url or self._default_url,
            "endpoint_type": endpoint_type,
            "ui": ui,
        }

        # Add all non-None/False parameters
        if streaming:
            cli_args["streaming"] = streaming
        if request_count is not None:
            cli_args["request_count"] = request_count
        if concurrency is not None:
            cli_args["concurrency"] = concurrency
        if benchmark_duration is not None:
            cli_args["benchmark_duration"] = benchmark_duration
        if image_width_mean is not None:
            cli_args["image_width_mean"] = image_width_mean
        if image_height_mean is not None:
            cli_args["image_height_mean"] = image_height_mean
        if image_format is not None:
            cli_args["image_format"] = image_format
        if audio_length_mean is not None:
            cli_args["audio_length_mean"] = audio_length_mean
        if audio_format is not None:
            cli_args["audio_format"] = audio_format
        if random_seed is not None:
            cli_args["random_seed"] = random_seed
        if workers_max is not None:
            cli_args["workers_max"] = workers_max
        if request_cancellation_rate is not None:
            cli_args["request_cancellation_rate"] = request_cancellation_rate
        if request_cancellation_delay is not None:
            cli_args["request_cancellation_delay"] = request_cancellation_delay

        # Merge user kwargs (override everything)
        merged = {**cli_args, **kwargs}

        # Build CLI args and run
        args = ["profile", *self._kwargs_to_args(**merged)]

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
    "AIPerfCLI",
    "assert_streaming_metrics",
    "assert_non_streaming_metrics",
    "assert_basic_metrics",
]
