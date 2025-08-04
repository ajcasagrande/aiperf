# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

from aiperf.metrics.types.benchmark_duration import BenchmarkDurationMetric
from aiperf.metrics.types.max_response_timestamp import MaxResponseTimestampMetric
from aiperf.metrics.types.min_request_timestamp import MinRequestTimestampMetric


def test_add_multiple_records(parsed_response_record_builder):
    metrics = {}
    metrics[MinRequestTimestampMetric.tag] = MinRequestTimestampMetric()
    metrics[MaxResponseTimestampMetric.tag] = MaxResponseTimestampMetric()
    records = (
        parsed_response_record_builder.with_request_start_time(10)
        .add_response(perf_ns=15)
        .new_record()
        .with_request_start_time(20)
        .add_response(perf_ns=25)
        .new_record()
        .with_request_start_time(30)
        .add_response(perf_ns=40)
        .build_all()
    )

    for record in records:
        for metric in metrics.values():
            value = metric._parse_record(record=record, record_metrics=None)
            metric._aggregate_value(value=value)

    benchmark_duration_metric = BenchmarkDurationMetric()
    assert (
        benchmark_duration_metric._derive_value(metric_results=metrics) == 30
    )  # 40 - 10
