# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
import pytest

from aiperf.common.config.endpoint_config import EndpointConfig
from aiperf.common.enums.endpoints_enums import EndpointType
from aiperf.metrics.types.time_to_second_token import TTSTMetric

from .conftest import (
    BaseMetricTest,
    ParsedRecord,
    ParsedResponseRecordBuilder,
    Response,
)


class TestTTSTMetric(BaseMetricTest):
    """Test suite for TTSTMetric using type-safe dataclasses."""

    @property
    def endpoint_config(self) -> EndpointConfig:
        return EndpointConfig(
            type=EndpointType.OPENAI_COMPLETIONS,
            streaming=True,
            model_names=["test-model"],
        )

    @property
    def metric_tag(self) -> str:
        return TTSTMetric.tag

    @pytest.mark.asyncio
    async def test_single_record(
        self, parsed_response_record_builder: ParsedResponseRecordBuilder
    ):
        """Test TTST metric with a single record with multiple responses."""
        record = parsed_response_record_builder.create_record_from_config(
            ParsedRecord(
                request_start_time=100,
                responses=[
                    Response(perf_ns=120, token_count=1),  # First token
                    Response(perf_ns=140, token_count=1),  # Second token
                ],
            )
        )

        summary = await self.process_single_record_and_get_summary(record)
        # TTST = second token time - request start = 140 - 100 = 40
        self.assert_metric_value(summary, expected_value=40)

    @pytest.mark.asyncio
    async def test_multiple_records(
        self, parsed_response_record_builder: ParsedResponseRecordBuilder
    ):
        """Test TTST metric with multiple records."""
        configs = [
            ParsedRecord(
                request_start_time=100,
                responses=[
                    Response(perf_ns=110, token_count=1),  # First token
                    Response(perf_ns=130, token_count=1),  # Second token
                ],
            ),
            ParsedRecord(
                request_start_time=200,
                responses=[
                    Response(perf_ns=220, token_count=1),  # First token
                    Response(perf_ns=250, token_count=1),  # Second token
                ],
            ),
        ]

        records = parsed_response_record_builder.create_records_from_configs(configs)
        summary = await self.process_records_and_get_summary(records)

        # Record 1 TTST: 130 - 100 = 30
        # Record 2 TTST: 250 - 200 = 50
        # Average: (30 + 50) / 2 = 40
        expected_avg = 40.0
        self.assert_metric_value(summary, expected_avg)

    @pytest.mark.asyncio
    async def test_invalid_record_raises_error(
        self, parsed_response_record_builder: ParsedResponseRecordBuilder
    ):
        """Test that record with insufficient responses raises an error."""
        record = parsed_response_record_builder.simple_record(
            request_start_time=100, response_perf_ns=120, token_count=1
        )

        # Only one response, need at least 2 for TTST
        await self.assert_record_processing_raises(record)
