# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
import pytest

from aiperf.common.aiperf_logger import AIPerfLogger
from aiperf.common.config.endpoint_config import EndpointConfig
from aiperf.common.config.user_config import UserConfig
from aiperf.common.enums.endpoints_enums import EndpointType
from aiperf.metrics.types import TTSTMetric
from aiperf.post_processors.metric_record_processor import MetricRecordProcessor
from aiperf.post_processors.metric_results_processor import MetricResultsProcessor


@pytest.fixture
def mock_user_config():
    return UserConfig(
        endpoint=EndpointConfig(
            type=EndpointType.OPENAI_COMPLETIONS,
            streaming=True,  # TTST requires streaming responses
            model_names=["test-model"],
        ),
    )


_logger = AIPerfLogger(__name__)


@pytest.mark.asyncio
async def test_ttst_metric_single_record(
    parsed_response_record_builder, mock_user_config
):
    """Test TTST metric with a single record having two responses."""
    record = (
        parsed_response_record_builder.with_request_start_time(100)
        .add_response(perf_ns=150, token_count=1)
        .add_response(perf_ns=180, token_count=1)
        .build()
    )

    record_processor = MetricRecordProcessor(user_config=mock_user_config)
    results_processor = MetricResultsProcessor(user_config=mock_user_config)

    record_metrics = await record_processor.process_record(record=record)
    await results_processor.process_result(record_metrics)

    summary = await results_processor.summarize()

    found = False
    for result in summary:
        if result.tag == TTSTMetric.tag:
            _logger.trace(f"Result: {result}")
            assert result.avg == 30  # 180 - 150
            found = True
            break
    assert found, "TTSTMetric not found in summary"


@pytest.mark.asyncio
async def test_ttst_metric_add_multiple_records(
    parsed_response_record_builder, mock_user_config
):
    """Test TTST metric with multiple records."""
    records = (
        parsed_response_record_builder.with_request_start_time(10)
        .add_response(perf_ns=15, token_count=1)
        .add_response(perf_ns=20, token_count=1)
        .new_record()
        .with_request_start_time(20)
        .add_response(perf_ns=25, token_count=1)
        .add_response(perf_ns=35, token_count=1)
        .new_record()
        .with_request_start_time(30)
        .add_response(perf_ns=40, token_count=1)
        .add_response(perf_ns=50, token_count=1)
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
        if result.tag == TTSTMetric.tag:
            _logger.trace(f"Result: {result}")
            # Expected TTSTs: [5, 10, 10] nanoseconds
            expected_avg = (5 + 10 + 10) / 3
            assert result.avg == expected_avg
            found = True
            break
    assert found, "TTSTMetric not found in summary"


@pytest.mark.asyncio
async def test_ttst_metric_with_one_response_raises(
    parsed_response_record_builder, mock_user_config
):
    """Test that TTST metric raises error with only one response."""
    record = (
        parsed_response_record_builder.with_request_start_time(10)
        .add_response(perf_ns=15, token_count=1)
        .build()
    )

    record_processor = MetricRecordProcessor(user_config=mock_user_config)

    with pytest.raises(ValueError, match="at least two responses"):
        await record_processor.process_record(record=record)


@pytest.mark.asyncio
async def test_ttst_metric_response_timestamp_order_raises(
    parsed_response_record_builder, mock_user_config
):
    """Test that TTST metric raises error when second response timestamp is before first."""
    record = (
        parsed_response_record_builder.with_request_start_time(100)
        .add_response(perf_ns=150, token_count=1)
        .add_response(perf_ns=140, token_count=1)  # Second response before first
        .build()
    )

    record_processor = MetricRecordProcessor(user_config=mock_user_config)

    with pytest.raises(
        ValueError,
        match="Second response timestamp must be greater than or equal to the first response timestamp.",
    ):
        await record_processor.process_record(record=record)
