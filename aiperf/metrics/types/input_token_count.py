# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0


from aiperf.common.enums import GenericMetricUnit, MetricFlags
from aiperf.common.models import ParsedResponseRecord
from aiperf.metrics.base_aggregate_metric import BaseAggregateMetric
from aiperf.metrics.metric_dicts import MetricRecordDict
from aiperf.metrics.types.input_sequence_length_metric import InputSequenceLengthMetric


class InputTokenCountMetric(BaseAggregateMetric[int]):
    """
    Post-processor for calculating the Input Token Count metric. This is the total number of tokens processed by the benchmark.

    Formula:
        Input Token Count = Sum of Input Sequence Lengths
    """

    tag = "input_token_count"
    header = "Input Token Count"
    short_header = "Tokens"
    short_header_hide_unit = True
    unit = GenericMetricUnit.TOKENS
    flags = (
        MetricFlags.PRODUCES_TOKENS_ONLY
        | MetricFlags.LARGER_IS_BETTER
        | MetricFlags.HIDDEN
    )
    required_metrics = {
        InputSequenceLengthMetric.tag,
    }

    def _parse_record(
        self,
        record: ParsedResponseRecord,
        record_metrics: MetricRecordDict,
    ) -> int:
        # NOTE: We don't need to update the value here, because we are just counting the number of tokens.
        #       The value is updated in the ResultsProcessor via the `_aggregate_value` method.
        return record_metrics[InputSequenceLengthMetric.tag]  # type: ignore

    def _aggregate_value(self, value: int) -> None:
        """Aggregate the metric value. For this metric, we just sum the values from the different processes."""
        self._value += value
