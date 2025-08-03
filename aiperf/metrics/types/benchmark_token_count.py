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

    def _parse_record(
        self,
        record: ParsedResponseRecord,
        record_metrics: MetricRecordDict,
    ) -> int:
        # NOTE: We don't need to update the value here, because we are just counting the number of tokens.
        #       The value is updated in the ResultsProcessor via the `_aggregate_value` method.
        return record_metrics[MetricTag.OSL]  # type: ignore

    def _aggregate_value(self, value: int) -> int:
        """Aggregate the metric value. For this metric, we just sum the values from the different processes."""
        self._value += value
        return self._value
