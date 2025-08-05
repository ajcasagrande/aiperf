# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
import pytest

from aiperf.common.aiperf_logger import AIPerfLogger
from aiperf.common.config.endpoint_config import EndpointConfig
from aiperf.common.config.user_config import UserConfig
from aiperf.common.enums.endpoints_enums import EndpointType
from aiperf.common.models.record_models import ParsedResponseRecord
from aiperf.post_processors.metric_record_processor import MetricRecordProcessor
from aiperf.post_processors.metric_results_processor import MetricResultsProcessor


@pytest.fixture
def mock_user_config():
    return UserConfig(
        endpoint=EndpointConfig(
            type=EndpointType.OPENAI_COMPLETIONS,
            streaming=True,
            model_names=["test-model"],
        ),
    )


_logger = AIPerfLogger(__name__)


def build_record(
    start_ns, first_resp_ns, last_resp_ns, input_tokens=5, output_tokens=5
):
    """Helper function to build a ParsedResponseRecord for testing."""
    from aiperf.common.models import RequestRecord, ResponseData

    return ParsedResponseRecord(
        worker_id="worker-1",
        request=RequestRecord(
            conversation_id="cid",
            turn_index=0,
            model_name="model",
            start_perf_ns=start_ns,
            timestamp_ns=start_ns,
        ),
        responses=[
            ResponseData(
                perf_ns=first_resp_ns,
                token_count=1,
                raw_text=["hi"],
                parsed_text=["hi"],
            ),
            ResponseData(
                perf_ns=last_resp_ns,
                token_count=output_tokens - 1,
                raw_text=["bye"],
                parsed_text=["bye"],
            ),
        ],
        input_token_count=input_tokens,
        output_token_count=output_tokens,
    )


@pytest.mark.asyncio
async def test_metric_summary_process_with_all_metrics(mock_user_config):
    """Test that all metrics can be processed successfully through the metric processors."""
    records = [
        build_record(0, 100, 150, input_tokens=5, output_tokens=5),
        build_record(10, 120, 160, input_tokens=6, output_tokens=4),
        build_record(20, 140, 180, input_tokens=7, output_tokens=3),
    ]

    record_processor = MetricRecordProcessor(user_config=mock_user_config)
    results_processor = MetricResultsProcessor(user_config=mock_user_config)

    for record in records:
        record_metrics = await record_processor.process_record(record)
        await results_processor.process_result(record_metrics)

    summary = await results_processor.summarize()

    # Verify that all metrics are computed successfully
    assert len(summary) > 0, "No metrics were computed"

    for result in summary:
        _logger.trace(f"Metric {result.tag}: avg={result.avg}")
        # Each metric should have a valid average value
        assert result.avg is not None, f"Metric {result.tag} has None average"
        # Basic sanity check that values are reasonable
        assert not (isinstance(result.avg, float) and (result.avg != result.avg)), (
            f"Metric {result.tag} has NaN average"
        )
