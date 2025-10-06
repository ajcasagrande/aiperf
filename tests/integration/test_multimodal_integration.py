# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""
Multi-modal Integration Tests

Beautiful, Pythonic integration tests using the clean CLI wrapper.
Tests validate end-to-end multi-modal behavior including images and audio.
"""

import pytest

from tests.integration.helpers import assert_streaming_metrics


@pytest.mark.integration
@pytest.mark.asyncio
class TestMultiModalIntegration:
    """Integration tests for multi-modal content support."""

    async def test_chat_with_images(self, cli):
        """Synthetic image generation and end-to-end handling."""
        result = await cli.profile(
            request_count=5,
            concurrency=2,
            image_width_mean=64,
            image_height_mean=64,
            min_requests=3,
        )

        assert "output_sequence_length" in result.metrics
        assert result.has_images

    async def test_chat_with_audio(self, cli):
        """Synthetic audio generation and end-to-end handling."""
        result = await cli.profile(
            request_count=5,
            concurrency=2,
            audio_length_mean=0.1,
            min_requests=3,
        )

        assert "output_sequence_length" in result.metrics
        assert result.has_audio

    async def test_mixed_multimodal_content(self, cli):
        """Text + image + audio in single request."""
        result = await cli.profile(
            request_count=5,
            concurrency=2,
            image_width_mean=64,
            image_height_mean=64,
            audio_length_mean=0.1,
            min_requests=3,
        )

        assert result.has_images
        assert result.has_audio

    async def test_streaming_with_images(self, cli):
        """Streaming with TTFT/ITL metrics and images."""
        result = await cli.profile(
            streaming=True,
            request_count=5,
            concurrency=2,
            image_width_mean=64,
            image_height_mean=64,
            min_requests=3,
        )

        assert_streaming_metrics(result)
        assert result.metrics["ttft"].avg >= 0

    async def test_streaming_with_audio(self, cli):
        """Streaming with TTFT/ITL metrics and audio."""
        result = await cli.profile(
            streaming=True,
            request_count=5,
            concurrency=2,
            audio_length_mean=0.1,
            min_requests=3,
        )

        assert_streaming_metrics(result)

    async def test_large_image_dataset(self, cli):
        """Image handling scales to 20 requests."""
        await cli.profile(
            request_count=20,
            concurrency=4,
            image_width_mean=64,
            image_height_mean=64,
            timeout=120.0,
            min_requests=16,
        )

    async def test_concurrency_with_multimodal(self, cli):
        """5 concurrent workers with multi-modal content."""
        await cli.profile(
            request_count=15,
            concurrency=5,
            image_width_mean=64,
            image_height_mean=64,
            audio_length_mean=0.1,
            timeout=120.0,
            min_requests=12,
        )


@pytest.mark.integration
@pytest.mark.asyncio
class TestMultiModalSyntheticGeneration:
    """Synthetic data generation variations."""

    async def test_jpeg_format(self, cli):
        """JPEG image format support."""
        await cli.profile(
            request_count=5,
            concurrency=1,
            image_width_mean=128,
            image_height_mean=128,
            image_format="jpeg",
        )

    async def test_mp3_audio_format(self, cli):
        """MP3 audio format support."""
        await cli.profile(
            request_count=5,
            concurrency=1,
            audio_length_mean=0.1,
            audio_format="mp3",
        )


@pytest.mark.integration
@pytest.mark.asyncio
class TestDashboardUI:
    """Dashboard UI tests."""

    async def test_dashboard_with_request_count(self, cli):
        """Dashboard UI with request count limit."""
        result = await cli.profile(
            ui="dashboard",
            request_count=10,
            concurrency=2,
            image_width_mean=64,
            image_height_mean=64,
            audio_length_mean=0.1,
            min_requests=8,
        )

        assert result.artifacts_exist

    async def test_dashboard_with_duration(self, cli):
        """Dashboard UI with duration-based limit."""
        result = await cli.profile(
            ui="dashboard",
            benchmark_duration="10",
            streaming=True,
            concurrency=3,
            image_width_mean=64,
            image_height_mean=64,
            audio_length_mean=0.1,
            timeout=30.0,
            min_requests=3,
        )

        assert "ttft" in result.metrics
        assert "Benchmark Duration" in result.csv


@pytest.mark.integration
@pytest.mark.asyncio
class TestHighThroughput:
    """Stress tests with high concurrency."""

    async def test_1000_concurrent_with_streaming(self, cli):
        """1000 concurrent workers with streaming and images."""
        result = await cli.profile(
            streaming=True,
            request_count=1000,
            concurrency=1000,
            image_width_mean=64,
            image_height_mean=64,
            timeout=180.0,
            min_requests=950,
        )

        assert result.artifacts_exist
        assert_streaming_metrics(result)
        assert len(result.inputs.data) >= 10

    async def test_1000_concurrent_with_multimodal(self, cli):
        """1000 concurrent workers with streaming, images, and audio."""
        result = await cli.profile(
            streaming=True,
            request_count=1000,
            concurrency=1000,
            image_width_mean=64,
            image_height_mean=64,
            audio_length_mean=0.1,
            timeout=180.0,
            min_requests=950,
        )

        assert_streaming_metrics(result)
        assert "output_sequence_length" in result.metrics


@pytest.mark.integration
@pytest.mark.asyncio
class TestRequestCancellation:
    """Request cancellation features."""

    async def test_cancellation_rate(self, cli):
        """30% request cancellation doesn't break pipeline."""
        result = await cli.profile(
            streaming=True,
            request_count=50,
            concurrency=5,
            image_width_mean=64,
            image_height_mean=64,
            request_cancellation_rate=0.3,
            request_cancellation_delay=0.5,
            timeout=120.0,
        )

        assert result.artifacts_exist


@pytest.mark.integration
@pytest.mark.asyncio
class TestDeterministicBehavior:
    """Deterministic behavior with random seeds."""

    async def test_same_seed_produces_identical_inputs(self, cli):
        """Random seed produces identical payloads (except session UUIDs)."""
        # Run twice with same seed
        result1 = await cli.profile(
            request_count=10,
            concurrency=2,
            random_seed=42,
            image_width_mean=64,
            image_height_mean=64,
            audio_length_mean=0.1,
        )

        result2 = await cli.profile(
            request_count=10,
            concurrency=2,
            random_seed=42,
            image_width_mean=64,
            image_height_mean=64,
            audio_length_mean=0.1,
        )

        # Compare inputs
        inputs_1, inputs_2 = result1.inputs, result2.inputs
        assert len(inputs_1.data) == len(inputs_2.data), "Session counts differ"

        # Payloads identical, session_ids differ (UUIDs)
        for s1, s2 in zip(inputs_1.data, inputs_2.data, strict=True):
            assert s1.session_id != s2.session_id, "Session IDs should differ (UUIDs)"
            assert s1.payloads == s2.payloads, "Payloads should be identical"
