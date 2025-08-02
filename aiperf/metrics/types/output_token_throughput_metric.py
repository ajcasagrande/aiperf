# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

from typing import cast

from aiperf.common.constants import NANOS_PER_SECOND
from aiperf.common.enums import MetricFlags, MetricOverTimeUnit, MetricTag
from aiperf.common.types import MetricTagT, MetricValueTypeT
from aiperf.metrics.base_metric import BaseDerivedMetric


class OutputTokenThroughputMetric(BaseDerivedMetric[float]):
    """
    Post Processor for calculating Output Token Throughput Metric.
    """

    tag = MetricTag.OUTPUT_TOKEN_THROUGHPUT
    header = "Output Token Throughput"
    unit = MetricOverTimeUnit.TOKENS_PER_SECOND
    larger_is_better = True
    flags = MetricFlags.TOKEN_BASED_ONLY
    required_metrics = {
        MetricTag.BENCHMARK_TOKEN_COUNT,
        MetricTag.BENCHMARK_DURATION,
    }

    def _derive_value(
        self,
        metrics: dict[MetricTagT, MetricValueTypeT],
    ) -> float:
        benchmark_token_count: int = cast(int, metrics[MetricTag.BENCHMARK_TOKEN_COUNT])
        benchmark_duration: int = cast(int, metrics[MetricTag.BENCHMARK_DURATION])
        # TODO: This is hardcoded to expect the benchmark duration to be in nanoseconds.
        return benchmark_token_count / (benchmark_duration / NANOS_PER_SECOND)
