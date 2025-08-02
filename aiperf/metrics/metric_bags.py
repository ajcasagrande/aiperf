# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

from aiperf.common.types import MetricTagT, MetricValueTypeT


class BaseMetricDict:
    """A dict of metrics."""

    def __init__(self) -> None:
        self.metrics: dict[MetricTagT, MetricValueTypeT] = {}

    def __getitem__(self, key: MetricTagT) -> MetricValueTypeT:
        return self.metrics[key]

    def __setitem__(self, key: MetricTagT, value: MetricValueTypeT) -> None:
        self.metrics[key] = value

    def __contains__(self, key: MetricTagT) -> bool:
        return key in self.metrics

    def __len__(self) -> int:
        return len(self.metrics)

    def __str__(self) -> str:
        return str(self.metrics)


class MetricRecordDict(BaseMetricDict):
    """
    A dict of metrics for a single record. This is used to store the current values
    of all metrics that have been computed for a single record.

    This will include:
    - The current value of any BaseRecordMetric that has been computed for this record.
    - The new value of any BaseAggregateMetric that has been computed for this record.
    - No BaseDerivedMetrics will be included.
    """


class MetricResultsDict(BaseMetricDict):
    """
    A dict of metrics over an entire run. This is used to store the final values
    of all metrics that have been computed for an entire run.

    This will include:
    - All BaseRecordMetrics as a list of their values.
    - The final value of each BaseAggregateMetric.
    - The value of any BaseDerivedMetric that has already been computed.
    """
