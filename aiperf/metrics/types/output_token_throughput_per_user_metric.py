# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

from typing import cast

from aiperf.common.enums import MetricFlags, MetricOverTimeUnit, MetricTag
from aiperf.metrics.base_metrics import BaseDerivedMetric
from aiperf.metrics.metric_dicts import MetricResultsDict


class OutputTokenThroughputPerUserMetric(BaseDerivedMetric[float]):
    """
    Post Processor for calculating Output Token Throughput per user metrics from records.
    """

    tag = MetricTag.OUTPUT_TOKEN_THROUGHPUT_PER_USER
    header = "Output Token Throughput Per User"
    unit = MetricOverTimeUnit.TOKENS_PER_SECOND_PER_USER
    larger_is_better = True
    flags = MetricFlags.STREAMING_ONLY | MetricFlags.TOKEN_BASED_ONLY
    required_metrics = {
        MetricTag.ITL,
        MetricTag.BENCHMARK_TOKEN_COUNT,
    }

    def _derive_value(
        self,
        metric_results: MetricResultsDict,
    ) -> float:
        inter_token_latencies: list[float] = cast(
            list[float], metric_results[MetricTag.ITL]
        )
        benchmark_token_count: int = cast(
            int, metric_results[MetricTag.BENCHMARK_TOKEN_COUNT]
        )
        return sum(inter_token_latencies) / benchmark_token_count
