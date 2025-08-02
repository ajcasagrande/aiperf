# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

from aiperf.common.enums import LegacyMetricType, MetricTag
from aiperf.common.models import ParsedResponseRecord
from aiperf.common.types import MetricTagT
from aiperf.metrics.legacy_base_metric import LegacyBaseMetric


class RequestCountMetric(LegacyBaseMetric):
    """
    Post-processor for counting the number of valid requests.
    """

    tag = MetricTag.REQUEST_COUNT
    unit = None
    larger_is_better = True
    header = "Request Count"
    type = LegacyMetricType.METRIC_OF_RECORDS
    streaming_only = False
    required_metrics = set()

    def __init__(self):
        self.metric: int = 0

    def update_value(
        self,
        record: ParsedResponseRecord | None = None,
        metrics: dict[MetricTagT, "LegacyBaseMetric"] | None = None,
    ) -> None:
        self._check_record(record)
        self.metric += 1

    def values(self) -> int:
        """
        Returns the Request Count metric.
        """
        return self.metric

    def _check_record(self, record: ParsedResponseRecord) -> None:
        self._require_valid_record(record)
