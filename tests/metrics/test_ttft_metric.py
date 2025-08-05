# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
import pytest

from aiperf.common.config.endpoint_config import EndpointConfig
from aiperf.common.enums.endpoints_enums import EndpointType
from aiperf.metrics.types.time_to_first_token import TTFTMetric

from .conftest import BaseMetricTest, ParsedRecord, Response


class TestTTFTMetric(BaseMetricTest):
    """Test suite for TTFTMetric using type-safe dataclasses."""

    @property
    def endpoint_config(self) -> EndpointConfig:
        return EndpointConfig(
            type=EndpointType.OPENAI_COMPLETIONS,
            streaming=True,
            model_names=["test-model"],
        )

    @property
    def metric_tag(self) -> str:
        return TTFTMetric.tag

    @pytest.mark.asyncio
    async def test_single_record(self, parsed_response_record_builder):
        """Test TTFT metric with a single record."""
        record = parsed_response_record_builder.simple_record(
            request_start_time=100, response_perf_ns=150, token_count=1
        )

        summary = await self.process_single_record_and_get_summary(record)
        self.assert_metric_value(summary, expected_value=50)  # 150 - 100

    @pytest.mark.asyncio
    async def test_multiple_records(self, parsed_response_record_builder):
        """Test TTFT metric with multiple records."""
        configs = [
            ParsedRecord(
                request_start_time=10, responses=[Response(perf_ns=15, token_count=1)]
            ),
            ParsedRecord(
                request_start_time=20, responses=[Response(perf_ns=25, token_count=1)]
            ),
            ParsedRecord(
                request_start_time=30, responses=[Response(perf_ns=40, token_count=1)]
            ),
        ]

        records = parsed_response_record_builder.create_records_from_configs(configs)
        summary = await self.process_records_and_get_summary(records)

        # Expected TTFTs: [5, 5, 10] nanoseconds
        expected_avg = (5 + 5 + 10) / 3
        self.assert_metric_value(summary, expected_avg)

    @pytest.mark.asyncio
    async def test_convert_metrics(self, parsed_response_record_builder):
        """Test TTFT metric conversion to milliseconds."""
        record = parsed_response_record_builder.simple_record(
            request_start_time=100_000_000,  # 100ms in nanoseconds
            response_perf_ns=150_000_000,  # 150ms in nanoseconds
            token_count=1,
        )

        summary = await self.process_single_record_and_get_summary(record)

        # TTFT = 150ms - 100ms = 50ms = 50_000_000 nanoseconds
        self.assert_metric_value(summary, expected_value=50_000_000)
