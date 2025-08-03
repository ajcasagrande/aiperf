# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

from aiperf.common.enums import MetricFlags, MetricOverTimeUnit, MetricTag
from aiperf.metrics.base_derived_metric import BaseDerivedMetric
from aiperf.metrics.metric_dicts import MetricResultsDict
from aiperf.metrics.metric_registry import MetricRegistry


class OutputTokenThroughputMetric(BaseDerivedMetric[float]):
    """
    Post Processor for calculating Output Token Throughput Metric.
    """

    tag = MetricTag.OUTPUT_TOKEN_THROUGHPUT
    header = "Output Token Throughput"
    unit = MetricOverTimeUnit.TOKENS_PER_SECOND
    flags = MetricFlags.PRODUCES_TOKENS_ONLY | MetricFlags.LARGER_IS_BETTER
    required_metrics = {
        MetricTag.BENCHMARK_TOKEN_COUNT,
        MetricTag.BENCHMARK_DURATION,
    }

    def _derive_value(
        self,
        metric_results: MetricResultsDict,
    ) -> float:
        benchmark_token_count = metric_results[MetricTag.BENCHMARK_TOKEN_COUNT]
        benchmark_duration = metric_results[MetricTag.BENCHMARK_DURATION]
        benchmark_duration_unit = MetricRegistry.get_unit(MetricTag.BENCHMARK_DURATION)
        benchmark_duration_converted = benchmark_duration_unit.convert_to(
            self.unit.time_unit, benchmark_duration
        )
        return benchmark_token_count / benchmark_duration_converted
