# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

from aiperf.common.enums import GenericMetricUnit, MetricTag
from aiperf.common.models import ParsedResponseRecord
from aiperf.metrics.base_metrics import BaseAggregateMetric
from aiperf.metrics.metric_dicts import MetricRecordDict


class ValidRequestCountMetric(BaseAggregateMetric[int]):
    """
    Post-processor for counting the number of valid requests.
    """

    tag = MetricTag.VALID_REQUEST_COUNT
    header = "Valid Request Count"
    unit = GenericMetricUnit.REQUESTS
    larger_is_better = True
    required_metrics = set()

    def __init__(self):
        self.value: int = 0

    def _update_value(
        self,
        record: ParsedResponseRecord,
        record_metrics: MetricRecordDict,
    ) -> int:
        self.value += 1
        return self.value
