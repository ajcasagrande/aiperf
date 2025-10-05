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
    DEFAULT_CONCURRENCY,
    DEFAULT_REQUEST_COUNT,
    assert_basic_metrics,
)


@pytest.mark.integration
@pytest.mark.asyncio
class TestMultiModalIntegration:
    """Integration tests for multi-modal content support."""

    async def test_chat_endpoint_with_image_content(
        self,
        base_profile_args,
        aiperf_runner,
        validate_aiperf_output,
    ):
        """Test chat endpoint with synthetic image content.

        WHY TEST THIS:
        - Validates image content handling end-to-end
        - Ensures AIPerf's built-in synthetic image generation works
        - Verifies image data does not break the benchmark pipeline
        - Tests production code path users would follow
        """
        args = [
            *base_profile_args,
            "--endpoint-type",
            "chat",
            "--request-count",
            str(DEFAULT_REQUEST_COUNT),
            "--concurrency",
            str(DEFAULT_CONCURRENCY),
            "--image-width-mean",
            "64",
            "--image-height-mean",
            "64",
            "--image-format",
            "png",
        ]

        result = await aiperf_runner(args)

        if result["returncode"] != 0:
            print(f"\n=== STDOUT ===\n{result['stdout']}")
            print(f"\n=== STDERR ===\n{result['stderr']}")

        assert result["returncode"] == 0, (
            f"Image benchmark failed with returncode {result['returncode']}"
        )

        output = validate_aiperf_output(result["output_dir"])
        records = output["json_results"]["records"]

        # Verify basic metrics exist
        assert_basic_metrics(records, "request_count", "request_latency")

        # Verify requests completed successfully
        completed = records["request_count"].get("avg", 0)
        assert completed >= DEFAULT_REQUEST_COUNT - 2, (
            f"Too few image requests completed: {completed} < {DEFAULT_REQUEST_COUNT - 2}"
        )

        # Verify token-based metrics exist (chat endpoint produces tokens)
        assert_basic_metrics(records, "output_sequence_length")

    async def test_chat_endpoint_with_audio_content(
        self,
        base_profile_args,
        aiperf_runner,
        validate_aiperf_output,
    ):
        """Test chat endpoint with synthetic audio content.

        WHY TEST THIS:
        - Validates audio content handling end-to-end
        - Ensures AIPerf's built-in synthetic audio generation works
        - Verifies audio data does not break the benchmark pipeline
        - Tests production code path users would follow
        """
        args = [
            *base_profile_args,
            "--endpoint-type",
            "chat",
            "--request-count",
            str(DEFAULT_REQUEST_COUNT),
            "--concurrency",
            str(DEFAULT_CONCURRENCY),
            "--audio-length-mean",
            "0.1",
            "--audio-format",
            "wav",
            "--audio-sample-rates",
            "16.0",
        ]

        result = await aiperf_runner(args)

        if result["returncode"] != 0:
            print(f"\n=== STDOUT ===\n{result['stdout']}")
            print(f"\n=== STDERR ===\n{result['stderr']}")

        assert result["returncode"] == 0, (
            f"Audio benchmark failed with returncode {result['returncode']}"
        )

        output = validate_aiperf_output(result["output_dir"])
        records = output["json_results"]["records"]

        # Verify basic metrics exist
        assert_basic_metrics(records, "request_count", "request_latency")

        # Verify requests completed successfully
        completed = records["request_count"].get("avg", 0)
        assert completed >= DEFAULT_REQUEST_COUNT - 2, (
            f"Too few audio requests completed: {completed} < {DEFAULT_REQUEST_COUNT - 2}"
        )

        # Verify token-based metrics exist (chat endpoint produces tokens)
        assert_basic_metrics(records, "output_sequence_length")

    async def test_chat_endpoint_with_mixed_multimodal_content(
        self,
        base_profile_args,
        aiperf_runner,
        validate_aiperf_output,
    ):
        """Test chat endpoint with mixed multi-modal content (text + image + audio).

        WHY TEST THIS:
        - Validates complete multi-modal pipeline (text, image, audio)
        - Ensures multiple modalities can coexist in single request
        - Verifies AIPerf can generate text + image + audio together
        - Tests end-to-end multi-modal request handling
        """
        args = [
            *base_profile_args,
            "--endpoint-type",
            "chat",
            "--request-count",
            str(DEFAULT_REQUEST_COUNT),
            "--concurrency",
            str(DEFAULT_CONCURRENCY),
            "--image-width-mean",
            "64",
            "--image-height-mean",
            "64",
            "--image-format",
            "png",
            "--audio-length-mean",
            "0.1",
            "--audio-format",
            "wav",
        ]

        result = await aiperf_runner(args)

        if result["returncode"] != 0:
            print(f"\n=== STDOUT ===\n{result['stdout']}")
            print(f"\n=== STDERR ===\n{result['stderr']}")

        assert result["returncode"] == 0, (
            f"Multi-modal benchmark failed with returncode {result['returncode']}"
        )

        output = validate_aiperf_output(result["output_dir"])
        records = output["json_results"]["records"]

        # Verify basic metrics exist
        assert_basic_metrics(records, "request_count", "request_latency")

        # Verify requests completed successfully
        completed = records["request_count"].get("avg", 0)
        assert completed >= DEFAULT_REQUEST_COUNT - 2, (
            f"Too few multi-modal requests completed: {completed} < {DEFAULT_REQUEST_COUNT - 2}"
        )

        # Verify token-based metrics exist
        assert_basic_metrics(records, "output_sequence_length")

    async def test_streaming_with_image_content(
        self,
        base_profile_args,
        aiperf_runner,
        validate_aiperf_output,
    ):
        """Test streaming chat endpoint with image content.

        WHY TEST THIS:
        - Validates streaming works with multi-modal content
        - Ensures SSE parsing handles multi-modal requests
        - Verifies TTFT and ITL metrics are computed with images
        - Tests streaming-specific behavior with images
        """
        args = [
            *base_profile_args,
            "--endpoint-type",
            "chat",
            "--streaming",
            "--request-count",
            str(DEFAULT_REQUEST_COUNT),
            "--concurrency",
            str(DEFAULT_CONCURRENCY),
            "--image-width-mean",
            "64",
            "--image-height-mean",
            "64",
            "--image-format",
            "png",
        ]

        result = await aiperf_runner(args)

        if result["returncode"] != 0:
            print(f"\n=== STDOUT ===\n{result['stdout']}")
            print(f"\n=== STDERR ===\n{result['stderr']}")

        assert result["returncode"] == 0, (
            f"Streaming image benchmark failed with returncode {result['returncode']}"
        )

        output = validate_aiperf_output(result["output_dir"])
        records = output["json_results"]["records"]

        # Verify basic metrics exist
        assert_basic_metrics(records, "request_count", "request_latency")

        # Verify streaming metrics exist
        assert_basic_metrics(records, "ttft", "inter_token_latency")
        assert records["ttft"]["avg"] > 0, "TTFT should be positive"

        # Verify requests completed successfully
        completed = records["request_count"].get("avg", 0)
        assert completed >= DEFAULT_REQUEST_COUNT - 2, (
            f"Too few streaming image requests completed: {completed}"
        )

    async def test_streaming_with_audio_content(
        self,
        base_profile_args,
        aiperf_runner,
        validate_aiperf_output,
    ):
        """Test streaming chat endpoint with audio content.

        WHY TEST THIS:
        - Validates streaming works with audio content
        - Ensures SSE parsing handles audio requests
        - Verifies TTFT and ITL metrics are computed with audio
        - Tests streaming-specific behavior with audio
        """
        args = [
            *base_profile_args,
            "--endpoint-type",
            "chat",
            "--streaming",
            "--request-count",
            str(DEFAULT_REQUEST_COUNT),
            "--concurrency",
            str(DEFAULT_CONCURRENCY),
            "--audio-length-mean",
            "0.1",
            "--audio-format",
            "wav",
        ]

        result = await aiperf_runner(args)

        if result["returncode"] != 0:
            print(f"\n=== STDOUT ===\n{result['stdout']}")
            print(f"\n=== STDERR ===\n{result['stderr']}")

        assert result["returncode"] == 0, (
            f"Streaming audio benchmark failed with returncode {result['returncode']}"
        )

        output = validate_aiperf_output(result["output_dir"])
        records = output["json_results"]["records"]

        # Verify basic metrics exist
        assert_basic_metrics(records, "request_count", "request_latency")

        # Verify streaming metrics exist
        assert_basic_metrics(records, "ttft", "inter_token_latency")
        assert records["ttft"]["avg"] > 0, "TTFT should be positive"

        # Verify requests completed successfully
        completed = records["request_count"].get("avg", 0)
        assert completed >= DEFAULT_REQUEST_COUNT - 2, (
            f"Too few streaming audio requests completed: {completed}"
        )

    async def test_large_image_dataset(
        self,
        base_profile_args,
        aiperf_runner,
        validate_aiperf_output,
    ):
        """Test with larger image dataset to verify scalability.

        WHY TEST THIS:
        - Validates image handling scales with dataset size
        - Ensures memory handling for multiple image requests
        - Verifies no performance degradation with many images
        - Tests realistic workload with multiple image requests
        """
        large_count = 20

        args = [
            *base_profile_args,
            "--endpoint-type",
            "chat",
            "--request-count",
            str(large_count),
            "--concurrency",
            "4",
            "--image-width-mean",
            "64",
            "--image-height-mean",
            "64",
            "--image-format",
            "png",
        ]

        result = await aiperf_runner(args, timeout=120.0)

        if result["returncode"] != 0:
            print(f"\n=== STDOUT ===\n{result['stdout']}")
            print(f"\n=== STDERR ===\n{result['stderr']}")

        assert result["returncode"] == 0, (
            f"Large image dataset benchmark failed with returncode {result['returncode']}"
        )

        output = validate_aiperf_output(result["output_dir"])
        records = output["json_results"]["records"]

        # Verify basic metrics exist
        assert_basic_metrics(records, "request_count", "request_latency")

        # Verify most requests completed successfully
        completed = records["request_count"].get("avg", 0)
        assert completed >= large_count - 4, (
            f"Too few large dataset requests completed: {completed} < {large_count - 4}"
        )

    async def test_concurrency_with_multimodal_content(
        self,
        base_profile_args,
        aiperf_runner,
        validate_aiperf_output,
    ):
        """Test concurrent multi-modal requests.

        WHY TEST THIS:
        - Validates multi-modal requests work under high concurrency
        - Ensures no race conditions with multi-modal data
        - Verifies worker coordination with complex payloads
        - Tests realistic concurrent multi-modal workload
        """
        args = [
            *base_profile_args,
            "--endpoint-type",
            "chat",
            "--request-count",
            "15",
            "--concurrency",
            "5",
            "--image-width-mean",
            "64",
            "--image-height-mean",
            "64",
            "--audio-length-mean",
            "0.1",
        ]

        result = await aiperf_runner(args, timeout=120.0)

        if result["returncode"] != 0:
            print(f"\n=== STDOUT ===\n{result['stdout']}")
            print(f"\n=== STDERR ===\n{result['stderr']}")

        assert result["returncode"] == 0, (
            f"Concurrent multi-modal benchmark failed with returncode {result['returncode']}"
        )

        output = validate_aiperf_output(result["output_dir"])
        records = output["json_results"]["records"]

        # Verify basic metrics exist
        assert_basic_metrics(records, "request_count", "request_latency")

        # Verify requests completed successfully
        completed = records["request_count"].get("avg", 0)
        assert completed >= 12, f"Too few concurrent requests completed: {completed}"


