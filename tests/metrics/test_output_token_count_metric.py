# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
import pytest

from aiperf.common.config.endpoint_config import EndpointConfig
from aiperf.common.enums.endpoints_enums import EndpointType
from aiperf.metrics.types.output_token_count import OutputTokenCountMetric

from .conftest import BaseMetricTest, ParsedRecord, Response


class TestOutputTokenCountMetric(BaseMetricTest):
    """Test suite for OutputTokenCountMetric using type-safe dataclasses."""

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
    async def test_single_record(self, parsed_response_record_builder):
        """Test output token count with a single record."""
        record = parsed_response_record_builder.create_record_from_config(
            ParsedRecord(
                request_start_time=100,
                responses=[Response(perf_ns=150, token_count=42)],
            )
        )

        summary = await self.process_single_record_and_get_summary(record)
        self.assert_metric_value(summary, expected_value=42)

    @pytest.mark.asyncio
    async def test_multiple_records(self, parsed_response_record_builder):
        """Test output token count with multiple records."""
        configs = [
            ParsedRecord(
                request_start_time=100,
                responses=[Response(perf_ns=150, token_count=10)],
            ),
            ParsedRecord(
                request_start_time=200,
                responses=[Response(perf_ns=250, token_count=20)],
            ),
        ]

        records = parsed_response_record_builder.create_records_from_configs(configs)
        summary = await self.process_records_and_get_summary(records)

        # Total tokens: 10 + 20 = 30
        self.assert_metric_value(summary, expected_value=30)

    @pytest.mark.asyncio
    async def test_multiple_responses_per_record(self, parsed_response_record_builder):
        """Test output token count with multiple responses per record."""
        record = parsed_response_record_builder.create_record_from_config(
            ParsedRecord(
                request_start_time=100,
                responses=[
                    Response(perf_ns=120, token_count=5),
                    Response(perf_ns=140, token_count=10),
                    Response(perf_ns=160, token_count=3),
                ],
            )
        )

        summary = await self.process_single_record_and_get_summary(record)
        # Total tokens: 5 + 10 + 3 = 18
        self.assert_metric_value(summary, expected_value=18)
