# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
import pytest

from aiperf.common.aiperf_logger import AIPerfLogger
from aiperf.common.config.endpoint_config import EndpointConfig
from aiperf.common.config.user_config import UserConfig
from aiperf.common.enums.endpoints_enums import EndpointType
from aiperf.metrics.types.min_request_timestamp import MinRequestTimestampMetric
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
        if result.tag == MinRequestTimestampMetric.tag:
            _logger.trace(f"Result: {result}")
            assert result.avg == 100
            found = True
            break
    assert found, "MinRequestTimestampMetric not found in summary"


@pytest.mark.asyncio
async def test_add_multiple_records(parsed_response_record_builder, mock_user_config):
    records = (
        parsed_response_record_builder.with_request_start_time(20)
        .add_response(perf_ns=25)
        .new_record()
        .with_request_start_time(10)
        .add_response(perf_ns=15)
        .new_record()
        .with_request_start_time(30)
        .add_response(perf_ns=40)
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
        if result.tag == MinRequestTimestampMetric.tag:
            _logger.trace(f"Result: {result}")
            assert result.avg == 10  # Min of [20, 10, 30]
            found = True
            break
    assert found, "MinRequestTimestampMetric not found in summary"


@pytest.mark.asyncio
async def test_record_with_no_request_raises(mock_user_config):
    record_processor = MetricRecordProcessor(user_config=mock_user_config)

    with pytest.raises((ValueError, AttributeError)):
        await record_processor.process_record(record=None)
