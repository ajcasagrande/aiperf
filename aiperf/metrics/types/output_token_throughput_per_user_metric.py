# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

from typing import cast

from aiperf.common.constants import NANOS_PER_SECOND
from aiperf.common.enums import MetricFlags, MetricOverTimeUnit, MetricTag
from aiperf.common.types import MetricTagT, MetricValueTypeT
from aiperf.metrics.base_metric import BaseDerivedMetric


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
        metrics: dict[MetricTagT, MetricValueTypeT],
    ) -> float:
        itl: float = cast(float, metrics[MetricTag.ITL])
        benchmark_token_count: int = cast(int, metrics[MetricTag.BENCHMARK_TOKEN_COUNT])
        return itl / benchmark_token_count
        inter_token_latencies = metrics[MetricTag.ITL].values()
        for inter_token_latency in inter_token_latencies:
            inter_token_latency_s = inter_token_latency / NANOS_PER_SECOND
            if inter_token_latency_s <= 0:
                raise ValueError("Inter-token latency must be greater than 0.")
            self.metric.append(1 / inter_token_latency_s)

    def values(self):
        """
        Returns the list of Output Token Throughput Per User metrics.
        """
        return self.metric

    def _check_record(self, record):
        pass
