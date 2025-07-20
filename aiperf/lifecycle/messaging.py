# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
Simple, clean messaging system for AIPerf services.

This module provides a straightforward message bus implementation that's
easy to use and understand, without the complexity of the current system.
"""

import asyncio
import logging
import time
from collections.abc import Callable
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


class Message(BaseModel):
    """
    Simple, clean message model.

    This replaces the complex message hierarchy with a single, flexible message type.
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


class Command(Message):
    """
    Command message that expects a response.

    Commands are a special type of message that typically expect a response.
    """

    expects_response: bool = Field(default=True)
    timeout: float = Field(default=30.0, description="Response timeout in seconds")


class MessageBus:
    """
    Simple, in-memory message bus for service communication.

    This provides a clean, straightforward messaging system without the complexity
    of multiple communication protocols and clients.

    Features:
    - Simple pub/sub messaging
    - Command/response patterns
    - Message filtering by type and target
    - Easy to extend and customize

    Example:
        bus = MessageBus()

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

    def __init__(self, logger: logging.Logger | None = None):
        self.logger = logger or logging.getLogger(__name__)
        self._subscribers: dict[str, list[Callable]] = {}
        self._service_subscribers: dict[str, Callable] = {}
        self._pending_responses: dict[str, asyncio.Future] = {}
        self._running = False
        self._message_queue: asyncio.Queue = asyncio.Queue()
        self._processor_task: asyncio.Task | None = None

    async def start(self) -> None:
        """Start the message bus."""
        if self._running:
            return

        self._running = True
        self._processor_task = asyncio.create_task(self._process_messages())
        self.logger.debug("Message bus started")

    async def stop(self) -> None:
        """Stop the message bus."""
        if not self._running:
            return

        self._running = False

        if self._processor_task:
            self._processor_task.cancel()
            try:
                await self._processor_task
            except asyncio.CancelledError:
                pass

        self.logger.debug("Message bus stopped")

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
        Publish a message to the bus.

        Args:
            message: Message to publish
        """
        if not self._running:
            await self.start()

        await self._message_queue.put(message)

    async def send_command(self, command: Command, timeout: float | None = None) -> Any:
        """
        Send a command and wait for response.

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
        Send a response to a message.

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

    async def _process_messages(self) -> None:
        """Process messages from the queue."""
        while self._running:
            try:
                message = await asyncio.wait_for(self._message_queue.get(), timeout=1.0)
                await self._handle_message(message)
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                self.logger.error(f"Error processing message: {e}")

    async def _handle_message(self, message: Message) -> None:
        """Handle a single message."""
        self.logger.debug(f"Processing message: {message.type}")

        # Check if this is a response to a pending command
        if message.reply_to and message.reply_to in self._pending_responses:
            future = self._pending_responses[message.reply_to]
            if not future.done():
                future.set_result(message.content)
            return

        # Handle targeted messages
        if message.target_id and message.target_id in self._service_subscribers:
            handler = self._service_subscribers[message.target_id]
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(message)
                else:
                    handler(message)
            except Exception as e:
                self.logger.error(
                    f"Error in service handler for {message.target_id}: {e}"
                )

        # Handle broadcast messages by type
        handlers = self._subscribers.get(message.type, [])
        for handler in handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(message)
                else:
                    handler(message)
            except Exception as e:
                self.logger.error(f"Error in message handler: {e}")


# Global message bus instance (can be overridden)
_global_bus: MessageBus | None = None


def get_message_bus() -> MessageBus:
    """Get the global message bus instance."""
    global _global_bus
    if _global_bus is None:
        _global_bus = MessageBus()
    return _global_bus


def set_message_bus(bus: MessageBus) -> None:
    """Set the global message bus instance."""
    global _global_bus
    _global_bus = bus
