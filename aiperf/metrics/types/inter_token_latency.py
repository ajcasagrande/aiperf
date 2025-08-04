# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

from aiperf.common.enums import MetricFlags, MetricTag, MetricTimeUnit
from aiperf.common.models import ParsedResponseRecord
from aiperf.metrics import BaseRecordMetric
from aiperf.metrics.metric_dicts import MetricRecordDict


class InterTokenLatencyMetric(BaseRecordMetric[float]):
    """
    Post Processor for calculating Inter Token Latency (ITL) metric.
    """

    tag = MetricTag.ITL
    header = "Inter Token Latency"
    unit = MetricTimeUnit.NANOSECONDS
    display_unit = MetricTimeUnit.MILLISECONDS
    flags = MetricFlags.STREAMING_TOKENS_ONLY | MetricFlags.LARGER_IS_BETTER
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
        osl = record_metrics[MetricTag.OSL]
        ttft = record_metrics[MetricTag.TTFT]
        request_latency = record_metrics[MetricTag.REQUEST_LATENCY]

        return (request_latency - ttft) / (osl - 1)  # type: ignore
