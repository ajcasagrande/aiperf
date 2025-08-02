# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
from typing import cast

from aiperf.common.enums import MetricFlags, MetricTag, MetricTimeUnit
from aiperf.common.models.record_models import ParsedResponseRecord
from aiperf.common.types import MetricTagT, MetricValueTypeT
from aiperf.metrics.base_metric import BaseRecordMetric


class InterTokenLatencyMetric(BaseRecordMetric[float]):
    """
    Post Processor for calculating Inter Token Latency (ITL) metric.
    """

    tag = MetricTag.ITL
    header = "Inter Token Latency (ITL)"
    unit = MetricTimeUnit.NANOSECONDS
    larger_is_better = False
    flags = MetricFlags.STREAMING_ONLY | MetricFlags.TOKEN_BASED_ONLY
    required_metrics = {
        MetricTag.REQUEST_LATENCY,
        MetricTag.TTFT,
        MetricTag.OSL,
    }

    def _parse_record(
        self,
        record: ParsedResponseRecord,
        metrics: dict[MetricTagT, MetricValueTypeT],
    ) -> float:
        """
        Calculates the Inter Token Latency (ITL) metric.
        """
        output_token_count: int = cast(int, metrics[MetricTag.OSL])
        ttft: int = cast(int, metrics[MetricTag.TTFT])
        request_latency: int = cast(int, metrics[MetricTag.REQUEST_LATENCY])

        return (request_latency - ttft) / (output_token_count - 1)
