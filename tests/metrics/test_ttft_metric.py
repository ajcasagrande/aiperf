# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

import pytest

from aiperf.common.aiperf_logger import AIPerfLogger
from aiperf.common.config.endpoint_config import EndpointConfig
from aiperf.common.config.user_config import UserConfig
from aiperf.common.enums.endpoints_enums import EndpointType
from aiperf.metrics.types.time_to_first_token import TTFTMetric
from aiperf.post_processors.metric_record_processor import MetricRecordProcessor
from aiperf.post_processors.metric_results_processor import MetricResultsProcessor


@pytest.fixture
def mock_user_config():
    return UserConfig(
        endpoint=EndpointConfig(
            type=EndpointType.OPENAI_COMPLETIONS,
            streaming=True,  # TTFT is for streaming tokens only
            model_names=["test-model"],
        ),
    )


_logger = AIPerfLogger(__name__)


@pytest.mark.asyncio
async def test_single_record(parsed_response_record_builder, mock_user_config):
    """Test TTFT metric with a single record."""
    record = (
        parsed_response_record_builder.with_request_start_time(100)
        .add_response(perf_ns=150, token_count=1)
        .build()
    )

    record_processor = MetricRecordProcessor(user_config=mock_user_config)
    results_processor = MetricResultsProcessor(user_config=mock_user_config)

    record_metrics = await record_processor.process_record(record=record)
    await results_processor.process_result(record_metrics)

    summary = await results_processor.summarize()

    found = False
    for result in summary:
        if result.tag == TTFTMetric.tag:
            _logger.trace(f"Result: {result}")
            assert result.avg == 50  # 150 - 100
            found = True
            break
    assert found, "TTFTMetric not found in summary"


@pytest.mark.asyncio
async def test_add_multiple_records(parsed_response_record_builder, mock_user_config):
    """Test TTFT metric with multiple records."""
    records = (
        parsed_response_record_builder.with_request_start_time(10)
        .add_response(perf_ns=15, token_count=1)
        .new_record()
        .with_request_start_time(20)
        .add_response(perf_ns=25, token_count=1)
        .new_record()
        .with_request_start_time(30)
        .add_response(perf_ns=40, token_count=1)
        .build_all()
    )

    record_processor = MetricRecordProcessor(user_config=mock_user_config)
    results_processor = MetricResultsProcessor(user_config=mock_user_config)

    for record in records:
        record_metrics = await record_processor.process_record(record=record)
        await results_processor.process_result(record_metrics)

    summary = await results_processor.summarize()

    found = False
    for result in summary:
        if result.tag == TTFTMetric.tag:
            _logger.trace(f"Result: {result}")
            # Expected TTFTs: [5, 5, 10] nanoseconds
            expected_avg = (5 + 5 + 10) / 3
            assert result.avg == expected_avg
            found = True
            break
    assert found, "TTFTMetric not found in summary"


@pytest.mark.asyncio
async def test_convert_metrics(parsed_response_record_builder, mock_user_config):
    """Test TTFT metric unit conversion."""
    records = (
        parsed_response_record_builder.with_request_start_time(10_000_000)  # 10ms in ns
        .add_response(perf_ns=15_000_000, token_count=1)  # 15ms in ns
        .new_record()
        .with_request_start_time(20_000_000)  # 20ms in ns
        .add_response(perf_ns=25_000_000, token_count=1)  # 25ms in ns
        .new_record()
        .with_request_start_time(30_000_000)  # 30ms in ns
        .add_response(perf_ns=40_000_000, token_count=1)  # 40ms in ns
        .build_all()
    )

    record_processor = MetricRecordProcessor(user_config=mock_user_config)
    results_processor = MetricResultsProcessor(user_config=mock_user_config)

    for record in records:
        record_metrics = await record_processor.process_record(record=record)
        await results_processor.process_result(record_metrics)

    summary = await results_processor.summarize()

    found = False
    for result in summary:
        if result.tag == TTFTMetric.tag:
            _logger.trace(f"Result: {result}")
            # When displayed in milliseconds, the values should be [5, 5, 10] milliseconds
            # Note: The summary already converts to display units automatically
            expected_avg_ms = (5 + 5 + 10) / 3  # milliseconds
            # The result should be in display units (milliseconds)
            assert abs(result.avg - expected_avg_ms) < 0.01
            found = True
            break
    assert found, "TTFTMetric not found in summary"
