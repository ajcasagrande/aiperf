# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
from typing import Any

from aiperf.common.decorators import implements_protocol
from aiperf.common.enums import ResultsProcessorType
from aiperf.common.enums.metric_enums import MetricFlags, MetricType
from aiperf.common.factories import ResultsProcessorFactory
from aiperf.common.mixins import AIPerfLoggerMixin
from aiperf.common.models.record_models import MetricResult
from aiperf.common.protocols import ResultsProcessorProtocol
from aiperf.metrics import BaseDerivedMetric
from aiperf.metrics.metric_dicts import MetricRecordDict, MetricResultsDict
from aiperf.metrics.metric_registry import MetricRegistry


@implements_protocol(ResultsProcessorProtocol)
@ResultsProcessorFactory.register(ResultsProcessorType.METRIC_RESULTS)
class MetricResultsProcessor(AIPerfLoggerMixin):
    """Processor for metric results.

    This is the final stage of the metrics processing pipeline, and is done is a unified manner by the RecordsManager.
    It is responsible for processing the results and returning them to the RecordsManager, as well as summarizing the results.
    """

    def __init__(self, **kwargs: Any):
        super().__init__(**kwargs)
        tags = MetricRegistry.tags_applicable_to(
            MetricFlags.NONE, MetricFlags.NONE, MetricType.DERIVED
        )
        self._metrics: list[BaseDerivedMetric] = [
            MetricRegistry.get_instance(tag)
            for tag in MetricRegistry.create_dependency_order_for(tags)
            if MetricRegistry.get_type_for(tag) == MetricType.DERIVED
        ]
        self._results: MetricResultsDict = MetricResultsDict()

    async def process_result(self, record_dict: MetricRecordDict) -> None:
        """Process a result from the metric record processor."""
        self.trace(lambda: f"Processing result: {record_dict}")
        for tag, value in record_dict.items():
            if MetricRegistry.get_type_for(tag) == MetricType.AGGREGATE:
                value = MetricRegistry.get_instance(tag)._aggregate_value(value)  # type: ignore
                self._results[tag] = value
            elif MetricRegistry.get_type_for(tag) == MetricType.RECORD:
                self._results.setdefault(tag, []).append(value)
            else:
                raise ValueError(f"Metric {tag} is not a valid metric type")
        self.trace(lambda: f"Results: {self._results}")

    async def summarize(self) -> list[MetricResult]:
        """Summarize the results."""
        for metric in self._metrics:
            if metric.type == MetricType.DERIVED:
                self._results[metric.tag] = metric.derive_value(self._results)
        return self._results.summarize()
