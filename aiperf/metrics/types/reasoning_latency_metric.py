# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
from aiperf.common.enums import MetricFlags, MetricTimeUnit
from aiperf.common.models import ParsedResponseRecord
from aiperf.metrics import BaseRecordMetric
from aiperf.metrics.metric_dicts import MetricRecordDict
from aiperf.metrics.types.time_to_first_output_token_metric import (
    TimeToFirstOutputTokenMetric,
)
from aiperf.metrics.types.ttft_metric import TTFTMetric


class ReasoningLatencyMetric(BaseRecordMetric[int]):
    """
    Post-processor for calculating Reasoning Latency (RL) metrics from records.

    Reasoning latency is the time between the first reasoning token and the first output (answer) token.

    Formula:
        Reasoning Latency = TTFOT - TTFT
    """

    tag = "reasoning_latency"
    header = "Reasoning Latency"
    short_header = "Reasoning Latency"
    unit = MetricTimeUnit.NANOSECONDS
    display_unit = MetricTimeUnit.MILLISECONDS
    flags = (
        MetricFlags.STREAMING_TOKENS_ONLY
        | MetricFlags.SUPPORTS_REASONING
        | MetricFlags.EXPERIMENTAL
    )
    required_metrics = {
        TTFTMetric.tag,
        TimeToFirstOutputTokenMetric.tag,
    }

    def _parse_record(
        self,
        record: ParsedResponseRecord,
        record_metrics: MetricRecordDict,
    ) -> int:
        """
        This method extracts the TTFT and TTFOT, and calculates the difference.
        """
        ttft: int = record_metrics.get_or_raise(TTFTMetric)  # type: ignore
        ttfot: int = record_metrics.get_or_raise(TimeToFirstOutputTokenMetric)  # type: ignore
        if ttfot < ttft:
            raise ValueError(
                "TTFOT is less than TTFT, cannot compute Reasoning Latency."
            )
        return ttfot - ttft
