# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
from typing import cast

from aiperf.common.enums import MetricFlags, MetricTag, MetricTimeUnit
from aiperf.metrics.base_metrics import BaseDerivedMetric
from aiperf.metrics.metric_dicts import MetricResultsDict


class BenchmarkDurationMetric(BaseDerivedMetric[int]):
    """
    Post-processor for calculating the Benchmark Duration metric.
    """

    tag = MetricTag.BENCHMARK_DURATION
    header = "Benchmark Duration"
    unit = MetricTimeUnit.NANOSECONDS
    larger_is_better = False
    flags = MetricFlags.NONE
    required_metrics = {
        MetricTag.MIN_REQUEST,
        MetricTag.MAX_RESPONSE,
    }

    def _validate_inputs(self, metric_results: MetricResultsDict) -> None:
        """
        Checks if the metric can be computed for the given inputs.

        Raises:
            ValueError: If the metric cannot be computed for the given inputs.
        """
        if (
            metric_results[MetricTag.MIN_REQUEST] is None
            or metric_results[MetricTag.MAX_RESPONSE] is None
        ):
            raise ValueError(
                "Min request and max response are required to calculate benchmark duration."
            )
        if cast(int, metric_results[MetricTag.MIN_REQUEST]) >= cast(
            int, metric_results[MetricTag.MAX_RESPONSE]
        ):
            raise ValueError(
                "Min request must be less than max response to calculate benchmark duration."
            )

    def _derive_value(
        self,
        metric_results: MetricResultsDict,
    ) -> int:
        min_req_time: int = cast(int, metric_results[MetricTag.MIN_REQUEST])
        max_res_time: int = cast(int, metric_results[MetricTag.MAX_RESPONSE])
        return max_res_time - min_req_time
