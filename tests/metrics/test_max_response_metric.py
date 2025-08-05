# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
import pytest

from aiperf.common.config.endpoint_config import EndpointConfig
from aiperf.common.enums.endpoints_enums import EndpointType
from aiperf.metrics.types.max_response_timestamp import MaxResponseTimestampMetric

from .conftest import BaseMetricTest, ParsedRecord, Response


class TestMaxResponseMetric(BaseMetricTest):
    """Test suite for MaxResponseTimestampMetric using type-safe dataclasses."""

    @property
    def endpoint_config(self) -> EndpointConfig:
        return EndpointConfig(
            type=EndpointType.OPENAI_EMBEDDINGS,
            streaming=False,
            model_names=["test-model"],
        )

    @property
    def metric_tag(self) -> str:
        return MaxResponseTimestampMetric.tag

    @pytest.mark.asyncio
    async def test_single_record(self, parsed_response_record_builder):
        """Test max response timestamp with a single record using simple_record."""
        record = parsed_response_record_builder.simple_record(
            request_start_time=100, response_perf_ns=150
        )

        summary = await self.process_single_record_and_get_summary(record)
        self.assert_metric_value(summary, expected_value=150)

    @pytest.mark.asyncio
    async def test_single_record_with_response_config(
        self, parsed_response_record_builder
    ):
        """Test with detailed Response configuration."""
        response = Response(
            perf_ns=150,
            token_count=1,
            raw_text=["hello", "world"],
            parsed_text=["hello", "world"],
            metadata={"test": True},
        )

        record = parsed_response_record_builder.create_record_from_config(
            ParsedRecord(request_start_time=100, responses=[response])
        )

        summary = await self.process_single_record_and_get_summary(record)
        self.assert_metric_value(summary, expected_value=150)

    @pytest.mark.asyncio
    async def test_multiple_records(self, parsed_response_record_builder):
        """Test max response timestamp with multiple records."""
        configs = [
            ParsedRecord(
                request_start_time=20,
                worker_id="worker_1",
                responses=[Response(perf_ns=25, token_count=2)],
            ),
            ParsedRecord(
                request_start_time=10,
                worker_id="worker_2",
                responses=[Response(perf_ns=15, token_count=1)],
            ),
            ParsedRecord(
                request_start_time=30,
                worker_id="worker_3",
                responses=[Response(perf_ns=40, token_count=3)],
            ),
        ]

        records = parsed_response_record_builder.create_records_from_configs(configs)
        summary = await self.process_records_and_get_summary(records)
        self.assert_metric_value(summary, expected_value=40)  # Max of [25, 15, 40]

    @pytest.mark.asyncio
    async def test_multiple_responses_per_record(self, parsed_response_record_builder):
        """Test with multiple responses per record."""
        record = parsed_response_record_builder.create_record_from_config(
            ParsedRecord(
                request_start_time=100,
                responses=[
                    Response(perf_ns=120, token_count=1),
                    Response(perf_ns=140, token_count=2),
                    Response(perf_ns=160, token_count=1, raw_text=["final"]),
                ],
            )
        )

        summary = await self.process_single_record_and_get_summary(record)
        self.assert_metric_value(summary, expected_value=160)  # Max response time

    @pytest.mark.asyncio
    async def test_complex_scenario_full_config(self, parsed_response_record_builder):
        """Test complex scenario with all configuration options."""
        config = ParsedRecord(
            request_start_time=1000,
            worker_id="specialized_worker",
            input_token_count=10,
            conversation_id="test-conversation-123",
            turn_index=5,
            model_name="gpt-4",
            responses=[
                Response(
                    perf_ns=1050,
                    token_count=3,
                    raw_text=["Hello", "there"],
                    parsed_text=["Hello", "there"],
                    metadata={"confidence": 0.95},
                ),
                Response(
                    perf_ns=1100,
                    token_count=2,
                    raw_text=["World"],
                    parsed_text=["World"],
                    metadata={"confidence": 0.98},
                ),
            ],
            request_kwargs={"recv_start_perf_ns": 1010, "custom_field": "test"},
        )

        record = parsed_response_record_builder.create_record_from_config(config)
        summary = await self.process_single_record_and_get_summary(record)
        self.assert_metric_value(summary, expected_value=1100)  # Max response time

    @pytest.mark.asyncio
    async def test_no_responses_raises_error(self, parsed_response_record_builder):
        """Test that record with no responses raises an error."""
        record = parsed_response_record_builder.create_record_from_config(
            ParsedRecord(
                request_start_time=10,
                responses=[],  # Empty responses list
            )
        )

        await self.assert_record_processing_raises(record, match="Invalid Record")

    @pytest.mark.asyncio
    async def test_missing_input_tokens(self, parsed_response_record_builder):
        """Test with missing input tokens."""
        record = parsed_response_record_builder.simple_record(
            request_start_time=100,
            input_token_count=None,  # Explicit None for testing
        )

        summary = await self.process_single_record_and_get_summary(record)
        self.assert_metric_value(summary, expected_value=150)
