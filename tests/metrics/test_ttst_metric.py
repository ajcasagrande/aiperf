# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
import pytest

from aiperf.common.config.endpoint_config import EndpointConfig
from aiperf.common.enums.endpoints_enums import EndpointType
from aiperf.metrics.types import TTSTMetric

from .conftest import BaseMetricTest


class TestTTSTMetric(BaseMetricTest):
    """Test suite for TTSTMetric using the base test framework."""

    @property
    def endpoint_config(self) -> EndpointConfig:
        return EndpointConfig(
            type=EndpointType.OPENAI_COMPLETIONS,
            streaming=True,  # TTST requires streaming responses
            model_names=["test-model"],
        )

    @property
    def metric_tag(self) -> str:
        return TTSTMetric.tag

    @pytest.mark.asyncio
    async def test_ttst_metric_single_record(self, parsed_response_record_builder):
        """Test TTST metric with a single record having two responses."""
        record = (
            parsed_response_record_builder.with_request_start_time(100)
            .add_response(perf_ns=150, token_count=1)
            .add_response(perf_ns=180, token_count=1)
            .build()
        )

        summary = await self.process_single_record_and_get_summary(record)
        self.assert_metric_value(summary, expected_value=30)  # 180 - 150

    @pytest.mark.asyncio
    async def test_ttst_metric_add_multiple_records(
        self, parsed_response_record_builder
    ):
        """Test TTST metric with multiple records."""
        records = (
            parsed_response_record_builder.with_request_start_time(10)
            .add_response(perf_ns=15, token_count=1)
            .add_response(perf_ns=20, token_count=1)
            .new_record()
            .with_request_start_time(20)
            .add_response(perf_ns=25, token_count=1)
            .add_response(perf_ns=35, token_count=1)
            .new_record()
            .with_request_start_time(30)
            .add_response(perf_ns=40, token_count=1)
            .add_response(perf_ns=50, token_count=1)
            .build_all()
        )

        summary = await self.process_records_and_get_summary(records)

        # Expected TTSTs: [5, 10, 10] nanoseconds
        expected_avg = (5 + 10 + 10) / 3
        self.assert_metric_value(summary, expected_avg)

    @pytest.mark.asyncio
    async def test_ttst_metric_with_one_response_raises(
        self, parsed_response_record_builder
    ):
        """Test that TTST metric raises error with only one response."""
        record = (
            parsed_response_record_builder.with_request_start_time(10)
            .add_response(perf_ns=15, token_count=1)
            .build()
        )

        await self.assert_record_processing_raises(
            record, match="at least two responses"
        )

    @pytest.mark.asyncio
    async def test_ttst_metric_response_timestamp_order_raises(
        self, parsed_response_record_builder
    ):
        """Test that TTST metric raises error when second response timestamp is before first."""
        record = (
            parsed_response_record_builder.with_request_start_time(100)
            .add_response(perf_ns=150, token_count=1)
            .add_response(perf_ns=140, token_count=1)  # Second response before first
            .build()
        )

        await self.assert_record_processing_raises(
            record,
            match="Second response timestamp must be greater than or equal to the first response timestamp.",
        )
