# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

from aiperf.common.enums import MetricFlags, MetricTag, MetricTimeUnit
from aiperf.common.models import ParsedResponseRecord
from aiperf.metrics import BaseRecordMetric
from aiperf.metrics.metric_dicts import MetricRecordDict


class FirstTokenLatencyMetric(BaseRecordMetric[int]):
    """
    Post-processor for calculating First Token Latency metrics from records. This is only applicable to streaming responses.

    This is the time it takes for the client to receive the first token of the response from the server, after
    already receiving the 200 OK response.
    """

    tag = MetricTag.FIRST_TOKEN_LATENCY
    header = "First Token Latency"
    unit = MetricTimeUnit.NANOSECONDS
    display_unit = MetricTimeUnit.MILLISECONDS
    flags = MetricFlags.STREAMING_TOKENS_ONLY
    required_metrics = {
        MetricTag.CONNECTION_LATENCY,
        MetricTag.TTFT,
    }

    def _parse_record(
        self,
        record: ParsedResponseRecord,
        record_metrics: MetricRecordDict,
    ) -> int:
        """This method calculates the first token latency by subtracting the connection latency from the TTFT."""

        connection_latency = record_metrics[MetricTag.CONNECTION_LATENCY]
        ttft = record_metrics[MetricTag.TTFT]
        return ttft - connection_latency  # type: ignore
