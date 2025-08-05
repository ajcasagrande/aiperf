#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0

import pytest

from aiperf.common.config.endpoint_config import EndpointConfig
from aiperf.common.enums.endpoints_enums import EndpointType
from aiperf.metrics.types.input_sequence_length import InputSequenceLengthMetric

from .conftest import BaseMetricTest


class TestInputSequenceLengthMetric(BaseMetricTest):
    """Test suite for InputSequenceLengthMetric using the base test framework."""

    @property
    def endpoint_config(self) -> EndpointConfig:
        return EndpointConfig(
            type=EndpointType.OPENAI_COMPLETIONS,
            streaming=False,
            model_names=["test-model"],
        )

    @property
    def metric_tag(self) -> str:
        return InputSequenceLengthMetric.tag

    @pytest.mark.asyncio
    async def test_isl_metric_with_multiple_records(
        self, parsed_response_record_builder
    ):
        """Test input sequence length metric with multiple records."""
        records = (
            parsed_response_record_builder.with_request_start_time(10)
            .with_input_token_count(5)  # Use builder method
            .add_response(perf_ns=15, token_count=1)
            .new_record()
            .with_request_start_time(20)
            .with_input_token_count(7)  # Use builder method
            .add_response(perf_ns=25, token_count=1)
            .build_all()
        )

        summary = await self.process_records_and_get_summary(records)

        expected_avg = (5 + 7) / 2  # Average of [5, 7]
        self.assert_metric_value(summary, expected_avg)

    @pytest.mark.asyncio
    async def test_isl_metric_missing_input_token_count(
        self, parsed_response_record_builder
    ):
        """Test that missing input token count raises an error."""
        record = (
            parsed_response_record_builder.with_request_start_time(10)
            .with_input_token_count(None)  # Explicitly set to None
            .add_response(perf_ns=15, token_count=1)
            .build()
        )

        await self.assert_record_processing_raises(
            record, match="Input Token Count is not available for the record"
        )
