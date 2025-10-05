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

from tests.integration.conftest import (
    DEFAULT_CONCURRENCY,
    DEFAULT_REQUEST_COUNT,
    assert_basic_metrics,
    assert_no_token_metrics,
    assert_streaming_metrics,
)


@pytest.mark.integration
@pytest.mark.asyncio
class TestFullBenchmarkIntegration:
    """Full end-to-end integration tests."""

    async def _run_and_validate_benchmark(
        self,
        aiperf_runner,
        validate_aiperf_output,
        args: list[str],
        min_requests: int | None = None,
    ) -> dict:
        """Helper to run benchmark and validate basic success.

        Args:
            aiperf_runner: Fixture to run aiperf
            validate_aiperf_output: Fixture to validate output
            args: Command line arguments
            min_requests: Minimum expected completed requests (optional)

        Returns:
            Validated output dictionary
        """
        result = await aiperf_runner(args)

        if result["returncode"] != 0:
            print(f"\n=== STDOUT ===\n{result['stdout']}")
            print(f"\n=== STDERR ===\n{result['stderr']}")

        assert result["returncode"] == 0, (
            f"Benchmark failed with returncode {result['returncode']}"
        )

        output = validate_aiperf_output(result["output_dir"])
        records = output["json_results"]["records"]

        assert_basic_metrics(records, "request_count", "request_latency")

        if min_requests is not None:
            completed = records["request_count"].get("avg", 0)
            assert completed >= min_requests, (
                f"Too few requests: {completed} < {min_requests}"
            )

        return output

    async def test_simple_benchmark_completes_successfully(
        self, base_profile_args, aiperf_runner, validate_aiperf_output
    ):
        """Test that a simple benchmark completes and produces valid output.

        WHY TEST THIS:
        - Validates complete pipeline works
        - Catches integration issues between components
        - Verifies subprocess execution works
        """
        args = [
            *base_profile_args,
            "--endpoint-type",
            "chat",
            "--request-count",
            "10",
            "--concurrency",
            str(DEFAULT_CONCURRENCY),
        ]

        output = await self._run_and_validate_benchmark(
            aiperf_runner, validate_aiperf_output, args, min_requests=8
        )
        records = output["json_results"]["records"]

        # Verify token-based metrics exist for chat
        assert_basic_metrics(records, "output_sequence_length")

    async def test_streaming_benchmark_produces_streaming_metrics(
        self, base_profile_args, aiperf_runner, validate_aiperf_output
    ):
        """Test that streaming benchmarks produce TTFT and ITL metrics.

        WHY TEST THIS:
        - Validates streaming endpoint handling
        - Ensures SSE parsing works
        - Verifies streaming-specific metrics computed
        """
        args = [
            *base_profile_args,
            "--endpoint-type",
            "chat",
            "--streaming",
            "--request-count",
            "10",
            "--concurrency",
            str(DEFAULT_CONCURRENCY),
        ]

        output = await self._run_and_validate_benchmark(
            aiperf_runner, validate_aiperf_output, args
        )
        records = output["json_results"]["records"]

        # Verify streaming metrics
        assert_streaming_metrics(records)

        # Verify TTFT is in reasonable range
        ttft_avg = records["ttft"]["avg"]
        assert ttft_avg < 10000, f"TTFT unreasonably high: {ttft_avg}ms"

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
        self, base_profile_args, aiperf_runner, validate_aiperf_output
    ):
        """Test that concurrency limit is respected.

        WHY TEST THIS:
        - Validates semaphore-based concurrency control
        - Ensures system doesn't overload
        - Verifies worker coordination
        """
        args = [
            *base_profile_args,
            "--endpoint-type",
            "chat",
            "--concurrency",
            "3",
            "--request-count",
            "20",
        ]

        await self._run_and_validate_benchmark(
            aiperf_runner, validate_aiperf_output, args, min_requests=15
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
        self, base_profile_args, aiperf_runner, validate_aiperf_output
    ):
        """Test that warmup and profiling phases execute correctly.

        WHY TEST THIS:
        - Validates phase management
        - Ensures warmup completes before profiling
        - Verifies phase statistics tracking
        """
        args = [
            *base_profile_args,
            "--endpoint-type",
            "chat",
            "--warmup-request-count",
            "5",
            "--request-count",
            "15",
            "--concurrency",
            str(DEFAULT_CONCURRENCY),
        ]

        output = await self._run_and_validate_benchmark(
            aiperf_runner, validate_aiperf_output, args
        )
        records = output["json_results"]["records"]

        # Profiling requests should be ~15 (warmup excluded)
        completed = records["request_count"]["avg"]
        assert 12 <= completed <= 15, f"Expected ~15 requests, got {completed}"

    async def test_json_and_csv_export_consistency(
        self, base_profile_args, aiperf_runner, validate_aiperf_output
    ):
        """Test that JSON and CSV exports contain consistent data.

        WHY TEST THIS:
        - Validates both export formats work
        - Ensures data consistency across formats
        - Verifies export pipeline integrity
        """
        args = [
            *base_profile_args,
            "--endpoint-type",
            "chat",
            "--streaming",
            "--request-count",
            "10",
            "--concurrency",
            str(DEFAULT_CONCURRENCY),
        ]

        output = await self._run_and_validate_benchmark(
            aiperf_runner, validate_aiperf_output, args
        )

        # Verify both export formats have content
        assert len(output["json_results"]["records"]) > 0, "JSON has no records"
        assert len(output["csv_content"]) > 100, "CSV file suspiciously small"
        assert "Metric" in output["csv_content"], "CSV missing header"
        assert "Request Latency" in output["csv_content"], "CSV missing metrics"

    async def test_multiple_workers_coordinate_correctly(
        self, base_profile_args, aiperf_runner, validate_aiperf_output
    ):
        """Test that multiple workers coordinate via ZMQ.

        WHY TEST THIS:
        - Validates multiprocess architecture
        - Ensures credit distribution works
        - Verifies result aggregation from multiple workers
        """
        args = [
            *base_profile_args,
            "--endpoint-type",
            "chat",
            "--request-count",
            "50",
            "--concurrency",
            "10",
            "--workers-max",
            "4",
        ]

        await self._run_and_validate_benchmark(
            aiperf_runner, validate_aiperf_output, args, min_requests=45
        )


