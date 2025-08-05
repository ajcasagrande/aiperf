# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
import pytest

from aiperf.common.config.endpoint_config import EndpointConfig
from aiperf.common.enums.endpoints_enums import EndpointType
from aiperf.metrics.types.max_response_timestamp import MaxResponseTimestampMetric

from .conftest import BaseMetricTest


class TestMaxResponseMetric(BaseMetricTest):
    """Test suite for MaxResponseTimestampMetric using the base test framework."""

    @property
    def endpoint_config(self) -> EndpointConfig:
        return EndpointConfig(
            type=EndpointType.OPENAI_EMBEDDINGS,
            streaming=False,
            model_names=["test-model"],
        )

    @property
    def metric_tag(self) -> str:
        return MaxResponseTimestampMetric.tag

    @pytest.mark.asyncio
    async def test_single_record(self, parsed_response_record_builder):
        """Test max response timestamp with a single record."""
        record = (
            parsed_response_record_builder.with_request_start_time(100)
            .add_response(perf_ns=150)
            .build()
        )

        summary = await self.process_single_record_and_get_summary(record)
        self.assert_metric_value(summary, expected_value=150)

    @pytest.mark.asyncio
    async def test_add_multiple_records(self, parsed_response_record_builder):
        """Test max response timestamp with multiple records."""
        records = (
            parsed_response_record_builder.with_request_start_time(20)
            .add_response(perf_ns=25)
            .new_record()
            .with_request_start_time(10)
            .add_response(perf_ns=15)
            .new_record()
            .with_request_start_time(30)
            .add_response(perf_ns=40)
            .build_all()
        )

        summary = await self.process_records_and_get_summary(records)
        self.assert_metric_value(summary, expected_value=40)  # Max of [25, 15, 40]

    @pytest.mark.asyncio
    async def test_record_with_no_responses_raises(
        self, parsed_response_record_builder
    ):
        """Test that record with no responses raises an error."""
        # Create a record builder but don't add any responses
        builder = parsed_response_record_builder.with_request_start_time(10)
        # Clear any default responses that might be added
        builder._current_record["responses"] = []
        record = builder.build()

        await self.assert_record_processing_raises(record, match="Invalid Record")
