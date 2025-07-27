# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

from aiperf.common.enums.base_enums import CaseInsensitiveStrEnum


class MetricTimeType(CaseInsensitiveStrEnum):
    """Defines the time types for metrics."""

    NANOSECONDS = "nanoseconds"
    MILLISECONDS = "milliseconds"
    SECONDS = "seconds"

    def short_name(self) -> str:
        """Get the short name for the time type."""
        _short_name_map = {
            MetricTimeType.NANOSECONDS: "ns",
            MetricTimeType.MILLISECONDS: "ms",
            MetricTimeType.SECONDS: "s",
        }
        return _short_name_map[self]


class MetricType(CaseInsensitiveStrEnum):
    METRIC_OF_RECORDS = "metric_of_records"
    METRIC_OF_METRICS = "metric_of_metrics"
    METRIC_OF_BOTH = "metric_of_both"


class MetricTag(CaseInsensitiveStrEnum):
    BENCHMARK_DURATION = "benchmark_duration"
    ISL = "isl"
    ITL = "itl"
    MAX_RESPONSE = "max_response"
    MIN_REQUEST = "min_request"
    OSL = "osl"
    OUTPUT_TOKEN_THROUGHPUT = "output_token_throughput"
    OUTPUT_TOKEN_THROUGHPUT_PER_USER = "output_token_throughput_per_user"
    REQUEST_COUNT = "request_count"
    REQUEST_LATENCY = "request_latency"
    REQUEST_THROUGHPUT = "request_throughput"
    TTFT = "ttft"
    TTST = "ttst"