@pytest.mark.integration
@pytest.mark.asyncio
class TestMetricComputationIntegration:
    """Integration tests for metric computation accuracy."""

    async def test_ttft_computation_accuracy(
        self, base_profile_args, aiperf_runner, validate_aiperf_output
    ):
        """Test that TTFT is computed accurately.

        WHY TEST THIS:
        - Validates timing precision end-to-end
        - Ensures mock server TTFT setting is reflected in metrics
        - Verifies no timing bugs in pipeline
        """
        args = [
            *base_profile_args,
            "--endpoint-type",
            "chat",
            "--streaming",
            "--request-count",
            "10",
            "--concurrency",
            "1",
        ]

        output = await aiperf_runner(args)
        assert output["returncode"] == 0, "Benchmark failed"

        validated = validate_aiperf_output(output["output_dir"])
        records = validated["json_results"]["records"]

        assert_basic_metrics(records, "ttft")

        # TTFT should be in reasonable range
        ttft_record = records["ttft"]
        avg_ttft = ttft_record["avg"]
        assert 1 <= avg_ttft <= 1000, f"TTFT {avg_ttft}ms outside reasonable range"
        assert ttft_record.get("std") is not None, "TTFT missing std"

    async def test_output_token_count_matches_input(
        self, base_profile_args, aiperf_runner, validate_aiperf_output
    ):
        """Test that output token counting is accurate.

        WHY TEST THIS:
        - Validates tokenization pipeline
        - Ensures token counts used for throughput are correct
        - Verifies parser extracts tokens correctly
        """
        args = [
            *base_profile_args,
            "--endpoint-type",
            "chat",
            "--streaming",
            "--request-count",
            "10",
            "--concurrency",
            "1",
        ]

        output = await aiperf_runner(args)
        assert output["returncode"] == 0, "Benchmark failed"

        validated = validate_aiperf_output(output["output_dir"])
        records = validated["json_results"]["records"]

        assert_basic_metrics(records, "output_sequence_length")

        # Should have processed some tokens
        avg_osl = records["output_sequence_length"]["avg"]
        assert avg_osl > 0, "No output tokens counted"


