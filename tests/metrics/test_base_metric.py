# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

import logging

from aiperf.common.enums import (
    MetricProcessingType,
    MetricTag,
    MetricTimeUnit,
    MetricValueType,
)
from aiperf.common.enums.metric_enums import MetricFlags
from aiperf.metrics.base_metric import BaseMetric

logging.basicConfig(level=logging.DEBUG)


class ExampleMetricDefinition(BaseMetric[int]):
    tag = MetricTag.ITL
    processing_type = MetricProcessingType.PER_REQUEST
    unit = MetricTimeUnit.NANOSECONDS
    larger_is_better = False
    header = "Inter-Token Latency"
    streaming_only = True
    required_metrics = {
        MetricTag.REQUEST_LATENCY,
        MetricTag.TTFT,
        MetricTag.OUTPUT_TOKEN_COUNT,
    }


def test_base_metric_value_type():
    class FloatListMetric(BaseMetric[list[float]]):
        tag = "FloatListMetric"

    assert FloatListMetric.value_type == MetricValueType.FLOAT_LIST

    class IntListMetric(BaseMetric[list[int]]):
        tag = "IntListMetric"

    assert IntListMetric.value_type == MetricValueType.INT_LIST

    class StrListMetric(BaseMetric[list[str]]):
        tag = "StrListMetric"

    assert StrListMetric.value_type == MetricValueType.STR_LIST

    class FloatMetric(BaseMetric[float]):
        tag = "FloatMetric"

    assert FloatMetric.value_type == MetricValueType.FLOAT

    class IntMetric(BaseMetric[int]):
        tag = "IntMetric"

    assert IntMetric.value_type == MetricValueType.INT

    class StrMetric(BaseMetric[str]):
        tag = "StrMetric"

    assert StrMetric.value_type == MetricValueType.STR


def test_metric_flags():
    f = MetricFlags.LARGER_IS_BETTER
    print(f.value)
    print(f.name)
    print(f & MetricFlags.LARGER_IS_BETTER)
    print(f & MetricFlags.SMALLER_IS_BETTER)
    print(f & MetricFlags.STREAMING_ONLY)
    print(f & MetricFlags.NONE)

    assert f & MetricFlags.LARGER_IS_BETTER == MetricFlags.LARGER_IS_BETTER
    assert f & MetricFlags.SMALLER_IS_BETTER == MetricFlags.NONE
    assert f & MetricFlags.STREAMING_ONLY == MetricFlags.NONE
    assert f & MetricFlags.NONE == MetricFlags.NONE
