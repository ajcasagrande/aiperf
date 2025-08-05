# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

import pytest

from aiperf.common.config.endpoint_config import EndpointConfig
from aiperf.common.enums.endpoints_enums import EndpointType
from aiperf.metrics.types.time_to_first_token import TTFTMetric

from .conftest import BaseMetricTest


class TestTTFTMetric(BaseMetricTest):
    """Test suite for TTFTMetric using the base test framework."""

    @property
    def endpoint_config(self) -> EndpointConfig:
        return EndpointConfig(
            type=EndpointType.OPENAI_COMPLETIONS,
            streaming=True,  # TTFT is for streaming tokens only
            model_names=["test-model"],
        )

    @property
    def metric_tag(self) -> str:
        return TTFTMetric.tag

    @pytest.mark.asyncio
    async def test_single_record(self, parsed_response_record_builder):
        """Test TTFT metric with a single record."""
        record = (
            parsed_response_record_builder.with_request_start_time(100)
            .add_response(perf_ns=150, token_count=1)
            .build()
        )

        summary = await self.process_single_record_and_get_summary(record)
        self.assert_metric_value(summary, expected_value=50)  # 150 - 100

    @pytest.mark.asyncio
    async def test_add_multiple_records(self, parsed_response_record_builder):
        """Test TTFT metric with multiple records."""
        records = (
            parsed_response_record_builder.with_request_start_time(10)
            .add_response(perf_ns=15, token_count=1)
            .new_record()
            .with_request_start_time(20)
            .add_response(perf_ns=25, token_count=1)
            .new_record()
            .with_request_start_time(30)
            .add_response(perf_ns=40, token_count=1)
            .build_all()
        )

        summary = await self.process_records_and_get_summary(records)

        # Expected TTFTs: [5, 5, 10] nanoseconds
        expected_avg = (5 + 5 + 10) / 3
        self.assert_metric_value(summary, expected_avg)

    @pytest.mark.asyncio
    async def test_convert_metrics(self, parsed_response_record_builder):
        """Test TTFT metric unit conversion."""
        records = (
            parsed_response_record_builder.with_request_start_time(
                10_000_000
            )  # 10ms in ns
            .add_response(perf_ns=15_000_000, token_count=1)  # 15ms in ns
            .new_record()
            .with_request_start_time(20_000_000)  # 20ms in ns
            .add_response(perf_ns=25_000_000, token_count=1)  # 25ms in ns
            .new_record()
            .with_request_start_time(30_000_000)  # 30ms in ns
            .add_response(perf_ns=40_000_000, token_count=1)  # 40ms in ns
            .build_all()
        )

        summary = await self.process_records_and_get_summary(records)

        # When displayed in milliseconds, the values should be [5, 5, 10] milliseconds
        # Note: The summary already converts to display units automatically
        expected_avg_ms = (5 + 5 + 10) / 3  # milliseconds
        # The result should be in display units (milliseconds)
        self.assert_metric_value(summary, expected_avg_ms, tolerance=0.01)
