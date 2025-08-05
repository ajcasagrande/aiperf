# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
import pytest

from aiperf.common.config.endpoint_config import EndpointConfig
from aiperf.common.enums.endpoints_enums import EndpointType
from aiperf.metrics.types.request_latency import RequestLatencyMetric

from .conftest import BaseMetricTest, ParsedRecord, Response


class TestRequestLatencyMetric(BaseMetricTest):
    """Test suite for RequestLatencyMetric using type-safe dataclasses."""

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
        """Test request latency with a single record."""
        record = parsed_response_record_builder.simple_record(
            request_start_time=100, response_perf_ns=200
        )

        summary = await self.process_single_record_and_get_summary(record)
        # Latency = 200 - 100 = 100 ns
        self.assert_metric_value(summary, expected_value=100)

    @pytest.mark.asyncio
    async def test_multiple_records(self, parsed_response_record_builder):
        """Test request latency with multiple records."""
        configs = [
            ParsedRecord(
                request_start_time=100, responses=[Response(perf_ns=150, token_count=1)]
            ),
            ParsedRecord(
                request_start_time=200, responses=[Response(perf_ns=300, token_count=1)]
            ),
            ParsedRecord(
                request_start_time=400, responses=[Response(perf_ns=450, token_count=1)]
            ),
        ]

        records = parsed_response_record_builder.create_records_from_configs(configs)
        summary = await self.process_records_and_get_summary(records)

        # Latencies: [50, 100, 50], average = 66.67
        expected_avg = (50 + 100 + 50) / 3
        self.assert_metric_value(summary, expected_avg)

    @pytest.mark.asyncio
    async def test_multiple_responses_per_record(self, parsed_response_record_builder):
        """Test request latency with multiple responses per record (uses last response)."""
        record = parsed_response_record_builder.create_record_from_config(
            ParsedRecord(
                request_start_time=100,
                responses=[
                    Response(perf_ns=120, token_count=1),
                    Response(perf_ns=140, token_count=1),
                    Response(perf_ns=180, token_count=1),  # Last response
                ],
            )
        )

        summary = await self.process_single_record_and_get_summary(record)
        # Latency = 180 - 100 = 80 ns (uses last response timestamp)
        self.assert_metric_value(summary, expected_value=80)

    @pytest.mark.asyncio
    async def test_invalid_record_raises_error(self, parsed_response_record_builder):
        """Test that invalid record raises an error."""
        record = parsed_response_record_builder.create_record_from_config(
            ParsedRecord(request_start_time=10, responses=[])
        )

        await self.assert_record_processing_raises(record)
