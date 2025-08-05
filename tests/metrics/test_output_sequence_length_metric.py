# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
import pytest

from aiperf.common.config.endpoint_config import EndpointConfig
from aiperf.common.enums.endpoints_enums import EndpointType
from aiperf.metrics.types.output_sequence_length import OutputSequenceLengthMetric

from .conftest import BaseMetricTest


class TestOutputSequenceLengthMetric(BaseMetricTest):
    """Test suite for OutputSequenceLengthMetric using the base test framework."""

    @property
    def endpoint_config(self) -> EndpointConfig:
        return EndpointConfig(
            type=EndpointType.OPENAI_COMPLETIONS,
            streaming=False,
            model_names=["test-model"],
        )

    @property
    def metric_tag(self) -> str:
        return OutputSequenceLengthMetric.tag

    @pytest.mark.asyncio
    async def test_osl_metric_with_multiple_records(
        self, parsed_response_record_builder
    ):
        """Test output sequence length metric with multiple records."""
        records = (
            parsed_response_record_builder.with_request_start_time(10)
            .add_response(perf_ns=15, token_count=3)
            .add_response(perf_ns=20, token_count=5)
            .new_record()
            .with_request_start_time(20)
            .add_response(perf_ns=25, token_count=7)
            .build_all()
        )

        # Token counts are now calculated automatically: 3+5=8, 7=7

        summary = await self.process_records_and_get_summary(records)

        expected_avg = (8 + 7) / 2  # Average of [8, 7]
        self.assert_metric_value(summary, expected_avg)

    @pytest.mark.asyncio
    async def test_osl_metric_invalid_record(self):
        """Test that invalid record raises an error."""
        await self.assert_invalid_record_raises()

    @pytest.mark.asyncio
    async def test_osl_metric_missing_output_token_count(
        self, parsed_response_record_builder
    ):
        """Test that missing output token count raises an error."""
        record = (
            parsed_response_record_builder.with_request_start_time(10)
            # Build a record with no responses to get None output_token_count
            .build()
        )

        await self.assert_record_processing_raises(
            record, match="Output token count is missing in the record"
        )
