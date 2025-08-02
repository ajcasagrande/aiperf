# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

from enum import Flag

from aiperf.common.enums.base_enums import CaseInsensitiveStrEnum


class MetricTimeUnit(CaseInsensitiveStrEnum):
    """Defines the time types for metrics."""

    NANOSECONDS = "ns"
    MICROSECONDS = "us"
    MILLISECONDS = "ms"
    SECONDS = "s"


class GenericMetricUnit(CaseInsensitiveStrEnum):
    """Defines the units for generic metrics."""

    BYTES = "bytes"
    PERCENT = "percent"
    REQUESTS = "requests"
    TOKENS = "tokens"
    USER = "user"
    USERS = "users"


class MetricOverTimeUnit(CaseInsensitiveStrEnum):
    """Defines the units for metrics that are a generic unit over a specific time unit."""

    REQUESTS_PER_SECOND = "req/s"
    TOKENS_PER_SECOND = "tokens/s"
    BYTES_PER_SECOND = "bytes/s"
    # TODO: Is there a better way to represent tokens/s/user metric type?
    TOKENS_PER_SECOND_PER_USER = "tokens/s/user"

    def generic_unit(self) -> GenericMetricUnit | None:
        """Get the generic unit for the metric."""
        _generic_unit_map = {
            MetricOverTimeUnit.REQUESTS_PER_SECOND: GenericMetricUnit.REQUESTS,
            MetricOverTimeUnit.TOKENS_PER_SECOND: GenericMetricUnit.TOKENS,
            MetricOverTimeUnit.BYTES_PER_SECOND: GenericMetricUnit.BYTES,
            MetricOverTimeUnit.TOKENS_PER_SECOND_PER_USER: GenericMetricUnit.TOKENS,
        }
        return _generic_unit_map[self]

    def time_unit(self) -> MetricTimeUnit | None:
        """Get the time unit for the metric."""
        _time_unit_map = {
            MetricOverTimeUnit.REQUESTS_PER_SECOND: MetricTimeUnit.SECONDS,
            MetricOverTimeUnit.TOKENS_PER_SECOND: MetricTimeUnit.SECONDS,
            MetricOverTimeUnit.BYTES_PER_SECOND: MetricTimeUnit.SECONDS,
            MetricOverTimeUnit.TOKENS_PER_SECOND_PER_USER: MetricTimeUnit.SECONDS,
        }
        return _time_unit_map[self]


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


class MetricValueType(CaseInsensitiveStrEnum):
    """Defines the possible types of values for metrics.

    NOTE: The string representation is important here, as it is used to automatically determine the type
    based on the python generic type definition.
    """

    FLOAT = "float"
    INT = "int"
    STR = "str"
    FLOAT_LIST = "list[float]"
    INT_LIST = "list[int]"
    STR_LIST = "list[str]"


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

    TOKEN_BASED_ONLY = 1 << 2
    """Metrics that are only applicable when profiling token-based endpoints."""

    HIDDEN = 1 << 3
    """Metrics that are not applicable to the user. These metrics are not displayed in the UI."""

    LARGER_IS_BETTER = 1 << 4
    """Metrics that are better when the value is larger. By default, it is assumed that metrics are
    better when the value is smaller."""

    STREAMING_TOKENS_ONLY = STREAMING_ONLY | TOKEN_BASED_ONLY
    """Metrics that are only applicable to streamed responses and token-based endpoints.
    This is a convenience flag that is the combination of the `STREAMING_ONLY` and `TOKEN_BASED_ONLY` flags."""

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
