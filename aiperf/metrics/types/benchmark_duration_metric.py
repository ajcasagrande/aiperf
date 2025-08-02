# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
from typing import cast

from aiperf.common.enums import MetricTag, MetricTimeUnit
from aiperf.common.types import MetricTagT, MetricValueTypeT
from aiperf.metrics.base_metric import BaseDerivedMetric


class BenchmarkDurationMetric(BaseDerivedMetric[int]):
    """
    Post-processor for calculating the Benchmark Duration metric.
    """

    tag = MetricTag.BENCHMARK_DURATION
    header = "Benchmark Duration"
    unit = MetricTimeUnit.NANOSECONDS
    larger_is_better = False
    required_metrics = {MetricTag.MIN_REQUEST, MetricTag.MAX_RESPONSE}

    def _derive_value(
        self,
        metrics: dict[MetricTagT, MetricValueTypeT],
    ) -> int:
        min_req_time: int = cast(int, metrics[MetricTag.MIN_REQUEST])
        max_res_time: int = cast(int, metrics[MetricTag.MAX_RESPONSE])
        return max_res_time - min_req_time