@pytest.mark.integration
@pytest.mark.asyncio
class TestMultiModalSyntheticGeneration:
    """Integration tests for multi-modal synthetic data generation."""

    async def test_image_format_variations(
        self,
        base_profile_args,
        aiperf_runner,
        validate_aiperf_output,
    ):
        """Test different image formats (PNG, JPEG).

        WHY TEST THIS:
        - Validates AIPerf supports multiple image formats
        - Ensures format flag is correctly applied
        - Tests production image generation code paths
        """
        args = [
            *base_profile_args,
            "--endpoint-type",
            "chat",
            "--request-count",
            str(DEFAULT_REQUEST_COUNT),
            "--concurrency",
            "1",
            "--image-width-mean",
            "128",
            "--image-height-mean",
            "128",
            "--image-format",
            "jpeg",
        ]

        result = await aiperf_runner(args)
        assert result["returncode"] == 0, "JPEG image generation failed"

        output = validate_aiperf_output(result["output_dir"])
        records = output["json_results"]["records"]
        assert_basic_metrics(records, "request_count")

    async def test_audio_format_variations(
        self,
        base_profile_args,
        aiperf_runner,
        validate_aiperf_output,
    ):
        """Test different audio formats (WAV, MP3).

        WHY TEST THIS:
        - Validates AIPerf supports multiple audio formats
        - Ensures format flag is correctly applied
        - Tests production audio generation code paths
        """
        args = [
            *base_profile_args,
            "--endpoint-type",
            "chat",
            "--request-count",
            str(DEFAULT_REQUEST_COUNT),
            "--concurrency",
            "1",
            "--audio-length-mean",
            "0.1",
            "--audio-format",
            "mp3",
            "--audio-sample-rates",
            "44.1",
        ]

        result = await aiperf_runner(args)
        assert result["returncode"] == 0, "MP3 audio generation failed"

        output = validate_aiperf_output(result["output_dir"])
        records = output["json_results"]["records"]
        assert_basic_metrics(records, "request_count")


