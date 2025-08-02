# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

from typing import cast

from aiperf.common.enums import GenericMetricUnit, MetricFlags, MetricTag
from aiperf.common.models import ParsedResponseRecord
from aiperf.metrics.base_metrics import BaseAggregateMetric
from aiperf.metrics.metric_dicts import MetricRecordDict


class BenchmarkTokenCountMetric(BaseAggregateMetric[int]):
    """
    Post-processor for calculating the Benchmark Token Count metric. This is the total number of tokens processed by the benchmark.
    """

    tag = MetricTag.BENCHMARK_TOKEN_COUNT
    header = "Benchmark Token Count"
    unit = GenericMetricUnit.TOKENS
    larger_is_better = True
    flags = MetricFlags.TOKEN_BASED_ONLY
    required_metrics = {
        MetricTag.OSL,
    }

    def __init__(self):
        self.value: int = 0

    def _update_value(
        self,
        record: ParsedResponseRecord,
        record_metrics: MetricRecordDict,
    ) -> int:
        osl: int = cast(int, record_metrics[MetricTag.OSL])
        self.value += osl
        return self.value
