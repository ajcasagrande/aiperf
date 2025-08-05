# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
import pytest

from aiperf.common.config.endpoint_config import EndpointConfig
from aiperf.common.enums.endpoints_enums import EndpointType
from aiperf.metrics.types.output_sequence_length import OutputSequenceLengthMetric

from .conftest import (
    BaseMetricTest,
    ParsedRecord,
    ParsedResponseRecordBuilder,
    Response,
)


class TestOutputSequenceLengthMetric(BaseMetricTest):
    """Test suite for OutputSequenceLengthMetric using type-safe dataclasses."""

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
    async def test_single_record(
        self, parsed_response_record_builder: ParsedResponseRecordBuilder
    ):
        """Test output sequence length with a single record."""
        record = parsed_response_record_builder.create_record_from_config(
            ParsedRecord(
                request_start_time=100,
                responses=[Response(perf_ns=150, token_count=5)],
            )
        )

        summary = await self.process_single_record_and_get_summary(record)
        self.assert_metric_value(summary, expected_value=5)

    @pytest.mark.asyncio
    async def test_multiple_records(
        self, parsed_response_record_builder: ParsedResponseRecordBuilder
    ):
        """Test output sequence length with multiple records."""
        configs = [
            ParsedRecord(
                request_start_time=100, responses=[Response(perf_ns=150, token_count=3)]
            ),
            ParsedRecord(
                request_start_time=200, responses=[Response(perf_ns=250, token_count=7)]
            ),
            ParsedRecord(
                request_start_time=300, responses=[Response(perf_ns=350, token_count=5)]
            ),
        ]

        records = parsed_response_record_builder.create_records_from_configs(configs)
        summary = await self.process_records_and_get_summary(records)

        # Expected values: [3, 7, 5], average = 5
        expected_avg = (3 + 7 + 5) / 3
        self.assert_metric_value(summary, expected_avg)

    @pytest.mark.asyncio
    async def test_multiple_responses_per_record(
        self, parsed_response_record_builder: ParsedResponseRecordBuilder
    ):
        """Test output sequence length with multiple responses per record."""
        record = parsed_response_record_builder.create_record_from_config(
            ParsedRecord(
                request_start_time=100,
                responses=[
                    Response(perf_ns=120, token_count=2),
                    Response(perf_ns=140, token_count=3),
                    Response(perf_ns=160, token_count=1),
                ],
            )
        )

        summary = await self.process_single_record_and_get_summary(record)
        # Total tokens: 2 + 3 + 1 = 6
        self.assert_metric_value(summary, expected_value=6)

    @pytest.mark.asyncio
    async def test_missing_output_token_count_raises_error(
        self, parsed_response_record_builder
    ):
        """Test that missing output token count raises an error."""
        record = parsed_response_record_builder.create_record_from_config(
            ParsedRecord(request_start_time=100, responses=[])
        )

        await self.assert_record_processing_raises(
            record, match="Output token count is missing in the record."
        )
