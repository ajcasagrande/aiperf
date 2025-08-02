# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
from aiperf.common.constants import NANOS_PER_SECOND
from aiperf.common.enums import LegacyMetricType, MetricTag, MetricTimeUnit
from aiperf.common.models import ParsedResponseRecord
from aiperf.common.types import MetricTagT
from aiperf.metrics.legacy_base_metric import LegacyBaseMetric


class RequestThroughputMetric(LegacyBaseMetric):
    """
    Post Processor for calculating Request throughput metrics from records.
    """

    tag = MetricTag.REQUEST_THROUGHPUT
    unit = MetricTimeUnit.SECONDS
    larger_is_better = True
    header = "Request Throughput"
    type = LegacyMetricType.METRIC_OF_METRICS
    streaming_only = False
    required_metrics = {MetricTag.REQUEST_COUNT, MetricTag.BENCHMARK_DURATION}

    def __init__(self):
        self.metric: float = 0.0

    def update_value(
        self,
        record: ParsedResponseRecord | None = None,
        metrics: dict[MetricTagT, "LegacyBaseMetric"] | None = None,
    ) -> None:
        self._check_metrics(metrics)
        total_requests = metrics[MetricTag.REQUEST_COUNT].values()
        benchmark_duration = metrics[MetricTag.BENCHMARK_DURATION].values()
        self.metric = total_requests / (benchmark_duration / NANOS_PER_SECOND)

    def values(self) -> float:
        """
        Returns the Request Throughput metric.
        """
        return self.metric

    def _check_record(self, record: ParsedResponseRecord) -> None:
        """
        Checks if the record is valid.

        Raises:
            ValueError: If the record is None or is invalid.
        """
        self._require_valid_record(record)
