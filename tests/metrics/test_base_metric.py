# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

import logging
from unittest.mock import patch

from aiperf.common.enums import (
    MetricTimeUnit,
    MetricValueType,
)
from aiperf.common.enums.metric_enums import MetricFlags
from aiperf.metrics.base_record_metric import BaseRecordMetric
from aiperf.metrics.metric_registry import MetricRegistry as MetricRegistry
from aiperf.metrics.types.output_sequence_length import OutputSequenceLengthMetric
from aiperf.metrics.types.request_latency import RequestLatencyMetric
from aiperf.metrics.types.time_to_first_token import TTFTMetric

logging.basicConfig(level=logging.DEBUG)


class ExampleMetricDefinition(BaseRecordMetric[int]):
    tag = "itl"
    unit = MetricTimeUnit.NANOSECONDS
    display_unit = MetricTimeUnit.MILLISECONDS
    header = "Inter-Token Latency"
    flags = MetricFlags.STREAMING_TOKENS_ONLY
    required_metrics = {
        RequestLatencyMetric.tag,
        TTFTMetric.tag,
        OutputSequenceLengthMetric.tag,
    }


@patch("inspect.isabstract", return_value=False)
def test_base_metric_value_type(patch_isabstract):
    # If no generic type is provided, the value type will default to float.
    class SimpleFloatMetric(BaseRecordMetric):
        tag = "SimpleFloatMetric"

    assert SimpleFloatMetric.value_type == MetricValueType.FLOAT

    class FloatMetric(BaseRecordMetric[float]):
        tag = "FloatMetric"

    assert FloatMetric.value_type == MetricValueType.FLOAT

    class IntMetric(BaseRecordMetric[int]):
        tag = "IntMetric"

    assert IntMetric.value_type == MetricValueType.INT

    class FloatListMetric(BaseRecordMetric[list[float]]):
        tag = "FloatListMetric"
        value_type = MetricValueType.FLOAT_LIST

    assert FloatListMetric.value_type == MetricValueType.FLOAT_LIST

    class IntListMetric(BaseRecordMetric[list[int]]):
        tag = "IntListMetric"
        value_type = MetricValueType.INT_LIST

    assert IntListMetric.value_type == MetricValueType.INT_LIST


def test_metric_flags():
    flags = MetricFlags.LARGER_IS_BETTER | MetricFlags.STREAMING_ONLY

    assert flags.has_flags(MetricFlags.LARGER_IS_BETTER)
    assert flags.has_flags(MetricFlags.STREAMING_ONLY)
    assert flags.has_flags(MetricFlags.NONE)
    assert not flags.has_flags(MetricFlags.PRODUCES_TOKENS_ONLY)
    assert not flags.has_flags(MetricFlags.SUPPORTS_AUDIO_ONLY)
    assert not flags.has_flags(MetricFlags.SUPPORTS_IMAGE_ONLY)
