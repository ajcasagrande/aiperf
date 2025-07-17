#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
from _typeshed import Incomplete

from aiperf.common.constants import NANOS_PER_SECOND as NANOS_PER_SECOND
from aiperf.common.enums import MetricTimeType as MetricTimeType
from aiperf.common.enums import MetricType as MetricType
from aiperf.common.models import ParsedResponseRecord as ParsedResponseRecord
from aiperf.services.records_manager.metrics.base_metric import BaseMetric as BaseMetric

class RequestThroughputMetric(BaseMetric):
    tag: str
    unit: Incomplete
    larger_is_better: bool
    header: str
    type: Incomplete
    streaming_only: bool
    total_requests: int
    metric: float
    def __init__(self) -> None: ...
    def update_value(
        self,
        record: ParsedResponseRecord | None = None,
        metrics: dict[str, BaseMetric] | None = None,
    ) -> None: ...
    def values(self) -> float: ...
