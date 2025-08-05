# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
import pytest

from aiperf.common.aiperf_logger import AIPerfLogger
from aiperf.common.config.endpoint_config import EndpointConfig
from aiperf.common.config.user_config import UserConfig
from aiperf.common.enums.endpoints_enums import EndpointType
from aiperf.common.models.record_models import ParsedResponseRecord
from aiperf.metrics.types.output_sequence_length import OutputSequenceLengthMetric
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
async def test_osl_metric_with_multiple_records(
    parsed_response_record_builder, mock_user_config
):
    """Test output sequence length metric with multiple records."""
    records: list[ParsedResponseRecord] = (
        parsed_response_record_builder.with_request_start_time(10)
        .add_response(perf_ns=15, token_count=3)
        .add_response(perf_ns=20, token_count=5)
        .new_record()
        .with_request_start_time(20)
        .add_response(perf_ns=25, token_count=7)
        .build_all()
    )

    # Set output token counts manually since the builder doesn't set them automatically
    records[0].output_token_count = 8  # 3 + 5
    records[1].output_token_count = 7

    record_processor = MetricRecordProcessor(user_config=mock_user_config)
    results_processor = MetricResultsProcessor(user_config=mock_user_config)

    for record in records:
        record_metrics = await record_processor.process_record(record=record)
        await results_processor.process_result(record_metrics)

    summary = await results_processor.summarize()

    found = False
    for result in summary:
        if result.tag == OutputSequenceLengthMetric.tag:
            _logger.trace(f"Result: {result}")
            expected_avg = (8 + 7) / 2  # Average of [8, 7]
            assert result.avg == expected_avg
            found = True
            break
    assert found, "OutputSequenceLengthMetric not found in summary"


@pytest.mark.asyncio
async def test_osl_metric_invalid_record(mock_user_config):
    """Test that invalid record raises an error."""
    record_processor = MetricRecordProcessor(user_config=mock_user_config)

    with pytest.raises((ValueError, AttributeError)):
        await record_processor.process_record(record=None)


@pytest.mark.asyncio
async def test_osl_metric_missing_output_token_count(
    parsed_response_record_builder, mock_user_config
):
    """Test that missing output token count raises an error."""
    record = (
        parsed_response_record_builder.with_request_start_time(10)
        .add_response(perf_ns=15, token_count=3)
        .build()
    )
    # Don't set output_token_count, leaving it as None

    record_processor = MetricRecordProcessor(user_config=mock_user_config)

    with pytest.raises(ValueError, match="Invalid Record"):
        await record_processor.process_record(record=record)
