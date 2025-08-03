# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
import sys

from aiperf.common.enums import MetricFlags, MetricTag, MetricTimeUnit
from aiperf.common.models import ParsedResponseRecord
from aiperf.metrics import BaseAggregateMetric
from aiperf.metrics.metric_dicts import MetricRecordDict


class MinRequestMetric(BaseAggregateMetric[int]):
    """
    Post-processor for calculating the minimum request time stamp metric from records.
    """

    tag = MetricTag.MIN_REQUEST
    header = "Minimum Request Timestamp"
    unit = MetricTimeUnit.NANOSECONDS
    flags = MetricFlags.HIDDEN
    required_metrics = None

    def __init__(self) -> None:
        super().__init__(sys.maxsize)

    def _parse_record(
        self,
        record: ParsedResponseRecord,
        record_metrics: MetricRecordDict,
    ) -> int:
        """Return the request timestamp."""
        # NOTE: Use the request timestamp_ns, not the start_perf_ns, because we want wall-clock timestamps,
        return record.timestamp_ns

    def _aggregate_value(self, value: int) -> int:
        """Aggregate the metric value. For this metric, we just take the min of the values from the different processes."""
        if value < self._value:
            self._value = value
        return self._value
