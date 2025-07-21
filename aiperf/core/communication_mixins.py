# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0


from collections.abc import Callable, Coroutine
from typing import cast

from aiperf.common.comms.base_comms import (
    BaseCommunication,
    CommunicationFactory,
    ReplyClientProtocol,
)
from aiperf.common.config.service_config import ServiceConfig
from aiperf.common.enums.communication_enums import CommunicationClientAddressType
from aiperf.common.messages.commands import CommandMessage, CommandResponseMessage
from aiperf.common.messages.message import Message
from aiperf.common.models.error_models import ErrorDetails
from aiperf.common.types import (
    Any,
    MessageTypeT,
)
from aiperf.core.decorators import attrs
from aiperf.core.lifecycle import LifecycleMixin


class CommunicationMixin(LifecycleMixin):
    """Mixin that provides an interface to the communication layer."""

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
    """Mixin that provides an interface to the message bus."""

    def __init__(self, comms: BaseCommunication, **kwargs) -> None:
        self.sub_client = comms.create_sub_client(
            CommunicationClientAddressType.EVENT_BUS_PROXY_BACKEND
        )  # type: ignore
        self.pub_client = comms.create_pub_client(
            CommunicationClientAddressType.EVENT_BUS_PROXY_FRONTEND
        )  # type: ignore

        # Handler discovery and management
        setattr(self, attrs.message_handler_types, {})
        setattr(self, attrs.command_handler_types, {})

        # Pass through the comms and clients to base classes
        super().__init__(
            comms=comms,
            pub_client=self.pub_client,
            sub_client=self.sub_client,
            **kwargs,
        )

    async def publish(self, message: Message) -> None:
        await self.pub_client.publish(message)

    async def _initialize(self) -> None:
        await super()._initialize()
        self._discover_message_handlers()
        await self._register_message_handlers()

    def _discover_message_handlers(self) -> None:
        """Discover message and command handlers from decorators."""
        for name in dir(self):
            method = getattr(self, name)
            if not callable(method):
                continue

            # Message handlers (@message_handler)
            if hasattr(method, attrs.message_handler_types):
                for message_type in getattr(method, attrs.message_handler_types):
                    self.debug(
                        lambda type=message_type,
                        method=method: f"{self}: Registering message handler for {type}: {method}"
                    )
                    getattr(self, attrs.message_handler_types).setdefault(
                        message_type, []
                    ).append(method)

            # Command handlers (@command_handler)
            if hasattr(method, attrs.command_handler_types):
                for command_type in getattr(method, attrs.command_handler_types):
                    self.debug(
                        lambda type=command_type,
                        method=method: f"{self}: Registering command handler for {type}: {method}"
                    )
                    getattr(self, attrs.command_handler_types).setdefault(
                        command_type, []
                    ).append(method)

    async def _register_message_handlers(self) -> None:
        """Register all of the discovered message and command handlers."""
        # For basic messages, we can just subscribe to all of them
        await self.sub_client.subscribe_all(getattr(self, attrs.message_handler_types))

        # For commands, we forward to our internal handler for filtering and automatic
        # response handling.
        command_handlers_dict: dict[MessageTypeT, list[Callable]] = {}
        for typ, handlers in getattr(self, attrs.command_handler_types).items():
            command_handlers_dict[typ] = [
                self._create_command_handler(handler) for handler in handlers
            ]
        await self.sub_client.subscribe_all(command_handlers_dict)

    def _create_command_handler(
        self, handler: Callable[[CommandMessage], Coroutine[Any, Any, Any | None]]
    ) -> Callable[[CommandMessage], Coroutine[Any, Any, None]]:
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

            response_data: CommandResponseMessage | None = None
            try:
                response_data = await handler(message)

                # Publish the success response
                await self.publish(
                    CommandResponseMessage(
                        message_type=f"{message.message_type}_response",
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


def _create_request_handler_mixin(
    name: str, address_type: CommunicationClientAddressType
) -> type[LifecycleMixin]:
    """Create a request handler mixin for a given address type."""

    class RequestHandlerMixin(LifecycleMixin):
        """Mixin that provides an interface to handle requests."""

        def __init__(self, comms: BaseCommunication, **kwargs) -> None:
            self.router_reply_client: ReplyClientProtocol = comms.create_reply_client(
                address_type
            )  # type: ignore
            super().__init__(
                comms=comms, router_reply_client=self.router_reply_client, **kwargs
            )

        async def _initialize(self) -> None:
            await super()._initialize()
            self._discover_request_handlers()
            self._register_request_handlers()

        def _discover_request_handlers(self) -> None:
            """Discover request handlers from decorators."""
            for name in dir(self):
                method = getattr(self, name)
                if not callable(method):
                    continue

                # Request handlers (@request_handler)
                if hasattr(method, attrs.request_handler_types):
                    for message_type in getattr(method, attrs.request_handler_types):
                        getattr(self, attrs.request_handler_types).setdefault(
                            message_type, []
                        ).append(method)

        def _register_request_handlers(self) -> None:
            """Register all of the discovered request handlers."""
            for message_type, handlers in getattr(
                self, attrs.request_handler_types
            ).items():
                for handler in handlers:
                    self.debug(
                        lambda type=message_type,
                        method=handler: f"{self}: Registering request handler for {type}: {method}"
                    )
                    # NOTE: The router reply client will handle errors and return a response message.
                    self.router_reply_client.register_request_handler(
                        self.id, message_type, handler
                    )

    RequestHandlerMixin.__name__ = name
    RequestHandlerMixin.__qualname__ = name
    RequestHandlerMixin.__doc__ = (
        f"Mixin that provides an interface to handle {name} requests."  # noqa: E501
    )
    return RequestHandlerMixin


DatasetRequestHandler = _create_request_handler_mixin(
    name="DatasetRequestHandler",
    address_type=CommunicationClientAddressType.DATASET_MANAGER_PROXY_BACKEND,
)
