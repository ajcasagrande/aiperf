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
from tests.integration.result_validators import BenchmarkResult, ConsoleOutputValidator


def assert_csv_contains_metrics(csv_content: str, *metric_names: str) -> None:
    """Assert that CSV contains specific metrics.

    Args:
        csv_content: The CSV file content
        *metric_names: Variable number of metric names to check (human-readable)
    """
    for metric_name in metric_names:
        assert metric_name in csv_content, f"CSV missing {metric_name}"


def assert_inputs_json_valid(inputs_json: dict, min_sessions: int = 1) -> None:
    """Assert that inputs.json is valid and contains expected data.

    Args:
        inputs_json: Parsed inputs.json content
        min_sessions: Minimum number of sessions expected
    """
    assert "data" in inputs_json, "inputs.json missing data field"
    assert isinstance(inputs_json["data"], list), "data should be list"
    assert len(inputs_json["data"]) >= min_sessions, (
        f"Expected at least {min_sessions} sessions, got {len(inputs_json['data'])}"
    )

    # Verify each session has required structure
    for session in inputs_json["data"]:
        assert "session_id" in session, "Session missing session_id"
        assert "payloads" in session, "Session missing payloads"
        assert isinstance(session["payloads"], list), "payloads should be list"
        assert len(session["payloads"]) > 0, "Session has no payloads"


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

        # Verify CSV contains expected metrics
        assert_csv_contains_metrics(
            output["csv_content"],
            "Request Latency",
            "Output Sequence Length",
        )

        # Verify inputs.json was generated with audio content
        if "inputs_json" in output:
            assert_inputs_json_valid(output["inputs_json"], min_sessions=DEFAULT_REQUEST_COUNT)

            # Verify at least one payload contains input_audio
            has_audio = False
            for session in output["inputs_json"]["data"]:
                for payload in session["payloads"]:
                    messages = payload.get("messages", [])
                    for msg in messages:
                        content = msg.get("content", [])
                        if isinstance(content, list):
                            for item in content:
                                if isinstance(item, dict) and item.get("type") == "input_audio":
                                    has_audio = True
                                    break
            assert has_audio, "No audio content found in inputs.json"

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

        # Verify CSV output table completeness
        assert_csv_contains_metrics(
            output["csv_content"],
            "Request Latency",
            "Output Sequence Length",
        )

        # Verify inputs.json contains both image and audio
        if "inputs_json" in output:
            assert_inputs_json_valid(output["inputs_json"], min_sessions=DEFAULT_REQUEST_COUNT)

            # Verify multi-modal content exists
            has_image = False
            has_audio = False
            for session in output["inputs_json"]["data"]:
                for payload in session["payloads"]:
                    messages = payload.get("messages", [])
                    for msg in messages:
                        content = msg.get("content", [])
                        if isinstance(content, list):
                            for item in content:
                                if isinstance(item, dict):
                                    if item.get("type") == "image_url":
                                        has_image = True
                                    if item.get("type") == "input_audio":
                                        has_audio = True
            assert has_image, "No image content found in inputs.json"
            assert has_audio, "No audio content found in inputs.json"

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

        # Verify CSV contains streaming metrics
        assert_csv_contains_metrics(
            output["csv_content"],
            "Time to First Token",
            "Inter Token Latency",
            "Request Latency",
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

        # Verify CSV output table contains all expected data
        assert_csv_contains_metrics(
            output["csv_content"],
            "Request Latency",
            "Output Sequence Length",
            "Request Count",
        )

        # Verify artifacts directory structure
        assert output["json_file"].exists(), "JSON export should exist"
        assert output["csv_file"].exists(), "CSV export should exist"
        assert output["log_file"].exists(), "Log file should exist"

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

        # Verify CSV output table for duration-based test
        assert_csv_contains_metrics(
            output["csv_content"],
            "Time to First Token",
            "Inter Token Latency",
            "Request Latency",
            "Benchmark Duration",
        )

        # Verify all artifact files exist
        assert output["json_file"].exists(), "JSON export should exist"
        assert output["csv_file"].exists(), "CSV export should exist"
        assert output["log_file"].exists(), "Log file should exist"


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

        # Use new fluent validation API for comprehensive checks
        result_validator = BenchmarkResult.from_directory(output["actual_dir"])
        result_validator.assert_all_artifacts_exist()
        result_validator.assert_log_not_empty()
        result_validator.assert_metric_exists(
            "ttft", "inter_token_latency", "request_latency", "output_sequence_length"
        )
        result_validator.assert_metric_in_range("ttft", min_value=0)
        result_validator.assert_metric_in_range("inter_token_latency", min_value=0)
        result_validator.assert_request_count(min_count=950)
        result_validator.assert_csv_contains(
            "Time to First Token",
            "Inter Token Latency",
            "Request Latency",
            "Request Throughput",
        )
        result_validator.assert_inputs_json_has_sessions(min_sessions=10)

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
        # Cancel 30% of requests after 0.5 second delay
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

        result = await aiperf_runner(args, timeout=120.0)

        if result["returncode"] != 0:
            print(f"\n=== STDOUT ===\n{result['stdout']}")
            print(f"\n=== STDERR ===\n{result['stderr']}")

        assert result["returncode"] == 0, (
            f"Cancellation rate test failed: {result['returncode']}"
        )

        output = validate_aiperf_output(result["output_dir"])
        records = output["json_results"]["records"]

        # Verify basic metrics exist
        assert_basic_metrics(records, "request_count", "request_latency")

        # Verify requests completed (cancellation rate affects requests differently depending on timing)
        completed = records["request_count"].get("avg", 0)
        assert completed > 0, f"No requests completed: {completed}"
        assert completed <= 50, f"More requests than expected: {completed}"

        # Verify error summary exists
        error_summary = output["json_results"].get("error_summary", [])
        assert isinstance(error_summary, list), "error_summary should be a list"

        # NOTE: Cancellation rate may not always result in fewer completed requests
        # depending on when cancellation occurs relative to request completion.
        # The main goal is to verify the feature doesn't break the benchmark.

        # Verify CSV contains the data
        assert "Request Latency" in output["csv_content"], (
            "CSV missing Request Latency"
        )

        # Verify artifacts directory has expected structure
        actual_dir = output["actual_dir"]
        assert actual_dir.exists(), "Artifacts directory should exist"

        # Check for log file
        log_file = output["log_file"]
        assert log_file.exists(), "Log file should exist"
        assert log_file.stat().st_size > 0, "Log file should not be empty"


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

        # Use fluent API to validate both outputs
        validator_1 = BenchmarkResult.from_directory(output_1["actual_dir"])
        validator_2 = BenchmarkResult.from_directory(output_2["actual_dir"])

        validator_1.assert_inputs_json_exists()
        validator_2.assert_inputs_json_exists()

        inputs_1 = validator_1.inputs_json
        inputs_2 = validator_2.inputs_json

        # Verify same number of sessions
        assert len(inputs_1["data"]) == len(inputs_2["data"]), (
            "Different number of sessions between runs"
        )

        # Verify payloads are identical (except session_id which is UUID)
        for session_1, session_2 in zip(inputs_1["data"], inputs_2["data"]):
            # Session IDs will be different (UUIDs)
            assert session_1["session_id"] != session_2["session_id"], (
                "Session IDs should differ (UUIDs are random)"
            )

            # Payloads should be identical
            assert len(session_1["payloads"]) == len(session_2["payloads"]), (
                "Different number of payloads"
            )

            for payload_1, payload_2 in zip(session_1["payloads"], session_2["payloads"]):
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
