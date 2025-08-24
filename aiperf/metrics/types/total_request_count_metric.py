# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

from aiperf.common.enums import GenericMetricUnit, MetricFlags
from aiperf.metrics.base_derived_metric import BaseDerivedMetric
from aiperf.metrics.metric_dicts import MetricResultsDict
from aiperf.metrics.types.error_request_count import ErrorRequestCountMetric
from aiperf.metrics.types.request_count_metric import RequestCountMetric


class TotalRequestCountMetric(BaseDerivedMetric[int]):
    """
    This is the total number of requests processed by the benchmark.

    Formula:
        ```
        Total Request Count = Valid Request Count + Error Request Count
        ```
    """

    tag = "total_request_count"
    header = "Total Request Count"
    short_header = "Total Req"
    short_header_hide_unit = True
    unit = GenericMetricUnit.REQUESTS
    flags = MetricFlags.HIDDEN | MetricFlags.LARGER_IS_BETTER
    required_metrics = {
        RequestCountMetric.tag,
        ErrorRequestCountMetric.tag,
    }

    def _derive_value(
        self,
        metric_results: MetricResultsDict,
    ) -> int:
        request_count = metric_results.get_or_raise(RequestCountMetric)
        error_request_count = metric_results.get_or_raise(ErrorRequestCountMetric)
        return request_count + error_request_count  # type: ignore
