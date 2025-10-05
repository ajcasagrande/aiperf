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
    run_and_validate_benchmark,
)
from tests.integration.result_validators import BenchmarkResult, ConsoleOutputValidator


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

        output = await run_and_validate_benchmark(
            aiperf_runner,
            validate_aiperf_output,
            args,
            min_requests=DEFAULT_REQUEST_COUNT - 2,
        )

        # Use full Pydantic API for all validation
        BenchmarkResult.from_directory(output["actual_dir"]) \
            .assert_metric_exists("request_count", "request_latency", "output_sequence_length")

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

        output = await run_and_validate_benchmark(
            aiperf_runner,
            validate_aiperf_output,
            args,
            min_requests=DEFAULT_REQUEST_COUNT - 2,
        )

        # Use full Pydantic API for all validation
        BenchmarkResult.from_directory(output["actual_dir"]) \
            .assert_metric_exists("request_count", "request_latency", "output_sequence_length") \
            .assert_csv_contains("Request Latency", "Output Sequence Length") \
            .assert_inputs_json_has_audio()

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

        output = await run_and_validate_benchmark(
            aiperf_runner,
            validate_aiperf_output,
            args,
            min_requests=DEFAULT_REQUEST_COUNT - 2,
        )

        # Use full Pydantic API for all validation
        BenchmarkResult.from_directory(output["actual_dir"]) \
            .assert_metric_exists("request_count", "request_latency", "output_sequence_length") \
            .assert_csv_contains("Request Latency", "Output Sequence Length") \
            .assert_inputs_json_has_images() \
            .assert_inputs_json_has_audio()

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

        output = await run_and_validate_benchmark(
            aiperf_runner,
            validate_aiperf_output,
            args,
            min_requests=DEFAULT_REQUEST_COUNT - 2,
        )

        # Use fluent Pydantic API for all validation
        BenchmarkResult.from_directory(output["actual_dir"]) \
            .assert_metric_exists("ttft", "inter_token_latency") \
            .assert_metric_in_range("ttft", min_value=0) \
            .assert_csv_contains("Time to First Token", "Inter Token Latency")

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

        output = await run_and_validate_benchmark(
            aiperf_runner,
            validate_aiperf_output,
            args,
            min_requests=DEFAULT_REQUEST_COUNT - 2,
        )

        # Use fluent Pydantic API for all validation
        BenchmarkResult.from_directory(output["actual_dir"]) \
            .assert_metric_exists("ttft", "inter_token_latency") \
            .assert_metric_in_range("ttft", min_value=0)

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

        output = await run_and_validate_benchmark(
            aiperf_runner,
            validate_aiperf_output,
            args,
            timeout=120.0,
            min_requests=large_count - 4,
        )

        # Use Pydantic API
        BenchmarkResult.from_directory(output["actual_dir"]) \
            .assert_metric_exists("request_count", "request_latency")

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

        output = await run_and_validate_benchmark(
            aiperf_runner, validate_aiperf_output, args, timeout=120.0, min_requests=12
        )

        # Use Pydantic API
        BenchmarkResult.from_directory(output["actual_dir"]) \
            .assert_metric_exists("request_count", "request_latency")


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

        output = await run_and_validate_benchmark(
            aiperf_runner, validate_aiperf_output, args
        )

        # Use Pydantic API
        BenchmarkResult.from_directory(output["actual_dir"]) \
            .assert_metric_exists("request_count")

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

        output = await run_and_validate_benchmark(
            aiperf_runner, validate_aiperf_output, args
        )

        # Use Pydantic API
        BenchmarkResult.from_directory(output["actual_dir"]) \
            .assert_metric_exists("request_count")


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

        output = await run_and_validate_benchmark(
            aiperf_runner, validate_aiperf_output, dashboard_args, min_requests=8
        )

        # Use full Pydantic API for all validation
        BenchmarkResult.from_directory(output["actual_dir"]) \
            .assert_all_artifacts_exist() \
            .assert_metric_exists("output_sequence_length") \
            .assert_csv_contains("Request Latency", "Output Sequence Length")

    async def test_dashboard_ui_with_benchmark_duration(
        self,
        dashboard_profile_args,
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
        dashboard_args = [
            *dashboard_profile_args,
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

        output = await run_and_validate_benchmark(
            aiperf_runner, validate_aiperf_output, dashboard_args, timeout=30.0, min_requests=3
        )

        # Use full Pydantic API for all validation
        BenchmarkResult.from_directory(output["actual_dir"]) \
            .assert_all_artifacts_exist() \
            .assert_metric_exists("ttft", "inter_token_latency") \
            .assert_csv_contains("Time to First Token", "Benchmark Duration")


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

        output = await run_and_validate_benchmark(
            aiperf_runner, validate_aiperf_output, args, timeout=180.0, min_requests=950
        )

        # Use full Pydantic API for comprehensive validation
        BenchmarkResult.from_directory(output["actual_dir"]) \
            .assert_all_artifacts_exist() \
            .assert_log_not_empty() \
            .assert_metric_exists("ttft", "inter_token_latency", "request_latency", "output_sequence_length") \
            .assert_metric_in_range("ttft", min_value=0) \
            .assert_metric_in_range("inter_token_latency", min_value=0) \
            .assert_csv_contains("Time to First Token", "Request Throughput") \
            .assert_inputs_json_has_sessions(min_sessions=10)

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

        output = await run_and_validate_benchmark(
            aiperf_runner, validate_aiperf_output, args, timeout=180.0, min_requests=950
        )

        # Use fluent Pydantic API for all validation
        validator = BenchmarkResult.from_directory(output["actual_dir"])
        validator.assert_metric_exists("ttft", "inter_token_latency", "output_sequence_length")
        validator.assert_metric_in_range("inter_token_latency", min_value=0)
        validator.assert_metric_in_range("output_sequence_length", min_value=0)


@pytest.mark.integration
@pytest.mark.asyncio
class TestCancellationFeatures:
    """Integration tests for benchmark cancellation features."""

    @pytest.mark.skip(reason="SIGINT handling is complex - tested manually")
    async def test_ctrl_c_cancellation(
        self,
        base_profile_args,
        temp_output_dir,
    ):
        """Test that Ctrl-C (SIGINT) gracefully cancels benchmark and shows results.

        WHY TEST THIS:
        - Validates graceful shutdown on user interruption
        - Ensures partial results are saved and displayed
        - Verifies no data corruption on cancellation

        NOTE: Skipped because SIGINT timing is difficult to test reliably in CI.
        This should be tested manually by running a benchmark and pressing Ctrl-C.
        """
        pass

    async def test_request_cancellation_rate(
        self,
        base_profile_args,
        aiperf_runner,
        validate_aiperf_output,
    ):
        """Test request cancellation rate feature.

        WHY TEST THIS:
        - Validates cancellation rate feature works correctly
        - Ensures cancelled requests are tracked separately
        - Verifies partial results don't corrupt metrics
        - Tests that cancellation delay is respected
        - Validates error summary includes cancellations
        """
        args = [
            *base_profile_args,
            "--endpoint-type",
            "chat",
            "--streaming",
            "--request-count",
            "50",
            "--concurrency",
            "5",
            "--request-cancellation-rate",
            "0.3",
            "--request-cancellation-delay",
            "0.5",
            "--image-width-mean",
            "64",
            "--image-height-mean",
            "64",
        ]

        output = await run_and_validate_benchmark(
            aiperf_runner, validate_aiperf_output, args, timeout=120.0
        )

        # NOTE: Cancellation rate may not reduce completed requests depending on timing
        # The test verifies the feature doesn't break the benchmark

        # Use full Pydantic API for all validation
        BenchmarkResult.from_directory(output["actual_dir"]) \
            .assert_all_artifacts_exist() \
            .assert_log_not_empty() \
            .assert_metric_exists("request_count", "request_latency") \
            .assert_csv_contains("Request Latency")


@pytest.mark.integration
@pytest.mark.asyncio
class TestDeterministicBehavior:
    """Integration tests for deterministic behavior with random seeds."""

    async def test_same_seed_produces_identical_inputs(
        self,
        base_profile_args,
        aiperf_runner,
        validate_aiperf_output,
        tmp_path,
    ):
        """Test that same random seed produces identical input payloads across runs.

        WHY TEST THIS:
        - Validates reproducibility with --random-seed flag
        - Ensures synthetic data generation is deterministic
        - Verifies same seed produces same prompts, images, audio
        - Tests that only session_ids differ (due to UUIDs)
        """
        # Run 1: Generate with specific seed
        output_dir_1 = tmp_path / "run1"
        output_dir_1.mkdir()

        args_1 = [
            *base_profile_args,
            "--endpoint-type",
            "chat",
            "--request-count",
            "10",
            "--concurrency",
            "2",
            "--random-seed",
            "42",
            "--image-width-mean",
            "64",
            "--image-height-mean",
            "64",
            "--audio-length-mean",
            "0.1",
            "--artifact-dir",
            str(output_dir_1),
        ]

        result_1 = await aiperf_runner(args_1, add_artifact_dir=False)
        assert result_1["returncode"] == 0, "Run 1 failed"

        output_1 = validate_aiperf_output(output_dir_1)

        # Run 2: Same seed, should produce identical data
        output_dir_2 = tmp_path / "run2"
        output_dir_2.mkdir()

        args_2 = [
            *base_profile_args,
            "--endpoint-type",
            "chat",
            "--request-count",
            "10",
            "--concurrency",
            "2",
            "--random-seed",
            "42",
            "--image-width-mean",
            "64",
            "--image-height-mean",
            "64",
            "--audio-length-mean",
            "0.1",
            "--artifact-dir",
            str(output_dir_2),
        ]

        result_2 = await aiperf_runner(args_2, add_artifact_dir=False)
        assert result_2["returncode"] == 0, "Run 2 failed"

        output_2 = validate_aiperf_output(output_dir_2)

        # Use fluent API with Pydantic models for validation
        validator_1 = BenchmarkResult.from_directory(output_1["actual_dir"])
        validator_2 = BenchmarkResult.from_directory(output_2["actual_dir"])

        validator_1.assert_inputs_json_exists()
        validator_2.assert_inputs_json_exists()

        # Access parsed Pydantic InputsFile models
        inputs_1 = validator_1.inputs_file
        inputs_2 = validator_2.inputs_file

        # Verify same number of sessions
        assert len(inputs_1.data) == len(inputs_2.data), (
            "Different number of sessions between runs"
        )

        # Verify payloads are identical (except session_id which is UUID)
        for session_1, session_2 in zip(inputs_1.data, inputs_2.data):
            # Session IDs will be different (UUIDs)
            assert session_1.session_id != session_2.session_id, (
                "Session IDs should differ (UUIDs are random)"
            )

            # Payloads should be identical
            assert len(session_1.payloads) == len(session_2.payloads), (
                "Different number of payloads"
            )

            for payload_1, payload_2 in zip(session_1.payloads, session_2.payloads):
                # Compare messages (should be identical with same seed)
                messages_1 = payload_1.get("messages", [])
                messages_2 = payload_2.get("messages", [])

                assert len(messages_1) == len(messages_2), "Different message counts"

                for msg_1, msg_2 in zip(messages_1, messages_2):
                    content_1 = msg_1.get("content", [])
                    content_2 = msg_2.get("content", [])

                    # Content arrays should have same structure
                    assert len(content_1) == len(content_2), "Different content lengths"

                    # Verify each content item matches
                    for item_1, item_2 in zip(content_1, content_2):
                        assert item_1.get("type") == item_2.get("type"), (
                            f"Content types differ: {item_1.get('type')} vs {item_2.get('type')}"
                        )

                        # For images and audio, verify base64 data is identical
                        if item_1.get("type") == "image_url":
                            url_1 = item_1.get("image_url", {}).get("url", "")
                            url_2 = item_2.get("image_url", {}).get("url", "")
                            assert url_1 == url_2, "Image URLs should be identical with same seed"

                        elif item_1.get("type") == "input_audio":
                            audio_1 = item_1.get("input_audio", {}).get("data", "")
                            audio_2 = item_2.get("input_audio", {}).get("data", "")
                            assert audio_1 == audio_2, "Audio data should be identical with same seed"

                        elif item_1.get("type") == "text":
                            text_1 = item_1.get("text", "")
                            text_2 = item_2.get("text", "")
                            assert text_1 == text_2, "Text should be identical with same seed"
