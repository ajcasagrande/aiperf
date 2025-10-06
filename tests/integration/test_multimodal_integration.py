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

from tests.integration.conftest import AUDIO_SHORT, IMAGE_64
from tests.integration.helpers import assert_streaming_metrics
from tests.integration.result_validators import BenchmarkResult
from tests.integration.test_models import AIPerfRunResult


@pytest.mark.integration
@pytest.mark.asyncio
class TestMultiModalIntegration:
    """Integration tests for multi-modal content support."""

    async def test_chat_endpoint_with_image_content(self, base_profile_args, runner):
        """Validates synthetic image generation and end-to-end image handling."""
        result = await runner.chat(base_profile_args, images=True, min_requests=3)

        assert "output_sequence_length" in result.metrics
        assert result.has_images

    async def test_chat_endpoint_with_audio_content(self, base_profile_args, runner):
        """Validates synthetic audio generation and end-to-end audio handling."""
        result = await runner.chat(base_profile_args, audio=True, min_requests=3)

        assert "output_sequence_length" in result.metrics
        assert result.has_audio

    async def test_chat_endpoint_with_mixed_multimodal_content(
        self, base_profile_args, runner
    ):
        """Validates text + image + audio together in single request."""
        result = await runner.chat(
            base_profile_args, images=True, audio=True, min_requests=3
        )

        assert result.has_images
        assert result.has_audio

    async def test_streaming_with_image_content(self, base_profile_args, runner):
        """Validates streaming + TTFT/ITL metrics with images."""
        result = await runner.chat(
            base_profile_args, streaming=True, images=True, min_requests=3
        )

        assert_streaming_metrics(result)
        assert result.metrics["ttft"].avg >= 0

    async def test_streaming_with_audio_content(self, base_profile_args, runner):
        """Validates streaming + TTFT/ITL metrics with audio."""
        result = await runner.chat(
            base_profile_args, streaming=True, audio=True, min_requests=3
        )

        assert_streaming_metrics(result)

    async def test_large_image_dataset(self, base_profile_args, runner):
        """Validates image handling scales to 20 requests."""
        await runner.chat(
            base_profile_args,
            request_count="20",
            concurrency="4",
            images=True,
            timeout=120.0,
            min_requests=16,
        )

    async def test_concurrency_with_multimodal_content(self, base_profile_args, runner):
        """Validates 5 concurrent workers with multi-modal content."""
        await runner.chat(
            base_profile_args,
            request_count="15",
            concurrency="5",
            images=True,
            audio=True,
            timeout=120.0,
            min_requests=12,
        )


@pytest.mark.integration
@pytest.mark.asyncio
class TestMultiModalSyntheticGeneration:
    """Integration tests for multi-modal synthetic data generation."""

    async def test_image_format_variations(self, base_profile_args, runner):
        """Validates JPEG format support."""
        await runner.chat(
            base_profile_args,
            concurrency="1",
            image_format="jpeg",
            extra_args=["--image-width-mean", "128", "--image-height-mean", "128"],
        )

    async def test_audio_format_variations(self, base_profile_args, runner):
        """Validates MP3 format support."""
        await runner.chat(
            base_profile_args,
            concurrency="1",
            audio=True,
            audio_format="mp3",
            extra_args=["--audio-sample-rates", "44.1"],
        )


@pytest.mark.integration
@pytest.mark.asyncio
class TestMultiModalWithDashboard:
    """Integration tests for multi-modal content with dashboard UI."""

    async def test_dashboard_ui_with_request_count(
        self, dashboard_profile_args, runner
    ):
        """Validates dashboard UI with request-count limit."""
        result = await runner.dashboard(
            dashboard_profile_args,
            request_count="10",
            images=True,
            audio=True,
            min_requests=8,
        )

        assert result.artifacts_exist

    async def test_dashboard_ui_with_benchmark_duration(
        self, dashboard_profile_args, runner
    ):
        """Validates dashboard UI with duration-based limit (10 seconds)."""
        result = await runner.dashboard(
            dashboard_profile_args,
            duration="10",
            streaming=True,
            concurrency="3",
            images=True,
            audio=True,
            timeout=30.0,
            min_requests=3,
        )

        assert "ttft" in result.metrics
        assert "Benchmark Duration" in result.csv


