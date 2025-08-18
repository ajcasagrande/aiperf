# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
import asyncio

from aiperf.common.config import ServiceConfig, UserConfig
from aiperf.common.enums import CommAddress
from aiperf.common.factories import (
    RecordProcessorFactory,
)
from aiperf.common.hooks import (
    on_init,
)
from aiperf.common.messages import (
    MetricRecordsMessage,
)
from aiperf.common.mixins import CommunicationMixin
from aiperf.common.models import RequestRecord
from aiperf.common.protocols import (
    PushClientProtocol,
    RecordProcessorProtocol,
)
from aiperf.metrics.metric_dicts import MetricRecordDict
from aiperf.parsers.inference_result_parser import InferenceResultParser


class RecordProcessorMixin(CommunicationMixin):
    """RecordProcessor is responsible for processing the records and pushing them to the RecordsManager.
    This service is meant to be run in a distributed fashion, where the amount of record processors can be scaled
    based on the load of the system.
    """

    def __init__(
        self,
        service_config: ServiceConfig,
        user_config: UserConfig,
        service_id: str | None = None,
        **kwargs,
    ) -> None:
        super().__init__(
            service_config=service_config,
            user_config=user_config,
            service_id=service_id,
            **kwargs,
        )
        self.user_config: UserConfig = user_config
        self.records_push_client: PushClientProtocol = self.comms.create_push_client(
            CommAddress.RECORDS,
        )
        self.inference_result_parser = InferenceResultParser(
            service_config=service_config,
            user_config=user_config,
        )
        self.records_processors: list[RecordProcessorProtocol] = []

    @on_init
    async def _initialize(self) -> None:
        """Initialize record processor-specific components."""
        self.debug("Initializing record processor")

        # Initialize all the records streamers
        for processor_type in RecordProcessorFactory.get_all_class_types():
            self.records_processors.append(
                RecordProcessorFactory.create_instance(
                    processor_type,
                    service_config=self.service_config,
                    user_config=self.user_config,
                )
            )

    async def configure(self) -> None:
        """Configure the record processor."""
        await self.inference_result_parser.configure()

    async def process_request_record(
        self, worker_id: str, record: RequestRecord
    ) -> None:
        """Handle a request record message."""
        parsed_record = await self.inference_result_parser.parse_request_record(record)
        tasks = [
            processor.process_record(parsed_record)
            for processor in self.records_processors
        ]
        raw_results: list[MetricRecordDict | BaseException] = await asyncio.gather(
            *tasks, return_exceptions=True
        )
        results = []
        for result in raw_results:
            if isinstance(result, BaseException):
                self.warning(f"Error processing record: {result}")
            else:
                results.append(result)
        await self.records_push_client.push(
            MetricRecordsMessage(
                service_id=self.id,
                worker_id=worker_id,
                credit_phase=record.credit_phase,
                results=results,
                error=record.error,
            )
        )
