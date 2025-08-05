# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

import pytest

from aiperf.common.config.endpoint_config import EndpointConfig
from aiperf.common.enums.endpoints_enums import EndpointType
from aiperf.metrics.types.request_throughput import RequestThroughputMetric

from .conftest import BaseMetricTest


class TestRequestThroughputMetric(BaseMetricTest):
    """Test suite for RequestThroughputMetric using the base test framework."""

    @property
    def endpoint_config(self) -> EndpointConfig:
        return EndpointConfig(
            type=EndpointType.OPENAI_EMBEDDINGS,
            streaming=False,
            model_names=["test-model"],
        )

    @property
    def metric_tag(self) -> str:
        return RequestThroughputMetric.tag

    @pytest.mark.asyncio
    async def test_request_throughput(self, parsed_response_record_builder):
        """Test request throughput metric with multiple records."""
        records = (
            parsed_response_record_builder.with_request_start_time(0)
            .add_response(perf_ns=1_000_000_000)  # 1 second
            .new_record()
            .with_request_start_time(1_000_000_000)  # Start at 1 second
            .add_response(perf_ns=2_000_000_000)  # Response at 2 seconds
            .new_record()
            .with_request_start_time(2_000_000_000)  # Start at 2 seconds
            .add_response(
                perf_ns=3_000_000_000
            )  # Response at 3 seconds (total duration = 3 seconds)
            .build_all()
        )

        summary = await self.process_records_and_get_summary(records)

        # Expected: 3 requests / 3 seconds = 1.0 req/sec
        expected = 1.0
        self.assert_metric_value(summary, expected, tolerance=0.01)
