# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

import pytest

from aiperf.common.aiperf_logger import AIPerfLogger
from aiperf.common.config.endpoint_config import EndpointConfig
from aiperf.common.config.user_config import UserConfig
from aiperf.common.enums.endpoints_enums import EndpointType
from aiperf.common.models.record_models import ParsedResponseRecord
from aiperf.metrics.types.inter_token_latency import InterTokenLatencyMetric
from aiperf.post_processors.metric_record_processor import MetricRecordProcessor
from aiperf.post_processors.metric_results_processor import MetricResultsProcessor


@pytest.fixture
def mock_user_config():
    return UserConfig(
        endpoint=EndpointConfig(
            type=EndpointType.OPENAI_COMPLETIONS,  # Use completions to get the required metrics
            streaming=True,
            model_names=["test-model"],
        ),
    )


_logger = AIPerfLogger(__name__)


@pytest.mark.asyncio
async def test_inter_token_latency_metric_computes_correctly(
    parsed_response_record_builder, mock_user_config
):
    """Test that inter-token latency is calculated correctly using multiple records."""
    records: list[ParsedResponseRecord] = (
        parsed_response_record_builder.with_request_start_time(0)
        .add_response(perf_ns=40, token_count=1)  # TTFT = 40ns
        .add_response(
            perf_ns=100, token_count=5
        )  # Total latency = 100ns, OSL = 6 tokens
        .new_record()
        .with_request_start_time(0)
        .add_response(perf_ns=60, token_count=1)  # TTFT = 60ns
        .add_response(
            perf_ns=200, token_count=2
        )  # Total latency = 200ns, OSL = 3 tokens
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
        if result.tag == InterTokenLatencyMetric.tag:
            _logger.trace(f"Result: {result}")

            # Expected calculations:
            # Record 1: (100 - 40) / (6 - 1) = 60 / 5 = 12
            # Record 2: (200 - 60) / (3 - 1) = 140 / 2 = 70
            # Average: (12 + 70) / 2 = 41

            expected_values = [12, 70]
            expected_avg = sum(expected_values) / len(expected_values)

            assert abs(result.avg - expected_avg) < 0.01
            found = True
            break
    assert found, "InterTokenLatencyMetric not found in summary"
