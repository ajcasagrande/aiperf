# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
import pytest

from aiperf.common.config.endpoint_config import EndpointConfig
from aiperf.common.enums.endpoints_enums import EndpointType
from aiperf.metrics.types.inter_token_latency import InterTokenLatencyMetric

from .conftest import (
    BaseMetricTest,
    ParsedRecord,
    ParsedResponseRecordBuilder,
    Response,
)


class TestInterTokenLatencyMetric(BaseMetricTest):
    """Test suite for InterTokenLatencyMetric using type-safe dataclasses."""

    @property
    def endpoint_config(self) -> EndpointConfig:
        return EndpointConfig(
            type=EndpointType.OPENAI_COMPLETIONS,
            streaming=True,
            model_names=["test-model"],
        )

    @property
    def metric_tag(self) -> str:
        return InterTokenLatencyMetric.tag

    @pytest.mark.asyncio
    async def test_single_record(
        self, parsed_response_record_builder: ParsedResponseRecordBuilder
    ):
        """Test inter-token latency with a single record with multiple responses."""
        record = parsed_response_record_builder.create_record_from_config(
            ParsedRecord(
                request_start_time=100,
                responses=[
                    Response(perf_ns=120, token_count=1),
                    Response(perf_ns=140, token_count=1),
                    Response(perf_ns=160, token_count=1),
                ],
            )
        )

        summary = await self.process_single_record_and_get_summary(record)
        # ITL between responses: [140-120, 160-140] = [20, 20]
        expected_avg = 20.0
        self.assert_metric_value(summary, expected_avg)

    @pytest.mark.asyncio
    async def test_multiple_records(
        self, parsed_response_record_builder: ParsedResponseRecordBuilder
    ):
        """Test inter-token latency with multiple records."""
        configs = [
            ParsedRecord(
                request_start_time=100,
                responses=[
                    Response(perf_ns=110, token_count=1),
                    Response(perf_ns=130, token_count=1),
                ],
            ),
            ParsedRecord(
                request_start_time=200,
                responses=[
                    Response(perf_ns=210, token_count=1),
                    Response(perf_ns=240, token_count=1),
                ],
            ),
        ]

        records = parsed_response_record_builder.create_records_from_configs(configs)
        summary = await self.process_records_and_get_summary(records)

        # Record 1 ITL: [130-110] = [20]
        # Record 2 ITL: [240-210] = [30]
        # Average: (20 + 30) / 2 = 25
        expected_avg = 25.0
        self.assert_metric_value(summary, expected_avg)
