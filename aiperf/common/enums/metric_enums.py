# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

from enum import Enum, Flag, auto

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

    TOKENS = "tokens"
    REQUESTS = "requests"


class LegacyMetricType(Enum):
    METRIC_OF_RECORDS = auto()
    METRIC_OF_METRICS = auto()
    METRIC_OF_BOTH = auto()


class MetricTag(CaseInsensitiveStrEnum):
    BENCHMARK_DURATION = "benchmark_duration"
    ISL = "isl"
    ITL = "itl"
    MAX_RESPONSE = "max_response"
    MIN_REQUEST = "min_request"
    OSL = "osl"
    OUTPUT_TOKEN_COUNT = "output_token_count"
    OUTPUT_TOKEN_THROUGHPUT = "output_token_throughput"
    OUTPUT_TOKEN_THROUGHPUT_PER_USER = "output_token_throughput_per_user"
    REQUEST_COUNT = "request_count"
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


class MetricProcessingType(CaseInsensitiveStrEnum):
    """Defines the possible types of processing for metrics."""

    PER_REQUEST = "per_request"
    """Metrics that provide a value for each request."""

    PER_REQUEST_UPDATES = "per_request_updates"
    """Metrics """

    PER_PROFILE_RUN = "per_profile_run"
    """Metrics that are computed for each profile run, that encompasses multiple requests."""

    PER_SWEEP = "per_sweep"
    """Metrics that are computed for an entire sweep, that encompasses multiple profile runs."""

    PER_BENCHMARK_SUITE = "per_benchmark_suite"
    """Metrics that are computed for an entire benchmark suite, that encompasses one or more sweeps and or profile runs."""


class MetricUpdateType(CaseInsensitiveStrEnum):
    """Defines the possible types of updates for metrics."""

    PER_REQUEST = "per_request"
    """Metrics that are supposed to be updated for each request."""

    PER_PROFILE_RUN = "per_profile_run"
    """Metrics that are supposed to be updated for each profile run."""


class MetricOutputType(CaseInsensitiveStrEnum):
    """Defines the possible types of output for metrics."""

    PER_REQUEST = "per_request"
    """Metrics that are supposed to be output for each request."""

    PER_PROFILE_RUN = "per_profile_run"
    """Metrics that are supposed to be output for each profile run."""


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


class MetricFlags(int, Flag):
    """Defines the possible flags for metrics that are used to determine how they are processed or grouped.
    These flags are intended to be an easy way to group metrics, or turn on/off certain features.
    """

    NONE = 0x00
    """No flags."""

    STREAMING_ONLY = 0x01
    """Metrics that are only applicable to streaming requests."""

    ERROR_METRIC = 0x02
    """Metrics that are used to track errors."""
