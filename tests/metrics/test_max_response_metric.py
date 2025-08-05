# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
import pytest

from aiperf.common.aiperf_logger import AIPerfLogger
from aiperf.common.config.endpoint_config import EndpointConfig
from aiperf.common.config.user_config import UserConfig
from aiperf.common.enums.endpoints_enums import EndpointType
from aiperf.metrics.types.max_response_timestamp import MaxResponseTimestampMetric
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
        if result.tag == MaxResponseTimestampMetric.tag:
            _logger.trace(f"Result: {result}")
            assert result.avg == 150
            found = True
            break
    assert found, "MaxResponseTimestampMetric not found in summary"


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
        if result.tag == MaxResponseTimestampMetric.tag:
            _logger.trace(f"Result: {result}")
            assert result.avg == 40  # Max of [25, 15, 40]
            found = True
            break
    assert found, "MaxResponseTimestampMetric not found in summary"


@pytest.mark.asyncio
async def test_record_with_no_responses_raises(
    parsed_response_record_builder, mock_user_config
):
    record = parsed_response_record_builder.with_request_start_time(10).build()

    record_processor = MetricRecordProcessor(user_config=mock_user_config)

    with pytest.raises(ValueError, match="Invalid Record"):
        await record_processor.process_record(record=record)
