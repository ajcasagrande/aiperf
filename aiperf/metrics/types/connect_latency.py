# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

from aiperf.common.enums import MetricFlags, MetricTag, MetricTimeUnit
from aiperf.common.models import ParsedResponseRecord
from aiperf.metrics import BaseRecordMetric
from aiperf.metrics.metric_dicts import MetricRecordDict


class ConnectionLatencyMetric(BaseRecordMetric[int]):
    """
    Post-processor for calculating Connection Latency metrics from records. This is only applicable to streaming responses.

    This is the time it takes for the client to connect to the server and receive the 200 OK response, before
    any SSE messages are received. It evaluates the time for the server to acknowledge the request. This value
    can be used to evaluate the performance of the server's connection handling, as well as the performance of the
    client's connection handling.
    """

    tag = MetricTag.CONNECTION_LATENCY
    header = "Connection Latency"
    unit = MetricTimeUnit.NANOSECONDS
    display_unit = MetricTimeUnit.MILLISECONDS
    flags = MetricFlags.STREAMING_ONLY
    required_metrics = None

    def _parse_record(
        self,
        record: ParsedResponseRecord,
        record_metrics: MetricRecordDict,
    ) -> int:
        """This method extracts the request and connect timestamps, and calculates the differences in time."""

        if record.request.recv_start_perf_ns is None:
            raise ValueError("Connection latency metric requires a recv_start_perf_ns")

        request_ts: int = record.start_perf_ns
        connect_ts: int = record.request.recv_start_perf_ns
        return connect_ts - request_ts
