# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
import pytest

from aiperf.common.config.endpoint_config import EndpointConfig
from aiperf.common.enums.endpoints_enums import EndpointType
from aiperf.metrics.types.request_latency import RequestLatencyMetric

from .conftest import BaseMetricTest


class TestRequestLatencyMetric(BaseMetricTest):
    """Test suite for RequestLatencyMetric using the base test framework."""

    @property
    def endpoint_config(self) -> EndpointConfig:
        return EndpointConfig(
            type=EndpointType.OPENAI_EMBEDDINGS,
            streaming=False,
            model_names=["test-model"],
        )

    @property
    def metric_tag(self) -> str:
        return RequestLatencyMetric.tag

    @pytest.mark.asyncio
    async def test_single_record(self, parsed_response_record_builder):
        """Test request latency metric with a single record."""
        record = (
            parsed_response_record_builder.with_request_start_time(100)
            .add_response(perf_ns=150)
            .build()
        )

        summary = await self.process_single_record_and_get_summary(record)
        self.assert_metric_value(summary, expected_value=50)  # 150 - 100

    @pytest.mark.asyncio
    async def test_add_multiple_records(self, parsed_response_record_builder):
        """Test request latency metric with multiple records."""
        records = (
            parsed_response_record_builder.with_request_start_time(10)
            .add_response(perf_ns=15)
            .add_response(perf_ns=25)  # Final response at 25ns
            .new_record()
            .with_request_start_time(20)
            .add_response(perf_ns=25)
            .add_response(perf_ns=35)  # Final response at 35ns
            .new_record()
            .with_request_start_time(30)
            .add_response(perf_ns=40)
            .add_response(perf_ns=50)  # Final response at 50ns
            .build_all()
        )

        summary = await self.process_records_and_get_summary(records)

        # Expected latencies: [15, 15, 20] (final_response - start_time)
        expected_avg = (15 + 15 + 20) / 3
        self.assert_metric_value(summary, expected_avg)

    @pytest.mark.asyncio
    async def test_response_timestamp_less_than_request_raises(
        self, parsed_response_record_builder
    ):
        """Test that response timestamp less than request timestamp raises an error."""
        record = (
            parsed_response_record_builder.with_request_start_time(100)
            .add_response(perf_ns=90)  # Response before request
            .build()
        )

        await self.assert_record_processing_raises(record, match="Invalid Record")
