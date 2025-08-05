# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

import pytest

from aiperf.common.config.endpoint_config import EndpointConfig
from aiperf.common.enums.endpoints_enums import EndpointType
from aiperf.metrics.types.output_token_count import OutputTokenCountMetric

from .conftest import BaseMetricTest


class TestOutputTokenCountMetric(BaseMetricTest):
    """Test suite for OutputTokenCountMetric using the base test framework."""

    @property
    def endpoint_config(self) -> EndpointConfig:
        return EndpointConfig(
            type=EndpointType.OPENAI_COMPLETIONS,
            streaming=False,
            model_names=["test-model"],
        )

    @property
    def metric_tag(self) -> str:
        return OutputTokenCountMetric.tag

    @pytest.mark.asyncio
    async def test_output_token_count_metric(self, parsed_response_record_builder):
        """Test output token count metric."""
        record = (
            parsed_response_record_builder.with_request_start_time(0)
            .add_response(
                perf_ns=100, token_count=5, raw_text=["hello"], parsed_text=["hello"]
            )
            .build()
        )

        # Token count is now calculated automatically: 5

        summary = await self.process_single_record_and_get_summary(record)
        self.assert_metric_value(summary, expected_value=5)
