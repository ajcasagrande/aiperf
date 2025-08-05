# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

import pytest

from aiperf.common.aiperf_logger import AIPerfLogger
from aiperf.common.config.endpoint_config import EndpointConfig
from aiperf.common.config.user_config import UserConfig
from aiperf.common.enums.endpoints_enums import EndpointType
from aiperf.common.models.record_models import ParsedResponseRecord
from aiperf.metrics.types.request_throughput import RequestThroughputMetric
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
async def test_request_throughput(parsed_response_record_builder, mock_user_config):
    """Test request throughput metric with multiple records."""
    records: list[ParsedResponseRecord] = (
        parsed_response_record_builder.with_request_start_time(0)
        .add_response(perf_ns=1_000_000_000)  # 1 second
        .new_record()
        .with_request_start_time(1_000_000_000)  # Start at 1 second
        .add_response(perf_ns=2_000_000_000)  # Response at 2 seconds
        .new_record()
        .with_request_start_time(2_000_000_000)  # Start at 2 seconds
        .add_response(
            perf_ns=3_000_000_000
        )  # Response at 3 seconds (total duration = 3 seconds)
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
        if result.tag == RequestThroughputMetric.tag:
            _logger.trace(f"Result: {result}")
            # Expected: 3 requests / 3 seconds = 1.0 req/sec
            expected = 1.0
            assert abs(result.avg - expected) < 0.01
            found = True
            break
    assert found, "RequestThroughputMetric not found in summary"
