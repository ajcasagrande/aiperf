# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

from aiperf.common.enums import GenericMetricUnit, MetricFlags
from aiperf.metrics.base_derived_metric import BaseDerivedMetric
from aiperf.metrics.metric_dicts import MetricResultsDict
from aiperf.metrics.types.error_request_count import ErrorRequestCountMetric
from aiperf.metrics.types.total_request_count_metric import TotalRequestCountMetric


class ErrorRateMetric(BaseDerivedMetric[float]):
    """
    This is the error rate of the benchmark, as a percentage.

    Formula:
        ```
        Error Rate = Error Request Count / Total Request Count
        ```
    """

    tag = "error_rate"
    header = "Error Rate"
    short_header = "Error Rate"
    short_header_hide_unit = True
    unit = GenericMetricUnit.PERCENT
    flags = MetricFlags.HIDDEN
    required_metrics = {
        TotalRequestCountMetric.tag,
        ErrorRequestCountMetric.tag,
    }

    def _derive_value(
        self,
        metric_results: MetricResultsDict,
    ) -> float:
        total_request_count = metric_results.get_or_raise(TotalRequestCountMetric)
        error_request_count = metric_results.get_or_raise(ErrorRequestCountMetric)
        return (error_request_count / total_request_count) * 100.0  # type: ignore
