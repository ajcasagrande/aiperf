# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
import sys

from aiperf.common.enums import MetricTag, MetricTimeUnit
from aiperf.common.models import ParsedResponseRecord
from aiperf.common.types import MetricTagT, MetricValueTypeT
from aiperf.metrics.base_metric import BaseAggregateMetric


class MinRequestMetric(BaseAggregateMetric[int]):
    """
    Post-processor for calculating the minimum request time stamp metric from records.
    """

    tag = MetricTag.MIN_REQUEST
    header = "Minimum Request Timestamp"
    unit = MetricTimeUnit.NANOSECONDS
    larger_is_better = False
    required_metrics = set()

    def __init__(self) -> None:
        self.value: int = sys.maxsize

    def _update_value(
        self,
        record: ParsedResponseRecord,
        metrics: dict[MetricTagT, MetricValueTypeT],
    ) -> int:
        """Calculates the minimum request timestamp metric."""
        # TODO: Is this the proper value to use? Should it be real-time and not perf-time?
        if record.start_perf_ns < self.value:
            self.value = record.start_perf_ns
        return self.value
