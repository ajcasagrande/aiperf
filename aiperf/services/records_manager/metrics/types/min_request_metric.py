# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
from aiperf.common.enums import MetricTimeType, MetricType
from aiperf.common.record_models import ParsedResponseRecord
from aiperf.services.records_manager.metrics.base_metric import BaseMetric


class MinRequestMetric(BaseMetric):
    """
    Post-processor for calculating the minimum request time stamp metric from records.
    """

    tag = "min_request"
    unit = MetricTimeType.NANOSECONDS
    type = MetricType.METRIC_OF_RECORDS
    larger_is_better = False
    header = "Minimum Request Timestamp"

    def __init__(self):
        self.metric: float = float("inf")

    def update_value(
        self,
        record: ParsedResponseRecord | None = None,
        metrics: dict[str, "BaseMetric"] | None = None,
    ) -> None:
        """
        Adds a new record and calculates the minimum request timestamp metric.

        """
        if record:
            self._check_record(record)
            if record.timestamp_ns < self.metric:
                self.metric = record.timestamp_ns

    def values(self) -> float:
        """
        Returns the minimum request timestamp.
        """
        return self.metric

    def _check_record(self, record: ParsedResponseRecord) -> None:
        """
        Checks if the record is valid for calculations.

        """
        if not record or not record.timestamp_ns:
            raise ValueError("Record must have a valid request with a timestamp.")
