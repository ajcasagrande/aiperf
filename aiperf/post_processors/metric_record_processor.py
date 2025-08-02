# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
from aiperf.common.config.service_config import ServiceConfig
from aiperf.common.config.user_config import UserConfig
from aiperf.common.decorators import implements_protocol
from aiperf.common.mixins.aiperf_lifecycle_mixin import AIPerfLifecycleMixin
from aiperf.common.models import ParsedResponseRecord
from aiperf.common.protocols import RecordProcessorProtocol


@implements_protocol(RecordProcessorProtocol)
class MetricRecordProcessor(AIPerfLifecycleMixin):
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
        super().__init__(
            service_config=service_config, user_config=user_config, **kwargs
        )
        self.metrics = []

    async def process_record(self, record: ParsedResponseRecord) -> None:
        """Process a record."""
        pass
