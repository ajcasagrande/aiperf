# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
from typing import cast

from aiperf.common.constants import NANOS_PER_SECOND
from aiperf.common.enums import MetricOverTimeUnit, MetricTag
from aiperf.common.enums.metric_enums import MetricFlags
from aiperf.metrics.base_metric import BaseSummaryMetric
from aiperf.metrics.metric_dicts import MetricResultsDict


class RequestThroughputMetric(BaseSummaryMetric[float]):
    """
    Post Processor for calculating Request throughput metrics from records.
    """

    tag = MetricTag.REQUEST_THROUGHPUT
    header = "Request Throughput"
    unit = MetricOverTimeUnit.REQUESTS_PER_SECOND
    flags = MetricFlags.LARGER_IS_BETTER
    required_metrics = {
        MetricTag.VALID_REQUEST_COUNT,
        MetricTag.BENCHMARK_DURATION,
    }

    def _validate_inputs(self, metric_results: MetricResultsDict) -> None:
        """Check that the metric can be computed for the given results.
        This method is called after the required metrics are checked, so it can assume that the required metrics are available.
        """
        if (
            metric_results[MetricTag.BENCHMARK_DURATION] is None
            or metric_results[MetricTag.BENCHMARK_DURATION] == 0
        ):
            raise ValueError(
                "Benchmark duration is required and must be greater than 0 to calculate request throughput."
            )
        if metric_results[MetricTag.VALID_REQUEST_COUNT] is None:
            raise ValueError(
                "Valid request count is required to calculate request throughput."
            )

    def _derive_value(
        self,
        metric_results: MetricResultsDict,
    ) -> float:
        valid_request_count: int = cast(
            int, metric_results[MetricTag.VALID_REQUEST_COUNT]
        )
        benchmark_duration: int = cast(
            int, metric_results[MetricTag.BENCHMARK_DURATION]
        )
        # TODO: HACK: This is hardcoded to expect the benchmark duration to be in nanoseconds.
        return valid_request_count / (benchmark_duration / NANOS_PER_SECOND)
