# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

import pytest

from aiperf.common.aiperf_logger import AIPerfLogger
from aiperf.common.config.endpoint_config import EndpointConfig
from aiperf.common.config.user_config import UserConfig
from aiperf.common.enums.endpoints_enums import EndpointType
from aiperf.common.models.record_models import ParsedResponseRecord
from aiperf.metrics.types.output_token_throughput import OutputTokenThroughputMetric
from aiperf.post_processors.metric_record_processor import MetricRecordProcessor
from aiperf.post_processors.metric_results_processor import MetricResultsProcessor


@pytest.fixture
def mock_user_config():
    return UserConfig(
        endpoint=EndpointConfig(
            type=EndpointType.OPENAI_COMPLETIONS,
            streaming=False,
            model_names=["test-model"],
        ),
    )


_logger = AIPerfLogger(__name__)


@pytest.mark.asyncio
async def test_output_token_throughput_metric(
    parsed_response_record_builder, mock_user_config
):
    """Test output token throughput metric with multiple records."""
    records: list[ParsedResponseRecord] = (
        parsed_response_record_builder.with_request_start_time(0)
        .add_response(perf_ns=1_000_000_000)  # 1 second
        .new_record()
        .with_request_start_time(1_000_000_000)  # Start 1 second later
        .add_response(perf_ns=3_000_000_000)  # Response at 3 seconds
        .new_record()
        .with_request_start_time(2_000_000_000)  # Start 2 seconds later
        .add_response(
            perf_ns=5_000_000_000
        )  # Response at 5 seconds (total duration = 5 seconds)
        .build_all()
    )

    # Set output token counts manually - total = 60 tokens
    records[0].output_token_count = 10
    records[1].output_token_count = 20
    records[2].output_token_count = 30

    record_processor = MetricRecordProcessor(user_config=mock_user_config)
    results_processor = MetricResultsProcessor(user_config=mock_user_config)

    for record in records:
        record_metrics = await record_processor.process_record(record=record)
        await results_processor.process_result(record_metrics)

    summary = await results_processor.summarize()

    found = False
    for result in summary:
        if result.tag == OutputTokenThroughputMetric.tag:
            _logger.trace(f"Result: {result}")
            # Expected: 60 tokens / 5 seconds = 12 tokens/sec
            expected = 60 / 5
            assert abs(result.avg - expected) < 0.01
            found = True
            break
    assert found, "OutputTokenThroughputMetric not found in summary"
