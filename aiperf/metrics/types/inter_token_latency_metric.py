# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

from aiperf.common.enums import LegacyMetricType, MetricTag, MetricTimeUnit
from aiperf.common.models.record_models import ParsedResponseRecord
from aiperf.common.types import MetricTagT
from aiperf.metrics.legacy_base_metric import LegacyBaseMetric


class InterTokenLatencyMetric(LegacyBaseMetric):
    """
    Post Processor for calculating Inter Token Latency (ITL) metric.
    """

    tag = MetricTag.ITL
    unit = MetricTimeUnit.MILLISECONDS
    larger_is_better = False
    header = "Inter Token Latency (ITL)"
    type = LegacyMetricType.METRIC_OF_METRICS
    streaming_only = True
    required_metrics = {
        MetricTag.REQUEST_LATENCY,
        MetricTag.TTFT,
        MetricTag.OUTPUT_TOKEN_COUNT,
    }

    def __init__(self):
        self.metric: list[float] = []

    def update_value(
        self,
        record: ParsedResponseRecord | None = None,
        metrics: dict[MetricTagT, "LegacyBaseMetric"] | None = None,
    ):
        self._check_metrics(metrics)
        # Clear the current value because we re-compute it each time
        self.metric.clear()

        latencies = metrics[MetricTag.REQUEST_LATENCY].values()
        ttfts = metrics[MetricTag.TTFT].values()
        output_token_counts = metrics[MetricTag.OUTPUT_TOKEN_COUNT].values()

        for latency, ttft, output_tokens in zip(
            latencies, ttfts, output_token_counts, strict=False
        ):
            itl = (latency - ttft) / (output_tokens - 1)
            self.metric.append(itl)

    def values(self) -> list[float]:
        """
        Returns the list of Inter Token Latency (ITL) metrics.
        """
        return self.metric

    def _check_record(self, record):
        pass
