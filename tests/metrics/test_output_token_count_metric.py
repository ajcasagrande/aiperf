# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

import pytest

from aiperf.common.aiperf_logger import AIPerfLogger
from aiperf.common.config.endpoint_config import EndpointConfig
from aiperf.common.config.user_config import UserConfig
from aiperf.common.enums.endpoints_enums import EndpointType
from aiperf.metrics.types.output_token_count import OutputTokenCountMetric
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
async def test_output_token_count_metric(
    parsed_response_record_builder, mock_user_config
):
    """Test output token count metric."""
    record = (
        parsed_response_record_builder.with_request_start_time(0)
        .add_response(
            perf_ns=100, token_count=5, raw_text=["hello"], parsed_text=["hello"]
        )
        .build()
    )

    # Set the output token count manually
    record.output_token_count = 5

    record_processor = MetricRecordProcessor(user_config=mock_user_config)
    results_processor = MetricResultsProcessor(user_config=mock_user_config)

    record_metrics = await record_processor.process_record(record=record)
    await results_processor.process_result(record_metrics)

    summary = await results_processor.summarize()

    found = False
    for result in summary:
        if result.tag == OutputTokenCountMetric.tag:
            _logger.trace(f"Result: {result}")
            assert result.avg == 5
            found = True
            break
    assert found, "OutputTokenCountMetric not found in summary"
