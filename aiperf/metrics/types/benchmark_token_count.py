# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0


from aiperf.common.enums import GenericMetricUnit, MetricFlags, MetricTag
from aiperf.common.models import ParsedResponseRecord
from aiperf.metrics.base_aggregate_metric import BaseAggregateMetric
from aiperf.metrics.metric_dicts import MetricRecordDict


class BenchmarkTokenCountMetric(BaseAggregateMetric[int]):
    """
    Post-processor for calculating the Benchmark Token Count metric. This is the total number of tokens processed by the benchmark.
    """

    tag = MetricTag.BENCHMARK_TOKEN_COUNT
    header = "Benchmark Token Count"
    unit = GenericMetricUnit.TOKENS
    flags = (
        MetricFlags.PRODUCES_TOKENS_ONLY
        | MetricFlags.LARGER_IS_BETTER
        | MetricFlags.HIDDEN
    )
    required_metrics = {
        MetricTag.OSL,
    }

    def __init__(self):
        super().__init__(0)

    def _update_value(
        self,
        record: ParsedResponseRecord,
        record_metrics: MetricRecordDict,
    ) -> int:
        osl = record_metrics[MetricTag.OSL]
        self._value += osl  # type: ignore
        return self._value