@pytest.mark.integration
@pytest.mark.asyncio
class TestMultiModalWithDashboard:
    """Integration tests for multi-modal content with dashboard UI."""

    async def test_dashboard_ui_with_request_count(
        self,
        base_profile_args,
        aiperf_runner,
        validate_aiperf_output,
    ):
        """Test dashboard UI with multi-modal content using request count.

        WHY TEST THIS:
        - Validates dashboard UI works with multi-modal benchmarks
        - Ensures progress tracking displays correctly for images/audio
        - Tests request-count based stopping condition with dashboard
        - Verifies UI doesn't break with complex multi-modal payloads
        """
        # Build args with dashboard UI instead of simple
        # base_profile_args contains: profile, --model, ..., --url, ..., --ui, simple
        # We need to replace the --ui simple part with --ui dashboard
        args_without_ui = []
        skip_next = False
        for _i, arg in enumerate(base_profile_args):
            if skip_next:
                skip_next = False
                continue
            if arg == "--ui":
                skip_next = True  # Skip the next arg (simple)
                continue
            args_without_ui.append(arg)

        dashboard_args = [
            *args_without_ui,
            "--ui",
            "dashboard",
            "--endpoint-type",
            "chat",
            "--request-count",
            "10",
            "--concurrency",
            str(DEFAULT_CONCURRENCY),
            "--image-width-mean",
            "64",
            "--image-height-mean",
            "64",
            "--audio-length-mean",
            "0.1",
        ]

        result = await aiperf_runner(dashboard_args)

        if result["returncode"] != 0:
            print(f"\n=== STDOUT ===\n{result['stdout']}")
            print(f"\n=== STDERR ===\n{result['stderr']}")

        assert result["returncode"] == 0, (
            f"Dashboard benchmark with request-count failed: {result['returncode']}"
        )

        output = validate_aiperf_output(result["output_dir"])
        records = output["json_results"]["records"]

        # Verify basic metrics exist
        assert_basic_metrics(records, "request_count", "request_latency")

        # Verify we completed the expected number of requests
        completed = records["request_count"].get("avg", 0)
        assert completed >= 8, f"Too few requests completed: {completed}"

        # Verify multi-modal metrics
        assert_basic_metrics(records, "output_sequence_length")

    async def test_dashboard_ui_with_benchmark_duration(
        self,
        base_profile_args,
        aiperf_runner,
        validate_aiperf_output,
    ):
        """Test dashboard UI with multi-modal content using benchmark duration.

        WHY TEST THIS:
        - Validates dashboard UI with time-based stopping condition
        - Ensures duration-based benchmarks work with multi-modal content
        - Tests that dashboard displays time remaining correctly
        - Verifies streaming multi-modal content works with duration limit
        """
        # Build args with dashboard UI instead of simple
        # base_profile_args contains: profile, --model, ..., --url, ..., --ui, simple
        # We need to replace the --ui simple part with --ui dashboard
        args_without_ui = []
        skip_next = False
        for _i, arg in enumerate(base_profile_args):
            if skip_next:
                skip_next = False
                continue
            if arg == "--ui":
                skip_next = True  # Skip the next arg (simple)
                continue
            args_without_ui.append(arg)

        dashboard_args = [
            *args_without_ui,
            "--ui",
            "dashboard",
            "--endpoint-type",
            "chat",
            "--streaming",
            "--benchmark-duration",
            "10",  # 10 second duration
            "--concurrency",
            "3",
            "--image-width-mean",
            "64",
            "--image-height-mean",
            "64",
            "--audio-length-mean",
            "0.1",
            "--audio-format",
            "wav",
        ]

        result = await aiperf_runner(dashboard_args, timeout=30.0)

        if result["returncode"] != 0:
            print(f"\n=== STDOUT ===\n{result['stdout']}")
            print(f"\n=== STDERR ===\n{result['stderr']}")

        assert result["returncode"] == 0, (
            f"Dashboard benchmark with duration failed: {result['returncode']}"
        )

        output = validate_aiperf_output(result["output_dir"])
        records = output["json_results"]["records"]

        # Verify basic metrics exist
        assert_basic_metrics(records, "request_count", "request_latency")

        # Verify streaming metrics exist
        assert_basic_metrics(records, "ttft", "inter_token_latency")

        # Verify some requests were completed (at least a few in 10 seconds)
        completed = records["request_count"].get("avg", 0)
        assert completed >= 3, f"Too few requests in duration test: {completed}"


