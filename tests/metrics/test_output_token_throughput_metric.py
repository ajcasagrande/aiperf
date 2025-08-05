# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
import pytest

from aiperf.common.config.endpoint_config import EndpointConfig
from aiperf.common.enums.endpoints_enums import EndpointType
from aiperf.metrics.types.output_token_throughput import OutputTokenThroughputMetric

from .conftest import (
    BaseMetricTest,
    ParsedRecord,
    ParsedResponseRecordBuilder,
    Response,
)


class TestOutputTokenThroughputMetric(BaseMetricTest):
    """Test suite for OutputTokenThroughputMetric using type-safe dataclasses."""

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
    async def test_single_record(
        self, parsed_response_record_builder: ParsedResponseRecordBuilder
    ):
        """Test output token throughput with a single record."""
        record = parsed_response_record_builder.create_record_from_config(
            ParsedRecord(
                request_start_time=100,
                responses=[Response(perf_ns=200, token_count=10)],
            )
        )

        summary = await self.process_single_record_and_get_summary(record)

        # Throughput = 10 tokens / 100 ns = 0.1 tokens/ns
        # For derived metrics: 10 tokens total in 100 ns duration = 0.1 tokens/ns
        expected_throughput = 10.0 / 100.0
        self.assert_metric_value(summary, expected_throughput)

    @pytest.mark.asyncio
    async def test_multiple_records(
        self, parsed_response_record_builder: ParsedResponseRecordBuilder
    ):
        """Test output token throughput with multiple records."""
        configs = [
            ParsedRecord(
                request_start_time=100,
                responses=[Response(perf_ns=150, token_count=5)],
            ),
            ParsedRecord(
                request_start_time=200,
                responses=[Response(perf_ns=300, token_count=10)],
            ),
        ]

        records = parsed_response_record_builder.create_records_from_configs(configs)
        summary = await self.process_records_and_get_summary(records)

        # Total tokens: 5 + 10 = 15
        # Total duration: (150-100) + (300-200) = 50 + 100 = 150
        # Throughput = 15 / 150 = 0.1 tokens/ns
        expected_throughput = 15.0 / 150.0
        self.assert_metric_value(summary, expected_throughput)

    @pytest.mark.asyncio
    async def test_multiple_responses_per_record(
        self, parsed_response_record_builder: ParsedResponseRecordBuilder
    ):
        """Test output token throughput with multiple responses per record."""
        record = parsed_response_record_builder.create_record_from_config(
            ParsedRecord(
                request_start_time=100,
                responses=[
                    Response(perf_ns=120, token_count=2),
                    Response(perf_ns=140, token_count=3),
                    Response(perf_ns=160, token_count=5),
                ],
            )
        )

        summary = await self.process_single_record_and_get_summary(record)

        # Total tokens: 2 + 3 + 5 = 10
        # Duration: 160 - 100 = 60 ns
        # Throughput = 10 / 60 = 0.1667 tokens/ns
        expected_throughput = 10.0 / 60.0
        self.assert_metric_value(summary, expected_throughput)
