# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
from typing import cast

from aiperf.common.enums import MetricTag, MetricTimeUnit
from aiperf.metrics.base_metric import BaseDerivedMetric
from aiperf.metrics.metric_dicts import MetricResultsDict


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
        metric_results: MetricResultsDict,
    ) -> int:
        min_req_time: int = cast(int, metric_results[MetricTag.MIN_REQUEST])
        max_res_time: int = cast(int, metric_results[MetricTag.MAX_RESPONSE])
        return max_res_time - min_req_time
