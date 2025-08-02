# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

from aiperf.common.types import MetricTagT, MetricValueTypeT


class BaseMetricDict(dict[MetricTagT, MetricValueTypeT]):
    """A base class for metric dicts."""


class MetricRecordDict(BaseMetricDict):
    """
    A dict of metrics for a single record. This is used to store the current values
    of all metrics that have been computed for a single record.

    This will include:
    - The current value of any `BaseRecordMetric` that has been computed for this record.
    - The new value of any `BaseAggregateMetric` that has been computed for this record.
    - No `BaseDerivedMetric`s will be included.
    """


class MetricResultsDict(BaseMetricDict):
    """
    A dict of metrics over an entire run. This is used to store the final values
    of all metrics that have been computed for an entire run.

    This will include:
    - All `BaseRecordMetric`s as a list of their values.
    - The final value of each `BaseAggregateMetric`.
    - The value of any `BaseDerivedMetric` that has already been computed.
    """
