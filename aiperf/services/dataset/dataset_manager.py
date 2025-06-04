# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
import sys
from typing import cast

from aiperf.common.comms.client_enums import ClientType, RepClientType
from aiperf.common.config.service_config import ServiceConfig
from aiperf.common.decorators import (
    on_cleanup,
    on_configure,
    on_init,
    on_start,
    on_stop,
)
from aiperf.common.enums import DataTopic, MessageType, ServiceType
from aiperf.common.models import (
    ConversationRequestMessage,
    ConversationResponseMessage,
    ConversationResponsePayload,
    Message,
    Payload,
)
from aiperf.common.service.base_component_service import BaseComponentService


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

    @property
    def service_type(self) -> ServiceType:
        """The type of service."""
        return ServiceType.DATASET_MANAGER

    @property
    def required_clients(self) -> list[ClientType]:
        """The communication clients required by the service."""
        return [
            *(super().required_clients or []),
            RepClientType.CONVERSATION_DATA,
        ]

    @on_init
    async def _initialize(self) -> None:
        """Initialize dataset manager-specific components."""
        self.logger.debug("Initializing dataset manager")
        # TODO: Implement dataset manager initialization
        await self.comms.register_request_handler(
            service_id=self.service_id,
            topic=DataTopic.CONVERSATION,
            message_type=MessageType.CONVERSATION_REQUEST,
            handler=self._handle_conversation_request,
        )

    @on_start
    async def _start(self) -> None:
        """Start the dataset manager."""
        self.logger.debug("Starting dataset manager")
        # TODO: Implement dataset manager start

    @on_stop
    async def _stop(self) -> None:
        """Stop the dataset manager."""
        self.logger.debug("Stopping dataset manager")
        # TODO: Implement dataset manager stop

    @on_cleanup
    async def _cleanup(self) -> None:
        """Clean up dataset manager-specific components."""
        self.logger.debug("Cleaning up dataset manager")
        # TODO: Implement dataset manager cleanup

    @on_configure
    async def _configure(self, payload: Payload) -> None:
        """Configure the dataset manager."""
        self.logger.debug(f"Configuring dataset manager with payload: {payload}")
        # TODO: Implement dataset manager configuration

    async def _handle_conversation_request(self, message: Message) -> Message:
        """Handle a conversation request."""
        self.logger.debug(f"Handling conversation request: {message}")
        message = cast(ConversationRequestMessage, message)
        # TODO: Implement conversation request handling
        return ConversationResponseMessage(
            service_id=self.service_id,
            request_id=message.request_id,
            payload=ConversationResponsePayload(
                conversation_id=message.payload.conversation_id,
                conversation_data=[
                    {"role": "system", "content": "You are a helpful assistant."},
                    {
                        "role": "user",
                        "content": "Tell me about NVIDIA AI performance testing.",
                    },
                ],
            ),
        )


def main() -> None:
    """Main entry point for the dataset manager."""

    from aiperf.common.bootstrap import bootstrap_and_run_service

    bootstrap_and_run_service(DatasetManager)


if __name__ == "__main__":
    sys.exit(main())
