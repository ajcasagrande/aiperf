# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

from aiperf.common.enums import MetricFlags, MetricTimeUnit
from aiperf.common.models import ParsedResponseRecord
from aiperf.metrics import BaseRecordMetric
from aiperf.metrics.metric_dicts import MetricRecordDict


class StreamSetupLatencyMetric(BaseRecordMetric[int]):
    """
    Post-processor for calculating Stream Setup Latency metrics from records. This is only applicable to streaming responses.

    This is the time it takes for the client to send the request and receive the 200 OK response from the server,
    before any SSE content is received. It measures the request processing and stream initialization time.

    Formula:
        Stream Setup Latency = Stream Start Timestamp - Request Start Timestamp
    """

    tag = "stream_setup_latency"
    header = "Stream Setup Latency"
    unit = MetricTimeUnit.NANOSECONDS
    display_unit = MetricTimeUnit.MILLISECONDS
    flags = MetricFlags.STREAMING_ONLY | MetricFlags.INTERNAL
    required_metrics = None

    def _parse_record(
        self,
        record: ParsedResponseRecord,
        record_metrics: MetricRecordDict,
    ) -> int:
        """This method extracts the request and receive start timestamps, and calculates the stream setup time."""

        if record.request.recv_start_perf_ns is None:
            raise ValueError(
                "Stream setup latency metric requires a recv_start_perf_ns"
            )

        request_ts: int = record.start_perf_ns
        stream_start_ts: int = record.request.recv_start_perf_ns
        return stream_start_ts - request_ts