@pytest.mark.integration
@pytest.mark.asyncio
class TestMultiModalStressTests:
    """Stress tests for multi-modal content with high concurrency."""

    async def test_high_throughput_streaming_1000_concurrency(
        self, base_profile_args, runner
    ):
        """Validates 1000 concurrent workers with streaming + images."""
        result = await runner.chat(
            base_profile_args,
            streaming=True,
            request_count="1000",
            concurrency="1000",
            images=True,
            timeout=180.0,
            min_requests=950,
            limit_workers=False,
        )

        assert result.artifacts_exist
        assert_streaming_metrics(result)
        assert len(result.inputs.data) >= 10

    async def test_high_throughput_streaming_with_audio(
        self, base_profile_args, runner
    ):
        """Validates 1000 concurrent workers with streaming + images + audio."""
        result = await runner.chat(
            base_profile_args,
            streaming=True,
            request_count="1000",
            concurrency="1000",
            images=True,
            audio=True,
            timeout=180.0,
            min_requests=950,
            limit_workers=False,
        )

        assert_streaming_metrics(result)
        assert "output_sequence_length" in result.metrics


@pytest.mark.integration
@pytest.mark.asyncio
class TestCancellationFeatures:
    """Integration tests for benchmark cancellation features."""

    async def test_request_cancellation_rate(self, base_profile_args, runner):
        """Validates 30% request cancellation doesn't break pipeline."""
        result = await runner.chat(
            base_profile_args,
            streaming=True,
            request_count="50",
            concurrency="5",
            images=True,
            timeout=120.0,
            extra_args=[
                "--request-cancellation-rate",
                "0.3",
                "--request-cancellation-delay",
                "0.5",
            ],
        )

        assert result.artifacts_exist


@pytest.mark.integration
@pytest.mark.asyncio
class TestDeterministicBehavior:
    """Integration tests for deterministic behavior with random seeds."""

    async def _run_aiperf_with_seed(
        self,
        run_number: int,
        base_args: list[str],
        tmp_path,
        aiperf_runner,
        validate_aiperf_output,
    ) -> BenchmarkResult:
        """Helper to run AIPerf and return BenchmarkResult."""
        output_dir = tmp_path / f"run{run_number}"
        output_dir.mkdir()
        args = [*base_args, "--artifact-dir", str(output_dir)]

        result: AIPerfRunResult = await aiperf_runner(args, add_artifact_dir=False)
        assert result.returncode == 0, (
            f"Run {run_number} failed with code {result.returncode}"
        )

        validated = validate_aiperf_output(output_dir)
        return BenchmarkResult(validated.actual_dir)

    async def test_same_seed_produces_identical_inputs(
        self, base_profile_args, aiperf_runner, validate_aiperf_output, tmp_path
    ):
        """Validates --random-seed produces identical payloads (except session UUIDs)."""
        base_args = [
            *base_profile_args,
            "--endpoint-type",
            "chat",
            "--request-count",
            "10",
            "--concurrency",
            "2",
            "--random-seed",
            "42",
            *IMAGE_64,
            *AUDIO_SHORT,
        ]

        # Run twice with same seed
        run1 = await self._run_aiperf_with_seed(
            1, base_args, tmp_path, aiperf_runner, validate_aiperf_output
        )
        run2 = await self._run_aiperf_with_seed(
            2, base_args, tmp_path, aiperf_runner, validate_aiperf_output
        )

        # Compare inputs files
        inputs_1, inputs_2 = run1.inputs, run2.inputs
        assert len(inputs_1.data) == len(inputs_2.data), "Session counts differ"

        # Payloads identical, session_ids differ (UUIDs)
        for s1, s2 in zip(inputs_1.data, inputs_2.data, strict=True):
            assert s1.session_id != s2.session_id, (
                "Session IDs should be different (UUIDs)"
            )
            assert s1.payloads == s2.payloads, "Payloads should be identical"
