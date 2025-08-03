# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

from collections.abc import Iterator
from typing import TYPE_CHECKING

import pandas as pd

from aiperf.common.enums import MetricType
from aiperf.common.enums.metric_enums import MetricValueTypeT
from aiperf.common.models.record_models import MetricResult
from aiperf.common.types import MetricTagT
from aiperf.metrics.metric_registry import MetricRegistry

if TYPE_CHECKING:
    pass


class BaseMetricDict(dict[MetricTagT, MetricValueTypeT]):
    """A base class for metric dicts."""

    pass


class MetricRecordDict(BaseMetricDict):
    """
    A dict of metrics for a single record. This is used to store the current values
    of all metrics that have been computed for a single record.

    This will include:
    - The current value of any `BaseRecordMetric` that has been computed for this record.
    - The new value of any `BaseAggregateMetric` that has been computed for this record.
    - No `BaseDerivedMetric`s will be included.
    """


class MetricResultsDict:
    """
    A dict of metrics over an entire run. This is used to store the final values
    of all metrics that have been computed for an entire run.

    This will include:
    - All `BaseRecordMetric`s as a list of their values (or similar such as pandas DataFrames).
    - The final value of each `BaseAggregateMetric`.
    - The value of any `BaseDerivedMetric` that has already been computed.
    """

    def __init__(self):
        MetricRegistry.discover_metrics()
        self._record_results: dict[MetricTagT, list[MetricValueTypeT]] = {}
        self._aggregate_results: dict[MetricTagT, MetricValueTypeT] = {}
        self._derived_results: dict[MetricTagT, MetricValueTypeT] = {}

    def __getitem__(self, key: MetricTagT) -> MetricValueTypeT | list[MetricValueTypeT]:
        """Get the value of a metric."""
        if key in self._aggregate_results:
            return self._aggregate_results[key]
        elif key in self._record_results:
            return self._record_results[key]
        elif key in self._derived_results:
            return self._derived_results[key]
        else:
            raise KeyError(f"Metric {key} not found in metric results")

    def __setitem__(
        self, key: MetricTagT, value: MetricValueTypeT | list[MetricValueTypeT]
    ) -> None:
        """Set the value of a metric."""
        if not MetricRegistry.has_tag(key):
            raise ValueError(f"Metric {key} not found in metric classes")

        metric_type = MetricRegistry.get_type_for(key)
        if metric_type == MetricType.RECORD:
            self._record_results[key] = value
        elif metric_type == MetricType.AGGREGATE:
            self._aggregate_results[key] = value
        elif metric_type == MetricType.DERIVED:
            self._derived_results[key] = value
        else:
            raise ValueError(f"Metric {key} is not a valid metric type")

    def __contains__(self, key: MetricTagT) -> bool:
        """Check if a metric is in the metric results dict."""
        return (
            key in self._aggregate_results
            or key in self._record_results
            or key in self._derived_results
        )

    def __iter__(self) -> Iterator[MetricTagT]:
        """Iterate over the metric results dict."""
        return iter(
            self._aggregate_results.keys()
            | self._record_results.keys()
            | self._derived_results.keys()
        )

    def __len__(self) -> int:
        """Get the number of metrics in the metric results dict."""
        return (
            len(self._aggregate_results)
            + len(self._record_results)
            + len(self._derived_results)
        )

    def __str__(self) -> str:
        """Get a string representation of the metric results dict."""
        return f"MetricResultsDict(aggregate_results={self._aggregate_results}, record_results={self._record_results}, derived_results={self._derived_results})"

    def __repr__(self) -> str:
        """Get a string representation of the metric results dict."""
        return self.__str__()

    def setdefault(
        self, key: MetricTagT, default: MetricValueTypeT | list[MetricValueTypeT]
    ) -> MetricValueTypeT | list[MetricValueTypeT]:
        """Set a default value for a metric."""
        if not MetricRegistry.has_tag(key):
            raise ValueError(f"Metric {key} not found in metric classes")

        if MetricRegistry.get_type_for(key) == MetricType.RECORD:
            if key not in self._record_results:
                self._record_results[key] = default
            return self._record_results[key]
        elif MetricRegistry.get_type_for(key) == MetricType.AGGREGATE:
            if key not in self._aggregate_results:
                self._aggregate_results[key] = default
            return self._aggregate_results[key]
        elif MetricRegistry.get_type_for(key) == MetricType.DERIVED:
            if key not in self._derived_results:
                self._derived_results[key] = default
            return self._derived_results[key]
        else:
            raise ValueError(f"Metric {key} is not a valid metric type")

    def update(self, metric_dict: BaseMetricDict) -> None:
        """Update the metric results dict with the values from another dict."""
        for key, value in metric_dict.items():
            if not MetricRegistry.has_tag(key):
                raise ValueError(f"Metric {key} not found in metric classes")

            metric_type = MetricRegistry.get_type_for(key)
            if metric_type == MetricType.RECORD:
                self._record_results.setdefault(key, []).append(value)
            elif metric_type == MetricType.AGGREGATE:
                self._aggregate_results[key] = value
            elif metric_type == MetricType.DERIVED:
                self._derived_results[key] = value
            else:
                raise ValueError(f"Metric {key} is not a valid metric type")

    def summarize(self) -> list[MetricResult]:
        """Summarize the metric results dict."""
        summary = []
        df = pd.DataFrame({tag: values for tag, values in self._record_results.items()})
        for tag in self._record_results:
            summary.append(_metric_result_from_dataframe(df, tag))
        for tag, value in self._aggregate_results.items():
            summary.append(_metric_result_from_value(value, tag))
        for tag, value in self._derived_results.items():
            summary.append(_metric_result_from_value(value, tag))
        return summary


def _metric_result_from_value(
    value: MetricValueTypeT, tag: MetricTagT
) -> MetricResult | None:
    """Create a MetricResult from a value and tag."""
    metric = MetricRegistry.get_instance(tag)
    return MetricResult(
        tag=tag,
        header=metric.header,
        unit=str(metric.unit),
        avg=value,
    )


def _metric_result_from_dataframe(df: pd.DataFrame, tag: MetricTagT) -> MetricResult:
    """Create a Record from a DataFrame."""
    metric = MetricRegistry.get_instance(tag)
    column = df[tag]
    quantiles = column.quantile([0.01, 0.05, 0.25, 0.50, 0.75, 0.90, 0.95, 0.99])

    return MetricResult(
        tag=metric.tag,
        header=metric.header,
        unit=str(metric.unit),
        avg=column.mean(),
        min=column.min(),
        max=column.max(),
        p1=quantiles[0.01],
        p5=quantiles[0.05],
        p25=quantiles[0.25],
        p50=quantiles[0.50],
        p75=quantiles[0.75],
        p90=quantiles[0.90],
        p95=quantiles[0.95],
        p99=quantiles[0.99],
        std=column.std(),
        count=int(column.count()),
    )
