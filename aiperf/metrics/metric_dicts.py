# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

from collections import deque
from collections.abc import Iterator
from itertools import chain
from typing import TYPE_CHECKING

import pandas as pd

from aiperf.common.enums import MetricType
from aiperf.common.enums.metric_enums import (
    MetricDictValueTypeT,
    MetricUnitT,
    MetricValueTypeT,
)
from aiperf.common.models.record_models import MetricResult
from aiperf.common.types import MetricTagT

if TYPE_CHECKING:
    from aiperf.metrics.base_metric import BaseMetric


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

    def get_converted(
        self, metric: type["BaseMetric"], other_unit: MetricUnitT
    ) -> float:
        """Get the value of a metric, but converted to a different unit."""
        return metric.unit.convert_to(other_unit, self[metric.tag])  # type: ignore


class MetricResultsDict:
    """
    A dict of metrics over an entire run. This is used to store the final values
    of all metrics that have been computed for an entire run.

    This will include:
    - All `BaseRecordMetric`s as a list of their values (or similar such as pandas Series).
    - The final value of each `BaseAggregateMetric`.
    - The value of any `BaseDerivedMetric` that has already been computed.
    """

    def __init__(self):
        self._results_dicts: dict[MetricType, dict[MetricTagT, MetricDictValueTypeT]] = {
            MetricType.RECORD: {},
            MetricType.AGGREGATE: {},
            MetricType.DERIVED: {},
        }  # fmt: skip

    def _validate_and_get_metric_type(self, tag: MetricTagT) -> MetricType:
        """Validate tag and return its metric type."""
        from aiperf.metrics.metric_registry import MetricRegistry

        metric_type = MetricRegistry.get_class(tag).type
        if metric_type not in self._results_dicts:
            raise ValueError(f"Metric {tag} is not a valid metric type")

        return metric_type

    def __getitem__(self, tag: MetricTagT) -> MetricDictValueTypeT:
        """Get the value of a metric."""
        try:
            return next(
                result_dict[tag]
                for result_dict in self._results_dicts.values()
                if tag in result_dict
            )
        except StopIteration:
            raise KeyError(f"Metric {tag} not found in metric results") from None

    def __setitem__(self, tag: MetricTagT, value: MetricDictValueTypeT) -> None:
        """Set the value of a metric."""
        metric_type = self._validate_and_get_metric_type(tag)
        self._results_dicts[metric_type][tag] = value  # type: ignore

    def __contains__(self, tag: MetricTagT) -> bool:
        """Check if a metric is in the metric results dict."""
        return any(tag in result_dict for result_dict in self._results_dicts.values())

    def __iter__(self) -> Iterator[MetricTagT]:
        """Iterate over all of the metric results dicts."""
        return chain.from_iterable(
            result_dict.keys() for result_dict in self._results_dicts.values()
        )

    def __len__(self) -> int:
        """Get the number of metrics in all of the metric results dicts."""
        return sum(len(result_dict) for result_dict in self._results_dicts.values())

    def __str__(self) -> str:
        """Get a string representation of the metric results dict."""
        return f"MetricResultsDict({self._results_dicts})"

    def __repr__(self) -> str:
        """Get a string representation of the metric results dict."""
        return self.__str__()

    def setdefault(
        self, tag: MetricTagT, default: MetricDictValueTypeT
    ) -> MetricDictValueTypeT:
        """Set a default value for a metric."""
        metric_type = self._validate_and_get_metric_type(tag)

        if tag not in self._results_dicts[metric_type]:
            self._results_dicts[metric_type][tag] = default  # type: ignore
        return self._results_dicts[metric_type][tag]

    def update(self, metric_dict: BaseMetricDict) -> None:
        """Update the metric results dicts with the values from another dict."""
        for tag, value in metric_dict.items():
            metric_type = self._validate_and_get_metric_type(tag)

            if metric_type in (MetricType.AGGREGATE, MetricType.DERIVED):
                self._results_dicts[metric_type][tag] = value  # type: ignore
            elif metric_type == MetricType.RECORD:
                self._results_dicts[metric_type].setdefault(tag, deque()).append(value)  # type: ignore

    def get_converted(
        self, metric: type["BaseMetric"], other_unit: MetricUnitT
    ) -> float:
        """Get the value of a metric, but converted to a different unit."""
        return metric.unit.convert_to(other_unit, self[metric.tag])  # type: ignore

    def summarize(self) -> list[MetricResult]:
        """Summarize the metric results dict."""
        summary = []

        # Process all non-empty result dicts with DataFrames
        for result_dict in filter(None, self._results_dicts.values()):
            summary.extend(
                _create_metric_result(tag, values)
                for tag, values in result_dict.items()
            )

        return summary


def _create_metric_result(
    tag: MetricTagT, values: MetricDictValueTypeT
) -> MetricResult:
    """Create a MetricResult from a the current values of a metric."""
    from aiperf.metrics.metric_registry import MetricRegistry

    metric_class = MetricRegistry.get_class(tag)
    column = pd.Series(values) if not isinstance(values, pd.Series) else values

    # Handle empty column case
    if column.empty:
        # TODO: Should we return None here? The caller would need to handle this case.
        return MetricResult(
            tag=metric_class.tag,
            header=metric_class.header,
            unit=metric_class.unit,
        )

    # Handle single value case (quantiles might not work properly)
    if len(column) == 1:
        return MetricResult(
            tag=metric_class.tag,
            header=metric_class.header,
            unit=metric_class.unit,
            avg=metric_class.value_type.converter(column.iloc[0]),  # type: ignore
        )

    # Normal case with multiple values
    quantiles = column.quantile([0.01, 0.05, 0.25, 0.50, 0.75, 0.90, 0.95, 0.99])

    return MetricResult(
        tag=metric_class.tag,
        header=metric_class.header,
        unit=metric_class.unit,
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
        count=len(column),
    )
