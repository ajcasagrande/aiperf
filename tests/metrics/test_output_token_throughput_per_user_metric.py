# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

import pytest

from aiperf.common.config.endpoint_config import EndpointConfig
from aiperf.common.enums.endpoints_enums import EndpointType
from aiperf.metrics.types.output_token_throughput_per_user import (
    OutputTokenThroughputPerUserMetric,
)

from .conftest import BaseMetricTest


class TestOutputTokenThroughputPerUserMetric(BaseMetricTest):
    """Test suite for OutputTokenThroughputPerUserMetric using the base test framework."""

    @property
    def endpoint_config(self) -> EndpointConfig:
        return EndpointConfig(
            type=EndpointType.OPENAI_COMPLETIONS,
            streaming=True,  # Use streaming to enable inter-token latency calculation
            model_names=["test-model"],
        )

    @property
    def metric_tag(self) -> str:
        return OutputTokenThroughputPerUserMetric.tag

    @pytest.mark.asyncio
    async def test_output_token_throughput_per_user_metric(
        self, parsed_response_record_builder
    ):
        """Test output token throughput per user metric with multiple records."""
        records = (
            parsed_response_record_builder.with_request_start_time(0)
            .add_response(perf_ns=250_000_000, token_count=1)  # TTFT = 250ms
            .add_response(
                perf_ns=750_000_000, token_count=1
            )  # ITL = (750-250)/(2-1) = 500ms = 500_000_000ns
            .new_record()
            .with_request_start_time(0)
            .add_response(perf_ns=125_000_000, token_count=1)  # TTFT = 125ms
            .add_response(
                perf_ns=375_000_000, token_count=1
            )  # ITL = (375-125)/(2-1) = 250ms = 250_000_000ns
            .build_all()
        )

        # Set output token counts manually for proper OSL calculation
        records[0].output_token_count = 2  # 2 tokens total
        records[1].output_token_count = 2  # 2 tokens total

        summary = await self.process_records_and_get_summary(records)

        # Expected calculations based on inter-token latency:
        # Record 1: ITL = 500_000_000ns → 1/ITL = 2.0 tokens/sec
        # Record 2: ITL = 250_000_000ns → 1/ITL = 4.0 tokens/sec
        # Average: (2.0 + 4.0) / 2 = 3.0 tokens/sec
        expected_avg = 3.0
        self.assert_metric_value(summary, expected_avg, tolerance=0.1)
