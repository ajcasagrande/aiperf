# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
import asyncio
import random
import sys

from aiperf.common.comms import ReplyClientProtocol
from aiperf.common.comms.base import (
    CommunicationClientAddressType,
)
from aiperf.common.config import ServiceConfig, UserConfig
from aiperf.common.dataset_models import Conversation
from aiperf.common.enums import (
    ComposerType,
    MessageType,
    NotificationType,
    ServiceType,
)
from aiperf.common.factories import ComposerFactory, ServiceFactory
from aiperf.common.hooks import (
    on_configure,
    on_init,
)
from aiperf.common.messages import (
    ConversationRequestMessage,
    ConversationResponseMessage,
    DatasetTimingRequest,
    DatasetTimingResponse,
    Message,
    NotificationMessage,
)
from aiperf.common.service.base_component_service import BaseComponentService
from aiperf.common.tokenizer import Tokenizer

DATASET_CONFIGURATION_TIMEOUT = 30.0


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
        user_config: UserConfig | None = None,
        service_id: str | None = None,
    ) -> None:
        super().__init__(
            service_config=service_config,
            user_config=user_config,
            service_id=service_id,
        )
        self.logger.debug("Dataset manager __init__")
        self.user_config = user_config
        self.tokenizer: Tokenizer | None = None
        self.dataset: dict[str, Conversation] = {}  # session ID -> Conversation mapping
        self.reply_client: ReplyClientProtocol = self.comms.create_reply_client(
            CommunicationClientAddressType.DATASET_MANAGER_PROXY_BACKEND
        )
        self.dataset_configured = asyncio.Event()

    @property
    def service_type(self) -> ServiceType:
        """The type of service."""
        return ServiceType.DATASET_MANAGER

    @on_init
    async def _initialize(self) -> None:
        """Initialize dataset manager-specific components."""
        self.logger.debug("Initializing dataset manager %s", self.service_id)

        self.reply_client.register_request_handler(
            service_id=self.service_id,
            message_type=MessageType.CONVERSATION_REQUEST,
            handler=self._handle_conversation_request,
        )
        self.reply_client.register_request_handler(
            service_id=self.service_id,
            message_type=MessageType.DATASET_TIMING_REQUEST,
            handler=self._handle_dataset_timing_request,
        )

        self.logger.debug("Dataset manager %s initialized", self.service_id)

    async def _configure_dataset(self) -> None:
        if self.user_config is None:
            raise self._service_error("User config is required for dataset manager")

        if self.user_config.input.file:
            composer_type = ComposerType.CUSTOM
            self.logger.debug(
                "Detected input file '%s'. Setting the composer type to %s.",
                self.user_config.input.file,
                ComposerType.CUSTOM,
            )
        else:
            composer_type = ComposerType.SYNTHETIC
            self.logger.debug(
                "No input file detected. Setting the composer type to %s.",
                ComposerType.SYNTHETIC,
            )

        tokenizer_name = self.user_config.tokenizer.name
        if tokenizer_name is None:
            # TODO: How do we support multiple?
            tokenizer_name = self.user_config.model_names[0]

        tokenizer = Tokenizer.from_pretrained(
            tokenizer_name,
            trust_remote_code=self.user_config.tokenizer.trust_remote_code,
            revision=self.user_config.tokenizer.revision,
        )
        composer = ComposerFactory.create_instance(
            composer_type,
            config=self.user_config.input,
            tokenizer=tokenizer,
        )
        conversations = composer.create_dataset()
        self.dataset = {conv.session_id: conv for conv in conversations}

        self.dataset_configured.set()
        await self.pub_client.publish(
            NotificationMessage(
                service_id=self.service_id,
                message_type=MessageType.NOTIFICATION,
                notification_type=NotificationType.DATASET_CONFIGURED,
                data=None,
            ),
        )

    @on_configure
    async def _configure(self, message: Message) -> None:
        """Configure the dataset manager."""
        # TODO: This is a temporary hack with the changes to user config loading
        self.dataset_configured.clear()
        await self._configure_dataset()

    async def _handle_conversation_request(
        self, message: ConversationRequestMessage
    ) -> ConversationResponseMessage:
        """Handle a conversation request."""
        self.logger.debug("Handling conversation request: %s", message)

        # Wait for the dataset to be configured if it is not already
        if not self.dataset_configured.is_set():
            self.logger.debug(
                "Dataset not configured. Waiting for dataset to be configured..."
            )
            await asyncio.wait_for(
                self.dataset_configured.wait(), timeout=DATASET_CONFIGURATION_TIMEOUT
            )

        if not self.dataset:
            raise self._service_error(
                "Dataset is empty and must be configured before handling requests.",
            )

        if message.conversation_id is None:
            return self._return_any_conversation(
                request_id=message.request_id,
            )
        else:
            return self._return_conversation_by_id(
                request_id=message.request_id,
                conversation_id=message.conversation_id,
            )

    def _return_any_conversation(
        self, request_id: str | None
    ) -> ConversationResponseMessage:
        """Return any conversation from the dataset based on the user specified method."""

        # TODO: Implement the user specified method (random, round robin, etc.)
        conversation = random.choice(list(self.dataset.values()))
        self.logger.debug("Sending random conversation response: %s", conversation)
        return ConversationResponseMessage(
            service_id=self.service_id,
            request_id=request_id,
            conversation=conversation,
        )

    def _return_conversation_by_id(
        self, request_id: str | None, conversation_id: str
    ) -> ConversationResponseMessage:
        """Return a conversation if it exists, otherwise raise an error."""

        if conversation_id not in self.dataset:
            raise self._service_error(
                f"Conversation {conversation_id} not found in dataset.",
            )

        conversation = self.dataset[conversation_id]
        self.logger.debug("Sending conversation response: %s", conversation)
        return ConversationResponseMessage(
            service_id=self.service_id,
            request_id=request_id,
            conversation=conversation,
        )

    async def _handle_dataset_timing_request(
        self, message: DatasetTimingRequest
    ) -> DatasetTimingResponse:
        """Handle a dataset timing request."""
        self.logger.debug("Handling dataset timing request: %s", message)
        if not self.dataset:
            raise self._service_error(
                "Dataset is empty and must be configured before handling timing requests.",
            )

        timing_dataset = []
        for conversation_id, conversation in self.dataset.items():
            for turn in conversation.turns:
                timing_dataset.append((turn.timestamp, conversation_id))

        return DatasetTimingResponse(
            service_id=self.service_id,
            request_id=message.request_id,
            timing_data=timing_dataset,
        )


def main() -> None:
    """Main entry point for the dataset manager."""

    from aiperf.common.bootstrap import bootstrap_and_run_service

    bootstrap_and_run_service(DatasetManager)


if __name__ == "__main__":
    sys.exit(main())
