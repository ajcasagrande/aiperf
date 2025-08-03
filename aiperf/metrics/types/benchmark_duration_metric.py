# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

from aiperf.common.enums import MetricFlags, MetricTag, MetricTimeUnit
from aiperf.metrics.base_derived_metric import BaseDerivedMetric
from aiperf.metrics.metric_dicts import MetricResultsDict


class BenchmarkDurationMetric(BaseDerivedMetric[int]):
    """
    Post-processor for calculating the Benchmark Duration metric.
    """

    tag = MetricTag.BENCHMARK_DURATION
    header = "Benchmark Duration"
    unit = MetricTimeUnit.NANOSECONDS
    flags = MetricFlags.HIDDEN
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
        min_req_time = metric_results[MetricTag.MIN_REQUEST]
        max_res_time = metric_results[MetricTag.MAX_RESPONSE]

        if min_req_time is None or max_res_time is None:
            raise ValueError(
                "Min request and max response are required to calculate benchmark duration."
            )

        if min_req_time >= max_res_time:  # type: ignore
            raise ValueError(
                "Min request must be less than max response to calculate benchmark duration."
            )

    def _derive_value(
        self,
        metric_results: MetricResultsDict,
    ) -> int:
        min_req_time = metric_results[MetricTag.MIN_REQUEST]
        max_res_time = metric_results[MetricTag.MAX_RESPONSE]
        return max_res_time - min_req_time  # type: ignore
