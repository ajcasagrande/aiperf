# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0


import asyncio
from collections.abc import Callable, Mapping
from typing import cast

from aiperf.common.comms.base_comms import (
    BaseCommunication,
    CommunicationFactory,
)
from aiperf.common.config.service_config import ServiceConfig
from aiperf.common.enums.communication_enums import CommunicationClientAddressType
from aiperf.common.enums.message_enums import CommandType
from aiperf.common.messages.commands import CommandMessage, CommandResponseMessage
from aiperf.common.messages.message import Message
from aiperf.common.models.error_models import ErrorDetails
from aiperf.common.types import MessageTypeT
from aiperf.core.lifecycle import LifecycleMixin


class CommunicationMixin(LifecycleMixin):
    """Mixin that provides a communications instance."""

    def __init__(self, service_config: ServiceConfig, **kwargs) -> None:
        self.comms: BaseCommunication = CommunicationFactory.create_instance(
            service_config.comm_backend,
            config=service_config.comm_config,
        )
        super().__init__(service_config=service_config, comms=self.comms, **kwargs)

    async def _initialize(self) -> None:
        await super()._initialize()
        await self.comms.initialize()

    async def _stop(self) -> None:
        await super()._stop()
        await self.comms.shutdown()


class MessageBusMixin(LifecycleMixin):
    """Mixin that provides a message bus instance."""

    def __init__(self, comms: BaseCommunication, **kwargs) -> None:
        self.sub_client = comms.create_sub_client(
            CommunicationClientAddressType.EVENT_BUS_PROXY_BACKEND
        )
        self.pub_client = comms.create_pub_client(
            CommunicationClientAddressType.EVENT_BUS_PROXY_FRONTEND
        )

        # Handler discovery and management
        self._message_handlers: dict[MessageTypeT, list[Callable]] = {}
        self._command_handlers: dict[MessageTypeT, list[Callable]] = {}
        self._command_responses: dict[str, asyncio.Future] = {}

        # Pass through the comms and clients to base classes
        super().__init__(
            comms=comms,
            pub_client=self.pub_client,
            sub_client=self.sub_client,
            **kwargs,
        )

    # =================================================================
    # Handler Discovery and Registration (Private)
    # =================================================================

    def _discover_handlers(self) -> None:
        """Discover message and command handlers from decorators."""
        for name in dir(self):
            method = getattr(self, name)
            if not callable(method):
                continue

            # Message handlers (@message_handler)
            if hasattr(method, "_message_types"):
                for message_type in method._message_types:
                    self._register_message_handler(message_type, method)

            # Command handlers (@command_handler)
            if hasattr(method, "_command_types"):
                for command_type in method._command_types:
                    self._register_command_handler(command_type, method)

    def _register_message_handler(
        self, message_type: MessageTypeT, handler: Callable
    ) -> None:
        self._message_handlers.setdefault(message_type, []).append(handler)

    def _register_command_handler(
        self, command_type: CommandType, handler: Callable
    ) -> None:
        self._command_handlers.setdefault(command_type, []).append(handler)

    ###########################################################################
    # Lifecycle Implementation
    ###########################################################################

    async def _initialize(self) -> None:
        await super()._initialize()
        self._discover_handlers()
        await self.subscribe_all(self._message_handlers)
        # For commands, we forward to our internal handler for filtering
        command_handlers_dict = {}
        for typ, handlers in self._command_handlers.items():
            command_handlers_dict[typ] = [
                self._create_command_handler(handler) for handler in handlers
            ]
        await self.subscribe_all(command_handlers_dict)

    # =================================================================
    # Message and Command Handling (Private)
    # =================================================================

    def _create_command_handler(self, handler: Callable) -> Callable:
        """Process a command message received from the controller.

        This method will process the command message and execute the appropriate action.
        """

        async def command_handler(message: CommandMessage) -> None:
            if (
                message.target_service_id is not None
                and message.target_service_id != self.id
            ):
                self.debug(
                    lambda: f"{self.id}: Ignoring command message from {message.target_service_id}: {message}"
                )
                return
                # Check service_type if it exists on this instance
            service_type = getattr(self, "service_type", None)
            if (
                message.target_service_type is not None
                and service_type is not None
                and service_type != message.target_service_type
            ):
                self.debug(
                    lambda: f"{self.id}: Ignoring command message from {message.target_service_type}: {message}"
                )
                return

            response_data = None
            try:
                response_data = await handler(message)

                # Publish the success response
                await self.publish(
                    CommandResponseMessage(
                        message_type=cast(
                            MessageTypeT, f"{message.message_type}_response"
                        ),
                        request_id=message.request_id,
                        service_id=self.id,
                        origin_service_id=message.service_id,
                        data=response_data,
                    ),
                )

            except Exception as e:
                self.exception(
                    f"Error processing command message {message.message_type}: {e}"
                )
                # Publish the failure response
                await self.publish(
                    CommandResponseMessage(
                        message_type=cast(
                            MessageTypeT, f"{message.message_type}_response"
                        ),
                        request_id=message.request_id,
                        service_id=self.id,
                        origin_service_id=message.service_id,
                        error=ErrorDetails.from_exception(e),
                    ),
                )

        return command_handler

    # =================================================================
    # Message and Command Publishing (Public)
    # =================================================================

    async def publish(self, message: Message) -> None:
        await self.pub_client.publish(message)

    async def subscribe(self, message_type: MessageTypeT, handler: Callable) -> None:
        await self.sub_client.subscribe(message_type, handler)

    async def subscribe_all(
        self, message_callback_map: Mapping[MessageTypeT, Callable | list[Callable]]
    ) -> None:
        await self.sub_client.subscribe_all(message_callback_map)
