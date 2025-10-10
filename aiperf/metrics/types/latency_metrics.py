# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

from aiperf.common.enums import MetricFlags, MetricTimeUnit
from aiperf.common.models import ParsedResponseRecord
from aiperf.metrics import BaseRecordMetric
from aiperf.metrics.metric_dicts import MetricRecordDict
from aiperf.metrics.types.time_to_first_output_metric import TimeToFirstOutputMetric


class RequestLatencyMetric(BaseRecordMetric[int]):
    """
    Post-processor for calculating Request Latency metrics from records.

    Formula:
        Request Latency = Final Response Timestamp - Request Start Timestamp
    """

    tag = "request_latency"
    header = "Request Latency"
    short_header = "Req Latency"
    unit = MetricTimeUnit.NANOSECONDS
    display_unit = MetricTimeUnit.MILLISECONDS
    display_order = 300
    flags = MetricFlags.NONE
    required_metrics = None

    def _parse_record(
        self,
        record: ParsedResponseRecord,
        record_metrics: MetricRecordDict,
    ) -> int:
        """
        This method extracts the request and last response timestamps, and calculates the differences in time.
        """
        request_ts: int = record.start_perf_ns
        final_response_ts: int = record.responses[-1].perf_ns
        if final_response_ts < request_ts:
            raise ValueError("Final response timestamp is less than request timestamp.")
        return final_response_ts - request_ts


class ReasoningLatencyMetric(BaseRecordMetric[int]):
    """
    Post-processor for calculating Reasoning Latency metrics from records. This is the time from when the first
    reasoning token is output to when the first non-reasoning token is output.

    Formula:
        Reasoning Latency = Time to First Output - Request Start Timestamp
    """

    tag = "reasoning_latency"
    header = "Reasoning Latency"
    unit = MetricTimeUnit.NANOSECONDS
    display_unit = MetricTimeUnit.MILLISECONDS
    flags = (
        MetricFlags.STREAMING_TOKENS_ONLY
        | MetricFlags.SUPPORTS_REASONING
        | MetricFlags.NO_CONSOLE
    )
    required_metrics = {
        TimeToFirstOutputMetric.tag,
    }

    def _parse_record(
        self,
        record: ParsedResponseRecord,
        record_metrics: MetricRecordDict,
    ) -> int:
        """
        This method extracts the request and first output timestamps, and calculates the differences in time.
        """
        request_ts: int = record.start_perf_ns
        first_output_ts: int = record_metrics.get_or_raise(TimeToFirstOutputMetric.tag)
        if first_output_ts < request_ts:
            raise ValueError("First output timestamp is less than request timestamp.")
        return first_output_ts - request_ts


class OutputLatencyMetric(BaseRecordMetric[int]):
    """
    Post-processor for calculating Output Latency metrics from records. This is the time from when the first
    non-reasoning token is output to when the final token is output.

    Formula:
        Output Latency = Final Response Timestamp - Time to First Output
    """

    tag = "output_latency"
    header = "Output Latency"
    unit = MetricTimeUnit.NANOSECONDS
    display_unit = MetricTimeUnit.MILLISECONDS
    flags = MetricFlags.STREAMING_TOKENS_ONLY | MetricFlags.NO_CONSOLE
    required_metrics = TimeToFirstOutputMetric.tag

    def _parse_record(
        self,
        record: ParsedResponseRecord,
        record_metrics: MetricRecordDict,
    ) -> int:
        """
        This method extracts the first output (non-reasoning) and final response timestamps, and calculates the differences in time.
        """
        first_output_ts: int = record_metrics.get_or_raise(TimeToFirstOutputMetric.tag)
        final_response_ts: int = record.responses[-1].perf_ns
        if final_response_ts < first_output_ts:
            raise ValueError(
                "Final response timestamp is less than first output timestamp."
            )
        return final_response_ts - first_output_ts
