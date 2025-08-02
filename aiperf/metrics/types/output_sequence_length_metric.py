# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

from aiperf.common.enums import GenericMetricUnit, MetricFlags, MetricTag
from aiperf.common.models import ParsedResponseRecord
from aiperf.common.types import MetricTagT, MetricValueTypeT
from aiperf.metrics.base_metric import BaseRecordMetric


class OutputSequenceLengthMetric(BaseRecordMetric[int]):
    """
    Post-processor for calculating Output Sequence Length (OSL) metrics from records.
    """

    tag = MetricTag.OSL
    header = "Output Sequence Length (OSL)"
    unit = GenericMetricUnit.TOKENS
    larger_is_better = True
    flags = MetricFlags.NONE
    required_metrics = set()

    def _parse_record(
        self,
        record: ParsedResponseRecord,
        metrics: dict[MetricTagT, MetricValueTypeT],
    ) -> int:
        if record.output_token_count is None:
            raise ValueError("Output token count is missing in the record.")
        return record.output_token_count
