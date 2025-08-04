# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

from aiperf.common.config import ServiceConfig, UserConfig
from aiperf.common.decorators import implements_protocol
from aiperf.common.enums import (
    EndpointType,
    MetricFlags,
    MetricType,
    RecordProcessorType,
)
from aiperf.common.factories import RecordProcessorFactory
from aiperf.common.mixins import AIPerfLoggerMixin
from aiperf.common.models import ParsedResponseRecord
from aiperf.common.protocols import RecordProcessorProtocol
from aiperf.metrics import BaseMetric
from aiperf.metrics.metric_dicts import MetricRecordDict
from aiperf.metrics.metric_registry import MetricRegistry


@implements_protocol(RecordProcessorProtocol)
@RecordProcessorFactory.register(RecordProcessorType.METRIC_RECORD)
class MetricRecordProcessor(AIPerfLoggerMixin):
    """Processor for metric records.
    This is the first stage of the metrics processing pipeline, and is done is a distributed manner across multiple service instances.
    It is responsible for streaming the records to the post processor, and computing the metrics from the records.
    It computes metrics from MetricType.RECORD and MetricType.AGGREGATE types."""

    def __init__(
        self,
        service_config: ServiceConfig,
        user_config: UserConfig,
        **kwargs,
    ) -> None:
        self.endpoint_type: EndpointType = user_config.endpoint.type
        self.is_streaming: bool = user_config.endpoint.streaming
        super().__init__(
            service_config=service_config, user_config=user_config, **kwargs
        )
        self.metrics: list[BaseMetric] = self._setup_metrics()

    def _setup_metrics(self) -> list[BaseMetric]:
        """Get an ordered list of metrics that are applicable to the endpoint type and user config.
        The metrics are ordered based on their dependencies, ensuring proper computation order.
        Be sure to compute the metrics sequentially, as some metrics may depend on the results of previous metrics.
        """
        # Start with no flags (unfiltered)
        required_flags, disallowed_flags = MetricFlags.NONE, MetricFlags.NONE
        # Disable metrics that are not applicable to the endpoint type
        if not self.endpoint_type.produces_tokens:
            disallowed_flags |= MetricFlags.PRODUCES_TOKENS_ONLY
        if not self.endpoint_type.supports_audio:
            disallowed_flags |= MetricFlags.SUPPORTS_AUDIO_ONLY
        if not self.endpoint_type.supports_images:
            disallowed_flags |= MetricFlags.SUPPORTS_IMAGE_ONLY
        if not self.is_streaming:
            disallowed_flags |= MetricFlags.STREAMING_ONLY

        metrics: list[BaseMetric] = []
        supported_tags = MetricRegistry.tags_applicable_to(
            required_flags,
            disallowed_flags,
            MetricType.RECORD,
            MetricType.AGGREGATE,
        )
        ordered_tags = MetricRegistry.create_dependency_order_for(supported_tags)
        for metric_tag in ordered_tags:
            metrics.append(MetricRegistry.get_instance(metric_tag))
        return metrics

    async def process_record(self, record: ParsedResponseRecord) -> MetricRecordDict:
        """Process a response record from the inference results parser."""
        record_metrics: MetricRecordDict = MetricRecordDict()
        for metric in self.metrics:
            record_metrics[metric.tag] = metric.parse_record(record, record_metrics)  # type: ignore
        return record_metrics
