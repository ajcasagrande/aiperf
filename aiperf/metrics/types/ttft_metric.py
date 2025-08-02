# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
from aiperf.common.enums import MetricFlags, MetricTag, MetricTimeUnit
from aiperf.common.models import ParsedResponseRecord
from aiperf.metrics.base_metrics import BaseRecordMetric
from aiperf.metrics.metric_dicts import MetricRecordDict


class TTFTMetric(BaseRecordMetric[int]):
    """
    Post-processor for calculating Time to First Token (TTFT) metrics from records.
    """

    tag = MetricTag.TTFT
    header = "Time to First Token (TTFT)"
    unit = MetricTimeUnit.NANOSECONDS
    flags = MetricFlags.STREAMING_ONLY | MetricFlags.TOKEN_BASED_ONLY
    required_metrics = None

    def _validate_inputs(
        self, record: ParsedResponseRecord, record_metrics: MetricRecordDict
    ) -> None:
        """
        Checks if the record is valid for TTFT calculation.

        Raises:
            ValueError: If the record does not have at least one response.
        """
        if len(record.responses) < 1:
            raise ValueError(
                "Record must have at least one response to calculate TTFT."
            )

    def _parse_record(
        self,
        record: ParsedResponseRecord,
        record_metrics: MetricRecordDict,
    ) -> int:
        """
        This method extracts the timestamps from the request start and the first response in the given
        RequestRecord object, computes the difference (TTFT), and returns the result.
        """
        request_ts: int = record.request.start_perf_ns
        first_response_ts: int = record.responses[0].perf_ns
        return first_response_ts - request_ts
