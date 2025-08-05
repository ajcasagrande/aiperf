# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

import pytest

from aiperf.common.config.endpoint_config import EndpointConfig
from aiperf.common.enums.endpoints_enums import EndpointType
from aiperf.metrics.types.valid_request_count import ValidRequestCountMetric

from .conftest import BaseMetricTest


class TestValidRequestCountMetric(BaseMetricTest):
    """Test suite for ValidRequestCountMetric using the base test framework."""

    @property
    def endpoint_config(self) -> EndpointConfig:
        return EndpointConfig(
            type=EndpointType.OPENAI_EMBEDDINGS,
            streaming=False,
            model_names=["test-model"],
        )

    @property
    def metric_tag(self) -> str:
        return ValidRequestCountMetric.tag

    @pytest.mark.asyncio
    async def test_request_count_with_multiple_valid_records(
        self, parsed_response_record_builder
    ):
        """Test valid request count metric with multiple records."""
        records = (
            parsed_response_record_builder.with_request_start_time(0)
            .add_response(perf_ns=5)
            .new_record()
            .with_request_start_time(10)
            .add_response(perf_ns=15)
            .new_record()
            .with_request_start_time(20)
            .add_response(perf_ns=25)
            .build_all()
        )

        summary = await self.process_records_and_get_summary(records)
        self.assert_metric_value(summary, expected_value=3)  # Count of valid requests

    @pytest.mark.asyncio
    async def test_request_count_invalid_record_raises(self):
        """Test that invalid record raises an error."""
        await self.assert_invalid_record_raises()
