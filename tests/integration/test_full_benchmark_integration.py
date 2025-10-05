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
    run_and_validate_benchmark,
)
from tests.integration.result_validators import BenchmarkResult
from tests.integration.test_models import AIPerfRunResult, ValidatedOutput


@pytest.mark.integration
@pytest.mark.asyncio
class TestFullBenchmarkIntegration:
    """Full end-to-end integration tests."""


    async def test_simple_benchmark_completes_successfully(
        self, base_profile_args, aiperf_runner, validate_aiperf_output
    ):
        """Validates complete benchmark pipeline."""
        args = [*base_profile_args, "--endpoint-type", "chat",
                "--request-count", "10", "--concurrency", DEFAULT_CONCURRENCY]

        output = await run_and_validate_benchmark(
            aiperf_runner, validate_aiperf_output, args, min_requests=8
        )

        BenchmarkResult.from_directory(output.actual_dir).assert_metric_exists("output_sequence_length")

    async def test_streaming_benchmark_produces_streaming_metrics(
        self, base_profile_args, aiperf_runner, validate_aiperf_output
    ):
        """Validates streaming produces TTFT and ITL metrics."""
        args = [*base_profile_args, "--endpoint-type", "chat", "--streaming",
                "--request-count", "10", "--concurrency", DEFAULT_CONCURRENCY]

        output = await run_and_validate_benchmark(
            aiperf_runner, validate_aiperf_output, args
        )

        BenchmarkResult.from_directory(output.actual_dir) \
            .assert_metric_exists("ttft", "inter_token_latency") \
            .assert_metric_in_range("ttft", max_value=10000)

    async def test_concurrency_benchmark_limits_concurrent_requests(
        self, base_profile_args, aiperf_runner, validate_aiperf_output
    ):
        """Validates concurrency limit is respected."""
        args = [*base_profile_args, "--endpoint-type", "chat",
                "--concurrency", "3", "--request-count", "20"]

        await run_and_validate_benchmark(
            aiperf_runner, validate_aiperf_output, args, min_requests=15
        )

    async def test_warmup_and_profiling_phases(
        self, base_profile_args, aiperf_runner, validate_aiperf_output
    ):
        """Validates warmup completes before profiling."""
        args = [*base_profile_args, "--endpoint-type", "chat",
                "--warmup-request-count", "5", "--request-count", "15",
                "--concurrency", DEFAULT_CONCURRENCY]

        output = await run_and_validate_benchmark(
            aiperf_runner, validate_aiperf_output, args
        )

        count = BenchmarkResult.from_directory(output.actual_dir).get_metric("request_count")
        assert 12 <= count.avg <= 15

    async def test_json_and_csv_export_consistency(
        self, base_profile_args, aiperf_runner, validate_aiperf_output
    ):
        """Validates both JSON and CSV export formats."""
        args = [*base_profile_args, "--endpoint-type", "chat", "--streaming",
                "--request-count", "10", "--concurrency", DEFAULT_CONCURRENCY]

        output = await run_and_validate_benchmark(
            aiperf_runner, validate_aiperf_output, args
        )

        BenchmarkResult.from_directory(output.actual_dir).assert_csv_contains("Metric", "Request Latency")
        assert len(output.csv_content) > 100

    async def test_multiple_workers_coordinate_correctly(
        self, base_profile_args, aiperf_runner, validate_aiperf_output
    ):
        """Validates multiprocess architecture with 4 workers."""
        args = [*base_profile_args, "--endpoint-type", "chat",
                "--request-count", "50", "--concurrency", "10", "--workers-max", "4"]

        await run_and_validate_benchmark(
            aiperf_runner, validate_aiperf_output, args, min_requests=45, limit_workers=False
        )


@pytest.mark.integration
@pytest.mark.asyncio
class TestMetricComputationIntegration:
    """Integration tests for metric computation accuracy."""

    async def test_ttft_computation_accuracy(
        self, base_profile_args, aiperf_runner, validate_aiperf_output
    ):
        """Validates TTFT computation accuracy."""
        args = [*base_profile_args, "--endpoint-type", "chat", "--streaming",
                "--request-count", "10", "--concurrency", "1"]

        output = await run_and_validate_benchmark(
            aiperf_runner, validate_aiperf_output, args
        )

        ttft = BenchmarkResult.from_directory(output.actual_dir).get_metric("ttft")
        assert 1 <= ttft.avg <= 1000, f"TTFT {ttft.avg}ms outside range"
        assert ttft.std is not None

    async def test_output_token_count_matches_input(
        self, base_profile_args, aiperf_runner, validate_aiperf_output
    ):
        """Validates output token counting accuracy."""
        args = [*base_profile_args, "--endpoint-type", "chat", "--streaming",
                "--request-count", "10", "--concurrency", "1"]

        output = await run_and_validate_benchmark(
            aiperf_runner, validate_aiperf_output, args
        )

        osl = BenchmarkResult.from_directory(output.actual_dir).get_metric("output_sequence_length")
        assert osl.avg > 0


