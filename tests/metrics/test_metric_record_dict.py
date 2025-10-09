# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

import pytest

from aiperf.common.enums import MetricFlags
from aiperf.metrics.metric_dicts import MetricRecordDict
from aiperf.metrics.metric_registry import MetricRegistry
from aiperf.metrics.types.request_latency_metric import RequestLatencyMetric
from aiperf.metrics.types.ttft_metric import TTFTMetric


class TestMetricRecordDictToDisplayDict:
    """Tests for MetricRecordDict.to_display_dict() helper method."""

    def test_basic_conversion_to_display_units(self):
        """Test that metrics are converted from internal to display units."""
        metric_dict = MetricRecordDict()
        metric_dict[TTFTMetric.tag] = 18260000  # 18.26 ms in nanoseconds

        result = metric_dict.to_display_dict(MetricRegistry, show_internal=False)

        assert TTFTMetric.tag in result
        ttft = result[TTFTMetric.tag]
        assert ttft["value"] == pytest.approx(18.26, rel=0.01)
        assert ttft["unit"] == "ms"
        assert ttft["header"] == "Time to First Token"

    def test_multiple_metrics_converted(self):
        """Test that multiple metrics are all converted properly."""
        metric_dict = MetricRecordDict()
        metric_dict[TTFTMetric.tag] = 20000000  # 20ms
        metric_dict[RequestLatencyMetric.tag] = 500000000  # 500ms

        result = metric_dict.to_display_dict(MetricRegistry, show_internal=False)

        assert len(result) == 2
        assert result[TTFTMetric.tag]["value"] == pytest.approx(20.0)
        assert result[RequestLatencyMetric.tag]["value"] == pytest.approx(500.0)

    def test_filters_hidden_metrics(self):
        """Test that HIDDEN metrics are filtered out."""
        from aiperf.metrics.types.min_request_metric import MinRequestTimestampMetric

        metric_dict = MetricRecordDict()
        metric_dict[TTFTMetric.tag] = 20000000
        # MinRequestTimestampMetric is HIDDEN
        metric_dict[MinRequestTimestampMetric.tag] = 1234567890

        result = metric_dict.to_display_dict(MetricRegistry, show_internal=False)

        assert TTFTMetric.tag in result
        assert MinRequestTimestampMetric.tag not in result

    def test_filters_error_only_metrics(self):
        """Test that ERROR_ONLY metrics are filtered out."""
        from aiperf.metrics.types.error_request_count import (
            ErrorRequestCountMetric,
        )

        metric_dict = MetricRecordDict()
        metric_dict[TTFTMetric.tag] = 20000000
        # ErrorRequestCountMetric is ERROR_ONLY
        metric_dict[ErrorRequestCountMetric.tag] = 5

        result = metric_dict.to_display_dict(MetricRegistry, show_internal=False)

        assert TTFTMetric.tag in result
        assert ErrorRequestCountMetric.tag not in result

    def test_show_internal_includes_experimental(self):
        """Test that show_internal=True includes experimental metrics."""
        metric_dict = MetricRecordDict()
        metric_dict[TTFTMetric.tag] = 20000000

        # Find an experimental metric if one exists
        experimental_tags = [
            tag
            for tag in MetricRegistry.all_tags()
            if MetricRegistry.get_class(tag).has_flags(MetricFlags.EXPERIMENTAL)
            and MetricRegistry.get_class(tag).missing_flags(
                MetricFlags.ERROR_ONLY | MetricFlags.HIDDEN
            )
        ]

        if experimental_tags:
            test_tag = experimental_tags[0]
            metric_dict[test_tag] = 100

            # Should be filtered out with show_internal=False
            result_filtered = metric_dict.to_display_dict(
                MetricRegistry, show_internal=False
            )
            assert test_tag not in result_filtered

            # Should be included with show_internal=True
            result_shown = metric_dict.to_display_dict(
                MetricRegistry, show_internal=True
            )
            assert test_tag in result_shown

    def test_handles_unknown_metric_gracefully(self):
        """Test that unknown metrics are silently skipped."""
        metric_dict = MetricRecordDict()
        metric_dict[TTFTMetric.tag] = 20000000
        metric_dict["unknown_metric_xyz"] = 123

        result = metric_dict.to_display_dict(MetricRegistry, show_internal=False)

        assert TTFTMetric.tag in result
        assert "unknown_metric_xyz" not in result

    def test_preserves_non_numeric_values(self):
        """Test that non-numeric values are preserved without conversion."""
        from aiperf.metrics.types.output_sequence_length_metric import (
            OutputSequenceLengthMetric,
        )

        metric_dict = MetricRecordDict()
        # OSL is integer tokens (no unit conversion)
        metric_dict[OutputSequenceLengthMetric.tag] = 42

        result = metric_dict.to_display_dict(MetricRegistry, show_internal=False)

        assert result[OutputSequenceLengthMetric.tag]["value"] == 42

    def test_empty_dict_returns_empty(self):
        """Test that empty MetricRecordDict returns empty result."""
        metric_dict = MetricRecordDict()

        result = metric_dict.to_display_dict(MetricRegistry, show_internal=False)

        assert result == {}

    def test_all_filtered_returns_empty(self):
        """Test that dict with only filtered metrics returns empty."""
        from aiperf.metrics.types.min_request_metric import MinRequestTimestampMetric

        metric_dict = MetricRecordDict()
        # Only add HIDDEN metrics
        metric_dict[MinRequestTimestampMetric.tag] = 1234567890

        result = metric_dict.to_display_dict(MetricRegistry, show_internal=False)

        assert result == {}

    def test_metric_without_unit_handled(self):
        """Test metrics without units are handled properly."""
        from aiperf.metrics.types.request_count_metric import RequestCountMetric

        metric_dict = MetricRecordDict()
        metric_dict[RequestCountMetric.tag] = 1

        result = metric_dict.to_display_dict(MetricRegistry, show_internal=False)

        assert RequestCountMetric.tag in result
        count_result = result[RequestCountMetric.tag]
        assert count_result["value"] == 1