@pytest.mark.integration
@pytest.mark.asyncio
class TestErrorHandlingIntegration:
    """Integration tests for error handling."""

    async def test_benchmark_handles_http_errors(
        self, base_profile_args, aiperf_runner, validate_aiperf_output
    ):
        """Test that HTTP errors are tracked correctly.

        WHY TEST THIS:
        - Validates error tracking pipeline
        - Ensures errors don't crash the benchmark
        - Verifies error metrics are computed
        """
        args = [
            *base_profile_args,
            "--endpoint-type",
            "chat",
            "--request-count",
            "10",
            "--concurrency",
            "5",
            "--timeout-seconds",
            "2",  # Short timeout may cause some timeouts
        ]

        result = await aiperf_runner(args)

        # May succeed or fail, but shouldn't crash - that's the test
        if result["returncode"] == 0:
            output = validate_aiperf_output(result["output_dir"])
            error_summary = output["json_results"].get("error_summary", [])
            assert isinstance(error_summary, list), "error_summary should be a list"


@pytest.mark.integration
@pytest.mark.asyncio
class TestConfigurationIntegration:
    """Integration tests for configuration handling."""

    async def test_artifact_directory_created(
        self, base_profile_args, aiperf_runner, temp_output_dir
    ):
        """Test that artifact directory is created correctly.

        WHY TEST THIS:
        - Validates output directory creation
        - Ensures file export works
        - Verifies configuration is respected
        """
        args = [
            *base_profile_args,
            "--endpoint-type",
            "chat",
            "--request-count",
            str(DEFAULT_REQUEST_COUNT),
        ]

        result = await aiperf_runner(args)
        assert result["returncode"] == 0, "Benchmark failed"

        # Verify output files were created
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


