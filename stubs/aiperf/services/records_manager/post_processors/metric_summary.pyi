#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
import pandas as pd
from _typeshed import Incomplete

from aiperf.common.constants import NANOS_PER_MILLIS as NANOS_PER_MILLIS
from aiperf.common.enums import MetricType as MetricType
from aiperf.common.enums import PostProcessorType as PostProcessorType
from aiperf.common.factories import PostProcessorFactory as PostProcessorFactory
from aiperf.common.models import MetricResult as MetricResult
from aiperf.common.models import ParsedResponseRecord as ParsedResponseRecord
from aiperf.services.records_manager.metrics.base_metric import BaseMetric as BaseMetric

logger: Incomplete

class MetricSummary:
    logger: Incomplete
    def __init__(self) -> None: ...
    def process(self, records: list[ParsedResponseRecord]) -> None: ...
    def get_metrics_summary(self) -> list[MetricResult]: ...

def record_from_dataframe(df: pd.DataFrame, metric: BaseMetric) -> MetricResult: ...
