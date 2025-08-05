# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
import pytest

from aiperf.common.config.endpoint_config import EndpointConfig
from aiperf.common.enums.endpoints_enums import EndpointType
from aiperf.common.models import RequestRecord, ResponseData
from aiperf.common.models.record_models import ParsedResponseRecord

from .conftest import BaseMetricTest


class TestMetricSummary(BaseMetricTest):
    """Test suite for comprehensive metric processing using the base test framework."""

    @property
    def endpoint_config(self) -> EndpointConfig:
        return EndpointConfig(
            type=EndpointType.OPENAI_COMPLETIONS,
            streaming=True,
            model_names=["test-model"],
        )

    @property
    def metric_tag(self) -> str:
        # This test doesn't focus on a single metric, so we return a placeholder
        return "comprehensive_test"

    def build_record(
        self, start_ns, first_resp_ns, last_resp_ns, input_tokens=5, output_tokens=5
    ):
        """Helper function to build a ParsedResponseRecord for testing."""
        return ParsedResponseRecord(
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
    async def test_metric_summary_process_with_all_metrics(self):
        """Test that all metrics can be processed successfully through the metric processors."""
        records = [
            self.build_record(0, 100, 150, input_tokens=5, output_tokens=5),
            self.build_record(10, 120, 160, input_tokens=6, output_tokens=4),
            self.build_record(20, 140, 180, input_tokens=7, output_tokens=3),
        ]

        summary = await self.process_records_and_get_summary(records)

        # Verify that all metrics are computed successfully
        assert len(summary) > 0, "No metrics were computed"

        for result in summary:
            self._logger.trace(f"Metric {result.tag}: avg={result.avg}")
            # Each metric should have a valid average value
            assert result.avg is not None, f"Metric {result.tag} has None average"
            # Basic sanity check that values are reasonable
            assert not (isinstance(result.avg, float) and (result.avg != result.avg)), (
                f"Metric {result.tag} has NaN average"
            )
