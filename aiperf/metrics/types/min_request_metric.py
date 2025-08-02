# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
import sys

from aiperf.common.enums import MetricFlags, MetricTag, MetricTimeUnit
from aiperf.common.models import ParsedResponseRecord
from aiperf.metrics.base_metrics import BaseAggregateMetric
from aiperf.metrics.metric_dicts import MetricRecordDict


class MinRequestMetric(BaseAggregateMetric[int]):
    """
    Post-processor for calculating the minimum request time stamp metric from records.
    """

    tag = MetricTag.MIN_REQUEST
    header = "Minimum Request Timestamp"
    unit = MetricTimeUnit.NANOSECONDS
    larger_is_better = False
    flags = MetricFlags.NONE
    required_metrics = None

    def __init__(self) -> None:
        self.value: int = sys.maxsize

    def _update_value(
        self,
        record: ParsedResponseRecord,
        record_metrics: MetricRecordDict,
    ) -> int:
        """Updates the minimum request timestamp metric."""
        # NOTE: Use the request timestamp_ns, not the start_perf_ns, because we want wall-clock timestamps,
        request_ts: int = record.timestamp_ns
        if request_ts < self.value:
            self.value = request_ts
        return self.value
