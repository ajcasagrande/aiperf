# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
from aiperf.common.constants import NANOS_PER_SECOND
from aiperf.common.enums import MetricOverTimeUnit, MetricTag
from aiperf.common.models import ParsedResponseRecord
from aiperf.metrics.base_metric import BaseDerivedMetric
from aiperf.metrics.metric_dicts import MetricResultsDict


class RequestThroughputMetric(BaseDerivedMetric):
    """
    Post Processor for calculating Request throughput metrics from records.
    """

    tag = MetricTag.REQUEST_THROUGHPUT
    unit = MetricOverTimeUnit.REQUESTS_PER_SECOND
    larger_is_better = True
    header = "Request Throughput"
    required_metrics = {
        MetricTag.VALID_REQUEST_COUNT,
        MetricTag.BENCHMARK_DURATION,
    }

    def _derive_value(
        self,
        metric_results: MetricResultsDict,
    ) -> None:
        total_requests = metrics[MetricTag.VALID_REQUEST_COUNT].values()
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
