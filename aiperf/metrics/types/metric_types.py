# # SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# # SPDX-License-Identifier: Apache-2.0

# from aiperf.common.enums.metric_enums import (
#     MetricFlags,
#     MetricTag,
#     MetricTimeUnit,
#     MetricType,
# )
# from aiperf.common.models.record_models import ParsedResponseRecord
# from aiperf.common.types import MetricTagT, MetricValueTypeT
# from aiperf.metrics.base_metric import BaseMetric


# class BenchmarkDurationMetric(BaseMetric[int]):
#     """Metric defining the entire duration of a benchmark run."""

#     header = "Benchmark Duration"
#     tag = MetricTag.BENCHMARK_DURATION
#     type = MetricType.DERIVED
#     unit = MetricTimeUnit.NANOSECONDS
#     larger_is_better = False
#     flags = MetricFlags.NONE

#     def _parse_record(
#         self, record: ParsedResponseRecord, metrics: dict[MetricTagT, MetricValueTypeT]
#     ) -> MetricValueTypeT:
#         """Parse a single record and return the metric value."""
#         return record.benchmark_duration


# class InputSequenceLengthMetric(BaseMetric[int]):
#     """Metric defining the length of the input sequence."""

#     header = "Input Sequence Length"
#     tag = MetricTag.ISL
#     type = MetricType.RECORD
#     unit = None
#     larger_is_better = False  # TODO: True?
#     flags = MetricFlags.NONE


# class InterTokenLatencyMetric(BaseMetric[float]):
#     """Metric defining the latency between tokens."""

#     header = "Inter Token Latency"
#     tag = MetricTag.ITL
#     type = MetricType.RECORD
#     unit = MetricTimeUnit.NANOSECONDS
#     larger_is_better = False
#     flags = MetricFlags.STREAMING_ONLY
#     required_metrics = {
#         MetricTag.REQUEST_LATENCY,
#         MetricTag.TTFT,
#         MetricTag.OSL,
#     }


# class MaxResponseMetric(BaseMetric[int]):
#     """Metric defining the maximum response time."""

#     header = "Max Response"
#     tag = MetricTag.MAX_RESPONSE
#     type = MetricType.AGGREGATE
#     unit = MetricTimeUnit.NANOSECONDS
#     larger_is_better = False
#     flags = MetricFlags.NONE


# class MinRequestMetric(BaseMetric[int]):
#     """Metric defining the minimum request time."""

#     header = "Min Request"
#     tag = MetricTag.MIN_REQUEST
#     type = MetricType.AGGREGATE
#     unit = MetricTimeUnit.NANOSECONDS
#     larger_is_better = False
#     flags = MetricFlags.NONE


# class OutputSequenceLengthMetric(BaseMetric[int]):
#     """Metric defining the length of the output sequence."""

#     header = "Output Sequence Length"
#     tag = MetricTag.OSL
#     type = MetricType.RECORD
#     unit = None
#     larger_is_better = True
#     flags = MetricFlags.NONE


# class OutputTokenCountMetric(BaseMetric[int]):
#     """Metric defining the number of tokens in the output."""

#     header = "Output Token Count"
#     tag = MetricTag.OSL
#     type = MetricType.RECORD
#     unit = None
#     larger_is_better = True
#     flags = MetricFlags.NONE


# class OutputTokenThroughputMetric(BaseMetric[float]):
#     """Metric defining the throughput of the output."""

#     header = "Output Token Throughput"
#     tag = MetricTag.OUTPUT_TOKEN_THROUGHPUT
#     type = MetricType.DERIVED
#     unit = None
#     larger_is_better = True
#     flags = MetricFlags.NONE
#     required_metrics = {
#         MetricTag.OSL,
#         MetricTag.BENCHMARK_DURATION,
#     }


# class OutputTokenThroughputPerUserMetric(BaseMetric[float]):
#     """Metric defining the throughput of the output per user."""

#     header = "Output Token Throughput Per User"
#     tag = MetricTag.OUTPUT_TOKEN_THROUGHPUT_PER_USER
#     type = MetricType.DERIVED
#     unit = None
#     larger_is_better = True
#     flags = MetricFlags.STREAMING_ONLY
#     required_metrics = {
#         MetricTag.ITL,
#     }


# class RequestCountMetric(BaseMetric[int]):
#     """Metric defining the number of requests."""

#     header = "Request Count"
#     tag = MetricTag.REQUEST_COUNT
#     type = MetricType.AGGREGATE
#     unit = None
#     larger_is_better = True
#     flags = MetricFlags.NONE


# class RequestLatencyMetric(BaseMetric[float]):
#     """Metric defining the latency of a request."""

#     header = "Request Latency"
#     tag = MetricTag.REQUEST_LATENCY
#     type = MetricType.RECORD
#     unit = MetricTimeUnit.NANOSECONDS
#     larger_is_better = False
#     flags = MetricFlags.NONE


# class RequestThroughputMetric(BaseMetric[float]):
#     """Metric defining the throughput of requests."""

#     header = "Request Throughput"
#     tag = MetricTag.REQUEST_THROUGHPUT
#     type = MetricType.DERIVED
#     unit = None
#     larger_is_better = True
#     flags = MetricFlags.NONE
#     required_metrics = {
#         MetricTag.REQUEST_COUNT,
#         MetricTag.BENCHMARK_DURATION,
#     }


# class TimeToFirstTokenMetric(BaseMetric[float]):
#     """Metric defining the time to the first token."""

#     header = "Time to First Token (TTFT)"
#     tag = MetricTag.TTFT
#     type = MetricType.RECORD
#     unit = MetricTimeUnit.NANOSECONDS
#     larger_is_better = False
#     flags = MetricFlags.STREAMING_ONLY


# class TimeToSecondTokenMetric(BaseMetric[float]):
#     """Metric defining the time to the second token."""

#     header = "Time to Second Token (TTST)"
#     tag = MetricTag.TTST
#     type = MetricType.RECORD
#     unit = MetricTimeUnit.NANOSECONDS
#     larger_is_better = False
#     flags = MetricFlags.STREAMING_ONLY
