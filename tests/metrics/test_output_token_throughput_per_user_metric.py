# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

import pytest

from aiperf.common.aiperf_logger import AIPerfLogger
from aiperf.common.config.endpoint_config import EndpointConfig
from aiperf.common.config.user_config import UserConfig
from aiperf.common.enums.endpoints_enums import EndpointType
from aiperf.common.models.record_models import ParsedResponseRecord
from aiperf.metrics.types.output_token_throughput_per_user import (
    OutputTokenThroughputPerUserMetric,
)
from aiperf.post_processors.metric_record_processor import MetricRecordProcessor
from aiperf.post_processors.metric_results_processor import MetricResultsProcessor


@pytest.fixture
def mock_user_config():
    return UserConfig(
        endpoint=EndpointConfig(
            type=EndpointType.OPENAI_COMPLETIONS,
            streaming=True,  # Use streaming to enable inter-token latency calculation
            model_names=["test-model"],
        ),
    )


_logger = AIPerfLogger(__name__)


@pytest.mark.asyncio
async def test_output_token_throughput_per_user_metric(
    parsed_response_record_builder, mock_user_config
):
    """Test output token throughput per user metric with multiple records."""
    records: list[ParsedResponseRecord] = (
        parsed_response_record_builder.with_request_start_time(0)
        .add_response(perf_ns=250_000_000, token_count=1)  # TTFT = 250ms
        .add_response(
            perf_ns=750_000_000, token_count=1
        )  # ITL = (750-250)/(2-1) = 500ms = 500_000_000ns
        .new_record()
        .with_request_start_time(0)
        .add_response(perf_ns=125_000_000, token_count=1)  # TTFT = 125ms
        .add_response(
            perf_ns=375_000_000, token_count=1
        )  # ITL = (375-125)/(2-1) = 250ms = 250_000_000ns
        .build_all()
    )

    # Set output token counts manually for proper OSL calculation
    records[0].output_token_count = 2  # 2 tokens total
    records[1].output_token_count = 2  # 2 tokens total

    record_processor = MetricRecordProcessor(user_config=mock_user_config)
    results_processor = MetricResultsProcessor(user_config=mock_user_config)

    for record in records:
        record_metrics = await record_processor.process_record(record=record)
        await results_processor.process_result(record_metrics)

    summary = await results_processor.summarize()

    found = False
    for result in summary:
        if result.tag == OutputTokenThroughputPerUserMetric.tag:
            _logger.trace(f"Result: {result}")

            # Expected calculations based on inter-token latency:
            # Record 1: ITL = 500_000_000ns → 1/ITL = 2.0 tokens/sec
            # Record 2: ITL = 250_000_000ns → 1/ITL = 4.0 tokens/sec
            # Average: (2.0 + 4.0) / 2 = 3.0 tokens/sec

            expected_avg = 3.0
            assert abs(result.avg - expected_avg) < 0.1
            found = True
            break
    assert found, "OutputTokenThroughputPerUserMetric not found in summary"
