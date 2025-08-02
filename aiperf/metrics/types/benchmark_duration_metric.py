# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

from aiperf.common.enums import MetricFlags, MetricTag, MetricTimeUnit
from aiperf.metrics.base_metric import BaseSummaryMetric
from aiperf.metrics.metric_dicts import MetricResultsDict


class BenchmarkDurationMetric(BaseSummaryMetric[int]):
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
        if None in (
            metric_results[MetricTag.MIN_REQUEST],
            metric_results[MetricTag.MAX_RESPONSE],
        ):
            raise ValueError(
                "Min request and max response are required to calculate benchmark duration."
            )

        if (
            metric_results[MetricTag.MIN_REQUEST]
            >= metric_results[MetricTag.MAX_RESPONSE]
        ):  # type: ignore
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
