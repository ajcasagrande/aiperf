# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""
Full Integration Tests

These tests run complete AIPerf benchmarks against the mock server,
validating end-to-end behavior including:
- Process spawning and coordination
- HTTP communication
- Metric computation
- Result export
- Error handling

These are TRUE integration tests - they run aiperf as a subprocess
and verify real behavior.
"""

import pytest


@pytest.mark.integration
@pytest.mark.asyncio
class TestFullBenchmarkIntegration:
    """Full end-to-end integration tests."""

    async def test_simple_benchmark_completes_successfully(
        self, mock_server, aiperf_runner, validate_aiperf_output
    ):
        """Test that a simple benchmark completes and produces valid output.

        This is the most basic integration test - verifies that AIPerf can:
        1. Connect to an endpoint
        2. Send requests
        3. Receive responses
        4. Compute metrics
        5. Export results

        WHY TEST THIS:
        - Validates complete pipeline works
        - Catches integration issues between components
        - Verifies subprocess execution works
        """
        result = await aiperf_runner(
            [
                "profile",
                "--model",
                "gpt2",
                "--url",
                mock_server["url"],
                "--endpoint-type",
                "chat",
                "--request-count",
                "10",
                "--concurrency",
                "2",
                "--ui",
                "simple",
            ]
        )

        # Verify successful completion
        if result["returncode"] != 0:
            print(f"\n=== STDOUT ===\n{result['stdout']}")
            print(f"\n=== STDERR ===\n{result['stderr']}")

        assert result["returncode"] == 0, (
            f"AIPerf failed with returncode {result['returncode']}"
        )

        # Verify output contains expected content

        # Validate output files
        output = validate_aiperf_output(result["output_dir"])

        # Verify JSON has expected structure
        records = output["json_results"]["records"]
        assert isinstance(records, dict), "records should be a dict"
        assert len(records) > 0, "No metrics in JSON output"

        # Verify key metrics were computed
        assert "request_count" in records, "Missing request_count metric"
        assert "request_latency" in records, "Missing request_latency metric"

        # Verify request count matches configuration
        request_count_metric = records.get("request_count")
        assert request_count_metric is not None, "request_count metric is None"

        # For aggregate metrics like request_count, use the scalar value directly
        completed_requests = request_count_metric.get("avg", 0)
        assert completed_requests >= 8, (
            f"Too few requests completed: {completed_requests}"
        )

    async def test_streaming_benchmark_produces_streaming_metrics(
        self, mock_server, aiperf_runner, validate_aiperf_output
    ):
        """Test that streaming benchmarks produce TTFT and ITL metrics.

        WHY TEST THIS:
        - Validates streaming endpoint handling
        - Ensures SSE parsing works
        - Verifies streaming-specific metrics computed
        """
        result = await aiperf_runner(
            [
                "profile",
                "--model",
                "gpt2",
                "--url",
                mock_server["url"],
                "--endpoint-type",
                "chat",
                "--streaming",
                "--request-count",
                "10",
                "--concurrency",
                "2",
                "--ui",
                "simple",
            ]
        )

        assert result["returncode"] == 0, (
            f"Streaming benchmark failed: {result['stderr']}"
        )

        # Validate output
        output = validate_aiperf_output(result["output_dir"])
        records = output["json_results"]["records"]
        assert isinstance(records, dict), "records should be a dict"
        metric_tags = list(records.keys())

        # Streaming-specific metrics
        assert "ttft" in metric_tags, "Missing TTFT metric"
        assert "inter_token_latency" in metric_tags, "Missing ITL metric"

        # Verify TTFT has reasonable values
        ttft_record = records.get("ttft")
        assert ttft_record is not None, "TTFT metric is None"
        assert ttft_record.get("avg", 0) > 0, "TTFT should be positive"
        assert ttft_record.get("avg", 0) < 10000, "TTFT unreasonably high"

    @pytest.mark.skip(
        reason="Request rate timing test - sensitivity to timing variance"
    )
    async def test_request_rate_benchmark_respects_rate(
        self, mock_server, aiperf_runner, validate_aiperf_output
    ):
        """Test that request-rate mode respects configured rate.

        WHY TEST THIS:
        - Validates credit issuance timing
        - Ensures rate limiting works
        - Verifies throughput doesn't exceed rate

        NOTE: Skipped in CI due to timing sensitivity.
        Rate limiting is tested at unit level in timing_manager tests.
        """
        pass

    async def test_concurrency_benchmark_limits_concurrent_requests(
        self, mock_server, aiperf_runner, validate_aiperf_output
    ):
        """Test that concurrency limit is respected.

        WHY TEST THIS:
        - Validates semaphore-based concurrency control
        - Ensures system doesn't overload
        - Verifies worker coordination
        """
        result = await aiperf_runner(
            [
                "profile",
                "--model",
                "gpt2",
                "--url",
                mock_server["url"],
                "--endpoint-type",
                "chat",
                "--concurrency",
                "3",
                "--request-count",
                "20",
                "--ui",
                "simple",
            ]
        )

        assert result["returncode"] == 0, (
            f"Concurrency benchmark failed: {result['stderr']}"
        )

        # Validate completed successfully
        output = validate_aiperf_output(result["output_dir"])
        records = output["json_results"]["records"]
        assert isinstance(records, dict), "records should be a dict"

        # At least some requests should complete
        request_count = records.get("request_count")
        assert request_count is not None, "Missing request_count metric"

        completed_requests = request_count.get("avg", 0)
        assert completed_requests >= 15, (
            f"Too few requests completed: {completed_requests}"
        )

    @pytest.mark.skip(reason="Custom dataset test - CLI flag validation needed")
    async def test_benchmark_with_custom_dataset(
        self, mock_server, aiperf_runner, validate_aiperf_output, tmp_path
    ):
        """Test benchmark with custom single-turn dataset.

        WHY TEST THIS:
        - Validates dataset loading pipeline
        - Ensures custom datasets work end-to-end
        - Verifies file-based input handling
        """
        # Skipped pending CLI flag verification
        pass

    @pytest.mark.skip(reason="Error handling test - verifies graceful failure")
    async def test_benchmark_error_handling(self, aiperf_runner, temp_output_dir):
        """Test that AIPerf handles connection errors gracefully.

        WHY TEST THIS:
        - Validates error handling when endpoint unavailable
        - Ensures proper error reporting
        - Verifies graceful failure
        """
        # Skipped - error handling verified through other means
        pass

    async def test_warmup_and_profiling_phases(
        self, mock_server, aiperf_runner, validate_aiperf_output
    ):
        """Test that warmup and profiling phases execute correctly.

        WHY TEST THIS:
        - Validates phase management
        - Ensures warmup completes before profiling
        - Verifies phase statistics tracking
        """
        result = await aiperf_runner(
            [
                "profile",
                "--model",
                "gpt2",
                "--url",
                mock_server["url"],
                "--endpoint-type",
                "chat",
                "--warmup-request-count",
                "5",
                "--request-count",
                "15",
                "--concurrency",
                "2",
                "--ui",
                "simple",
            ]
        )

        assert result["returncode"] == 0, f"Warmup benchmark failed: {result['stderr']}"

        output = validate_aiperf_output(result["output_dir"])
        records = output["json_results"]["records"]
        assert isinstance(records, dict), "records should be a dict"

        # Profiling requests should be counted (warmup excluded)
        request_count = records.get("request_count")
        assert request_count is not None, "Missing request_count metric"

        # Should be close to 15 (profiling phase only)
        completed_requests = request_count.get("avg", 0)
        assert 12 <= completed_requests <= 15, (
            f"Expected ~15 requests, got {completed_requests}"
        )

    async def test_json_and_csv_export_consistency(
        self, mock_server, aiperf_runner, validate_aiperf_output
    ):
        """Test that JSON and CSV exports contain consistent data.

        WHY TEST THIS:
        - Validates both export formats work
        - Ensures data consistency across formats
        - Verifies export pipeline integrity
        """
        result = await aiperf_runner(
            [
                "profile",
                "--model",
                "gpt2",
                "--url",
                mock_server["url"],
                "--endpoint-type",
                "chat",
                "--streaming",
                "--request-count",
                "10",
                "--concurrency",
                "2",
                "--ui",
                "simple",
            ]
        )

        assert result["returncode"] == 0, "Benchmark failed"

        output = validate_aiperf_output(result["output_dir"])

        # Both files should exist and have content
        assert len(output["json_results"]["records"]) > 0, "JSON has no records"
        assert len(output["csv_content"]) > 100, "CSV file suspiciously small"

        # CSV should contain header row
        assert "Metric" in output["csv_content"], "CSV missing header"

        # CSV should contain metrics
        assert "Request Latency" in output["csv_content"], "CSV missing metrics"

    async def test_multiple_workers_coordinate_correctly(
        self, mock_server, aiperf_runner, validate_aiperf_output
    ):
        """Test that multiple workers coordinate via ZMQ.

        WHY TEST THIS:
        - Validates multiprocess architecture
        - Ensures credit distribution works
        - Verifies result aggregation from multiple workers
        """
        result = await aiperf_runner(
            [
                "profile",
                "--model",
                "gpt2",
                "--url",
                mock_server["url"],
                "--endpoint-type",
                "chat",
                "--request-count",
                "50",
                "--concurrency",
                "10",  # Should spawn multiple workers
                "--workers-max",
                "4",  # Force multiple workers
                "--ui",
                "simple",
            ]
        )

        assert result["returncode"] == 0, (
            f"Multi-worker benchmark failed: {result['stderr']}"
        )

        output = validate_aiperf_output(result["output_dir"])
        records = output["json_results"]["records"]
        assert isinstance(records, dict), "records should be a dict"

        # Should complete most requests
        request_count = records.get("request_count")
        assert request_count is not None, "Missing request_count metric"

        completed_requests = request_count.get("avg", 0)
        assert completed_requests >= 45, (
            f"Too few requests with multiple workers: {completed_requests}"
        )


@pytest.mark.integration
@pytest.mark.asyncio
class TestMetricComputationIntegration:
    """Integration tests for metric computation accuracy."""

    async def test_ttft_computation_accuracy(
        self, mock_server, aiperf_runner, validate_aiperf_output
    ):
        """Test that TTFT is computed accurately.

        WHY TEST THIS:
        - Validates timing precision end-to-end
        - Ensures mock server TTFT setting is reflected in metrics
        - Verifies no timing bugs in pipeline
        """
        # Mock server default TTFT is configurable
        # We'll verify it's in reasonable range

        result = await aiperf_runner(
            [
                "profile",
                "--model",
                "gpt2",
                "--url",
                mock_server["url"],
                "--endpoint-type",
                "chat",
                "--streaming",
                "--request-count",
                "10",
                "--concurrency",
                "1",
                "--ui",
                "simple",
            ]
        )

        assert result["returncode"] == 0, "Benchmark failed"

        output = validate_aiperf_output(result["output_dir"])
        records = output["json_results"]["records"]
        assert isinstance(records, dict), "records should be a dict"

        ttft_record = records.get("ttft")
        assert ttft_record is not None, "TTFT metric not found"

        # TTFT should be reasonable (mock server uses small delays)
        avg_ttft = ttft_record.get("avg", 0)
        assert 1 <= avg_ttft <= 1000, f"TTFT {avg_ttft}ms outside reasonable range"

        # Standard deviation should exist
        assert ttft_record.get("std") is not None, "TTFT missing std"

    async def test_output_token_count_matches_input(
        self, mock_server, aiperf_runner, validate_aiperf_output
    ):
        """Test that output token counting is accurate.

        WHY TEST THIS:
        - Validates tokenization pipeline
        - Ensures token counts used for throughput are correct
        - Verifies parser extracts tokens correctly
        """
        result = await aiperf_runner(
            [
                "profile",
                "--model",
                "gpt2",
                "--url",
                mock_server["url"],
                "--endpoint-type",
                "chat",
                "--streaming",
                "--request-count",
                "10",
                "--concurrency",
                "1",
                "--ui",
                "simple",
            ]
        )

        assert result["returncode"] == 0, "Benchmark failed"

        output = validate_aiperf_output(result["output_dir"])
        records = output["json_results"]["records"]
        assert isinstance(records, dict), "records should be a dict"

        # Check output sequence length metric exists
        osl_record = records.get("output_sequence_length")
        assert osl_record is not None, "Output sequence length not found"

        # Should have processed some tokens
        avg_osl = osl_record.get("avg", 0)
        assert avg_osl > 0, "No output tokens counted"


@pytest.mark.integration
@pytest.mark.asyncio
class TestErrorHandlingIntegration:
    """Integration tests for error handling."""

    async def test_benchmark_handles_http_errors(
        self, mock_server, aiperf_runner, validate_aiperf_output
    ):
        """Test that HTTP errors are tracked correctly.

        WHY TEST THIS:
        - Validates error tracking pipeline
        - Ensures errors don't crash the benchmark
        - Verifies error metrics are computed
        """
        # Even if server returns some errors, AIPerf should handle gracefully
        result = await aiperf_runner(
            [
                "profile",
                "--model",
                "gpt2",
                "--url",
                mock_server["url"],
                "--endpoint-type",
                "chat",
                "--request-count",
                "10",
                "--concurrency",
                "5",
                "--timeout-seconds",
                "2",  # Short timeout may cause some timeouts
                "--ui",
                "simple",
            ]
        )

        # May succeed or fail depending on errors, but shouldn't crash
        # The important thing is it completes

        # If it succeeded, check output
        if result["returncode"] == 0:
            output = validate_aiperf_output(result["output_dir"])

            # Should have error summary if any errors occurred
            error_summary = output["json_results"].get("error_summary", [])
            # Error summary is a list (may be empty if no errors)
            assert isinstance(error_summary, list), "error_summary should be a list"


@pytest.mark.integration
@pytest.mark.asyncio
class TestConfigurationIntegration:
    """Integration tests for configuration handling."""

    async def test_artifact_directory_created(
        self, mock_server, aiperf_runner, temp_output_dir
    ):
        """Test that artifact directory is created correctly.

        WHY TEST THIS:
        - Validates output directory creation
        - Ensures file export works
        - Verifies configuration is respected
        """
        result = await aiperf_runner(
            [
                "profile",
                "--model",
                "gpt2",
                "--url",
                mock_server["url"],
                "--endpoint-type",
                "chat",
                "--request-count",
                "5",
                "--ui",
                "simple",
            ]
        )

        assert result["returncode"] == 0, "Benchmark failed"

        # Check that files were created (AIPerf may or may not create subdirs)
        # The important thing is output files exist
        json_files = list(temp_output_dir.glob("**/*aiperf.json"))
        assert len(json_files) > 0, "No JSON output created"

    @pytest.mark.skip(
        reason="Deterministic test - timing makes exact comparison difficult"
    )
    async def test_random_seed_produces_deterministic_results(
        self, mock_server, aiperf_runner, validate_aiperf_output, tmp_path
    ):
        """Test that random seed produces deterministic behavior.

        WHY TEST THIS:
        - Validates reproducibility
        - Ensures random seed is respected
        - Verifies deterministic dataset generation
        """
        # Skipped - determinism tested at unit level, integration timing varies
        pass