@pytest.mark.integration
@pytest.mark.asyncio
class TestErrorHandlingIntegration:
    """Integration tests for error handling."""

    async def test_benchmark_handles_http_errors(
        self, base_profile_args, aiperf_runner, validate_aiperf_output
    ):
        """Validates HTTP error tracking."""
        args = [*base_profile_args, "--endpoint-type", "chat",
                "--request-count", "10", "--concurrency", "5", "--timeout-seconds", "2"]

        result: AIPerfRunResult = await aiperf_runner(args)

        # May succeed or fail, but shouldn't crash
        if result.returncode == 0:
            output = validate_aiperf_output(result.output_dir)
            errors = BenchmarkResult.from_directory(output.actual_dir).error_summary
            assert isinstance(errors, list)


@pytest.mark.integration
@pytest.mark.asyncio
class TestConfigurationIntegration:
    """Integration tests for configuration handling."""

    async def test_artifact_directory_created(
        self, base_profile_args, aiperf_runner, temp_output_dir
    ):
        """Validates artifact directory creation."""
        args = [*base_profile_args, "--endpoint-type", "chat",
                "--request-count", DEFAULT_REQUEST_COUNT]

        result: AIPerfRunResult = await aiperf_runner(args)
        assert result.returncode == 0

        assert list(temp_output_dir.glob("**/*aiperf.json"))

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
    ) -> ValidatedOutput:
        args = [*base_profile_args, "--endpoint-type", endpoint_type,
                "--request-count", DEFAULT_REQUEST_COUNT, "--concurrency", DEFAULT_CONCURRENCY]

        if streaming:
            args.append("--streaming")
        if extra_args:
            args.extend(extra_args)

        result: AIPerfRunResult = await aiperf_runner(args)
        assert result.returncode == 0, f"{endpoint_type} failed: {result.stderr}"

        output = validate_aiperf_output(result.output_dir)
        validator = BenchmarkResult.from_directory(output.actual_dir)

        validator.assert_metric_exists("request_count", "request_latency")

        if verify_streaming:
            validator.assert_metric_exists("ttft", "inter_token_latency")
        if verify_no_tokens:
            assert "ttft" not in validator.records
            assert "output_sequence_length" not in validator.records

        return output

    async def test_chat_endpoint_non_streaming(
        self, base_profile_args, aiperf_runner, validate_aiperf_output
    ):
        """Validates /v1/chat/completions non-streaming."""
        output = await self._test_endpoint(
            base_profile_args, aiperf_runner, validate_aiperf_output, "chat"
        )
        BenchmarkResult.from_directory(output.actual_dir).assert_metric_exists("output_sequence_length")

    async def test_chat_endpoint_streaming(
        self, base_profile_args, aiperf_runner, validate_aiperf_output
    ):
        """Validates /v1/chat/completions streaming."""
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
        """Validates /v1/completions non-streaming."""
        output = await self._test_endpoint(
            base_profile_args, aiperf_runner, validate_aiperf_output, "completions"
        )
        validator = BenchmarkResult.from_directory(output.actual_dir)
        validator.assert_metric_exists("output_sequence_length")
        validator.assert_request_count(min_count=4)

    async def test_completions_endpoint_streaming(
        self, base_profile_args, aiperf_runner, validate_aiperf_output
    ):
        """Validates /v1/completions streaming."""
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
        """Validates /v1/embeddings endpoint."""
        await self._test_endpoint(
            base_profile_args,
            aiperf_runner,
            validate_aiperf_output,
            "embeddings",
            verify_no_tokens=True,
        )

    async def test_rankings_endpoint(
        self, base_profile_args, aiperf_runner, validate_aiperf_output, create_rankings_dataset
    ):
        """Validates /v1/ranking endpoint with custom dataset."""
        dataset_path = create_rankings_dataset(int(DEFAULT_REQUEST_COUNT))

        extra_args = ["--input-file", str(dataset_path), "--custom-dataset-type", "single_turn"]

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
        """Validates /v1/responses endpoint."""
        output = await self._test_endpoint(
            base_profile_args, aiperf_runner, validate_aiperf_output, "responses"
        )
        BenchmarkResult.from_directory(output.actual_dir).assert_metric_exists("output_sequence_length")

    @pytest.mark.skip(reason="Bug in aiperf responses API - needs to be fixed")
    async def test_responses_endpoint_streaming(
        self, base_profile_args, aiperf_runner, validate_aiperf_output
    ):
        """Validates /v1/responses with streaming."""
        await self._test_endpoint(
            base_profile_args, aiperf_runner, validate_aiperf_output, "responses",
            streaming=True, verify_streaming=True
        )
