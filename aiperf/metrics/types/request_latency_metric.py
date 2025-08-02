# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

from aiperf.common.enums import (
    LegacyMetricType,
    MetricProcessingType,
    MetricTag,
    MetricTimeUnit,
)
from aiperf.common.models import ParsedResponseRecord
from aiperf.common.types import MetricTagT
from aiperf.metrics.legacy_base_metric import LegacyBaseMetric


class RequestLatencyMetric(LegacyBaseMetric[int]):
    """
    Post-processor for calculating Request Latency metrics from records.
    """

    tag = MetricTag.REQUEST_LATENCY
    unit = MetricTimeUnit.NANOSECONDS
    processing_type = MetricProcessingType.PER_REQUEST
    type = LegacyMetricType.METRIC_OF_RECORDS
    larger_is_better = False
    header = "Request Latency"
    required_metrics = set()

    def update_value(
        self,
        record: ParsedResponseRecord | None = None,
        metrics: dict[MetricTagT, "LegacyBaseMetric"] | None = None,
    ) -> None:
        """
        Adds a new record and calculates the Request Latency metric.

        This method extracts the request and last response timestamps, calculates the differences in time, and
        appends the result to the metric list.
        """
        self._check_record(record)
        request_ts = record.start_perf_ns
        final_response_ts = record.responses[-1].perf_ns
        request_latency = final_response_ts - request_ts
        self.metric = request_latency

    def values(self) -> int:
        """
        Returns the list of Request Latency metrics.
        """
        return self.metric

    def _check_record(self, record: ParsedResponseRecord) -> None:
        self._require_valid_record(record)
