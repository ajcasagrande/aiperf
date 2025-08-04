# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

from collections import deque
from collections.abc import Callable
from enum import Flag
from typing import Any, TypeAlias, TypeVar

import pandas as pd
from pydantic import BaseModel

from aiperf.common.enums.base_enums import (
    BasePydanticBackedStrEnum,
    BasePydanticEnumInfo,
    CaseInsensitiveStrEnum,
)

MetricValueTypeT: TypeAlias = str | int | float | list[float] | list[int] | list[str]
MetricValueTypeVarT = TypeVar("MetricValueTypeVarT", bound=MetricValueTypeT)
MetricDictValueTypeT: TypeAlias = MetricValueTypeT | deque[MetricValueTypeT] | pd.Series


class MetricSizeUnitInfo(BasePydanticEnumInfo):
    """Information about a metric size unit."""

    long_name: str
    num_bytes: int


class MetricSizeUnit(BasePydanticBackedStrEnum):
    """Defines the size types for metrics."""

    BYTES = MetricSizeUnitInfo(
        tag="B",
        long_name="bytes",
        num_bytes=1,
    )
    KILOBYTES = MetricSizeUnitInfo(
        tag="KB",
        long_name="kilobytes",
        num_bytes=1024,
    )
    MEGABYTES = MetricSizeUnitInfo(
        tag="MB",
        long_name="megabytes",
        num_bytes=1024 * 1024,
    )
    GIGABYTES = MetricSizeUnitInfo(
        tag="GB",
        long_name="gigabytes",
        num_bytes=1024 * 1024 * 1024,
    )
    TERABYTES = MetricSizeUnitInfo(
        tag="TB",
        long_name="terabytes",
        num_bytes=1024 * 1024 * 1024 * 1024,
    )

    @property
    def info(self) -> MetricSizeUnitInfo:
        """Get the info for the metric size unit."""
        return self._info  # type: ignore

    @property
    def num_bytes(self) -> int:
        """The number of bytes in the metric size unit."""
        return self.info.num_bytes

    @property
    def long_name(self) -> str:
        """The long name of the metric size unit."""
        return self.info.long_name

    def convert_to(self, other_unit: "MetricSizeUnit", size: int | float) -> float:
        """Convert a value from this unit to another unit."""
        return size * (self.num_bytes / other_unit.num_bytes)


class SizeWithUnit(BaseModel):
    """A size with a corresponding unit. Can be converted to other units of size."""

    size: int | float
    unit: MetricSizeUnit

    def convert_to(self, other_unit: "MetricSizeUnit") -> "SizeWithUnit":
        """Convert the value to another unit of size."""
        return SizeWithUnit(
            size=self.size * (self.unit.num_bytes / other_unit.num_bytes),
            unit=other_unit,
        )


class MetricTimeUnitInfo(BasePydanticEnumInfo):
    """Information about a metric time unit."""

    long_name: str
    per_second: int


class MetricTimeUnit(BasePydanticBackedStrEnum):
    """Defines the time types for metrics."""

    NANOSECONDS = MetricTimeUnitInfo(
        tag="ns",
        long_name="nanoseconds",
        per_second=1_000_000_000,
    )
    MICROSECONDS = MetricTimeUnitInfo(
        tag="us",
        long_name="microseconds",
        per_second=1_000_000,
    )
    MILLISECONDS = MetricTimeUnitInfo(
        tag="ms",
        long_name="milliseconds",
        per_second=1_000,
    )
    SECONDS = MetricTimeUnitInfo(
        tag="s",
        long_name="seconds",
        per_second=1,
    )

    @property
    def info(self) -> MetricTimeUnitInfo:
        """Get the info for the metric time unit."""
        return self._info  # type: ignore

    @property
    def per_second(self) -> int:
        """How many of these units there are in one second. Used as a conversion factor to convert to other units."""
        return self.info.per_second

    @property
    def long_name(self) -> str:
        """The long name of the metric time unit."""
        return self.info.long_name

    def convert_to(self, other_unit: "MetricTimeUnit", value: int | float) -> float:
        """Convert a value from this unit to another unit."""
        return value * (other_unit.per_second / self.per_second)


class TimeWithUnit(BaseModel):
    """A duration of time with a corresponding unit. Can be converted to other units of time."""

    value: int | float
    unit: MetricTimeUnit

    def convert_to(self, other_unit: "MetricTimeUnit") -> "TimeWithUnit":
        """Convert the value to another unit of time."""
        return TimeWithUnit(
            value=self.value * (other_unit.per_second / self.unit.per_second),
            unit=other_unit,
        )


