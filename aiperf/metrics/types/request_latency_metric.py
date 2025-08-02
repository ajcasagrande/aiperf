# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

from aiperf.common.enums import MetricFlags, MetricTag, MetricTimeUnit
from aiperf.common.models import ParsedResponseRecord
from aiperf.metrics import BaseRecordMetric
from aiperf.metrics.metric_dicts import MetricRecordDict


class RequestLatencyMetric(BaseRecordMetric[int]):
    """
    Post-processor for calculating Request Latency metrics from records.
    """

    tag = MetricTag.REQUEST_LATENCY
    header = "Request Latency"
    unit = MetricTimeUnit.NANOSECONDS
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
        return final_response_ts - request_ts
