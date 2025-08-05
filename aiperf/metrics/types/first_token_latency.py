# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

from aiperf.common.enums import MetricFlags, MetricTimeUnit
from aiperf.common.models import ParsedResponseRecord
from aiperf.metrics import BaseRecordMetric
from aiperf.metrics.metric_dicts import MetricRecordDict
from aiperf.metrics.types.connect_latency import ConnectionLatencyMetric
from aiperf.metrics.types.time_to_first_token import TTFTMetric


class FirstTokenLatencyMetric(BaseRecordMetric[int]):
    """
    Post-processor for calculating First Token Latency metrics from records. This is only applicable to streaming responses.

    This is the time it takes for the client to receive the first token of the response from the server, after
    already receiving the 200 OK response.

    Formula:
        First Token Latency = Time to First Token - Connection Latency
    """

    tag = "first_token_latency"
    header = "First Token Latency"
    unit = MetricTimeUnit.NANOSECONDS
    display_unit = MetricTimeUnit.MILLISECONDS
    flags = MetricFlags.STREAMING_TOKENS_ONLY
    required_metrics = {
        ConnectionLatencyMetric.tag,
        TTFTMetric.tag,
    }

    def _parse_record(
        self,
        record: ParsedResponseRecord,
        record_metrics: MetricRecordDict,
    ) -> int:
        """This method calculates the first token latency by subtracting the connection latency from the TTFT."""

        connection_latency = record_metrics[ConnectionLatencyMetric.tag]
        ttft = record_metrics[TTFTMetric.tag]
        return ttft - connection_latency  # type: ignore
