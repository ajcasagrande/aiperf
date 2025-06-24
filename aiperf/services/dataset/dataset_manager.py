# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
import os
import sys

from aiperf.common.comms.base import RepClientInterface
from aiperf.common.config import ServiceConfig
from aiperf.common.enums import MessageType, NotificationType, ServiceType, Topic
from aiperf.common.exceptions import AIPerfError
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
    NotificationMessage,
)
from aiperf.common.service.base_component_service import BaseComponentService
from aiperf.common.tokenizer import Tokenizer


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

        self.tokenizer = Tokenizer.from_pretrained(
            os.getenv("AIPERF_MODEL", "deepseek-ai/DeepSeek-R1-Distill-Llama-8B")
        )

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

        # TODO: Re-enable tokenizer
        # if self.tokenizer is None:
        #     raise ValueError("Tokenizer is not initialized")

        self.logger.debug(f"Handling conversation request: {message}")
        # TODO: Implement conversation request handling
        return ConversationResponseMessage(
            service_id=self.service_id,
            request_id=message.request_id,
            conversation_id=message.conversation_id,
            conversation_data=[
                # {"role": "system", "content": "You are a helpful assistant."},
                {
                    "role": "user",
                    "content": "IO Sir you say well and well you do conceive And since you do profess to be a suitor You must as we do gratify this gentleman To whom we all rest generally beholding TRANIO Sir I shall not be slack in sign whereof Please ye we may contrive this afternoon And quaff carouses to our mistress health And do as adversaries do in law Strive mightily but eat and drink as friends GRUMIO BIONDELLO O excellent motion Fellows lets be gone HORT",
                    # "content": PromptGenerator.create_synthetic_prompt(
                    #     tokenizer=self.tokenizer,
                    #     prompt_tokens_mean=100,
                    #     prompt_tokens_stddev=0,
                    # ),
                },
            ],
        )

    async def _handle_dataset_timing_request(
        self, message: DatasetTimingRequest
    ) -> DatasetTimingResponse:
        """Handle a dataset timing request."""
        self.logger.info(
            "Handling dataset timing request %s",
            message,
        )
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
