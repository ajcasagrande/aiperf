# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

from aiperf.common.enums.metric_enums import MetricTimeUnit
from aiperf.common.models.record_models import ParsedResponseRecord
from aiperf.metrics.base_record_metric import BaseRecordMetric
from aiperf.metrics.metric_dicts import MetricRecordDict


class InterTokenLatencyList(BaseRecordMetric[list[int]]):
    """A record metric that calculates the inter-token latency for a list of tokens."""

    tag = "itl_list"
    header = "Inter-Token Latency List"
    unit = MetricTimeUnit.NANOSECONDS
    display_unit = MetricTimeUnit.MILLISECONDS

    def _parse_record(
        self,
        record: ParsedResponseRecord,
        record_metrics: MetricRecordDict,
    ) -> list[int]:
        """Process the record and return the list of inter-token latencies."""
        return [
            record.responses[i].perf_ns - record.responses[i - 1].perf_ns
            for i in range(1, len(record.responses))
        ]

    def _validate_inputs(
        self, record: ParsedResponseRecord, record_metrics: MetricRecordDict
    ) -> None:
        """Validate the inputs for the metric."""
        if len(record.responses) < 2:
            raise ValueError("Inter-Token Latency List requires at least 2 responses")
