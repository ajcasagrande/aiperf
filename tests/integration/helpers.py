# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Seamless helpers for writing integration tests with minimal boilerplate."""

from typing import Literal

from .conftest import (
    AUDIO_SHORT,
    DEFAULT_CONCURRENCY,
    DEFAULT_REQUEST_COUNT,
    IMAGE_64,
    run_and_validate_benchmark,
)
from .result_validators import BenchmarkResult

EndpointType = Literal["chat", "completions", "embeddings", "rankings", "responses"]


async def run_chat_benchmark(
    base_profile_args,
    aiperf_runner,
    validate_aiperf_output,
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
    """Run a chat benchmark with sensible defaults and return validated result.

    This is the ultimate helper - just specify what you want to test!

    Args:
        base_profile_args: Base profile arguments fixture
        aiperf_runner: Runner fixture
        validate_aiperf_output: Validator fixture
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

    Example:
        # Minimal - just test chat
        result = await run_chat_benchmark(base_profile_args, aiperf_runner, validate_aiperf_output)
        assert "request_latency" in result.metrics

        # With images
        result = await run_chat_benchmark(..., images=True)
        assert result.has_images

        # Streaming with multi-modal
        result = await run_chat_benchmark(..., streaming=True, images=True, audio=True)
        assert "ttft" in result.metrics
        assert result.has_images and result.has_audio
    """
    args = [*base_profile_args, "--endpoint-type", "chat"]

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
        aiperf_runner,
        validate_aiperf_output,
        args,
        timeout=timeout,
        min_requests=min_requests,
        **kwargs,
    )

    return BenchmarkResult(output.actual_dir)


async def run_benchmark(
    base_profile_args,
    aiperf_runner,
    validate_aiperf_output,
    endpoint: EndpointType,
    *,
    streaming: bool = False,
    request_count: str = DEFAULT_REQUEST_COUNT,
    concurrency: str = DEFAULT_CONCURRENCY,
    min_requests: int | None = None,
    timeout: float = 60.0,
    extra_args: list[str] | None = None,
    **kwargs,
) -> BenchmarkResult:
    """Run any endpoint benchmark with minimal configuration.

    Universal helper for any endpoint type.

    Args:
        base_profile_args: Base profile arguments
        aiperf_runner: Runner fixture
        validate_aiperf_output: Validator fixture
        endpoint: Endpoint type (chat, completions, embeddings, rankings, responses)
        streaming: Enable streaming
        request_count: Number of requests
        concurrency: Concurrency level
        min_requests: Minimum expected requests
        timeout: Timeout in seconds
        extra_args: Additional arguments
        **kwargs: Passed to run_and_validate_benchmark

    Returns:
        BenchmarkResult ready for assertions

    Example:
        result = await run_benchmark(..., endpoint="embeddings")
        assert "request_latency" in result.metrics
    """
    args = [
        *base_profile_args,
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
        aiperf_runner,
        validate_aiperf_output,
        args,
        timeout=timeout,
        min_requests=min_requests,
        **kwargs,
    )

    return BenchmarkResult(output.actual_dir)


async def run_dashboard_benchmark(
    dashboard_profile_args,
    aiperf_runner,
    validate_aiperf_output,
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
        dashboard_profile_args: Dashboard profile arguments fixture
        aiperf_runner: Runner fixture
        validate_aiperf_output: Validator fixture
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

    Example:
        # Duration-based
        result = await run_dashboard_benchmark(..., duration="10", streaming=True)
        assert "ttft" in result.metrics

        # Request-count based
        result = await run_dashboard_benchmark(..., request_count="20")
        assert result.request_count >= 18
    """
    args = [*dashboard_profile_args, "--endpoint-type", "chat"]

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
        aiperf_runner,
        validate_aiperf_output,
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
