# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

import inspect
from abc import ABC
from typing import ClassVar, Generic, get_args, get_origin

from aiperf.common.enums.metric_enums import MetricFlags, MetricType, MetricValueType
from aiperf.common.models.record_models import ParsedResponseRecord
from aiperf.common.types import (
    MetricTagT,
    MetricUnitT,
    MetricValueTypeT,
    MetricValueTypeVarT,
)

# keep a reference to the type keyword to be able to still use it when "type" is also a variable name
_type = type


class BaseMetric(Generic[MetricValueTypeVarT], ABC):
    """A definition of a metric type."""

    tag: ClassVar[MetricTagT] = ""
    header: ClassVar[str] = ""
    unit: ClassVar[MetricUnitT] = None
    value_type: ClassVar[MetricValueType]  # Will be auto-detected
    larger_is_better: ClassVar[bool] = False
    type: ClassVar[MetricType] = MetricType.RECORD
    flags: ClassVar[MetricFlags] = MetricFlags.NONE
    required_metrics: ClassVar[set[MetricTagT]] = set()

    metric_interfaces: ClassVar[dict[MetricTagT, _type["BaseMetric"]]] = {}

    def __init_subclass__(cls, **kwargs):
        """
        This method is called when a class is subclassed from Metric.
        It automatically registers the subclass in the metric_interfaces
        dictionary using the `tag` class attribute.
        The `tag` attribute must be a non-empty string that uniquely identifies the
        metric type. Only concrete (non-abstract) classes will be registered.
        """

        super().__init_subclass__(**kwargs)

        # Only register concrete classes (not abstract ones)
        if inspect.isabstract(cls):
            return

        # Enforce that concrete subclasses are a subclass of BaseRecordMetric, BaseAggregateMetric, or BaseDerivedMetric
        if (
            not isinstance(cls, BaseRecordMetric)
            and not isinstance(cls, BaseAggregateMetric)
            and not isinstance(cls, BaseDerivedMetric)
        ):
            raise TypeError(
                f"Concrete metric class {cls.__name__} must be a subclass of BaseRecordMetric, BaseAggregateMetric, or BaseDerivedMetric"
            )

        # Enforce that subclasses define a non-empty tag
        if not cls.tag or not isinstance(cls.tag, str):
            raise TypeError(
                f"Concrete metric class {cls.__name__} must define a non-empty 'tag' class attribute"
            )

        # Check for duplicate tags
        if cls.tag in cls.metric_interfaces:
            raise ValueError(
                f"Metric tag '{cls.tag}' is already registered by {cls.metric_interfaces[cls.tag].__name__}"
            )

        # Auto-detect value type from generic parameter
        cls.value_type = cls._detect_value_type()

        cls.metric_interfaces[cls.tag] = cls

    @classmethod
    def get_all(cls) -> dict[str, _type["BaseMetric"]]:
        """Get all defined metric types."""
        return cls.metric_interfaces

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

    def _check_metrics(self, metrics: dict[MetricTagT, MetricValueTypeT]) -> None:
        """Check that the required metrics are available."""
        for tag in self.required_metrics:
            if tag not in metrics:
                raise ValueError(f"Missing required metric: '{tag}'")

    def has_flag(self, flag: MetricFlags) -> bool:
        """Check that the flags are valid."""
        return flag & self.flags == flag


class BaseRecordMetric(
    Generic[MetricValueTypeVarT], BaseMetric[MetricValueTypeVarT], ABC
):
    """A base class for record metrics."""

    type = MetricType.RECORD

    def parse_record(
        self, record: ParsedResponseRecord, metrics: dict[MetricTagT, MetricValueTypeT]
    ) -> MetricValueTypeVarT:
        """Parse a single record and return the metric value."""
        self._require_valid_record(record)
        self._check_metrics(metrics)
        return self._parse_record(record, metrics)

    def _parse_record(
        self, record: ParsedResponseRecord, metrics: dict[MetricTagT, MetricValueTypeT]
    ) -> MetricValueTypeVarT:
        """Parse a single record and return the metric value. This method is implemented by subclasses."""
        raise NotImplementedError("Subclasses must implement this method")


class BaseAggregateMetric(
    Generic[MetricValueTypeVarT], BaseMetric[MetricValueTypeVarT], ABC
):
    """A base class for aggregate metrics."""

    type = MetricType.AGGREGATE

    def update_value(
        self, record: ParsedResponseRecord, metrics: dict[MetricTagT, MetricValueTypeT]
    ) -> MetricValueTypeVarT:
        """Update the metric value."""
        self._require_valid_record(record)
        self._check_metrics(metrics)
        return self._update_value(record, metrics)

    def _update_value(
        self, record: ParsedResponseRecord, metrics: dict[MetricTagT, MetricValueTypeT]
    ) -> MetricValueTypeVarT:
        """Update the metric value. This method is implemented by subclasses."""
        raise NotImplementedError("Subclasses must implement this method")


class BaseDerivedMetric(
    Generic[MetricValueTypeVarT], BaseMetric[MetricValueTypeVarT], ABC
):
    """A base class for derived metrics."""

    type = MetricType.DERIVED

    def derive_value(
        self, metrics: dict[MetricTagT, MetricValueTypeT]
    ) -> MetricValueTypeVarT:
        """Derive the metric value."""
        self._check_metrics(metrics)
        return self._derive_value(metrics)

    def _derive_value(
        self, metrics: dict[MetricTagT, MetricValueTypeT]
    ) -> MetricValueTypeVarT:
        """Derive the metric value. This method is implemented by subclasses."""
        raise NotImplementedError("Subclasses must implement this method")
