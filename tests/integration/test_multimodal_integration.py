# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""
Multi-modal Integration Tests

These tests validate end-to-end behavior of AIPerf with multi-modal content
including synthetic images and audio. They test:
- Image content handling
- Audio content handling
- Mixed multi-modal content (text + image + audio)
- Dataset loading and conversion
- Request formatting for multi-modal payloads
- Response parsing with multi-modal inputs

These are TRUE integration tests - they run aiperf as a subprocess with
fakeai mock server and verify real multi-modal behavior.
"""

import pytest

from tests.integration.conftest import (
    AUDIO_SHORT,
    DEFAULT_CONCURRENCY,
    DEFAULT_REQUEST_COUNT,
    IMAGE_64,
    run_and_validate_benchmark,
)
from tests.integration.result_validators import BenchmarkResult
from tests.integration.test_models import AIPerfRunResult


@pytest.mark.integration
@pytest.mark.asyncio
class TestMultiModalIntegration:
    """Integration tests for multi-modal content support."""

    async def test_chat_endpoint_with_image_content(
        self, base_profile_args, aiperf_runner, validate_aiperf_output
    ):
        """Validates synthetic image generation and end-to-end image handling."""
        args = [*base_profile_args, "--endpoint-type", "chat",
                "--request-count", DEFAULT_REQUEST_COUNT, "--concurrency", DEFAULT_CONCURRENCY,
                *IMAGE_64, "--image-format", "png"]

        output = await run_and_validate_benchmark(
            aiperf_runner, validate_aiperf_output, args, min_requests=3
        )

        BenchmarkResult.from_directory(output.actual_dir) \
            .assert_metric_exists("output_sequence_length") \
            .assert_inputs_json_has_images()

    async def test_chat_endpoint_with_audio_content(
        self, base_profile_args, aiperf_runner, validate_aiperf_output
    ):
        """Validates synthetic audio generation and end-to-end audio handling."""
        args = [*base_profile_args, "--endpoint-type", "chat",
                "--request-count", DEFAULT_REQUEST_COUNT, "--concurrency", DEFAULT_CONCURRENCY,
                *AUDIO_SHORT, "--audio-format", "wav"]

        output = await run_and_validate_benchmark(
            aiperf_runner, validate_aiperf_output, args, min_requests=3
        )

        BenchmarkResult.from_directory(output.actual_dir) \
            .assert_metric_exists("output_sequence_length") \
            .assert_inputs_json_has_audio()

    async def test_chat_endpoint_with_mixed_multimodal_content(
        self, base_profile_args, aiperf_runner, validate_aiperf_output
    ):
        """Validates text + image + audio together in single request."""
        args = [*base_profile_args, "--endpoint-type", "chat",
                "--request-count", DEFAULT_REQUEST_COUNT, "--concurrency", DEFAULT_CONCURRENCY,
                *IMAGE_64, *AUDIO_SHORT]

        output = await run_and_validate_benchmark(
            aiperf_runner, validate_aiperf_output, args, min_requests=3
        )

        BenchmarkResult.from_directory(output.actual_dir) \
            .assert_inputs_json_has_images() \
            .assert_inputs_json_has_audio()

    async def test_streaming_with_image_content(
        self, base_profile_args, aiperf_runner, validate_aiperf_output
    ):
        """Validates streaming + TTFT/ITL metrics with images."""
        args = [*base_profile_args, "--endpoint-type", "chat", "--streaming",
                "--request-count", DEFAULT_REQUEST_COUNT, "--concurrency", DEFAULT_CONCURRENCY,
                *IMAGE_64]

        output = await run_and_validate_benchmark(
            aiperf_runner, validate_aiperf_output, args, min_requests=3
        )

        BenchmarkResult.from_directory(output.actual_dir) \
            .assert_metric_exists("ttft", "inter_token_latency") \
            .assert_metric_in_range("ttft", min_value=0)

    async def test_streaming_with_audio_content(
        self, base_profile_args, aiperf_runner, validate_aiperf_output
    ):
        """Validates streaming + TTFT/ITL metrics with audio."""
        args = [*base_profile_args, "--endpoint-type", "chat", "--streaming",
                "--request-count", DEFAULT_REQUEST_COUNT, "--concurrency", DEFAULT_CONCURRENCY,
                *AUDIO_SHORT]

        output = await run_and_validate_benchmark(
            aiperf_runner, validate_aiperf_output, args, min_requests=3
        )

        BenchmarkResult.from_directory(output.actual_dir) \
            .assert_metric_exists("ttft", "inter_token_latency")

    async def test_large_image_dataset(
        self, base_profile_args, aiperf_runner, validate_aiperf_output
    ):
        """Validates image handling scales to 20 requests."""
        args = [*base_profile_args, "--endpoint-type", "chat",
                "--request-count", "20", "--concurrency", "4", *IMAGE_64]

        await run_and_validate_benchmark(
            aiperf_runner, validate_aiperf_output, args, timeout=120.0, min_requests=16
        )

    async def test_concurrency_with_multimodal_content(
        self, base_profile_args, aiperf_runner, validate_aiperf_output
    ):
        """Validates 5 concurrent workers with multi-modal content."""
        args = [*base_profile_args, "--endpoint-type", "chat",
                "--request-count", "15", "--concurrency", "5", *IMAGE_64, *AUDIO_SHORT]

        await run_and_validate_benchmark(
            aiperf_runner, validate_aiperf_output, args, timeout=120.0, min_requests=12
        )


@pytest.mark.integration
@pytest.mark.asyncio
class TestMultiModalSyntheticGeneration:
    """Integration tests for multi-modal synthetic data generation."""

    async def test_image_format_variations(
        self, base_profile_args, aiperf_runner, validate_aiperf_output
    ):
        """Validates JPEG format support."""
        args = [*base_profile_args, "--endpoint-type", "chat",
                "--request-count", DEFAULT_REQUEST_COUNT, "--concurrency", "1",
                "--image-width-mean", "128", "--image-height-mean", "128", "--image-format", "jpeg"]

        await run_and_validate_benchmark(aiperf_runner, validate_aiperf_output, args)

    async def test_audio_format_variations(
        self, base_profile_args, aiperf_runner, validate_aiperf_output
    ):
        """Validates MP3 format support."""
        args = [*base_profile_args, "--endpoint-type", "chat",
                "--request-count", DEFAULT_REQUEST_COUNT, "--concurrency", "1",
                *AUDIO_SHORT, "--audio-format", "mp3", "--audio-sample-rates", "44.1"]

        await run_and_validate_benchmark(aiperf_runner, validate_aiperf_output, args)


@pytest.mark.integration
@pytest.mark.asyncio
class TestMultiModalWithDashboard:
    """Integration tests for multi-modal content with dashboard UI."""

    async def test_dashboard_ui_with_request_count(
        self, dashboard_profile_args, aiperf_runner, validate_aiperf_output
    ):
        """Validates dashboard UI with request-count limit."""
        args = [*dashboard_profile_args, "--endpoint-type", "chat",
                "--request-count", "10", "--concurrency", DEFAULT_CONCURRENCY,
                *IMAGE_64, *AUDIO_SHORT]

        output = await run_and_validate_benchmark(
            aiperf_runner, validate_aiperf_output, args, min_requests=8
        )

        BenchmarkResult.from_directory(output.actual_dir) \
            .assert_all_artifacts_exist()

    async def test_dashboard_ui_with_benchmark_duration(
        self, dashboard_profile_args, aiperf_runner, validate_aiperf_output
    ):
        """Validates dashboard UI with duration-based limit (10 seconds)."""
        args = [*dashboard_profile_args, "--endpoint-type", "chat", "--streaming",
                "--benchmark-duration", "10", "--concurrency", "3", *IMAGE_64, *AUDIO_SHORT]

        output = await run_and_validate_benchmark(
            aiperf_runner, validate_aiperf_output, args, timeout=30.0, min_requests=3
        )

        BenchmarkResult.from_directory(output.actual_dir) \
            .assert_metric_exists("ttft") \
            .assert_csv_contains("Benchmark Duration")


@pytest.mark.integration
@pytest.mark.asyncio
class TestMultiModalStressTests:
    """Stress tests for multi-modal content with high concurrency."""

    async def test_high_throughput_streaming_1000_concurrency(
        self, base_profile_args, aiperf_runner, validate_aiperf_output
    ):
        """Validates 1000 concurrent workers with streaming + images."""
        args = [*base_profile_args, "--endpoint-type", "chat", "--streaming",
                "--request-count", "1000", "--concurrency", "1000", *IMAGE_64]

        output = await run_and_validate_benchmark(
            aiperf_runner, validate_aiperf_output, args, timeout=180.0, min_requests=950
        )

        BenchmarkResult.from_directory(output.actual_dir) \
            .assert_all_artifacts_exist() \
            .assert_metric_exists("ttft", "inter_token_latency") \
            .assert_inputs_json_has_sessions(min_sessions=10)

    async def test_high_throughput_streaming_with_audio(
        self, base_profile_args, aiperf_runner, validate_aiperf_output
    ):
        """Validates 1000 concurrent workers with streaming + images + audio."""
        args = [*base_profile_args, "--endpoint-type", "chat", "--streaming",
                "--request-count", "1000", "--concurrency", "1000", *IMAGE_64, *AUDIO_SHORT]

        output = await run_and_validate_benchmark(
            aiperf_runner, validate_aiperf_output, args, timeout=180.0, min_requests=950
        )

        BenchmarkResult.from_directory(output.actual_dir) \
            .assert_metric_exists("ttft", "inter_token_latency", "output_sequence_length")


@pytest.mark.integration
@pytest.mark.asyncio
class TestCancellationFeatures:
    """Integration tests for benchmark cancellation features."""

    async def test_request_cancellation_rate(
        self, base_profile_args, aiperf_runner, validate_aiperf_output
    ):
        """Validates 30% request cancellation doesn't break pipeline."""
        args = [*base_profile_args, "--endpoint-type", "chat", "--streaming",
                "--request-count", "50", "--concurrency", "5",
                "--request-cancellation-rate", "0.3", "--request-cancellation-delay", "0.5",
                *IMAGE_64]

        output = await run_and_validate_benchmark(
            aiperf_runner, validate_aiperf_output, args, timeout=120.0
        )

        BenchmarkResult.from_directory(output.actual_dir).assert_all_artifacts_exist()


