#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0

from typing import cast

from aiperf.common.enums import GenericMetricUnit, MetricFlags, MetricTag
from aiperf.common.models import ParsedResponseRecord
from aiperf.metrics.base_metric import BaseRecordMetric
from aiperf.metrics.metric_dicts import MetricRecordDict


class InputSequenceLengthMetric(BaseRecordMetric[int]):
    """
    Post-processor for calculating Input Sequence Length (ISL) metrics from records.
    """

    tag = MetricTag.ISL
    header = "Input Sequence Length (ISL)"
    unit = GenericMetricUnit.TOKENS
    larger_is_better = True
    flags = MetricFlags.TOKEN_BASED_ONLY
    required_metrics = set()

    def _validate_inputs(
        self, record: ParsedResponseRecord, record_metrics: MetricRecordDict
    ) -> None:
        """
        Checks if the record is valid for ISL calculation.

        Raises:
            ValueError: If the record does not have an input token count.
        """
        if record.input_token_count is None:
            raise ValueError("Input Token Count is not available for the record.")

    def _parse_record(
        self,
        record: ParsedResponseRecord,
        record_metrics: MetricRecordDict,
    ) -> int:
        return cast(int, record.input_token_count)
