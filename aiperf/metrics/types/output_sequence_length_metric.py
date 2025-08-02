# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

from typing import cast

from aiperf.common.enums import GenericMetricUnit, MetricFlags, MetricTag
from aiperf.common.models import ParsedResponseRecord
from aiperf.metrics import BaseRecordMetric
from aiperf.metrics.metric_dicts import MetricRecordDict


class OutputSequenceLengthMetric(BaseRecordMetric[int]):
    """
    Post-processor for calculating Output Sequence Length (OSL) metrics from records.
    """

    tag = MetricTag.OSL
    header = "Output Sequence Length (OSL)"
    unit = GenericMetricUnit.TOKENS
    flags = MetricFlags.TOKEN_BASED_ONLY | MetricFlags.LARGER_IS_BETTER
    required_metrics = None

    def _validate_inputs(
        self, record: ParsedResponseRecord, record_metrics: MetricRecordDict
    ) -> None:
        """
        Checks if the record is valid for OSL calculation.

        Raises:
            ValueError: If the record does not have an output token count.
        """
        if record.output_token_count is None:
            raise ValueError("Output token count is missing in the record.")

    def _parse_record(
        self,
        record: ParsedResponseRecord,
        record_metrics: MetricRecordDict,
    ) -> int:
        return cast(int, record.output_token_count)
