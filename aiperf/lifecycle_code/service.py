# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
Enhanced LifecycleService with integrated messaging and task management.

This module provides a user-friendly service class that combines
lifecycle management, messaging, and task management using simple inheritance.
"""

import asyncio
import logging
from typing import Any

from .base import LifecycleService
from .messaging import Command, Message, MessageBus, get_message_bus
from .tasks import TaskManager, get_task_manager


class ManagedLifecycleService(LifecycleService):
    """
    User-friendly service class with messaging and task management built-in.

    This class combines lifecycle management, messaging, and task management
    using simple inheritance patterns. Just override lifecycle methods and
    use decorators for handlers.

    Features:
    - Simple inheritance for lifecycle (just call super())
    - Automatic message bus integration
    - Built-in task management
    - Publish/subscribe messaging
    - Command/response patterns

    Example:
        class MyService(ManagedLifecycleService):
            def __init__(self):
                super().__init__(service_id="my_service")
                self.data = []

            async def initialize(self):
                await super().initialize()  # Always call super()
                self.db = await connect_database()

            async def start(self):
                await super().start()  # Always call super()
                self.logger.info("Service ready!")

            async def stop(self):
                await super().stop()  # Always call super()
                await self.db.close()  # Stop and cleanup together

            @message_handler("DATA_RECEIVED")
            async def handle_data(self, message):
                self.data.append(message.content)
                await self.publish_message("DATA_PROCESSED", len(self.data))

            @command_handler("GET_STATS")
            async def get_stats(self, command):
                return {"total_items": len(self.data)}

            @background_task(interval=30.0)
            async def cleanup(self):
                self.data = self.data[-1000:]  # Keep last 1000
    """

    def __init__(
        self,
        service_id: str | None = None,
        logger: logging.Logger | None = None,
        message_bus: MessageBus | None = None,
        task_manager: TaskManager | None = None,
        **kwargs,
    ):
        super().__init__(service_id=service_id, logger=logger, **kwargs)

        # Use provided instances or get global ones
        self.message_bus = message_bus or get_message_bus()
        self.task_manager = task_manager or get_task_manager()

    # =================================================================
    # Simple Lifecycle Methods - Override and Call super()
    # =================================================================

    async def initialize(self):
        """Initialize messaging. Override and call super().initialize()"""
        await super().initialize()

        # Start message bus if not already running
        if not self.message_bus._running:
            await self.message_bus.start()

        # Register this service with the message bus
        self.message_bus.register_service(
            self.service_id, self._handle_targeted_message
        )

        # Subscribe to message types this service handles
        self._subscribe_to_messages()

    async def stop(self):
        """Stop and cleanup messaging. Override and call super().stop()"""
        await super().stop()

        # Unregister from message bus
        self.message_bus.unregister_service(self.service_id)

        # Shutdown task manager
        await self.task_manager.shutdown()

    # =================================================================
    # Messaging Methods
    # =================================================================

    async def publish_message(
        self, message_type: str, content: Any = None, target_id: str | None = None
    ) -> None:
        """Publish a message to the message bus."""
        message = Message(
            type=message_type,
            content=content,
            sender_id=self.service_id,
            target_id=target_id,
        )
        await self.message_bus.publish(message)

    async def send_command(
        self,
        command_type: str,
        target_id: str,
        content: Any = None,
        timeout: float = 30.0,
    ) -> Any:
        """Send a command and wait for response."""
        command = Command(
            type=command_type,
            content=content,
            sender_id=self.service_id,
            target_id=target_id,
            timeout=timeout,
        )
        return await self.message_bus.send_command(command, timeout)

    async def reply_to_message(self, original_message: Message, content: Any) -> None:
        """Send a reply to a message."""
        await self.message_bus.send_response(original_message, content)

    # =================================================================
    # Task Management Methods
    # =================================================================

    def create_background_task(
        self, coro: Any, name: str | None = None
    ) -> asyncio.Task:
        """Create a background task managed by the task manager."""
        return self.task_manager.create_task(coro, name)

    def create_periodic_task(
        self, func: Any, interval: float, name: str | None = None
    ) -> asyncio.Task:
        """Create a periodic task managed by the task manager."""
        return self.task_manager.create_periodic_task(func, interval, name)

    def get_task_status(self) -> dict:
        """Get status of all background tasks."""
        return self.task_manager.get_task_status()

    # =================================================================
    # Internal Message Handling
    # =================================================================

    async def _handle_targeted_message(self, message: Message) -> None:
        """Handle messages targeted specifically to this service."""
        # Check if it's a command that expects a response
        if isinstance(message, Command) and message.expects_response:
            try:
                response = await self.handle_command(message.type, message)
                await self.reply_to_message(message, response)
            except Exception as e:
                self.logger.error(f"Error handling command {message.type}: {e}")
                await self.reply_to_message(message, {"error": str(e)})
        else:
            # Regular message handling
            await self.handle_message(message.type, message)

    def _subscribe_to_messages(self) -> None:
        """Subscribe to all message types this service can handle."""
        # Subscribe to message types from @message_handler decorators
        for message_type, handlers in self._message_handlers.items():
            if handlers:  # Only subscribe if we have handlers
                self.message_bus.subscribe(message_type, self._handle_broadcast_message)

    async def _handle_broadcast_message(self, message: Message) -> None:
        """Handle broadcast messages."""
        await self.handle_message(message.type, message)


# Convenience base class alias
AIPerf = ManagedLifecycleService
