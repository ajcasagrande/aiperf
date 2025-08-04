# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
from collections import deque
from typing import Any

from aiperf.common.decorators import implements_protocol
from aiperf.common.enums import ResultsProcessorType
from aiperf.common.enums.metric_enums import MetricFlags, MetricType
from aiperf.common.factories import ResultsProcessorFactory
from aiperf.common.mixins import AIPerfLoggerMixin
from aiperf.common.models.record_models import MetricResult
from aiperf.common.protocols import ResultsProcessorProtocol
from aiperf.metrics import BaseAggregateMetric, BaseDerivedMetric
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
        # Create the dependency order for the derived metrics, and create the instances.
        self._derived_metrics: list[BaseDerivedMetric] = [  # type: ignore
            MetricRegistry.get_instance(tag)
            for tag in MetricRegistry.create_dependency_order_for(tags)
        ]
        # Create the results dict, which will be used to store the results of non-derived metrics.
        self._results: MetricResultsDict = MetricResultsDict()

    async def process_result(self, record_dict: MetricRecordDict) -> None:
        """Process a result from the metric record processor."""
        self.trace(lambda: f"Processing result: {record_dict}")
        for tag, value in record_dict.items():
            if MetricRegistry.get_type(tag) == MetricType.AGGREGATE:
                metric: BaseAggregateMetric = MetricRegistry.get_instance(tag)  # type: ignore
                metric.aggregate_value(value)
                self._results[tag] = metric.current_value
            elif MetricRegistry.get_type(tag) == MetricType.RECORD:
                self._results.setdefault(tag, deque()).append(value)  # type: ignore
            else:
                raise ValueError(f"Metric {tag} is not a valid metric type")
        self.trace(lambda: f"Results: {self._results}")

    async def summarize(self) -> list[MetricResult]:
        """Summarize the results."""
        # Derive the values for the derived metrics, and store them in the results dict.
        for metric in self._derived_metrics:
            self._results[metric.tag] = metric.derive_value(self._results)

        # Summarize the results, and return them.
        return self._results.summarize()