class GenericMetricUnit(CaseInsensitiveStrEnum):
    """Defines the units for generic metrics."""

    PERCENT = "percent"
    REQUESTS = "requests"
    TOKENS = "tokens"
    USER = "user"
    USERS = "users"


class MetricOverTimeUnitInfo(BasePydanticEnumInfo):
    """Information about a metric over time unit."""

    primary_unit: GenericMetricUnit | MetricSizeUnit
    time_unit: MetricTimeUnit
    third_unit: GenericMetricUnit | None = None


class MetricOverTimeUnit(BasePydanticBackedStrEnum):
    """Defines the units for metrics that are a generic unit over a specific time unit."""

    REQUESTS_PER_SECOND = MetricOverTimeUnitInfo(
        tag="req/s",
        primary_unit=GenericMetricUnit.REQUESTS,
        time_unit=MetricTimeUnit.SECONDS,
    )
    TOKENS_PER_SECOND = MetricOverTimeUnitInfo(
        tag="tokens/s",
        primary_unit=GenericMetricUnit.TOKENS,
        time_unit=MetricTimeUnit.SECONDS,
    )
    BYTES_PER_SECOND = MetricOverTimeUnitInfo(
        tag="bytes/s",
        primary_unit=MetricSizeUnit.BYTES,
        time_unit=MetricTimeUnit.SECONDS,
    )
    TOKENS_PER_SECOND_PER_USER = MetricOverTimeUnitInfo(
        tag="tokens/s/user",
        primary_unit=GenericMetricUnit.TOKENS,
        time_unit=MetricTimeUnit.SECONDS,
        third_unit=GenericMetricUnit.USER,
    )

    @property
    def info(self) -> MetricOverTimeUnitInfo:
        """Get the info for the metric over time unit."""
        return self._info  # type: ignore

    @property
    def primary_unit(self) -> GenericMetricUnit | MetricSizeUnit:
        """Get the primary unit."""
        return self.info.primary_unit

    @property
    def time_unit(self) -> MetricTimeUnit:
        """Get the time unit."""
        return self.info.time_unit

    @property
    def third_unit(self) -> GenericMetricUnit | None:
        """Get the third unit (if applicable)."""
        return self.info.third_unit


class MetricTag(CaseInsensitiveStrEnum):
    BENCHMARK_DURATION = "benchmark_duration"
    BENCHMARK_TOKEN_COUNT = "benchmark_token_count"
    ISL = "isl"
    ITL = "itl"
    MAX_RESPONSE = "max_response"
    MIN_REQUEST = "min_request"
    OSL = "osl"
    OUTPUT_TOKEN_THROUGHPUT = "output_token_throughput"
    OUTPUT_TOKEN_THROUGHPUT_PER_USER = "output_token_throughput_per_user"
    VALID_REQUEST_COUNT = "valid_request_count"
    REQUEST_LATENCY = "request_latency"
    REQUEST_THROUGHPUT = "request_throughput"
    TTFT = "ttft"
    TTST = "ttst"


class MetricType(CaseInsensitiveStrEnum):
    """Defines the possible types of metrics."""

    RECORD = "record"
    """Metrics that provide a distinct value for each request. Every request that comes in will produce a new value that is not affected by any other requests.
    These metrics can be tracked over time and compared to each other.
    Examples: request latency, ISL, ITL, OSL, etc."""

    AGGREGATE = "aggregate"
    """Metrics that keep track of one or more values over time, that are updated for each request, such as total counts, min/max values, etc.
    These metrics may or may not change each request, and are affected by other requests.
    Examples: min/max request latency, total request count, benchmark duration, etc."""

    DERIVED = "derived"
    """Metrics that are purely derived from other metrics as a summary, and do not require per-request values.
    Examples: request throughput, output token throughput, etc."""


class MetricValueTypeInfo(BasePydanticEnumInfo):
    """Information about a metric value type."""

    default_factory: Callable[[], MetricValueTypeT]
    converter: Callable[[Any], MetricValueTypeT]