@pytest.mark.integration
@pytest.mark.asyncio
class TestDeterministicBehavior:
    """Integration tests for deterministic behavior with random seeds."""

    async def test_same_seed_produces_identical_inputs(
        self, base_profile_args, aiperf_runner, validate_aiperf_output, tmp_path
    ):
        """Validates --random-seed produces identical payloads (except session UUIDs)."""
        base_args = [*base_profile_args, "--endpoint-type", "chat",
                     "--request-count", "10", "--concurrency", "2",
                     "--random-seed", "42", *IMAGE_64, *AUDIO_SHORT]

        # Run twice with same seed
        results = []
        for i in [1, 2]:
            output_dir = tmp_path / f"run{i}"
            output_dir.mkdir()
            args = [*base_args, "--artifact-dir", str(output_dir)]

            result: AIPerfRunResult = await aiperf_runner(args, add_artifact_dir=False)
            assert result.returncode == 0
            results.append(validate_aiperf_output(output_dir))

        # Compare using Pydantic models
        v1 = BenchmarkResult.from_directory(results[0].actual_dir)
        v2 = BenchmarkResult.from_directory(results[1].actual_dir)

        inputs_1, inputs_2 = v1.inputs_file, v2.inputs_file
        assert len(inputs_1.data) == len(inputs_2.data)

        # Payloads identical, session_ids differ (UUIDs)
        for s1, s2 in zip(inputs_1.data, inputs_2.data):
            assert s1.session_id != s2.session_id
            assert s1.payloads == s2.payloads
