# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
import asyncio
import os
import sys

from aiperf.common.comms.base import PullClient, PushClient
from aiperf.common.config import ServiceConfig
from aiperf.common.config.user_config import UserConfig
from aiperf.common.enums import ClientAddressType, MessageType, ServiceType
from aiperf.common.factories import ServiceFactory
from aiperf.common.hooks import (
    on_cleanup,
    on_configure,
    on_init,
    on_start,
    on_stop,
)
from aiperf.common.models.messages import (
    CommandMessage,
    InferenceResultsMessage,
    ParsedInferenceResultsMessage,
)
from aiperf.common.models.record_models import ErrorDetails, ParsedResponseRecord
from aiperf.common.service.base_component_service import BaseComponentService
from aiperf.common.tokenizer import Tokenizer
from aiperf.parsers.openai_parsers import OpenAIResponseExtractor


@ServiceFactory.register(ServiceType.POST_PROCESSOR_MANAGER)
class PostProcessorManager(BaseComponentService):
    """PostProcessorManager is primarily responsible for iterating over the
    records to generate metrics and other conclusions from the records.
    """

    def __init__(
        self, service_config: ServiceConfig, service_id: str | None = None
    ) -> None:
        super().__init__(service_config=service_config, service_id=service_id)
        self.logger.debug("Initializing post processor manager")
        self.inference_results_client: PullClient = self.comms.create_pull_client(
            ClientAddressType.PUSH_PULL_BACKEND,
        )
        self.response_results_client: PushClient = self.comms.create_push_client(
            ClientAddressType.INFERENCE_RESULTS_PUSH_PULL,
        )
        self.tokenizers: dict[str, Tokenizer] = {}
        self.user_config: UserConfig | None = None
        self.tokenizer_lock: asyncio.Lock = asyncio.Lock()
        self.extractor = OpenAIResponseExtractor()

    @property
    def service_type(self) -> ServiceType:
        """The type of service."""
        return ServiceType.POST_PROCESSOR_MANAGER

    @on_init
    async def _initialize(self) -> None:
        """Initialize post processor manager-specific components."""
        self.logger.debug("Initializing post processor manager")
        # TODO: Implement post processor manager initialization
        # self.incoming_records_client.register_request_handler(
        #     service_id=self.service_id,
        #     message_type=MessageType.INFERENCE_RESULTS,
        #     handler=self._on_inference_results,
        # )
        await self.inference_results_client.register_pull_callback(
            message_type=MessageType.INFERENCE_RESULTS,
            callback=self._on_inference_results,
            max_concurrency=1000000,
        )

    @on_start
    async def _start(self) -> None:
        """Start the post processor manager."""
        self.logger.debug("Starting post processor manager")
        # TODO: Implement post processor manager start

    @on_stop
    async def _stop(self) -> None:
        """Stop the post processor manager."""
        self.logger.debug("Stopping post processor manager")
        # TODO: Implement post processor manager stop

    @on_cleanup
    async def _cleanup(self) -> None:
        """Clean up post processor manager-specific components."""
        self.logger.debug("Cleaning up post processor manager")
        # TODO: Implement post processor manager cleanup

    async def get_tokenizer(self, model: str) -> Tokenizer:
        """Get the tokenizer for a given model."""
        async with self.tokenizer_lock:
            if model not in self.tokenizers:
                self.tokenizers[model] = Tokenizer.from_pretrained(model)
            return self.tokenizers[model]

    @on_configure
    async def _configure(self, message: CommandMessage) -> None:
        """Configure the post processor manager."""
        self.logger.debug(f"Configuring post processor manager with message: {message}")
        self.user_config = (
            message.data if isinstance(message.data, UserConfig) else None
        )

        await self.get_tokenizer(
            os.getenv("AIPERF_MODEL", "deepseek-ai/DeepSeek-R1-Distill-Llama-8B")
        )

        if self.user_config:
            await asyncio.gather(
                *[self.get_tokenizer(model) for model in self.user_config.model_names]
            )
            self.logger.info(
                "Initialized tokenizers for %d models", len(self.tokenizers)
            )

    async def _on_inference_results(self, message: InferenceResultsMessage) -> None:
        """Handle an inference results message."""
        self.logger.debug(f"Received inference results message: {message}")

        if message.record.has_error:
            await self.response_results_client.push(
                ParsedInferenceResultsMessage(
                    service_id=self.service_id,
                    record=ParsedResponseRecord(
                        worker_id=message.service_id,
                        request=message.record,
                        responses=[],
                        token_count=None,
                    ),
                )
            )

        elif message.record.valid:
            tokenizer = await self.get_tokenizer(message.record.request["model"])
            resp = await self.extractor.extract_response_data(message.record, tokenizer)
            token_count = sum(r.token_count for r in resp if r.token_count is not None)
            self.logger.debug(
                "Received %d responses, %d total tokens",
                len(resp),
                token_count,
            )

            result = ParsedInferenceResultsMessage(
                service_id=self.service_id,
                record=ParsedResponseRecord(
                    worker_id=message.service_id,
                    request=message.record,
                    responses=resp,
                    token_count=token_count if token_count > 0 else None,
                ),
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
                        token_count=None,
                    ),
                )
            )


def main() -> None:
    """Main entry point for the post processor manager."""

    from aiperf.common.bootstrap import bootstrap_and_run_service

    bootstrap_and_run_service(PostProcessorManager)


if __name__ == "__main__":
    sys.exit(main())
