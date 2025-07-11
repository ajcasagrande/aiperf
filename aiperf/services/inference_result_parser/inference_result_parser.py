# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
import asyncio
import sys

from aiperf.clients.model_endpoint_info import ModelEndpointInfo
from aiperf.common.comms.base import PullClientProtocol, PushClientProtocol
from aiperf.common.config import ServiceConfig
from aiperf.common.config.user_config import UserConfig
from aiperf.common.enums import CommunicationClientAddressType, MessageType, ServiceType
from aiperf.common.factories import ServiceFactory
from aiperf.common.hooks import (
    on_configure,
    on_init,
)
from aiperf.common.messages import (
    CommandMessage,
    InferenceResultsMessage,
    ParsedInferenceResultsMessage,
)
from aiperf.common.record_models import ErrorDetails, ParsedResponseRecord
from aiperf.common.service.base_component_service import BaseComponentService
from aiperf.common.tokenizer import Tokenizer
from aiperf.services.inference_result_parser.openai_parsers import (
    OpenAIResponseExtractor,
)


@ServiceFactory.register(ServiceType.INFERENCE_RESULT_PARSER)
class InferenceResultParser(BaseComponentService):
    """InferenceResultParser is responsible for parsing the inference results
    and pushing them to the RecordsManager.
    """

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
        )
        self.logger.debug("Initializing inference result parser")
        self.inference_results_client: PullClientProtocol = (
            self.comms.create_pull_client(
                CommunicationClientAddressType.RAW_INFERENCE_PROXY_BACKEND,
            )
        )
        self.response_results_client: PushClientProtocol = (
            self.comms.create_push_client(
                CommunicationClientAddressType.RECORDS,
            )
        )
        self.tokenizers: dict[str, Tokenizer] = {}
        self.user_config: UserConfig = user_config
        self.tokenizer_lock: asyncio.Lock = asyncio.Lock()
        self.extractor = OpenAIResponseExtractor()
        self.model_endpoint: ModelEndpointInfo = ModelEndpointInfo.from_user_config(
            user_config
        )

    @property
    def service_type(self) -> ServiceType:
        """The type of service."""
        return ServiceType.INFERENCE_RESULT_PARSER

    @on_init
    async def _initialize(self) -> None:
        """Initialize inference result parser-specific components."""
        self.logger.debug("Initializing inference result parser")

        await self.inference_results_client.register_pull_callback(
            message_type=MessageType.INFERENCE_RESULTS,
            callback=self._on_inference_results,
            # TODO: Support for unbounded concurrency in the future by setting to None or 0?
            max_concurrency=1000000,
        )

        self.model_endpoint = ModelEndpointInfo.from_user_config(self.user_config)
        async with self.tokenizer_lock:
            self.tokenizers = {
                model.name: Tokenizer.from_pretrained(
                    self.user_config.tokenizer.name or model.name,
                    trust_remote_code=self.user_config.tokenizer.trust_remote_code,
                    revision=self.user_config.tokenizer.revision,
                )
                for model in self.model_endpoint.models.models
            }
            self.logger.info(
                "Initialized tokenizers for %d models", len(self.tokenizers)
            )

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

    @on_configure
    async def _configure(self, message: CommandMessage) -> None:
        """Configure the inference result parser."""

    async def _on_inference_results(self, message: InferenceResultsMessage) -> None:
        """Handle an inference results message."""
        self.logger.debug("Received inference results message: %s", message)

        if message.record.has_error:
            await self.response_results_client.push(
                ParsedInferenceResultsMessage(
                    service_id=self.service_id,
                    record=ParsedResponseRecord(
                        worker_id=message.service_id,
                        request=message.record,
                        responses=[],
                    ),
                )
            )

        elif message.record.valid:
            tokenizer = await self.get_tokenizer(message.record.request["model"])
            resp = await self.extractor.extract_response_data(message.record, tokenizer)

            result = ParsedInferenceResultsMessage(
                service_id=self.service_id,
                record=ParsedResponseRecord(
                    worker_id=message.service_id,
                    request=message.record,
                    responses=resp,
                ),
            )
            self.logger.debug(
                "Received %d responses, %d total tokens",
                len(resp),
                result.record.token_count,
            )
            await self.response_results_client.push(result)
        else:
            self.logger.warning(
                "Received invalid inference results: %s", message.record
            )
            message.record.error = ErrorDetails(
                code=None,
                message="Invalid inference results",
                type="InvalidInferenceResults",
            )
            await self.response_results_client.push(
                ParsedInferenceResultsMessage(
                    service_id=self.service_id,
                    record=ParsedResponseRecord(
                        worker_id=message.service_id,
                        request=message.record,
                        responses=[],
                    ),
                )
            )


def main() -> None:
    from aiperf.common.bootstrap import bootstrap_and_run_service

    bootstrap_and_run_service(InferenceResultParser)


if __name__ == "__main__":
    sys.exit(main())
