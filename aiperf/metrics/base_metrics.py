# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

import inspect
from abc import ABC, abstractmethod
from typing import ClassVar, Generic, get_args, get_origin

from aiperf.common.enums.metric_enums import MetricFlags, MetricType, MetricValueType
from aiperf.common.models.record_models import ParsedResponseRecord
from aiperf.common.types import MetricTagT, MetricUnitT, MetricValueTypeVarT
from aiperf.metrics.metric_dicts import (
    BaseMetricDict,
    MetricRecordDict,
    MetricResultsDict,
)
from aiperf.metrics.metric_registry import MetricRegistry


class BaseMetric(Generic[MetricValueTypeVarT], ABC):
    """A definition of a metric type."""

    tag: ClassVar[MetricTagT] = ""
    header: ClassVar[str] = ""
    unit: ClassVar[MetricUnitT] = None
    value_type: ClassVar[
        MetricValueType
    ]  # Will be auto-detected based on generic type parameter
    larger_is_better: ClassVar[bool] = False
    type: ClassVar[MetricType]  # Will be set by base subclasses
    flags: ClassVar[MetricFlags] = MetricFlags.NONE
    required_metrics: ClassVar[set[MetricTagT] | None] = None

    def __init_subclass__(cls, **kwargs):
        """
        This method is called when a class is subclassed from Metric.
        It automatically registers the subclass in the MetricRegistry
        dictionary using the `tag` class attribute.
        The `tag` attribute must be a non-empty string that uniquely identifies the
        metric type. Only concrete (non-abstract) classes will be registered.
        """

        super().__init_subclass__(**kwargs)

        # Only register concrete classes (not abstract ones)
        if inspect.isabstract(cls):
            return

        # Enforce that concrete subclasses are a subclass of BaseRecordMetric, BaseAggregateMetric, or BaseDerivedMetric
        valid_base_classes = {
            "BaseRecordMetric",
            "BaseAggregateMetric",
            "BaseDerivedMetric",
        }
        class_names_in_mro = {base.__name__ for base in cls.__mro__}
        if not valid_base_classes.intersection(class_names_in_mro):
            raise TypeError(
                f"Concrete metric class {cls.__name__} must be a subclass of BaseRecordMetric, BaseAggregateMetric, or BaseDerivedMetric"
            )

        # Enforce that subclasses define a non-empty tag
        if not cls.tag or not isinstance(cls.tag, str):
            raise TypeError(
                f"Concrete metric class {cls.__name__} must define a non-empty 'tag' class attribute"
            )

        # Check for duplicate tags
        if cls.tag in MetricRegistry.all_tags():
            raise ValueError(
                f"Metric tag '{cls.tag}' is already registered by {MetricRegistry.get_class(cls.tag).__name__}"
            )

        # Auto-detect value type from generic parameter
        cls.value_type = cls._detect_value_type()

        MetricRegistry.register_metric(cls)

    @classmethod
    def _detect_value_type(cls) -> MetricValueType:
        """Automatically detect the MetricValueType from the generic type parameter."""
        # Look through the class hierarchy for the first Generic[Type] definition
        for base in cls.__orig_bases__:  # type: ignore
            if get_origin(base) is not None:
                args = get_args(base)
                if args:
                    # the first argument is the generic type
                    generic_type = args[0]
                    # if the generic type is a simple type like float or int, we have to use __name__
                    # this is because using str() on float or int will return <class 'float'> or <class 'int'>, etc.
                    name = generic_type.__name__
                    if name == "list":
                        # However, if the generic type is a list, we have to use str() to get the list type as well, e.g. list[int]
                        name = str(generic_type)
                    return MetricValueType(name)

        raise ValueError(
            f"Unable to detect the value type for {cls.__name__}. Please check the generic type parameter."
        )

    def _require_valid_record(self, record: ParsedResponseRecord) -> None:
        """Check that the record is valid."""
        if (not record or not record.valid) and not self.has_flag(
            MetricFlags.ERROR_METRIC
        ):
            raise ValueError("Invalid Record")

    def _check_metrics(self, metrics: BaseMetricDict) -> None:
        """Check that the required metrics are available."""
        if self.required_metrics is None:
            return
        for tag in self.required_metrics:
            if tag not in metrics:
                raise ValueError(f"Missing required metric: '{tag}'")

    @classmethod
    def has_flag(cls, flag: MetricFlags) -> bool:
        """Return True if the metric has the given flag(s) (regardless of other flags)."""
        return flag & cls.flags == flag


class BaseRecordMetric(
    Generic[MetricValueTypeVarT], BaseMetric[MetricValueTypeVarT], ABC
):
    """A base class for record-based metrics. These metrics are computed for each record,
    and are independent of other records. The final results will be a list of values, one for each record.

    NOTE: Set the generic type to be the type of the individual values, and NOT a list, unless the metric produces
    a list for every record. In that case, the result will be a list of lists.
    """

    type = MetricType.RECORD

    def parse_record(
        self, record: ParsedResponseRecord, record_metrics: MetricRecordDict
    ) -> MetricValueTypeVarT:
        """Parse a single record and return the metric value."""
        self._require_valid_record(record)
        self._check_metrics(record_metrics)
        self._validate_inputs(record, record_metrics)
        return self._parse_record(record, record_metrics)

    @abstractmethod
    def _parse_record(
        self, record: ParsedResponseRecord, record_metrics: MetricRecordDict
    ) -> MetricValueTypeVarT:
        """Parse a single record and return the metric value. This method is implemented by subclasses.
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


class BaseAggregateMetric(
    Generic[MetricValueTypeVarT], BaseMetric[MetricValueTypeVarT], ABC
):
    """A base class for aggregate metrics. These metrics are computed for each record,
    but are dependent on other records, and will vary over time. They will produce a single final value (or list of values)."""

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


class BaseDerivedMetric(
    Generic[MetricValueTypeVarT], BaseMetric[MetricValueTypeVarT], ABC
):
    """A base class for derived metrics. These metrics are computed from other metrics,
    and do not require any knowledge of the individual records. The final results will be a single computed value (or list of values).

    NOTE: The generic type can be a list of values, or a single value.
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
