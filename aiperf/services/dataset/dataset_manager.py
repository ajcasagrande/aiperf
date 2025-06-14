# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
import sys

from aiperf.common.comms.client_enums import ClientType, RepClientType
from aiperf.common.config.service_config import ServiceConfig
from aiperf.common.enums import MessageType, ServiceType, Topic
from aiperf.common.factories import ServiceFactory
from aiperf.common.hooks import (
    on_cleanup,
    on_configure,
    on_init,
    on_start,
    on_stop,
)
from aiperf.common.messages import (
    ConversationRequestMessage,
    ConversationResponseMessage,
    Message,
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
        self.tokenizer = Tokenizer.from_pretrained(
            "deepseek-ai/DeepSeek-R1-Distill-Llama-8B"
        )
        await self.comms.register_request_handler(
            service_id=self.service_id,
            topic=Topic.CONVERSATION_DATA,
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
    async def _configure(self, message: Message) -> None:
        """Configure the dataset manager."""
        self.logger.debug(f"Configuring dataset manager with message: {message}")
        # TODO: Implement dataset manager configuration

    async def _handle_conversation_request(
        self, message: ConversationRequestMessage
    ) -> ConversationResponseMessage:
        """Handle a conversation request."""
        if self.tokenizer is None:
            raise ValueError("Tokenizer is not initialized")

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
                    "content": "softly smiteth That from the cold stone sparks of fire do fly Whereat a waxen torch forthwith he lighteth Which must be lodestar to his lustful eye And to the flame thus speaks advisedly As from this cold flint I enforced this fire So Lucrece must I force to my desire Here pale with fear he doth premeditate The dangers of his loathsome enterprise And in his inward mind he doth debate What following sorrow may on this arise Then looking scorn",
                    # "content": PromptGenerator.create_synthetic_prompt(
                    #     tokenizer=self.tokenizer,
                    #     prompt_tokens_mean=100,
                    #     prompt_tokens_stddev=0,
                    # ),
                },
            ],
        )


def main() -> None:
    """Main entry point for the dataset manager."""

    from aiperf.common.bootstrap import bootstrap_and_run_service

    bootstrap_and_run_service(DatasetManager)


if __name__ == "__main__":
    sys.exit(main())
