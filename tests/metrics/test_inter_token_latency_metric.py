# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

import pytest

from aiperf.common.config.endpoint_config import EndpointConfig
from aiperf.common.enums.endpoints_enums import EndpointType
from aiperf.metrics.types.inter_token_latency import InterTokenLatencyMetric

from .conftest import BaseMetricTest


class TestInterTokenLatencyMetric(BaseMetricTest):
    """Test suite for InterTokenLatencyMetric using the base test framework."""

    @property
    def endpoint_config(self) -> EndpointConfig:
        return EndpointConfig(
            type=EndpointType.OPENAI_COMPLETIONS,  # Use completions to get the required metrics
            streaming=True,
            model_names=["test-model"],
        )

    @property
    def metric_tag(self) -> str:
        return InterTokenLatencyMetric.tag

    @pytest.mark.asyncio
    async def test_inter_token_latency_metric_computes_correctly(
        self, parsed_response_record_builder
    ):
        """Test that inter-token latency is calculated correctly using multiple records."""
        records = (
            parsed_response_record_builder.with_request_start_time(0)
            .add_response(perf_ns=40, token_count=1)  # TTFT = 40ns
            .add_response(
                perf_ns=100, token_count=5
            )  # Total latency = 100ns, OSL = 6 tokens
            .new_record()
            .with_request_start_time(0)
            .add_response(perf_ns=60, token_count=1)  # TTFT = 60ns
            .add_response(
                perf_ns=200, token_count=2
            )  # Total latency = 200ns, OSL = 3 tokens
            .build_all()
        )

        summary = await self.process_records_and_get_summary(records)

        # Expected calculations:
        # Record 1: (100 - 40) / (6 - 1) = 60 / 5 = 12
        # Record 2: (200 - 60) / (3 - 1) = 140 / 2 = 70
        # Average: (12 + 70) / 2 = 41
        expected_values = [12, 70]
        expected_avg = sum(expected_values) / len(expected_values)

        self.assert_metric_value(summary, expected_avg, tolerance=0.01)
