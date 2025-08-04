# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

from aiperf.common.config import UserConfig
from aiperf.common.decorators import implements_protocol
from aiperf.common.enums import MetricType, RecordProcessorType
from aiperf.common.factories import RecordProcessorFactory
from aiperf.common.models import ParsedResponseRecord
from aiperf.common.protocols import RecordProcessorProtocol
from aiperf.metrics.metric_dicts import MetricRecordDict
from aiperf.post_processors.base_metrics_processor import BaseMetricsProcessor


@implements_protocol(RecordProcessorProtocol)
@RecordProcessorFactory.register(RecordProcessorType.METRIC_RECORD)
class MetricRecordProcessor(BaseMetricsProcessor):
    """Processor for metric records.

    This is the first stage of the metrics processing pipeline, and is done is a distributed manner across multiple service instances.
    It is responsible for streaming the records to the post processor, and computing the metrics from the records.
    It computes metrics from MetricType.RECORD and MetricType.AGGREGATE types."""

    def __init__(
        self,
        user_config: UserConfig,
        **kwargs,
    ) -> None:
        super().__init__(
            MetricType.RECORD,
            MetricType.AGGREGATE,
            user_config=user_config,
            **kwargs,
        )

    async def process_record(self, record: ParsedResponseRecord) -> MetricRecordDict:
        """Process a response record from the inference results parser."""
        record_metrics: MetricRecordDict = MetricRecordDict()
        metrics = self.metrics if record.valid else self.error_metrics
        for metric in metrics:
            record_metrics[metric.tag] = metric.parse_record(record, record_metrics)  # type: ignore
        return record_metrics
