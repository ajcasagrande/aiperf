# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

import pytest

from aiperf.metrics.types.valid_request_count import (
    ValidRequestCountMetric,
)


def test_request_count_with_multiple_valid_records(parsed_response_record_builder):
    metric = ValidRequestCountMetric()
    records = (
        parsed_response_record_builder.with_request_start_time(0)
        .add_response(perf_ns=5)
        .new_record()
        .with_request_start_time(10)
        .add_response(perf_ns=15)
        .new_record()
        .with_request_start_time(20)
        .add_response(perf_ns=25)
        .build_all()
    )

    for record in records:
        metric.parse_record(record)

    assert metric.values() == 3


def test_request_count_invalid_record_raises():
    metric = ValidRequestCountMetric()
    with pytest.raises(ValueError, match="Invalid Record"):
        metric.parse_record(record=None)
