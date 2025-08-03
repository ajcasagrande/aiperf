# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
from abc import ABC, abstractmethod
from typing import Generic

from aiperf.common.enums import MetricType, MetricValueTypeVarT
from aiperf.metrics.base_metric import BaseMetric
from aiperf.metrics.metric_dicts import MetricResultsDict


class BaseDerivedMetric(
    Generic[MetricValueTypeVarT], BaseMetric[MetricValueTypeVarT], ABC
):
    """A base class for derived metrics. These metrics are computed from other metrics,
    and do not require any knowledge of the individual records. The final results will be a single computed value (or list of values).

    NOTE: The generic type can be a list of values, or a single value.

    Examples:
    ```python
    class RequestThroughputMetric(BaseDerivedMetric[float]):
        # ... Metric attributes ...
        # ... Input validation ...

        def _derive_value(self, metric_results: MetricResultsDict) -> float:
            request_count = metric_results[MetricTag.REQUEST_COUNT]
            benchmark_duration = metric_results[MetricTag.BENCHMARK_DURATION]
            return request_count / (benchmark_duration / NANOS_PER_SECOND)
    ```
    """

    type = MetricType.DERIVED

    def derive_value(self, metric_results: MetricResultsDict) -> MetricValueTypeVarT:
        """Derive the metric value."""
        self._check_metrics(metric_results)
        self._validate_inputs(metric_results)
        return self._derive_value(metric_results)

    @abstractmethod
    def _derive_value(self, metric_results: MetricResultsDict) -> MetricValueTypeVarT:
        """Derive the metric value. This method is implemented by subclasses.
        This method is called after the required metrics are checked, so it can assume that the required metrics are available.
        """
        raise NotImplementedError("Subclasses must implement this method")

    def _validate_inputs(self, metric_results: MetricResultsDict) -> None:
        """Check that the metric can be computed for the given inputs. This method can be implemented by subclasses.
        This method is called after the required metrics are checked, so it can assume that the required metrics are available.
        Raises:
            ValueError: If the metric cannot be computed for the given inputs.
        """
        pass
