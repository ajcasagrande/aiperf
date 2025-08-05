# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
import pytest

from aiperf.common.config.endpoint_config import EndpointConfig
from aiperf.common.constants import NANOS_PER_SECOND
from aiperf.common.enums.endpoints_enums import EndpointType
from aiperf.metrics.types.output_token_throughput_per_user import (
    OutputTokenThroughputPerUserMetric,
)

from .conftest import (
    BaseMetricTest,
    ParsedRecord,
    ParsedResponseRecordBuilder,
    Response,
)


class TestOutputTokenThroughputPerUserMetric(BaseMetricTest):
    """Test suite for OutputTokenThroughputPerUserMetric using type-safe dataclasses."""

    @property
    def endpoint_config(self) -> EndpointConfig:
        return EndpointConfig(
            type=EndpointType.OPENAI_COMPLETIONS,
            streaming=False,
            model_names=["test-model"],
        )

    @property
    def metric_tag(self) -> str:
        return OutputTokenThroughputPerUserMetric.tag

    @pytest.mark.asyncio
    async def test_single_record(
        self, parsed_response_record_builder: ParsedResponseRecordBuilder
    ):
        """Test output token throughput per user with a single record."""
        record = parsed_response_record_builder.create_record_from_config(
            ParsedRecord(
                request_start_time=100,
                worker_id="user_1",
                responses=[Response(perf_ns=200, token_count=10)],
                recv_start_perf_ns=110,
            )
        )

        summary = await self.process_single_record_and_get_summary(record)

        # Connection latency: 110 - 100 = 10 ns
        # Total latency: 200 - 100 = 100 ns
        # Processing time: 100 - 10 = 90 ns
        # Throughput per user: 10 tokens / 90 ns = 0.111... tokens/ns
        expected_throughput = 10.0 / 90.0 * NANOS_PER_SECOND
        self.assert_metric_value(summary, expected_throughput)

    @pytest.mark.asyncio
    async def test_multiple_records_same_user(
        self, parsed_response_record_builder: ParsedResponseRecordBuilder
    ):
        """Test output token throughput per user with multiple records from same user."""
        configs = [
            ParsedRecord(
                request_start_time=100,
                worker_id="user_1",
                responses=[Response(perf_ns=150, token_count=5)],
                recv_start_perf_ns=105,
            ),
            ParsedRecord(
                request_start_time=200,
                worker_id="user_1",
                responses=[Response(perf_ns=300, token_count=10)],
                recv_start_perf_ns=210,
            ),
        ]

        records = parsed_response_record_builder.create_records_from_configs(configs)
        summary = await self.process_records_and_get_summary(records)

        # Record 1: Connection: 5, Processing: (150-100) - 5 = 45, Tokens: 5
        # Record 2: Connection: 10, Processing: (300-200) - 10 = 90, Tokens: 10
        # Total: 15 tokens, 135 ns processing time
        # Per-user throughput: 15 / 135 = 0.111... tokens/ns
        expected_throughput = 15.0 / 135.0 * NANOS_PER_SECOND
        self.assert_metric_value(summary, expected_throughput)

    @pytest.mark.asyncio
    async def test_multiple_users(
        self, parsed_response_record_builder: ParsedResponseRecordBuilder
    ):
        """Test output token throughput per user with multiple users."""
        configs = [
            ParsedRecord(
                request_start_time=100,
                worker_id="user_1",
                responses=[Response(perf_ns=200, token_count=10)],
                recv_start_perf_ns=110,
            ),
            ParsedRecord(
                request_start_time=300,
                worker_id="user_2",
                responses=[Response(perf_ns=450, token_count=15)],
                recv_start_perf_ns=320,
            ),
        ]

        records = parsed_response_record_builder.create_records_from_configs(configs)
        summary = await self.process_records_and_get_summary(records)

        # User 1: 10 tokens, 90 ns processing = 0.111... tokens/ns
        # User 2: 15 tokens, 130 ns processing = 0.115... tokens/ns
        # Average: (0.111... + 0.115...) / 2
        user1_throughput = 10.0 / 90.0 * NANOS_PER_SECOND
        user2_throughput = 15.0 / 130.0 * NANOS_PER_SECOND
        expected_avg = (user1_throughput + user2_throughput) / 2
        self.assert_metric_value(summary, expected_avg)
