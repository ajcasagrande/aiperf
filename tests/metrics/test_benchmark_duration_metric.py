# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

import pytest

from aiperf.common.aiperf_logger import AIPerfLogger
from aiperf.common.config.endpoint_config import EndpointConfig
from aiperf.common.config.user_config import UserConfig
from aiperf.common.enums.endpoints_enums import EndpointType
from aiperf.common.models.record_models import ParsedResponseRecord
from aiperf.metrics.types.benchmark_duration import BenchmarkDurationMetric
from aiperf.post_processors.metric_record_processor import MetricRecordProcessor
from aiperf.post_processors.metric_results_processor import MetricResultsProcessor
from tests.metrics.conftest import ParsedRecord, ParsedResponseRecordBuilder, Response


@pytest.fixture
def mock_user_config():
    return UserConfig(
        endpoint=EndpointConfig(
            # NOTE: Using embeddings endpoint to avoid token count metrics.
            type=EndpointType.OPENAI_EMBEDDINGS,
            streaming=False,
            model_names=["test-model"],
        ),
    )


_logger = AIPerfLogger(__name__)


@pytest.mark.asyncio
async def test_add_multiple_records(
    parsed_response_record_builder: ParsedResponseRecordBuilder, mock_user_config
):
    records: list[ParsedResponseRecord] = (
        parsed_response_record_builder.create_records_from_configs(
            [
                ParsedRecord(request_start_time=10, responses=[Response(perf_ns=15)]),
                ParsedRecord(request_start_time=20, responses=[Response(perf_ns=25)]),
                ParsedRecord(request_start_time=30, responses=[Response(perf_ns=40)]),
            ]
        )
    )

    # Create a record processor to ingest the raw records
    record_processor = MetricRecordProcessor(user_config=mock_user_config)
    # Create a results processor to aggregate the results
    results_processor = MetricResultsProcessor(user_config=mock_user_config)

    # Process the records one by one, feeding the results to the results processor.
    for record in records:
        record_metrics = await record_processor.process_record(record=record)
        await results_processor.process_result(record_metrics)

    # Compute the derived metrics, and calculate the min/max/avg/std/etc.
    summary = await results_processor.summarize()

    found = False
    for result in summary:
        if result.tag == BenchmarkDurationMetric.tag:
            _logger.trace(f"Result: {result}")
            assert result.avg == 30
            found = True
            break
    assert found, "BenchmarkDurationMetric not found in summary"
