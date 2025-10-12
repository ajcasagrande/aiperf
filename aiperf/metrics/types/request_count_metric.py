# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

from aiperf.common.enums import GenericMetricUnit, MetricFlags
from aiperf.metrics.base_aggregate_counter_metric import BaseAggregateCounterMetric
from aiperf.metrics.base_derived_metric import BaseDerivedMetric
from aiperf.metrics.metric_dicts import MetricResultsDict
from aiperf.metrics.types.error_request_count import ErrorRequestCountMetric


class RequestCountMetric(BaseAggregateCounterMetric[int]):
    """
    This is the total number of valid requests processed by the benchmark.
    It is incremented for each valid request.

    Formula:
        ```
        Request Count = Sum(Valid Requests)
        ```
    """

    tag = "request_count"
    header = "Request Count"
    short_header = "Requests"
    short_header_hide_unit = True
    unit = GenericMetricUnit.REQUESTS
    display_order = 1000
    flags = MetricFlags.LARGER_IS_BETTER
    required_metrics = None


class TotalRequestCountMetric(BaseDerivedMetric[int]):
    """
    This is the total number of requests processed by the benchmark including errors.
    It is the sum of the request count and error request count.

    Formula:
        ```
        Total Request Count = Request Count + Error Request Count
        ```
    """

    tag = "total_request_count"
    header = "Total Request Count"
    short_header = "Total Requests"
    short_header_hide_unit = True
    unit = GenericMetricUnit.REQUESTS
    flags = MetricFlags.LARGER_IS_BETTER
    required_metrics = {RequestCountMetric.tag, ErrorRequestCountMetric.tag}

    def _derive_value(self, metric_results: MetricResultsDict) -> int:
        """Derive the metric value as the sum of the request count and error request count."""
        request_count = metric_results[RequestCountMetric.tag]
        error_count = metric_results[ErrorRequestCountMetric.tag]
        return request_count + error_count
