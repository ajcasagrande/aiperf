# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
from aiperf.common.enums import MetricTag, MetricTimeUnit
from aiperf.common.models import ParsedResponseRecord
from aiperf.common.types import MetricTagT, MetricValueTypeT
from aiperf.metrics.base_metric import BaseAggregateMetric


class MinRequestMetric(BaseAggregateMetric[int]):
    """
    Post-processor for calculating the minimum request time stamp metric from records.
    """

    tag = MetricTag.MIN_REQUEST
    unit = MetricTimeUnit.NANOSECONDS
    larger_is_better = False
    header = "Minimum Request Timestamp"
    required_metrics = set()

    def __init__(self):
        self.value: float = float("inf")

    def _parse_record(
        self,
        record: ParsedResponseRecord,
        metrics: dict[MetricTagT, MetricValueTypeT],
    ) -> None:
        """Calculates the minimum request timestamp metric."""
        if record.start_perf_ns < self.value:
            self.value = record.start_perf_ns
