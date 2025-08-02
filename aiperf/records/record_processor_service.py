# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
import asyncio
from collections.abc import AsyncIterator

from aiperf.clients.model_endpoint_info import ModelEndpointInfo
from aiperf.common.base_component_service import BaseComponentService
from aiperf.common.comms.base_comms import (
    PushClientProtocol,
    RequestClientProtocol,
)
from aiperf.common.config import ServiceConfig
from aiperf.common.config.user_config import UserConfig
from aiperf.common.constants import DEFAULT_PULL_CLIENT_MAX_CONCURRENCY
from aiperf.common.enums import CommAddress, MessageType, ServiceType
from aiperf.common.enums.command_enums import CommandType
from aiperf.common.factories import (
    ResponseExtractorFactory,
    ServiceFactory,
    StreamingRecordProcessorFactory,
)
from aiperf.common.hooks import (
    on_command,
    on_init,
    on_pull_message,
)
from aiperf.common.messages import (
    InferenceResultsMessage,
)
from aiperf.common.messages.command_messages import ProfileConfigureCommand
from aiperf.common.messages.inference_messages import MetricRecordsMessage
from aiperf.common.mixins import PullClientMixin
from aiperf.common.models.record_models import (
    MetricRecords,
    ParsedResponseRecord,
    RecordProcessorResult,
)
from aiperf.common.protocols import StreamingRecordProcessorProtocol
from aiperf.common.tokenizer import Tokenizer
from aiperf.parsers.inference_result_parser import InferenceResultParser


@ServiceFactory.register(ServiceType.RECORD_PROCESSOR)
class RecordProcessor(PullClientMixin, BaseComponentService):
    """RecordProcessor is responsible for processing the records and pushing them to the RecordsManager."""

    def __init__(
        self,
        service_config: ServiceConfig,
        user_config: UserConfig,
        service_id: str | None = None,
    ) -> None:
        super().__init__(
            service_config=service_config,
            user_config=user_config,
            service_id=service_id,
            pull_client_address=CommAddress.RAW_INFERENCE_PROXY_BACKEND,
            pull_client_bind=False,
            pull_client_max_concurrency=DEFAULT_PULL_CLIENT_MAX_CONCURRENCY,
        )
        self.records_push_client: PushClientProtocol = self.comms.create_push_client(
            CommAddress.RECORDS,
        )
        self.conversation_request_client: RequestClientProtocol = (
            self.comms.create_request_client(
                CommAddress.DATASET_MANAGER_PROXY_FRONTEND,
            )
        )
        self.tokenizers: dict[str, Tokenizer] = {}
        self.user_config: UserConfig = user_config
        self.tokenizer_lock: asyncio.Lock = asyncio.Lock()
        self.model_endpoint: ModelEndpointInfo = ModelEndpointInfo.from_user_config(
            user_config
        )
        self.inference_result_parser = InferenceResultParser(
            service_config=service_config,
            user_config=user_config,
        )
        self.records_streamers: list[StreamingRecordProcessorProtocol] = []

    @on_init
    async def _initialize(self) -> None:
        """Initialize record processor-specific components."""
        self.debug("Initializing record processor")

        self.extractor = ResponseExtractorFactory.create_instance(
            self.model_endpoint.endpoint.type,
            model_endpoint=self.model_endpoint,
        )

        # Initialize all the records streamers
        for streamer_type in StreamingRecordProcessorFactory.get_all_class_types():
            self.records_streamers.append(
                StreamingRecordProcessorFactory.create_instance(
                    streamer_type,
                    service_config=self.service_config,
                    user_config=self.user_config,
                )
            )

    @on_command(CommandType.PROFILE_CONFIGURE)
    async def _profile_configure_command(
        self, message: ProfileConfigureCommand
    ) -> None:
        """Configure the tokenizers."""
        await self.inference_result_parser.configure()

    async def get_tokenizer(self, model: str) -> Tokenizer:
        """Get the tokenizer for a given model."""
        async with self.tokenizer_lock:
            if model not in self.tokenizers:
                self.tokenizers[model] = Tokenizer.from_pretrained(
                    self.user_config.tokenizer.name or model,
                    trust_remote_code=self.user_config.tokenizer.trust_remote_code,
                    revision=self.user_config.tokenizer.revision,
                )
            return self.tokenizers[model]

    @on_pull_message(MessageType.INFERENCE_RESULTS)
    async def _on_inference_results(self, message: InferenceResultsMessage) -> None:
        """Handle an inference results message."""
        parsed_record = await self.inference_result_parser.parse_request_record(
            message.record
        )
        results = await self._stream_record(parsed_record)
        await self.records_push_client.push(
            MetricRecordsMessage(
                service_id=self.id,
                worker_id=message.service_id,
                metric_records=results,
            )
        )

    async def _stream_record(self, record: ParsedResponseRecord) -> MetricRecords:
        """Stream a record to the records streamers."""
        tasks = [streamer.stream_record(record) for streamer in self.records_streamers]
        results: list[RecordProcessorResult] = await asyncio.gather(*tasks)
        metric_records = MetricRecords(
            timestamp_ns=record.timestamp_ns,
            records=[record for result in results for record in result.records],
            errors=[error for result in results for error in result.errors],
        )
        return metric_records

    async def _yield_streamers(self) -> AsyncIterator[StreamingRecordProcessorProtocol]:
        """Yield the records streamers."""
        for streamer in self.records_streamers:
            yield streamer


def main() -> None:
    from aiperf.common.bootstrap import bootstrap_and_run_service

    bootstrap_and_run_service(RecordProcessor)


if __name__ == "__main__":
    main()
