# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

from aiperf.common.enums import MetricOverTimeUnit, MetricTag
from aiperf.common.enums.metric_enums import MetricFlags
from aiperf.metrics.base_derived_metric import BaseDerivedMetric
from aiperf.metrics.metric_dicts import MetricResultsDict


class RequestThroughputMetric(BaseDerivedMetric[float]):
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

    def _derive_value(
        self,
        metric_results: MetricResultsDict,
    ) -> float:
        benchmark_duration = metric_results[MetricTag.BENCHMARK_DURATION]
        if benchmark_duration is None or benchmark_duration == 0:
            raise ValueError(
                "Benchmark duration is required and must be greater than 0 to calculate request throughput."
            )

        valid_request_count = metric_results[MetricTag.VALID_REQUEST_COUNT]
        if valid_request_count is None:
            raise ValueError(
                "Valid request count is required to calculate request throughput."
            )

        benchmark_duration_converted = MetricTag.BENCHMARK_DURATION.unit.convert_to(  # type: ignore
            self.unit.time_unit, benchmark_duration  # type: ignore
        )  # fmt: skip
        return valid_request_count / benchmark_duration_converted  # type: ignore
