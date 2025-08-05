# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
import pytest

from aiperf.common.config.endpoint_config import EndpointConfig
from aiperf.common.enums.endpoints_enums import EndpointType

from .conftest import (
    BaseMetricTest,
    ParsedRecord,
    ParsedResponseRecordBuilder,
    Response,
)


class TestMetricSummary(BaseMetricTest):
    """Test suite for metric summary."""

    @property
    def endpoint_config(self) -> EndpointConfig:
        return EndpointConfig(
            type=EndpointType.OPENAI_COMPLETIONS,
            streaming=False,
            model_names=["test-model"],
        )

    @property
    def metric_tag(self) -> str:
        return "request_latency"  # Placeholder for summary tests

    @pytest.mark.asyncio
    async def test_metric_summary_computation(
        self, parsed_response_record_builder: ParsedResponseRecordBuilder
    ):
        """Test metric summary computation with various records."""
        configs = [
            ParsedRecord(
                request_start_time=100,
                worker_id="worker-1",
                responses=[Response(perf_ns=150, token_count=5)],
                recv_start_perf_ns=110,
            ),
            ParsedRecord(
                request_start_time=200,
                worker_id="worker-2",
                responses=[Response(perf_ns=300, token_count=10)],
                recv_start_perf_ns=220,
            ),
            ParsedRecord(
                request_start_time=400,
                worker_id="worker-3",
                responses=[Response(perf_ns=500, token_count=8)],
                recv_start_perf_ns=430,
            ),
        ]

        records = parsed_response_record_builder.create_records_from_configs(configs)
        summary = await self.process_records_and_get_summary(records)

        # Verify summary contains multiple metrics
        assert len(summary) > 1, "Summary should contain multiple metric results"

        # Check that we have some key metrics
        metric_tags = {result.tag for result in summary}
        expected_metrics = {
            "request_latency",
            "valid_request_count",
            "output_sequence_length",
        }

        # At least some expected metrics should be present
        assert len(expected_metrics.intersection(metric_tags)) > 0, (
            f"Expected some of {expected_metrics} in {metric_tags}"
        )

    @pytest.mark.asyncio
    async def test_metric_summary_single_record(
        self, parsed_response_record_builder: ParsedResponseRecordBuilder
    ):
        """Test metric summary with a single record."""
        record = parsed_response_record_builder.create_record_from_config(
            ParsedRecord(
                request_start_time=1000,
                worker_id="single-worker",
                responses=[
                    Response(perf_ns=1100, token_count=3),
                    Response(perf_ns=1200, token_count=2),
                ],
                recv_start_perf_ns=1050,
            )
        )

        summary = await self.process_single_record_and_get_summary(record)

        # Should have multiple metric results
        assert len(summary) > 0, "Summary should contain metric results"

        # Check for request latency specifically
        request_latency_result = None
        for result in summary:
            if result.tag == "request_latency":
                request_latency_result = result
                break

        assert request_latency_result is not None, "Should have request_latency metric"
        # Latency should be 1200 - 1000 = 200
        assert request_latency_result.avg == 200, (
            f"Expected latency 200, got {request_latency_result.avg}"
        )
