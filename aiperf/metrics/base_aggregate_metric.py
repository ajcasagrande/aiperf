# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
from abc import ABC, abstractmethod
from typing import Generic

from aiperf.common.enums import MetricType, MetricValueTypeVarT
from aiperf.common.models import ParsedResponseRecord
from aiperf.metrics.base_metric import BaseMetric
from aiperf.metrics.metric_dicts import MetricRecordDict

# TODO: For the aggregate metrics, how are we going to coordinate the values from a distributed manner?
#       we need a way to merge/aggregate the values from the different processes.
#       For this, we may consider having a "merge" or "aggregate" method that is called by the ResultsProcessor.
#       This method would be called after all the records have been processed, and would be responsible for merging/aggregating the values from the different processes.


class BaseAggregateMetric(
    Generic[MetricValueTypeVarT], BaseMetric[MetricValueTypeVarT], ABC
):
    """A base class for aggregate metrics. These metrics keep track of a value or list of values over time.
    They are updated for each record, and the value should be based on previous values.
    They will produce a single final value (or list of values).

    NOTE: The generic type can be a list of values, or a single value.

    Examples:
    ```python
    class RequestCountMetric(BaseAggregateMetric[int]):
        # ... Metric attributes ...

        def __init__(self):
            super().__init__(0)

        def _update_value(self, record: ParsedResponseRecord, record_metrics: MetricRecordDict) -> int:
            self._value += 1
            return self._value
    ```
    """

    type = MetricType.AGGREGATE

    # NOTE: We are using this as a workaround to not have to implement a default_value method.
    def __init__(self, default_value: MetricValueTypeVarT) -> None:
        """Initialize the metric with a default value."""
        self._value: MetricValueTypeVarT = default_value

    @property
    def current_value(self) -> MetricValueTypeVarT:
        """Get the current value of the metric."""
        return self._value

    def update_value(
        self, record: ParsedResponseRecord, record_metrics: MetricRecordDict
    ) -> MetricValueTypeVarT:
        """Update the metric value.
        This method is called after the required metrics are checked, so it can assume that the required metrics are available.
        Raises:
            ValueError: If the metric cannot be computed for the given inputs.
        """
        self._require_valid_record(record)
        self._check_metrics(record_metrics)
        self._validate_inputs(record, record_metrics)
        return self._update_value(record, record_metrics)

    @abstractmethod
    def _update_value(
        self, record: ParsedResponseRecord, record_metrics: MetricRecordDict
    ) -> MetricValueTypeVarT:
        """Update the metric value. This method is implemented by subclasses.
        This method is called after the required metrics are checked, so it can assume that the required metrics are available.
        This method is called after the record is checked, so it can assume that the record is valid.
        """
        raise NotImplementedError("Subclasses must implement this method")

    def _validate_inputs(
        self, record: ParsedResponseRecord, record_metrics: MetricRecordDict
    ) -> None:
        """Check that the metric can be computed for the given inputs. This method can be implemented by subclasses.
        This method is called after the required metrics are checked, so it can assume that the required metrics are available.
        Raises:
            ValueError: If the metric cannot be computed for the given inputs.
        """
        pass

    @abstractmethod
    def _aggregate_value(self, value: MetricValueTypeVarT) -> MetricValueTypeVarT:
        """Aggregate the metric value. This method is implemented by subclasses.
        This method is called with values from different processes, and should be implemented to aggregate the values.
        It is the responsibility of each metric class to implement how values from different processes are aggregated.
        """
        raise NotImplementedError("Subclasses must implement this method")