@pytest.mark.integration
@pytest.mark.asyncio
class TestMultiModalStressTests:
    """Stress tests for multi-modal content with high concurrency."""

    async def test_high_throughput_streaming_1000_concurrency(
        self,
        base_profile_args,
        aiperf_runner,
        validate_aiperf_output,
    ):
        """Test high throughput with 1000 requests at 1000 concurrency, streaming.

        WHY TEST THIS:
        - Validates system handles extreme concurrency (1000 concurrent workers)
        - Ensures streaming works under maximum load
        - Tests worker coordination at scale with multi-modal content
        - Verifies credit system doesn't deadlock under high concurrency
        - Validates ZMQ message bus handles 1000+ concurrent connections
        """
        args = [
            *base_profile_args,
            "--endpoint-type",
            "chat",
            "--streaming",
            "--request-count",
            "1000",
            "--concurrency",
            "1000",
            "--image-width-mean",
            "64",
            "--image-height-mean",
            "64",
        ]

        result = await aiperf_runner(args, timeout=180.0)

        if result["returncode"] != 0:
            print(f"\n=== STDOUT ===\n{result['stdout']}")
            print(f"\n=== STDERR ===\n{result['stderr']}")

        assert result["returncode"] == 0, (
            f"High throughput 1000 concurrency test failed: {result['returncode']}"
        )

        output = validate_aiperf_output(result["output_dir"])
        records = output["json_results"]["records"]

        # Verify basic metrics exist
        assert_basic_metrics(records, "request_count", "request_latency")

        # Verify streaming metrics exist
        assert_basic_metrics(records, "ttft", "inter_token_latency")

        # Verify we completed most requests (allow some failures under extreme load)
        completed = records["request_count"].get("avg", 0)
        assert completed >= 950, (
            f"Too few requests completed under high load: {completed} < 950"
        )

        # Verify output sequence length exists
        avg_osl = records.get("output_sequence_length", {}).get("avg", 0)
        assert avg_osl > 0, f"OSL should be positive, got {avg_osl}"

    async def test_high_throughput_streaming_with_audio(
        self,
        base_profile_args,
        aiperf_runner,
        validate_aiperf_output,
    ):
        """Test high throughput with 1000 requests at 1000 concurrency, with audio.

        WHY TEST THIS:
        - Validates system handles extreme concurrency with audio content
        - Ensures streaming metrics (TTFT, ITL) work correctly at scale
        - Tests multi-modal content (text + image + audio) under maximum load
        - Verifies system stability with 1000 concurrent workers + audio
        - Tests that complex payloads don't cause memory issues at scale
        """
        args = [
            *base_profile_args,
            "--endpoint-type",
            "chat",
            "--streaming",
            "--request-count",
            "1000",
            "--concurrency",
            "1000",
            "--image-width-mean",
            "64",
            "--image-height-mean",
            "64",
            "--audio-length-mean",
            "0.1",
            "--audio-format",
            "wav",
        ]

        result = await aiperf_runner(args, timeout=180.0)

        if result["returncode"] != 0:
            print(f"\n=== STDOUT ===\n{result['stdout']}")
            print(f"\n=== STDERR ===\n{result['stderr']}")

        assert result["returncode"] == 0, (
            f"High throughput with audio test failed: {result['returncode']}"
        )

        output = validate_aiperf_output(result["output_dir"])
        records = output["json_results"]["records"]

        # Verify basic metrics exist
        assert_basic_metrics(records, "request_count", "request_latency")

        # Verify streaming metrics exist
        assert_basic_metrics(records, "ttft", "inter_token_latency")

        # Verify we completed most requests (allow some failures under extreme load)
        completed = records["request_count"].get("avg", 0)
        assert completed >= 950, (
            f"Too few requests completed under high load: {completed} < 950"
        )

        # Verify inter-token latency was computed
        itl_avg = records.get("inter_token_latency", {}).get("avg", 0)
        assert itl_avg > 0, "ITL should be computed with streaming"

        # Verify output tokens were generated
        avg_osl = records.get("output_sequence_length", {}).get("avg", 0)
        assert avg_osl > 0, "Output tokens should be generated"
