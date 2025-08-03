# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

from aiperf.common.enums import GenericMetricUnit, MetricFlags, MetricTag
from aiperf.common.models import ParsedResponseRecord
from aiperf.metrics import BaseAggregateMetric
from aiperf.metrics.metric_dicts import MetricRecordDict


class ValidRequestCountMetric(BaseAggregateMetric[int]):
    """
    Post-processor for counting the number of valid requests.
    """

    tag = MetricTag.VALID_REQUEST_COUNT
    header = "Valid Request Count"
    unit = GenericMetricUnit.REQUESTS
    flags = MetricFlags.LARGER_IS_BETTER
    required_metrics = None

    def __init__(self):
        super().__init__(0)

    def _update_value(
        self,
        record: ParsedResponseRecord,
        record_metrics: MetricRecordDict,
    ) -> int:
        self._value += 1
        return self._value

    def _aggregate_value(self, value: int) -> int:
        """Aggregate the metric value. For this metric, we just sum the values from the different processes."""
        self._value += value
        return self._value
