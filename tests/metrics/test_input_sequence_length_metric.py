# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
import pytest

from aiperf.common.config.endpoint_config import EndpointConfig
from aiperf.common.enums.endpoints_enums import EndpointType
from aiperf.metrics.types.input_sequence_length import InputSequenceLengthMetric

from .conftest import (
    BaseMetricTest,
    ParsedRecord,
    ParsedResponseRecordBuilder,
    Response,
)


class TestInputSequenceLengthMetric(BaseMetricTest):
    """Test suite for InputSequenceLengthMetric using type-safe dataclasses."""

    @property
    def endpoint_config(self) -> EndpointConfig:
        return EndpointConfig(
            type=EndpointType.OPENAI_EMBEDDINGS,
            streaming=False,
            model_names=["test-model"],
        )

    @property
    def metric_tag(self) -> str:
        return InputSequenceLengthMetric.tag

    @pytest.mark.asyncio
    async def test_single_record(
        self, parsed_response_record_builder: ParsedResponseRecordBuilder
    ):
        """Test input sequence length with a single record."""
        record = parsed_response_record_builder.simple_record(
            request_start_time=100, input_token_count=10
        )

        summary = await self.process_single_record_and_get_summary(record)
        self.assert_metric_value(summary, expected_value=10)

    @pytest.mark.asyncio
    async def test_multiple_records(
        self, parsed_response_record_builder: ParsedResponseRecordBuilder
    ):
        """Test input sequence length with multiple records."""
        configs = [
            ParsedRecord(input_token_count=5, responses=[Response(perf_ns=120)]),
            ParsedRecord(input_token_count=15, responses=[Response(perf_ns=130)]),
            ParsedRecord(input_token_count=10, responses=[Response(perf_ns=140)]),
        ]

        records = parsed_response_record_builder.create_records_from_configs(configs)
        summary = await self.process_records_and_get_summary(records)

        # Expected values: [5, 15, 10], average = 10
        expected_avg = (5 + 15 + 10) / 3
        self.assert_metric_value(summary, expected_avg)

    @pytest.mark.asyncio
    async def test_missing_input_token_count_raises_error(
        self, parsed_response_record_builder
    ):
        """Test that missing input token count raises an error."""
        record = parsed_response_record_builder.simple_record(
            request_start_time=100, input_token_count=None
        )

        await self.assert_record_processing_raises(
            record, match="Input Token Count is not available for the record."
        )
