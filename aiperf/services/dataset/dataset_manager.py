# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
import os
import sys
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from aiperf.common.comms.base import RepClientInterface
from aiperf.common.config import ServiceConfig
from aiperf.common.dataset_models import Conversation
from aiperf.common.enums import (
    ComposerType,
    CustomDatasetType,
    MessageType,
    NotificationType,
    ServiceType,
    Topic,
)
from aiperf.common.exceptions import AIPerfError, ServiceErrorType
from aiperf.common.factories import ServiceFactory
from aiperf.common.hooks import (
    on_cleanup,
    on_configure,
    on_init,
    on_start,
    on_stop,
)
from aiperf.common.models import (
    ConversationRequestMessage,
    ConversationResponseMessage,
    DatasetTimingRequest,
    DatasetTimingResponse,
    Message,
)
from aiperf.common.models.messages import NotificationMessage
from aiperf.common.service.base_component_service import BaseComponentService
from aiperf.common.tokenizer import Tokenizer
from aiperf.services.dataset.composer import ComposerFactory
from aiperf.services.dataset.config import DatasetConfig, PromptConfig


################################################################################
# TODO: Temporary (remove when command config is ready)
class MockConfig(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    filename: str | None = None
    tokenizer: Tokenizer | None = None
    custom_dataset_type: CustomDatasetType | None = None
    public_dataset: str | None = None
    prompt: PromptConfig | None = None


################################################################################


@ServiceFactory.register(ServiceType.DATASET_MANAGER)
class DatasetManager(BaseComponentService):
    """
    The DatasetManager primary responsibility is to manage the data generation or acquisition.
    For synthetic generation, it contains the code to generate the prompts or tokens.
    It will have an API for dataset acquisition of a dataset if available in a remote repository or database.
    """

    def __init__(
        self,
        service_config: ServiceConfig,
        service_id: str | None = None,
    ) -> None:
        super().__init__(service_config=service_config, service_id=service_id)
        self.logger.debug("Initializing dataset manager")
        self.tokenizer: Tokenizer | None = None
        self.conversation_data_client: RepClientInterface
        self.dataset: dict[str, Conversation] = {}  # session ID -> Conversation mapping

    @property
    def service_type(self) -> ServiceType:
        """The type of service."""
        return ServiceType.DATASET_MANAGER

    @on_init
    async def _initialize(self) -> None:
        """Initialize dataset manager-specific components."""
        self.logger.info("Initializing dataset manager %s", self.service_id)

        if self.comms is None:
            raise AIPerfError("Communication is not initialized")

        self.conversation_data_client = await self.comms.create_rep_client(
            address=self.service_config.comm_config.conversation_data_address,
            bind=True,
        )
        await self.conversation_data_client.initialize()

        if self.conversation_data_client is None:
            raise AIPerfError("Conversation data client is not initialized")

        self.conversation_data_client.register_request_handler(
            service_id=self.service_id,
            message_type=MessageType.CONVERSATION_REQUEST,
            handler=self._handle_conversation_request,
        )
        self.conversation_data_client.register_request_handler(
            service_id=self.service_id,
            message_type=MessageType.DATASET_TIMING_REQUEST,
            handler=self._handle_dataset_timing_request,
        )

        self.logger.info("Dataset manager %s initialized", self.service_id)

    @on_start
    async def _start(self) -> None:
        """Start the dataset manager."""
        self.logger.info("Starting dataset manager %s", self.service_id)
        # TODO: Implement dataset manager start

    @on_stop
    async def _stop(self) -> None:
        """Stop the dataset manager."""
        self.logger.debug("Stopping dataset manager %s", self.service_id)
        # TODO: Implement dataset manager stop

    @on_cleanup
    async def _cleanup(self) -> None:
        """Clean up dataset manager-specific components."""
        self.logger.debug("Cleaning up dataset manager %s", self.service_id)
        # TODO: Implement dataset manager cleanup

    @on_configure
    async def _configure(self, message: Message) -> None:
        """Configure the dataset manager."""
        self.logger.info(
            "Configuring dataset manager %s with message: %s",
            self.service_id,
            message,
        )
        # TODO: remove this mock config
        # mocks config inside the message
        config = MockConfig()
        config.filename = os.getenv("AIPERF_DATASET_FILENAME", "trace1.jsonl")
        config.tokenizer = Tokenizer.from_pretrained(
            os.getenv("AIPERF_MODEL", "deepseek-ai/DeepSeek-R1-Distill-Llama-8B")
        )

        if config.filename:
            composer_type = ComposerType.CUSTOM
            config.custom_dataset_type = CustomDatasetType.TRACE
        else:
            composer_type = ComposerType.SYNTHETIC
            config.custom_dataset_type = CustomDatasetType.SINGLE_TURN  # ignored

        # TODO: update once we integrate with command config
        dataset_config = DatasetConfig(
            filename=Path(config.filename) if config.filename else None,
            tokenizer=config.tokenizer,
            custom_dataset_type=config.custom_dataset_type,
            prompt=PromptConfig(mean=10, stddev=2),
        )

        composer = ComposerFactory.create_instance(composer_type, config=dataset_config)
        conversations = composer.create_dataset()
        self.dataset = {conv.session_id: conv for conv in conversations}

        await self.pub_client.publish(
            topic=Topic.NOTIFICATION,
            message=NotificationMessage(
                service_id=self.service_id,
                message_type=MessageType.NOTIFICATION,
                notification_type=NotificationType.DATASET_CONFIGURED,
                data=None,
            ),
        )

    async def _handle_conversation_request(
        self, message: ConversationRequestMessage
    ) -> ConversationResponseMessage:
        """Handle a conversation request."""
        self.logger.debug("Handling conversation request: %s", message)

        if not self.dataset:
            raise self._service_error(
                ServiceErrorType.DATASET_EMPTY,
                "Dataset is empty and must be configured before handling requests.",
            )

        if message.conversation_id not in self.dataset:
            raise self._service_error(
                ServiceErrorType.CONVERSATION_NOT_FOUND,
                f"Conversation {message.conversation_id} not found in dataset.",
            )

        conversation = self.dataset[message.conversation_id]
        self.logger.debug("Sending conversation response: %s", conversation)
        return ConversationResponseMessage(
            service_id=self.service_id,
            request_id=message.request_id,
            conversation=conversation,
        )

    async def _handle_dataset_timing_request(
        self, message: DatasetTimingRequest
    ) -> DatasetTimingResponse:
        """Handle a dataset timing request."""
        self.logger.debug("Handling dataset timing request: %s", message)
        # TODO: Implement dataset timing request handling
        return DatasetTimingResponse(
            service_id=self.service_id,
            request_id=message.request_id,
            timing_data=[
                (1719000000000, "123"),
                (1719000000001, "456"),
            ],
        )


def main() -> None:
    """Main entry point for the dataset manager."""

    from aiperf.common.bootstrap import bootstrap_and_run_service

    bootstrap_and_run_service(DatasetManager)


if __name__ == "__main__":
    sys.exit(main())
