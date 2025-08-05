# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
import pytest

from aiperf.common.aiperf_logger import AIPerfLogger
from aiperf.common.config.endpoint_config import EndpointConfig
from aiperf.common.config.user_config import UserConfig
from aiperf.common.enums.endpoints_enums import EndpointType
from aiperf.metrics.types.request_latency import RequestLatencyMetric
from aiperf.post_processors.metric_record_processor import MetricRecordProcessor
from aiperf.post_processors.metric_results_processor import MetricResultsProcessor


@pytest.fixture
def mock_user_config():
    return UserConfig(
        endpoint=EndpointConfig(
            type=EndpointType.OPENAI_EMBEDDINGS,
            streaming=False,
            model_names=["test-model"],
        ),
    )


_logger = AIPerfLogger(__name__)


@pytest.mark.asyncio
async def test_single_record(parsed_response_record_builder, mock_user_config):
    """Test request latency metric with a single record."""
    record = (
        parsed_response_record_builder.with_request_start_time(100)
        .add_response(perf_ns=150)
        .build()
    )

    record_processor = MetricRecordProcessor(user_config=mock_user_config)
    results_processor = MetricResultsProcessor(user_config=mock_user_config)

    record_metrics = await record_processor.process_record(record=record)
    await results_processor.process_result(record_metrics)

    summary = await results_processor.summarize()

    found = False
    for result in summary:
        if result.tag == RequestLatencyMetric.tag:
            _logger.trace(f"Result: {result}")
            assert result.avg == 50  # 150 - 100
            found = True
            break
    assert found, "RequestLatencyMetric not found in summary"


@pytest.mark.asyncio
async def test_add_multiple_records(parsed_response_record_builder, mock_user_config):
    """Test request latency metric with multiple records."""
    records = (
        parsed_response_record_builder.with_request_start_time(10)
        .add_response(perf_ns=15)
        .add_response(perf_ns=25)  # Final response at 25ns
        .new_record()
        .with_request_start_time(20)
        .add_response(perf_ns=25)
        .add_response(perf_ns=35)  # Final response at 35ns
        .new_record()
        .with_request_start_time(30)
        .add_response(perf_ns=40)
        .add_response(perf_ns=50)  # Final response at 50ns
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
        if result.tag == RequestLatencyMetric.tag:
            _logger.trace(f"Result: {result}")
            # Expected latencies: [15, 15, 20] (final_response - start_time)
            expected_avg = (15 + 15 + 20) / 3
            assert result.avg == expected_avg
            found = True
            break
    assert found, "RequestLatencyMetric not found in summary"


@pytest.mark.asyncio
async def test_response_timestamp_less_than_request_raises(
    parsed_response_record_builder, mock_user_config
):
    """Test that response timestamp less than request timestamp raises an error."""
    record = (
        parsed_response_record_builder.with_request_start_time(100)
        .add_response(perf_ns=90)  # Response before request
        .build()
    )

    record_processor = MetricRecordProcessor(user_config=mock_user_config)

    with pytest.raises(ValueError, match="Invalid Record"):
        await record_processor.process_record(record=record)
