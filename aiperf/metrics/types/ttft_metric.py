# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
from aiperf.common.enums import LegacyMetricType, MetricFlags, MetricTag, MetricTimeUnit
from aiperf.common.models import ParsedResponseRecord
from aiperf.common.types import MetricTagT
from aiperf.metrics.legacy_base_metric import LegacyBaseMetric


class TTFTMetric(LegacyBaseMetric):
    """
    Post-processor for calculating Time to First Token (TTFT) metrics from records.
    """

    tag = MetricTag.TTFT
    unit = MetricTimeUnit.NANOSECONDS
    larger_is_better = False
    header = "Time to First Token (TTFT)"
    type = LegacyMetricType.METRIC_OF_RECORDS
    flags = MetricFlags.STREAMING_ONLY | MetricFlags.TOKEN_BASED_ONLY
    required_metrics = set()

    def __init__(self):
        self.metric: list[int] = []

    def update_value(
        self,
        record: ParsedResponseRecord | None = None,
        metrics: dict[MetricTagT, "LegacyBaseMetric"] | None = None,
    ) -> None:
        """
        Adds a new record and calculates the Time To First Token (TTFT) metric.

        This method extracts the timestamp from the request and the first response in the given
        RequestRecord object, computes the difference (TTFT), and appends the result to the metric list.
        """
        self._check_record(record)
        request_ts = record.request.start_perf_ns
        response_ts = record.responses[0].perf_ns
        ttft = response_ts - request_ts
        self.metric.append(ttft)

    def values(self) -> list[int]:
        """
        Returns the list of Time to First Token (TTFT) metrics.
        """
        return self.metric

    def _check_record(self, record: ParsedResponseRecord) -> None:
        """
        Checks if the record is valid for TTFT calculation.

        Raises:
            ValueError: If record is None or record is not valid
        """
        self._require_valid_record(record)
