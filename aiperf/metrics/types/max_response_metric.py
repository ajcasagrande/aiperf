# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
from typing import cast

from aiperf.common.enums import MetricFlags, MetricTag, MetricTimeUnit
from aiperf.common.models import ParsedResponseRecord
from aiperf.metrics import BaseAggregateMetric
from aiperf.metrics.metric_dicts import MetricRecordDict


class MaxResponseMetric(BaseAggregateMetric[int]):
    """
    Post-processor for calculating the maximum response time stamp metric from records.
    """

    tag = MetricTag.MAX_RESPONSE
    header = "Maximum Response Timestamp"
    unit = MetricTimeUnit.NANOSECONDS
    flags = MetricFlags.HIDDEN
    required_metrics = {
        MetricTag.REQUEST_LATENCY,
    }

    def __init__(self) -> None:
        self.value: int = 0

    def _update_value(
        self,
        record: ParsedResponseRecord,
        record_metrics: MetricRecordDict,
    ) -> int:
        """
        Updates the maximum response timestamp metric.
        """
        # Compute the final response timestamp by adding the request latency to the request timestamp.
        # We do this because we want wall-clock timestamps, and the only one we have that is wall-clock
        # time is the timestamp_ns for the start of the request, so we need to use that and work from there.
        request_latency: int = cast(int, record_metrics[MetricTag.REQUEST_LATENCY])
        final_response_ts: int = record.timestamp_ns + request_latency

        if final_response_ts > self.value:
            self.value = final_response_ts
        return self.value
