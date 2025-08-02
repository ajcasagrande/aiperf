# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
from aiperf.common.enums import MetricTag, MetricTimeUnit
from aiperf.common.models import ParsedResponseRecord
from aiperf.common.types import MetricTagT, MetricValueTypeT
from aiperf.metrics.base_metric import BaseAggregateMetric


class MaxResponseMetric(BaseAggregateMetric[int]):
    """
    Post-processor for calculating the maximum response time stamp metric from records.
    """

    tag = MetricTag.MAX_RESPONSE
    header = "Maximum Response Timestamp"
    unit = MetricTimeUnit.NANOSECONDS
    larger_is_better = False
    required_metrics = set()

    def __init__(self) -> None:
        self.value: int = 0

    def _update_value(
        self,
        record: ParsedResponseRecord,
        metrics: dict[MetricTagT, MetricValueTypeT],
    ) -> int:
        """
        Adds a new record and calculates the maximum response timestamp metric.
        """
        # TODO: Is this the proper value to use? Should we use the last response? Should it be real-time and not perf-time?
        if record.responses[-1].perf_ns > self.value:
            self.value = record.responses[-1].perf_ns
        return self.value
