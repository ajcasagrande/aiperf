# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
from abc import ABC, abstractmethod
from typing import Generic

from aiperf.common.enums import MetricType
from aiperf.common.models import ParsedResponseRecord
from aiperf.common.types import MetricValueTypeVarT
from aiperf.metrics import BaseMetric, MetricRecordDict


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
            self.value = 0

        def _update_value(self, record: ParsedResponseRecord, record_metrics: MetricRecordDict) -> int:
            self.value += 1
            return self.value
    ```
    """

    type = MetricType.AGGREGATE

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