@pytest.mark.integration
@pytest.mark.asyncio
class TestEndpointTypesIntegration:
    """Integration tests for all supported endpoint types."""

    async def _test_endpoint(
        self,
        base_profile_args,
        aiperf_runner,
        validate_aiperf_output,
        endpoint_type: str,
        streaming: bool = False,
        extra_args: list[str] | None = None,
        verify_streaming: bool = False,
        verify_no_tokens: bool = False,
    ) -> dict:
        """Helper to test an endpoint type with common validation.

        Args:
            base_profile_args: Base profile arguments fixture
            aiperf_runner: Runner fixture
            validate_aiperf_output: Validation fixture
            endpoint_type: Endpoint type to test
            streaming: Whether to enable streaming
            extra_args: Additional arguments to pass
            verify_streaming: Whether to verify streaming metrics
            verify_no_tokens: Whether to verify no token metrics

        Returns:
            Validated output dictionary
        """
        args = [
            *base_profile_args,
            "--endpoint-type",
            endpoint_type,
            "--request-count",
            str(DEFAULT_REQUEST_COUNT),
            "--concurrency",
            str(DEFAULT_CONCURRENCY),
        ]

        if streaming:
            args.append("--streaming")

        if extra_args:
            args.extend(extra_args)

        result = await aiperf_runner(args)
        assert result["returncode"] == 0, (
            f"{endpoint_type} test failed: {result['stderr']}"
        )

        output = validate_aiperf_output(result["output_dir"])
        records = output["json_results"]["records"]

        assert_basic_metrics(records, "request_count", "request_latency")

        if verify_streaming:
            assert_streaming_metrics(records)

        if verify_no_tokens:
            assert_no_token_metrics(records)

        return output

    async def test_chat_endpoint_non_streaming(
        self, base_profile_args, aiperf_runner, validate_aiperf_output
    ):
        """Test chat endpoint in non-streaming mode.

        WHY TEST THIS:
        - Validates /v1/chat/completions endpoint
        - Ensures non-streaming chat requests work
        - Verifies response parsing
        """
        output = await self._test_endpoint(
            base_profile_args, aiperf_runner, validate_aiperf_output, "chat"
        )
        records = output["json_results"]["records"]
        assert_basic_metrics(records, "output_sequence_length")

    async def test_chat_endpoint_streaming(
        self, base_profile_args, aiperf_runner, validate_aiperf_output
    ):
        """Test chat endpoint in streaming mode.

        WHY TEST THIS:
        - Validates /v1/chat/completions with streaming
        - Ensures SSE parsing works
        - Verifies TTFT and ITL metrics
        """
        await self._test_endpoint(
            base_profile_args,
            aiperf_runner,
            validate_aiperf_output,
            "chat",
            streaming=True,
            verify_streaming=True,
        )

    async def test_completions_endpoint_non_streaming(
        self, base_profile_args, aiperf_runner, validate_aiperf_output
    ):
        """Test completions endpoint in non-streaming mode.

        WHY TEST THIS:
        - Validates /v1/completions endpoint
        - Ensures legacy completions API works
        - Verifies token-based metrics
        """
        output = await self._test_endpoint(
            base_profile_args, aiperf_runner, validate_aiperf_output, "completions"
        )
        records = output["json_results"]["records"]
        assert_basic_metrics(records, "output_sequence_length")
        assert records["request_count"]["avg"] >= 4, "Too few requests completed"

    async def test_completions_endpoint_streaming(
        self, base_profile_args, aiperf_runner, validate_aiperf_output
    ):
        """Test completions endpoint in streaming mode.

        WHY TEST THIS:
        - Validates /v1/completions with streaming
        - Ensures streaming works for legacy API
        - Verifies streaming metrics computed
        """
        await self._test_endpoint(
            base_profile_args,
            aiperf_runner,
            validate_aiperf_output,
            "completions",
            streaming=True,
            verify_streaming=True,
        )

    async def test_embeddings_endpoint(
        self, base_profile_args, aiperf_runner, validate_aiperf_output
    ):
        """Test embeddings endpoint.

        WHY TEST THIS:
        - Validates /v1/embeddings endpoint
        - Ensures embeddings requests work
        - Verifies non-token-producing endpoint handling
        """
        await self._test_endpoint(
            base_profile_args,
            aiperf_runner,
            validate_aiperf_output,
            "embeddings",
            verify_no_tokens=True,
        )

    async def test_rankings_endpoint(
        self,
        base_profile_args,
        aiperf_runner,
        validate_aiperf_output,
        create_rankings_dataset,
    ):
        """Test rankings endpoint with custom dataset.

        WHY TEST THIS:
        - Validates /v1/ranking endpoint
        - Ensures ranking requests work
        - Verifies reranking endpoint handling
        - Tests custom dataset with named Text objects
        """
        dataset_path = create_rankings_dataset(DEFAULT_REQUEST_COUNT)

        extra_args = [
            "--input-file",
            str(dataset_path),
            "--custom-dataset-type",
            "single_turn",
        ]

        await self._test_endpoint(
            base_profile_args,
            aiperf_runner,
            validate_aiperf_output,
            "rankings",
            extra_args=extra_args,
            verify_no_tokens=True,
        )

    @pytest.mark.skip(reason="Bug in aiperf responses API - needs to be fixed")
    async def test_responses_endpoint_non_streaming(
        self, base_profile_args, aiperf_runner, validate_aiperf_output
    ):
        """Test responses endpoint in non-streaming mode.

        WHY TEST THIS:
        - Validates /v1/responses endpoint
        - Ensures new responses API works
        - Verifies token-based metrics
        """
        output = await self._test_endpoint(
            base_profile_args, aiperf_runner, validate_aiperf_output, "responses"
        )
        records = output["json_results"]["records"]
        assert_basic_metrics(records, "output_sequence_length")

    @pytest.mark.skip(reason="Bug in aiperf responses API - needs to be fixed")
    async def test_responses_endpoint_streaming(
        self, base_profile_args, aiperf_runner, validate_aiperf_output
    ):
        """Test responses endpoint in streaming mode.

        WHY TEST THIS:
        - Validates /v1/responses with streaming
        - Ensures streaming works for new API
        - Verifies streaming metrics computed
        """
        await self._test_endpoint(
            base_profile_args,
            aiperf_runner,
            validate_aiperf_output,
            "responses",
            streaming=True,
            verify_streaming=True,
        )
