# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
Legacy-compatible messaging system for AIPerf services.

This module provides a drop-in replacement for the simple messaging system
that utilizes the real pub/sub clients from the legacy aiperf infrastructure.
"""

import asyncio
import logging
import time
from collections.abc import Callable
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field

from aiperf.common.comms.base_comms import (
    BaseCommunication,
    CommunicationFactory,
    PubClientProtocol,
    SubClientProtocol,
)
from aiperf.common.config import ServiceConfig, UserConfig
from aiperf.common.enums import (
    CommandType as LegacyCommandType,
)
from aiperf.common.enums import (
    CommunicationClientAddressType,
)
from aiperf.common.enums import (
    MessageType as LegacyMessageType,
)
from aiperf.common.messages import Message as LegacyMessage
from aiperf.common.types import MessageTypeT


class Message(BaseModel):
    """
    Simple, clean message model compatible with legacy infrastructure.

    This maintains the same API as the simple message system but uses
    legacy message types underneath.
    """

    id: str = Field(default_factory=lambda: str(uuid4()))
    type: str = Field(..., description="Message type identifier")
    content: Any = Field(default=None, description="Message content/payload")
    sender_id: str | None = Field(default=None, description="ID of sending service")
    target_id: str | None = Field(
        default=None, description="ID of target service (None for broadcast)"
    )
    timestamp: float = Field(default_factory=time.time, description="Message timestamp")
    reply_to: str | None = Field(
        default=None, description="Message ID this is replying to"
    )

    class Config:
        arbitrary_types_allowed = True

    def to_legacy_message(self) -> LegacyMessage:
        """Convert to legacy message format for transmission."""
        # Map simple message type to legacy message type
        legacy_type = self._map_to_legacy_type(self.type)

        # Create a generic legacy message with our content
        from aiperf.common.messages.message import Message as BaseLegacyMessage

        class SimpleMessage(BaseLegacyMessage):
            message_type: MessageTypeT = legacy_type
            data: Any = Field(default=None)
            sender_id: str | None = Field(default=None)
            target_id: str | None = Field(default=None)
            original_id: str | None = Field(default=None)
            reply_to: str | None = Field(default=None)

        return SimpleMessage(
            message_type=legacy_type,
            data=self.content,
            sender_id=self.sender_id,
            target_id=self.target_id,
            original_id=self.id,
            reply_to=self.reply_to,
        )

    @classmethod
    def from_legacy_message(cls, legacy_msg: LegacyMessage) -> "Message":
        """Convert from legacy message format."""
        return cls(
            id=getattr(legacy_msg, "original_id", str(uuid4())),
            type=str(legacy_msg.message_type),
            content=getattr(legacy_msg, "data", None),
            sender_id=getattr(legacy_msg, "sender_id", None),
            target_id=getattr(legacy_msg, "target_id", None),
            reply_to=getattr(legacy_msg, "reply_to", None),
        )

    def _map_to_legacy_type(self, simple_type: str) -> MessageTypeT:
        """Map simple message types to legacy message types."""
        # Common mappings
        mapping = {
            "DATA_MESSAGE": LegacyMessageType.Test,
            "STATUS": LegacyMessageType.Status,
            "Error": LegacyMessageType.Error,
            "HEARTBEAT": LegacyMessageType.Heartbeat,
            "REGISTRATION": LegacyMessageType.Registration,
            "HEALTH_CHECK": LegacyMessageType.ServiceHealth,
            # Generic mapping for unknown types
        }

        # Try direct mapping first
        if simple_type in mapping:
            return mapping[simple_type]

        # Try to find a legacy type that matches
        for legacy_type in LegacyMessageType:
            if legacy_type.value.upper() == simple_type.upper():
                return legacy_type

        # Default to TEST for unknown types
        return LegacyMessageType.Test


class Command(Message):
    """
    Command message that expects a response.

    Commands are a special type of message that typically expect a response.
    """

    expects_response: bool = Field(default=True)
    timeout: float = Field(default=30.0, description="Response timeout in seconds")

    def _map_to_legacy_type(self, simple_type: str) -> MessageTypeT:
        """Map simple command types to legacy command types."""
        # Command-specific mappings
        mapping = {
            "GET_STATUS": LegacyCommandType.ProfileStart,
            "CONFIGURE": LegacyCommandType.ProfileConfigure,
            "START": LegacyCommandType.ProfileStart,
            "STOP": LegacyCommandType.ProfileStop,
            "Shutdown": LegacyCommandType.Shutdown,
        }

        # Try direct mapping first
        if simple_type in mapping:
            return mapping[simple_type]

        # Try to find a legacy command type that matches
        for legacy_type in LegacyCommandType:
            if legacy_type.value.upper() == simple_type.upper():
                return legacy_type

        # Default to ProfileStart for unknown command types
        return LegacyCommandType.ProfileStart


class MessageBus:
    """
    Legacy-compatible message bus for service communication.

    This provides the same API as the simple message bus but uses
    the real ZMQ pub/sub infrastructure from the legacy system.

    Features:
    - Real ZMQ pub/sub messaging
    - Service configuration integration
    - Legacy message compatibility
    - Command/response patterns
    - Message filtering by type and target

    Example:
        # Create with service configuration
        service_config = ServiceConfig(comm_backend=CommunicationBackend.ZMQ_TCP)
        bus = MessageBus(service_config=service_config)

        # Subscribe to messages
        async def handle_data(message):
            print(f"Received: {message.content}")

        bus.subscribe("DATA_MESSAGE", handle_data)

        # Publish messages
        await bus.publish(Message(type="DATA_MESSAGE", content="Hello World"))

        # Send commands with responses
        response = await bus.send_command(
            Command(type="GET_STATUS", target_id="service1")
        )
    """

    def __init__(
        self,
        logger: logging.Logger | None = None,
        service_config: ServiceConfig | None = None,
        user_config: UserConfig | None = None,
    ):
        self.logger = logger or logging.getLogger(__name__)
        self.service_config = service_config or ServiceConfig()
        self.user_config = user_config

        # Legacy communication infrastructure
        self.comms: BaseCommunication | None = None
        self.pub_client: PubClientProtocol | None = None
        self.sub_client: SubClientProtocol | None = None

        # Message handling
        self._subscribers: dict[str, list[Callable]] = {}
        self._service_subscribers: dict[str, Callable] = {}
        self._pending_responses: dict[str, asyncio.Future] = {}
        self._running = False

    async def start(self) -> None:
        """Start the message bus using legacy infrastructure."""
        if self._running:
            return

        # Create communication instance from service config
        self.comms = CommunicationFactory.create_instance(
            self.service_config.comm_backend,
            config=self.service_config.comm_config,
        )

        # Initialize communication
        await self.comms.initialize()

        # Create pub/sub clients for event bus
        self.pub_client = self.comms.create_pub_client(
            CommunicationClientAddressType.EVENT_BUS_PROXY_FRONTEND
        )
        self.sub_client = self.comms.create_sub_client(
            CommunicationClientAddressType.EVENT_BUS_PROXY_BACKEND
        )

        # Set up message handling
        await self._setup_message_handling()

        self._running = True
        self.logger.debug("Legacy message bus started")

    async def stop(self) -> None:
        """Stop the message bus and cleanup legacy infrastructure."""
        if not self._running:
            return

        self._running = False

        # Shutdown communication
        if self.comms:
            await self.comms.shutdown()

        self.logger.debug("Legacy message bus stopped")

    async def _setup_message_handling(self) -> None:
        """Set up message handling using legacy subscription mechanisms."""
        if not self.sub_client:
            return

        # Subscribe to all registered message types
        message_handlers = {}
        for message_type, handlers in self._subscribers.items():
            if handlers:
                # Map simple type to legacy type for subscription
                temp_msg = Message(type=message_type, content=None)
                legacy_type = temp_msg._map_to_legacy_type(message_type)
                message_handlers[legacy_type] = self._create_legacy_handler(
                    message_type, handlers
                )

        if message_handlers:
            await self.sub_client.subscribe_all(message_handlers)

    def _create_legacy_handler(
        self, message_type: str, handlers: list[Callable]
    ) -> Callable:
        """Create a legacy message handler that converts back to simple messages."""

        async def legacy_handler(legacy_msg: LegacyMessage) -> None:
            # Convert legacy message back to simple message
            simple_msg = Message.from_legacy_message(legacy_msg)
            simple_msg.type = message_type  # Preserve original simple type

            # Check if this is a response to a pending command
            if simple_msg.reply_to and simple_msg.reply_to in self._pending_responses:
                future = self._pending_responses[simple_msg.reply_to]
                if not future.done():
                    future.set_result(simple_msg.content)
                return

            # Handle targeted messages
            if (
                simple_msg.target_id
                and simple_msg.target_id in self._service_subscribers
            ):
                handler = self._service_subscribers[simple_msg.target_id]
                try:
                    if asyncio.iscoroutinefunction(handler):
                        await handler(simple_msg)
                    else:
                        handler(simple_msg)
                except Exception as e:
                    self.logger.error(
                        f"Error in service handler for {simple_msg.target_id}: {e}"
                    )

            # Handle broadcast messages
            for handler in handlers:
                try:
                    if asyncio.iscoroutinefunction(handler):
                        await handler(simple_msg)
                    else:
                        handler(simple_msg)
                except Exception as e:
                    self.logger.error(f"Error in message handler: {e}")

        return legacy_handler

    def subscribe(self, message_type: str, handler: Callable[[Message], Any]) -> None:
        """
        Subscribe to messages of a specific type.

        Args:
            message_type: Type of messages to receive
            handler: Function to call when message is received
        """
        if message_type not in self._subscribers:
            self._subscribers[message_type] = []
        self._subscribers[message_type].append(handler)
        self.logger.debug(f"Subscribed to {message_type}")

        # If already running, update subscriptions
        if self._running and self.sub_client:
            asyncio.create_task(self._update_subscription(message_type))

    async def _update_subscription(self, message_type: str) -> None:
        """Update subscription for a new message type."""
        if not self.sub_client:
            return

        # Map to legacy type and subscribe
        temp_msg = Message(type=message_type, content=None)
        legacy_type = temp_msg._map_to_legacy_type(message_type)
        handlers = self._subscribers[message_type]
        legacy_handler = self._create_legacy_handler(message_type, handlers)

        await self.sub_client.subscribe(legacy_type, legacy_handler)

    def unsubscribe(self, message_type: str, handler: Callable[[Message], Any]) -> None:
        """
        Unsubscribe from messages of a specific type.

        Args:
            message_type: Type of messages to stop receiving
            handler: Handler function to remove
        """
        if message_type in self._subscribers:
            try:
                self._subscribers[message_type].remove(handler)
                if not self._subscribers[message_type]:
                    del self._subscribers[message_type]
                self.logger.debug(f"Unsubscribed from {message_type}")
            except ValueError:
                pass

    def register_service(
        self, service_id: str, handler: Callable[[Message], Any]
    ) -> None:
        """
        Register a service to receive targeted messages.

        Args:
            service_id: ID of the service
            handler: Function to call for messages targeted to this service
        """
        self._service_subscribers[service_id] = handler
        self.logger.debug(f"Registered service {service_id}")

    def unregister_service(self, service_id: str) -> None:
        """
        Unregister a service.

        Args:
            service_id: ID of the service to unregister
        """
        if service_id in self._service_subscribers:
            del self._service_subscribers[service_id]
            self.logger.debug(f"Unregistered service {service_id}")

    async def publish(self, message: Message) -> None:
        """
        Publish a message to the bus using legacy infrastructure.

        Args:
            message: Message to publish
        """
        if not self._running:
            await self.start()

        if not self.pub_client:
            raise RuntimeError("Pub client not initialized")

        # Convert to legacy message and publish
        legacy_msg = message.to_legacy_message()
        await self.pub_client.publish(legacy_msg)

    async def send_command(self, command: Command, timeout: float | None = None) -> Any:
        """
        Send a command and wait for response using legacy infrastructure.

        Args:
            command: Command to send
            timeout: Response timeout (uses command timeout if None)

        Returns:
            Response content

        Raises:
            asyncio.TimeoutError: If no response received within timeout
        """
        if not self._running:
            await self.start()

        timeout = timeout or command.timeout
        future = asyncio.Future()
        self._pending_responses[command.id] = future

        try:
            await self.publish(command)
            return await asyncio.wait_for(future, timeout=timeout)
        except asyncio.TimeoutError:
            self._pending_responses.pop(command.id, None)
            raise
        finally:
            self._pending_responses.pop(command.id, None)

    async def send_response(self, original_message: Message, content: Any) -> None:
        """
        Send a response to a message using legacy infrastructure.

        Args:
            original_message: Message being responded to
            content: Response content
        """
        response = Message(
            type=f"{original_message.type}_RESPONSE",
            content=content,
            reply_to=original_message.id,
            target_id=original_message.sender_id,
        )
        await self.publish(response)


# Global message bus instance (can be overridden)
_global_bus: MessageBus | None = None


def get_message_bus(
    service_config: ServiceConfig | None = None,
    user_config: UserConfig | None = None,
) -> MessageBus:
    """Get the global message bus instance."""
    global _global_bus
    if _global_bus is None:
        _global_bus = MessageBus(
            service_config=service_config,
            user_config=user_config,
        )
    return _global_bus


def set_message_bus(bus: MessageBus) -> None:
    """Set the global message bus instance."""
    global _global_bus
    _global_bus = bus
