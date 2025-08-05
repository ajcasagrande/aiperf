# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

import pytest

from aiperf.common.config.endpoint_config import EndpointConfig
from aiperf.common.enums.endpoints_enums import EndpointType
from aiperf.metrics.types.output_token_throughput import OutputTokenThroughputMetric

from .conftest import BaseMetricTest


class TestOutputTokenThroughputMetric(BaseMetricTest):
    """Test suite for OutputTokenThroughputMetric using the base test framework."""

    @property
    def endpoint_config(self) -> EndpointConfig:
        return EndpointConfig(
            type=EndpointType.OPENAI_COMPLETIONS,
            streaming=False,
            model_names=["test-model"],
        )

    @property
    def metric_tag(self) -> str:
        return OutputTokenThroughputMetric.tag

    @pytest.mark.asyncio
    async def test_output_token_throughput_metric(self, parsed_response_record_builder):
        """Test output token throughput metric with multiple records."""
        records = (
            parsed_response_record_builder.with_request_start_time(0)
            .add_response(perf_ns=1_000_000_000, token_count=10)  # 10 tokens
            .new_record()
            .with_request_start_time(1_000_000_000)  # Start 1 second later
            .add_response(perf_ns=3_000_000_000, token_count=20)  # 20 tokens
            .new_record()
            .with_request_start_time(2_000_000_000)  # Start 2 seconds later
            .add_response(
                perf_ns=5_000_000_000, token_count=30
            )  # 30 tokens - total = 60 tokens
            .build_all()
        )

        # Token counts are now calculated automatically: 10 + 20 + 30 = 60 total

        summary = await self.process_records_and_get_summary(records)

        # Expected: 60 tokens / 5 seconds = 12 tokens/sec
        expected = 60 / 5
        self.assert_metric_value(summary, expected, tolerance=0.01)
