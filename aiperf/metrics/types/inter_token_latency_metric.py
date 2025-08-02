# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
from typing import cast

from aiperf.common.enums import MetricFlags, MetricTag, MetricTimeUnit
from aiperf.common.models import ParsedResponseRecord
from aiperf.metrics.base_metrics import BaseRecordMetric
from aiperf.metrics.metric_dicts import MetricRecordDict


class InterTokenLatencyMetric(BaseRecordMetric[float]):
    """
    Post Processor for calculating Inter Token Latency (ITL) metric.
    """

    tag = MetricTag.ITL
    header = "Inter Token Latency (ITL)"
    unit = MetricTimeUnit.NANOSECONDS
    flags = (
        MetricFlags.STREAMING_ONLY
        | MetricFlags.TOKEN_BASED_ONLY
        | MetricFlags.LARGER_IS_BETTER
    )
    required_metrics = {
        MetricTag.REQUEST_LATENCY,
        MetricTag.TTFT,
        MetricTag.OSL,
    }

    def _parse_record(
        self,
        record: ParsedResponseRecord,
        record_metrics: MetricRecordDict,
    ) -> float:
        """
        Calculates the Inter Token Latency (ITL) metric.
        """
        osl: int = cast(int, record_metrics[MetricTag.OSL])
        ttft: int = cast(int, record_metrics[MetricTag.TTFT])
        request_latency: int = cast(int, record_metrics[MetricTag.REQUEST_LATENCY])

        return (request_latency - ttft) / (osl - 1)
