# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
import pytest

from aiperf.common.config.endpoint_config import EndpointConfig
from aiperf.common.enums.endpoints_enums import EndpointType
from aiperf.metrics.types.valid_request_count import ValidRequestCountMetric

from .conftest import (
    BaseMetricTest,
    ParsedRecord,
    ParsedResponseRecordBuilder,
    Response,
)


class TestRequestCountMetric(BaseMetricTest):
    """Test suite for ValidRequestCountMetric using type-safe dataclasses."""

    @property
    def endpoint_config(self) -> EndpointConfig:
        return EndpointConfig(
            type=EndpointType.OPENAI_EMBEDDINGS,
            streaming=False,
            model_names=["test-model"],
        )

    @property
    def metric_tag(self) -> str:
        return ValidRequestCountMetric.tag

    @pytest.mark.asyncio
    async def test_single_record(
        self, parsed_response_record_builder: ParsedResponseRecordBuilder
    ):
        """Test valid request count with a single record."""
        record = parsed_response_record_builder.simple_record(request_start_time=100)

        summary = await self.process_single_record_and_get_summary(record)
        self.assert_metric_value(summary, expected_value=1)

    @pytest.mark.asyncio
    async def test_multiple_records(
        self, parsed_response_record_builder: ParsedResponseRecordBuilder
    ):
        """Test valid request count with multiple records."""
        configs = [
            ParsedRecord(
                request_start_time=100, responses=[Response(perf_ns=150, token_count=1)]
            ),
            ParsedRecord(
                request_start_time=200, responses=[Response(perf_ns=250, token_count=1)]
            ),
            ParsedRecord(
                request_start_time=300, responses=[Response(perf_ns=350, token_count=1)]
            ),
        ]

        records = parsed_response_record_builder.create_records_from_configs(configs)
        summary = await self.process_records_and_get_summary(records)

        # 3 valid records
        self.assert_metric_value(summary, expected_value=3)

    @pytest.mark.asyncio
    async def test_invalid_record_raises_error(
        self, parsed_response_record_builder: ParsedResponseRecordBuilder
    ):
        """Test that invalid record raises an error."""
        record = parsed_response_record_builder.create_record_from_config(
            ParsedRecord(request_start_time=10, responses=[])
        )

        await self.assert_invalid_record_raises(record)
