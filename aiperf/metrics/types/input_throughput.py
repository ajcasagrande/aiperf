# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

from aiperf.common.enums import MetricFlags, MetricOverTimeUnit
from aiperf.common.models import ParsedResponseRecord
from aiperf.metrics import BaseRecordMetric
from aiperf.metrics.metric_dicts import MetricRecordDict
from aiperf.metrics.types.input_sequence_length import InputSequenceLengthMetric
from aiperf.metrics.types.time_to_first_token import TTFTMetric


class InputThroughputMetric(BaseRecordMetric[float]):
    """
    Post-processor for calculating Input Throughput metrics from records. This is only applicable to streaming responses.

    This is the time it takes for the client to receive the first token of the response from the server, after
    already receiving the 200 OK response.
    """

    tag = "input_throughput"
    header = "Input Throughput"
    unit = MetricOverTimeUnit.TOKENS_PER_SECOND
    flags = MetricFlags.STREAMING_TOKENS_ONLY | MetricFlags.LARGER_IS_BETTER
    required_metrics = {
        InputSequenceLengthMetric.tag,
        TTFTMetric.tag,
    }

    def _parse_record(
        self,
        record: ParsedResponseRecord,
        record_metrics: MetricRecordDict,
    ) -> float:
        """This method calculates the input throughput by subtracting the connection latency from the TTFT."""

        isl = record_metrics[InputSequenceLengthMetric.tag]
        ttft = record_metrics[TTFTMetric.tag]
        converted_ttft: float = TTFTMetric.unit.convert_to(  # type: ignore
            self.unit.time_unit, ttft,  # type: ignore
        )  # fmt: skip
        return isl / converted_ttft  # type: ignore
