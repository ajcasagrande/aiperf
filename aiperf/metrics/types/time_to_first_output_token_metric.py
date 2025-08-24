# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
from aiperf.common.enums import MetricFlags, MetricTimeUnit
from aiperf.common.exceptions import NoMetricValue
from aiperf.common.models import ParsedResponseRecord, ReasoningResponseData
from aiperf.metrics import BaseRecordMetric
from aiperf.metrics.metric_dicts import MetricRecordDict


class TimeToFirstOutputTokenMetric(BaseRecordMetric[int]):
    """
    Post-processor for calculating Time to First Output Token (TTFOT) metrics from records.

    This metric searches for the first output token in the responses, which is defined as the first response
    that contains output (answer) content.

    Formula:
        TTFOT = First Output Token Timestamp - Request Start Timestamp
    """

    tag = "ttfot"
    header = "Time to First Output Token"
    short_header = "TTFOT"
    unit = MetricTimeUnit.NANOSECONDS
    display_unit = MetricTimeUnit.MILLISECONDS
    flags = (
        MetricFlags.STREAMING_TOKENS_ONLY
        | MetricFlags.SUPPORTS_REASONING
        | MetricFlags.EXPERIMENTAL
    )
    required_metrics = None

    def _parse_record(
        self,
        record: ParsedResponseRecord,
        record_metrics: MetricRecordDict,
    ) -> int:
        """
        This method extracts the timestamps from the request start and the first output token in the given
        RequestRecord object, computes the difference (TTFOT), and returns the result.

        Raises:
            NoMetricValue: If the record does not have at least one response
            ValueError: If the first output token is before the request start timestamp.
        """
        # Find the first output token timestamp by looking for the first response that is not a reasoning response
        # or has content.
        first_output_token_ts: int | None = next(
            (
                response.perf_ns
                for response in record.responses
                if not isinstance(response.data, ReasoningResponseData)
                or response.data.content
            ),
            None,
        )
        if first_output_token_ts is None:
            raise NoMetricValue(
                "Record must have at least one output token to calculate TTFOT."
            )

        request_ts: int = record.request.start_perf_ns
        if first_output_token_ts < request_ts:
            raise ValueError(
                "First output token timestamp is before request start timestamp, cannot compute TTFOT."
            )
        return first_output_token_ts - request_ts
