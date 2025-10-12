# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES.
# SPDX-License-Identifier: Apache-2.0

from typing import ClassVar

from aiperf.common.enums import GenericMetricUnit, MetricFlags
from aiperf.common.exceptions import MetricTypeError, NoMetricValue
from aiperf.common.models import ParsedResponseRecord
from aiperf.metrics.base_aggregate_metric import BaseAggregateMetric
from aiperf.metrics.base_derived_metric import BaseDerivedMetric
from aiperf.metrics.base_metric import BaseMetric
from aiperf.metrics.base_record_metric import BaseRecordMetric
from aiperf.metrics.metric_dicts import MetricRecordDict, MetricResultsDict
from aiperf.metrics.metric_registry import MetricRegistry
from aiperf.metrics.types.request_count_metric import TotalRequestCountMetric


class GoodRequestMetric(BaseRecordMetric[bool]):
    """
    Keeps track of requests that satisfy all user-provided SLO thresholds.
    """

    tag = "good_request"
    header = "GoodRequest"
    short_header_hide_unit = True
    unit = None
    flags = MetricFlags.GOODPUT | MetricFlags.NO_CONSOLE
    required_metrics: set[str] | None = None

    _thresholds: ClassVar[dict[str, float]] = {}

    @classmethod
    def set_slos(cls, slos: dict[str, float] | None) -> None:
        """
        Configure SLO thresholds and update dependencies.
        """
        slos = slos or {}
        if not slos:
            cls._thresholds = {}
            cls.required_metrics = None
            return

        normalized_slos: dict[str, float] = {}

        for metric_tag, value in slos.items():
            try:
                metric_cls = MetricRegistry.get_class(metric_tag)
            except MetricTypeError as e:
                raise ValueError(
                    f"Unknown metric tag(s) in --goodput: {metric_tag}."
                ) from e
            unit = metric_cls.unit
            display_unit = metric_cls.display_unit
            if display_unit != unit:
                try:
                    value = display_unit.convert_to(unit, float(value))
                except Exception as e:
                    raise ValueError(
                        f"Failed to convert from {display_unit} to "
                        f"{unit} for '{metric_tag}': {e}"
                    ) from e
            normalized_slos[metric_tag] = value

        cls._thresholds = normalized_slos
        cls.required_metrics = set(cls._thresholds) if cls._thresholds else None

    def _parse_record(
        self,
        record: ParsedResponseRecord,
        record_metrics: MetricRecordDict,
    ) -> bool:
        """Check if the record satisfies all configured SLOs."""
        if not self._thresholds:
            raise ValueError("No SLOs configured")

        for metric_tag, threshold in self._thresholds.items():
            metric_cls = MetricRegistry.get_class(metric_tag)

            target_unit = metric_cls.unit
            try:
                value = record_metrics.get_converted_or_raise(metric_cls, target_unit)
            except NoMetricValue:
                return False

            if not self._passes(metric_cls, value, float(threshold)):
                return False

        return True

    def _passes(
        self, metric_cls: type[BaseMetric], record_value: float, threshold_value: float
    ) -> bool:
        """Compare a record value against its SLO using the metric's directionality."""
        if metric_cls.flags.has_flags(MetricFlags.LARGER_IS_BETTER):
            return record_value >= threshold_value
        return record_value <= threshold_value


class GoodRequestCountMetric(BaseAggregateMetric[int]):
    """
    Counts requests that satisfy all user-provided SLO thresholds.
    """

    tag = "good_request_count"
    header = "GoodRequest Count"
    short_header = "Good Requests"
    short_header_hide_unit = True
    unit = GenericMetricUnit.REQUESTS
    flags = MetricFlags.GOODPUT | MetricFlags.NO_CONSOLE
    required_metrics = {GoodRequestMetric.tag}

    def _parse_record(
        self, record: ParsedResponseRecord, record_metrics: MetricRecordDict
    ) -> int:
        raise NoMetricValue("GoodRequestCountMetric does not parse records.")

    def _aggregate_value(self, value: int, record_metrics: MetricRecordDict) -> None:
        """Aggregate the value by incrementing the count if the good request metric is True."""
        if record_metrics[GoodRequestMetric.tag]:
            self._value += 1


class GoodRequestPercentMetric(BaseDerivedMetric[float]):
    """
    Calculates the percentage of requests that satisfy all user-provided SLO thresholds.
    """

    tag = "good_request_percent"
    header = "GoodRequest Percent"
    short_header = "Good Percent"
    short_header_hide_unit = True
    unit = GenericMetricUnit.PERCENT
    flags = MetricFlags.GOODPUT | MetricFlags.NO_CONSOLE
    required_metrics = {GoodRequestCountMetric.tag, TotalRequestCountMetric.tag}

    def _derive_value(self, metric_results: MetricResultsDict) -> float:
        """Derive the good_request_percent value as the percentage of good requests over the total requests."""
        good_request_count = metric_results[GoodRequestCountMetric.tag]
        total_request_count = metric_results.get_or_raise(TotalRequestCountMetric)
        return (good_request_count / total_request_count) * 100.0
