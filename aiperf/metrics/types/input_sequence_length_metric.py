#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0

from aiperf.common.enums import GenericMetricUnit, MetricFlags, MetricTag
from aiperf.common.models import ParsedResponseRecord
from aiperf.common.types import MetricTagT, MetricValueTypeT
from aiperf.metrics.base_metric import BaseRecordMetric


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

    def _parse_record(
        self,
        record: ParsedResponseRecord,
        metrics: dict[MetricTagT, MetricValueTypeT],
    ) -> int:
        if record.input_token_count is None:
            raise ValueError("Input Token Count is not available for the record.")
        return record.input_token_count
