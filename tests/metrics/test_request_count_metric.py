# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

import pytest

from aiperf.common.aiperf_logger import AIPerfLogger
from aiperf.common.config.endpoint_config import EndpointConfig
from aiperf.common.config.user_config import UserConfig
from aiperf.common.enums.endpoints_enums import EndpointType
from aiperf.metrics.types.valid_request_count import ValidRequestCountMetric
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
async def test_request_count_with_multiple_valid_records(
    parsed_response_record_builder, mock_user_config
):
    """Test valid request count metric with multiple records."""
    records = (
        parsed_response_record_builder.with_request_start_time(0)
        .add_response(perf_ns=5)
        .new_record()
        .with_request_start_time(10)
        .add_response(perf_ns=15)
        .new_record()
        .with_request_start_time(20)
        .add_response(perf_ns=25)
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
        if result.tag == ValidRequestCountMetric.tag:
            _logger.trace(f"Result: {result}")
            assert result.avg == 3  # Count of valid requests
            found = True
            break
    assert found, "ValidRequestCountMetric not found in summary"


@pytest.mark.asyncio
async def test_request_count_invalid_record_raises(mock_user_config):
    """Test that invalid record raises an error."""
    record_processor = MetricRecordProcessor(user_config=mock_user_config)

    with pytest.raises((ValueError, AttributeError)):
        await record_processor.process_record(record=None)
