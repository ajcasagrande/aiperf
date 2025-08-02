# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

from enum import Flag

from aiperf.common.enums.base_enums import CaseInsensitiveStrEnum


class MetricTimeUnit(CaseInsensitiveStrEnum):
    """Defines the time types for metrics."""

    NANOSECONDS = "nanoseconds"
    MILLISECONDS = "milliseconds"
    SECONDS = "seconds"

    def short_name(self) -> str:
        """Get the short name for the time type."""
        _short_name_map = {
            MetricTimeUnit.NANOSECONDS: "ns",
            MetricTimeUnit.MILLISECONDS: "ms",
            MetricTimeUnit.SECONDS: "s",
        }
        return _short_name_map[self]


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
    """Metrics that are purely derived from other metrics, and do not require per-request values.
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
    """

    NONE = 0x00
    """No flags."""

    STREAMING_ONLY = 0x01
    """Metrics that are only applicable to streamed responses."""

    ERROR_METRIC = 0x02
    """Metrics that are used to track errors. These metrics should only by computed if the record is invalid.
    By default, metrics are only computed if the record is valid."""

    TOKEN_BASED_ONLY = 0x04
    """Metrics that are only applicable when profiling token-based endpoints."""
