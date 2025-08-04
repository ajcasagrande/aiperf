# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

from collections import deque
from collections.abc import Iterator
from itertools import chain

import pandas as pd

from aiperf.common.enums import MetricType
from aiperf.common.enums.metric_enums import MetricValueTypeT
from aiperf.common.models.record_models import MetricResult
from aiperf.common.types import MetricTagT
from aiperf.metrics.metric_registry import MetricRegistry


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
        self._results_dicts: dict[MetricType, dict[MetricTagT, MetricValueTypeT] | dict[MetricTagT, deque[MetricValueTypeT]]] = {
            MetricType.RECORD: {},
            MetricType.AGGREGATE: {},
            MetricType.DERIVED: {},
        }  # fmt: skip

    def _validate_and_get_metric_type(self, key: MetricTagT) -> MetricType:
        """Validate key and return its metric type."""
        try:
            metric_type = MetricRegistry.get_type(key)
        except ValueError:
            raise ValueError(f"Metric {key} not found in metric classes") from None

        if metric_type not in self._results_dicts:
            raise ValueError(f"Metric {key} is not a valid metric type")

        return metric_type

    def __getitem__(
        self, key: MetricTagT
    ) -> MetricValueTypeT | deque[MetricValueTypeT]:
        """Get the value of a metric."""
        for result_dict in self._results_dicts.values():
            if key in result_dict:
                return result_dict[key]
        raise KeyError(f"Metric {key} not found in metric results")

    def __setitem__(
        self, key: MetricTagT, value: MetricValueTypeT | deque[MetricValueTypeT]
    ) -> None:
        """Set the value of a metric."""
        metric_type = self._validate_and_get_metric_type(key)
        self._results_dicts[metric_type][key] = value  # type: ignore

    def __contains__(self, key: MetricTagT) -> bool:
        """Check if a metric is in the metric results dict."""
        return any(key in result_dict for result_dict in self._results_dicts.values())

    def __iter__(self) -> Iterator[MetricTagT]:
        """Iterate over all of the metric results dicts."""
        return iter(
            chain.from_iterable(
                result_dict.keys() for result_dict in self._results_dicts.values()
            )
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
        self, key: MetricTagT, default: MetricValueTypeT | deque[MetricValueTypeT]
    ) -> MetricValueTypeT | deque[MetricValueTypeT]:
        """Set a default value for a metric."""
        metric_type = self._validate_and_get_metric_type(key)

        if key not in self._results_dicts[metric_type]:
            self._results_dicts[metric_type][key] = default  # type: ignore
        return self._results_dicts[metric_type][key]

    def update(self, metric_dict: BaseMetricDict) -> None:
        """Update the metric results dicts with the values from another dict."""
        for key, value in metric_dict.items():
            metric_type = self._validate_and_get_metric_type(key)

            if metric_type in (MetricType.AGGREGATE, MetricType.DERIVED):
                self._results_dicts[metric_type][key] = value  # type: ignore
            elif metric_type == MetricType.RECORD:
                self._results_dicts[metric_type].setdefault(key, deque()).append(value)  # type: ignore

    def summarize(self) -> list[MetricResult]:
        """Summarize the metric results dict."""
        summary = []

        # Summarize the metrics using a DataFrame
        for result_dict in self._results_dicts.values():
            if not result_dict:
                continue

            df = pd.DataFrame(result_dict)
            for tag in result_dict:
                summary.append(_metric_result_from_dataframe(df, tag))

        return summary


def _metric_result_from_dataframe(df: pd.DataFrame, tag: MetricTagT) -> MetricResult:
    """Create a Record from a DataFrame."""
    metric_class = MetricRegistry.get_class(tag)
    column = df[tag]

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
        single_value = metric_class.value_type.converter(column.iloc[0])
        return MetricResult(
            tag=metric_class.tag,
            header=metric_class.header,
            unit=metric_class.unit,
            avg=single_value,
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