class MetricValueType(BasePydanticBackedStrEnum):
    """Defines the possible types of values for metrics.

    NOTE: The string representation is important here, as it is used to automatically determine the type
    based on the python generic type definition.
    """

    FLOAT = MetricValueTypeInfo(
        tag="float",
        default_factory=float,
        converter=float,
    )
    INT = MetricValueTypeInfo(
        tag="int",
        default_factory=int,
        converter=int,
    )
    STR = MetricValueTypeInfo(
        tag="str",
        default_factory=str,
        converter=str,
    )
    FLOAT_LIST = MetricValueTypeInfo(
        tag="list[float]",
        default_factory=list[float],
        converter=lambda values: [
            float(value) for value in (values if isinstance(values, list) else [values])
        ],
    )
    INT_LIST = MetricValueTypeInfo(
        tag="list[int]",
        default_factory=list[int],
        converter=lambda values: [
            int(value) for value in (values if isinstance(values, list) else [values])
        ],
    )
    STR_LIST = MetricValueTypeInfo(
        tag="list[str]",
        default_factory=list[str],
        converter=lambda values: [
            str(value) for value in (values if isinstance(values, list) else [values])
        ],
    )

    @property
    def info(self) -> MetricValueTypeInfo:
        """Get the info for the metric value type."""
        return self._info  # type: ignore

    @property
    def default_factory(self) -> Callable[[], MetricValueTypeT]:
        """Get the default value generator for the metric value type."""
        return self.info.default_factory

    @property
    def converter(self) -> Callable[[Any], MetricValueTypeT]:
        """Get the converter for the metric value type."""
        return self.info.converter

    @classmethod
    def from_type(cls, type: type[MetricValueTypeT]) -> "MetricValueType":
        """Get the MetricValueType for a given type."""
        # If the type is a simple type like float or int, we have to use __name__.
        # This is because using str() on float or int will return <class 'float'> or <class 'int'>, etc.
        type_name = type.__name__
        if type_name == "list":
            # However, if the type is a list, we have to use str() to get the list type as well, e.g. list[int]
            type_name = str(type)
        return MetricValueType(type_name)


class MetricFlags(Flag):
    """Defines the possible flags for metrics that are used to determine how they are processed or grouped.
    These flags are intended to be an easy way to group metrics, or turn on/off certain features.

    Note that the flags are a bitmask, so they can be combined using the bitwise OR operator (`|`).
    For example, to create a flag that is both `STREAMING_ONLY` and `HIDDEN`, you can do:
    ```python
    MetricFlags.STREAMING_ONLY | MetricFlags.HIDDEN
    ```

    To check if a metric has a flag, you can use the `has_flags` method.
    For example, to check if a metric has both the `STREAMING_ONLY` and `HIDDEN` flags, you can do:
    ```python
    metric.has_flags(MetricFlags.STREAMING_ONLY | MetricFlags.HIDDEN)
    ```

    To check if a metric does not have a flag(s), you can use the `missing_flags` method.
    For example, to check if a metric does not have the `STREAMING_ONLY` or `HIDDEN` flags, you can do:
    ```python
    metric.missing_flags(MetricFlags.STREAMING_ONLY | MetricFlags.HIDDEN)
    ```
    """

    # NOTE: The flags are a bitmask, so they must be powers of 2.

    NONE = 0
    """No flags."""

    STREAMING_ONLY = 1 << 0
    """Metrics that are only applicable to streamed responses."""

    ERROR_ONLY = 1 << 1
    """Metrics that are only applicable to error records. By default, metrics are only computed if the record is valid.
    If this flag is set, the metric will only be computed if the record is invalid."""

    PRODUCES_TOKENS_ONLY = 1 << 2
    """Metrics that are only applicable when profiling an endpoint that produces tokens."""

    HIDDEN = 1 << 3
    """Metrics that are not applicable to the user. These metrics are not displayed in the UI."""

    LARGER_IS_BETTER = 1 << 4
    """Metrics that are better when the value is larger. By default, it is assumed that metrics are
    better when the value is smaller."""

    STREAMING_TOKENS_ONLY = STREAMING_ONLY | PRODUCES_TOKENS_ONLY
    """Metrics that are only applicable to streamed responses and token-based endpoints.
    This is a convenience flag that is the combination of the `STREAMING_ONLY` and `PRODUCES_TOKENS_ONLY` flags."""

    def has_flags(self, flags: "MetricFlags") -> bool:
        """Return True if the metric has ALL of the given flag(s) (regardless of other flags)."""
        return flags & self == flags

    def missing_flags(self, flags: "MetricFlags") -> bool:
        """Return True if the metric does not have ANY of the given flag(s) (regardless of other flags). It will
        return False if the metric has ANY of the given flags. If the input flags are NONE, it will return True."""
        if flags == MetricFlags.NONE or self == MetricFlags.NONE:
            return True  # NONE means there are no flags to check, so we return True

        # NOTE: We need to check each possible flag separately, as we want to return False if the metric has ANY of
        #       the given flags. If we simply & the flags, that would only return False if the metric has ALL of the
        #       given flags.
        return not any(
            flags.has_flags(flag) and self.has_flags(flag) for flag in MetricFlags
        )
