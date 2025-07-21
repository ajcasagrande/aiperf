# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
Ultimate AIPerf Messaging System - Real Infrastructure Integration

This module provides the ultimate messaging system that uses REAL aiperf
infrastructure while maintaining a clean, user-friendly API.

Key Features:
- Real aiperf types: MessageType, CommandType, Message, CommandMessage
- Real ZMQ communication via aiperf infrastructure
- Type-safe messaging with full IDE support
- Clean, simple API for publishing and commanding
- Automatic integration with ServiceConfig and the entire aiperf ecosystem
- No custom message types or converters - everything is ground truth aiperf

This replaces the simple in-memory messaging system with a real ZMQ-based
system that integrates seamlessly with the existing aiperf infrastructure.

Usage:
    from aiperf.lifecycle.messaging import MessageBus
    from aiperf.common.enums import MessageType, CommandType
    from aiperf.common.config import ServiceConfig

    # Create with real service configuration
    service_config = ServiceConfig(comm_backend=CommunicationBackend.ZMQ_TCP)
    bus = MessageBus(service_config=service_config)

    # Subscribe to real message types
    @bus.message_handler(MessageType.STATUS)
    async def handle_status(message: Message):
        print(f"Status: {message}")

    # Publish real messages
    await bus.publish(MessageType.HEARTBEAT, service_id="my_service")

    # Send real commands
    response = await bus.send_command(
        CommandType.ProfileStart,
        target_service_id="worker_1"
    )
"""

import asyncio
import inspect
import logging
from collections.abc import Callable
from typing import Any

from aiperf.common.comms.base_comms import (
    BaseCommunication,
    CommunicationFactory,
    PubClientProtocol,
    SubClientProtocol,
)
from aiperf.common.config import ServiceConfig, UserConfig
from aiperf.common.enums import (
    CommandType,
    CommunicationClientAddressType,
    MessageType,
    ServiceType,
)
from aiperf.common.messages import (
    CommandMessage,
    CommandResponseMessage,
    HeartbeatMessage,
    Message,
    RegistrationMessage,
    StatusMessage,
)
from aiperf.common.types import MessageTypeT


class MessageBus:
    """
    Ultimate messaging system using real aiperf infrastructure.

    This provides a clean API while using the actual ZMQ pub/sub infrastructure,
    real message types, and full integration with the aiperf ecosystem.

    Features:
    - Real ZMQ pub/sub messaging via aiperf infrastructure
    - Type-safe with real MessageType and CommandType enums
    - Real Message and CommandMessage classes
    - Service configuration integration
    - Command/response patterns with timeout handling
    - Automatic message routing and subscription management

    This is the ONE messaging system you need for AIPerf development.
    """

    def __init__(
        self,
        service_config: ServiceConfig,
        user_config: UserConfig | None = None,
        logger: logging.Logger | None = None,
        **kwargs,
    ):
        self.service_config = service_config
        self.user_config = user_config
        self.logger = logger or logging.getLogger(__name__)

        # Real aiperf communication infrastructure
        self.comms: BaseCommunication | None = None
        self.pub_client: PubClientProtocol | None = None
        self.sub_client: SubClientProtocol | None = None

        # Message handling
        self._message_handlers: dict[MessageTypeT, list[Callable]] = {}
        self._command_handlers: dict[MessageTypeT, list[Callable]] = {}
        self._service_handlers: dict[str, Callable] = {}
        self._command_responses: dict[str, asyncio.Future] = {}

        # State
        self._running = False

    async def start(self) -> None:
        """Start the message bus using real aiperf infrastructure."""
        if self._running:
            return

        try:
            # Create real aiperf communication instance
            self.comms = CommunicationFactory.create_instance(
                self.service_config.comm_backend,
                config=self.service_config.comm_config,
            )

            # Initialize communication
            await self.comms.initialize()

            # Create pub/sub clients for event bus (real aiperf pattern)
            self.pub_client = self.comms.create_pub_client(
                CommunicationClientAddressType.EVENT_BUS_PROXY_FRONTEND
            )
            self.sub_client = self.comms.create_sub_client(
                CommunicationClientAddressType.EVENT_BUS_PROXY_BACKEND
            )

            # Set up message subscriptions
            await self._setup_subscriptions()

            self._running = True
            self.logger.debug(
                "Ultimate message bus started with real aiperf infrastructure"
            )

        except Exception as e:
            self.logger.error(f"Failed to start message bus: {e}")
            raise

    async def _stop(self) -> None:
        """Stop the message bus and cleanup real aiperf infrastructure."""
        if not self._running:
            return

        self._running = False

        try:
            # Shutdown real aiperf communication
            if self.comms:
                await self.comms.shutdown()

            # Cancel pending command responses
            for future in self._command_responses.values():
                if not future.done():
                    future.cancel()
            self._command_responses.clear()

            self.logger.debug("Ultimate message bus stopped")

        except Exception as e:
            self.logger.error(f"Error stopping message bus: {e}")

    # =================================================================
    # Simple Publishing API - Real aiperf Types
    # =================================================================

    async def publish(
        self,
        message_type: MessageTypeT,
        content: Any = None,
        service_id: str | None = None,
        service_type: ServiceType | None = None,
        **kwargs,
    ) -> None:
        """
        Publish a message using real aiperf infrastructure.

        Args:
            message_type: Real MessageType or CommandType enum
            content: Message content/data (for applicable message types)
            service_id: Service ID for messages that require it
            service_type: Service type for messages that require it
            **kwargs: Additional message fields

        Example:
            await bus.publish(MessageType.STATUS, service_id="my_service")
            await bus.publish(MessageType.HEARTBEAT, service_id="worker_1")
        """
        if not self.pub_client:
            raise RuntimeError("Message bus not started - call start() first")

        # Create appropriate real aiperf message based on type
        message = self._create_message(
            message_type, content, service_id, service_type, **kwargs
        )

        await self.pub_client.publish(message)
        self.logger.debug(f"Published {message_type}: {content}")

    async def send_command(
        self,
        command_type: CommandType,
        target_service_id: str | None = None,
        target_service_type: ServiceType | None = None,
        data: Any = None,
        timeout: float = 30.0,
        service_id: str | None = None,
        **kwargs,
    ) -> Any:
        """
        Send a command and wait for response using real aiperf infrastructure.

        Args:
            command_type: Real CommandType enum
            target_service_id: Target service ID (optional)
            target_service_type: Target service type (optional)
            data: Command data
            timeout: Response timeout in seconds
            service_id: Sending service ID
            **kwargs: Additional command fields

        Returns:
            Response data from the target service

        Example:
            response = await bus.send_command(
                CommandType.ProfileStart,
                target_service_id="worker_1",
                service_id="controller"
            )
        """
        if not self.pub_client:
            raise RuntimeError("Message bus not started - call start() first")

        # Create real aiperf command message
        command = CommandMessage(
            message_type=command_type,
            service_id=service_id,
            target_service_id=target_service_id,
            target_service_type=target_service_type,
            data=data,
            require_response=True,
            **kwargs,
        )

        # Set up response handling
        response_future = asyncio.Future()
        self._command_responses[command.request_id] = response_future

        try:
            # Send command
            await self.pub_client.publish(command)

            # Wait for response
            return await asyncio.wait_for(response_future, timeout=timeout)

        except asyncio.TimeoutError:
            self.logger.error(
                f"Command {command_type} to {target_service_id} timed out"
            )
            raise
        finally:
            # Cleanup
            self._command_responses.pop(command.request_id, None)

    # =================================================================
    # Subscription Management - Real aiperf Types
    # =================================================================

    def subscribe(
        self, message_type: MessageTypeT, handler: Callable[[Message], Any]
    ) -> None:
        """
        Subscribe to messages of a specific real aiperf type.

        Args:
            message_type: Real MessageType or CommandType enum
            handler: Function to call when message is received

        Example:
            def handle_status(message: StatusMessage):
                print(f"Status: {message}")

            bus.subscribe(MessageType.STATUS, handle_status)
        """
        if message_type not in self._message_handlers:
            self._message_handlers[message_type] = []
        self._message_handlers[message_type].append(handler)
        self.logger.debug(f"Subscribed to {message_type}")

    def unsubscribe(
        self, message_type: MessageTypeT, handler: Callable[[Message], Any]
    ) -> None:
        """
        Unsubscribe from messages of a specific type.

        Args:
            message_type: Real MessageType or CommandType enum
            handler: Handler function to remove
        """
        if message_type in self._message_handlers:
            try:
                self._message_handlers[message_type].remove(handler)
                if not self._message_handlers[message_type]:
                    del self._message_handlers[message_type]
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
        self._service_handlers[service_id] = handler
        self.logger.debug(f"Registered service {service_id}")

    def unregister_service(self, service_id: str) -> None:
        """
        Unregister a service.

        Args:
            service_id: ID of the service to unregister
        """
        if service_id in self._service_handlers:
            del self._service_handlers[service_id]
            self.logger.debug(f"Unregistered service {service_id}")

    # =================================================================
    # Decorator API for Clean Handler Registration
    # =================================================================

    def message_handler(self, *message_types: MessageTypeT) -> Callable:
        """
        Decorator for registering message handlers directly on the bus.

        Example:
            @bus.message_handler(MessageType.STATUS, MessageType.HEARTBEAT)
            async def handle_status_messages(message: Message):
                print(f"Received: {message}")
        """

        def decorator(func: Callable) -> Callable:
            for message_type in message_types:
                self.subscribe(message_type, func)
            return func

        return decorator

    def command_handler(self, *command_types: CommandType) -> Callable:
        """
        Decorator for registering command handlers directly on the bus.

        Example:
            @bus.command_handler(CommandType.ProfileStart)
            async def handle_profile_start(command: CommandMessage):
                # Process command
                return {"status": "started"}
        """

        def decorator(func: Callable) -> Callable:
            for command_type in command_types:
                self.subscribe(command_type, func)
            return func

        return decorator

    # =================================================================
    # Private Implementation Methods
    # =================================================================

    async def _setup_subscriptions(self) -> None:
        """Set up subscriptions for registered handlers."""
        if not self.sub_client:
            return

        # Create subscription map for all handlers
        subscription_map = {}

        # Add message handlers
        for message_type, handlers in self._message_handlers.items():
            if handlers:
                subscription_map[message_type] = self._handle_message

        # Add command handlers
        for command_type, handlers in self._command_handlers.items():
            if handlers:
                subscription_map[command_type] = self._handle_command

        # Always subscribe to command responses for our outgoing commands
        for command_type in CommandType:
            response_type = f"{command_type}_response"
            subscription_map[response_type] = self._handle_command_response

        if subscription_map:
            await self.sub_client.subscribe_all(subscription_map)

    async def _handle_message(self, message: Message) -> None:
        """Handle incoming message using registered handlers."""
        handlers = self._message_handlers.get(message.message_type, [])

        for handler in handlers:
            try:
                if inspect.iscoroutinefunction(handler):
                    await handler(message)
                else:
                    handler(message)
            except Exception as e:
                self.logger.error(f"Error in message handler {handler.__name__}: {e}")

    async def _handle_command(self, command: CommandMessage) -> None:
        """Handle incoming command using registered handlers."""
        handlers = self._command_handlers.get(command.message_type, [])

        for handler in handlers:
            try:
                if inspect.iscoroutinefunction(handler):
                    result = await handler(command)
                else:
                    result = handler(command)

                # Send response if command expects one
                if command.require_response and command.service_id:
                    response = CommandResponseMessage(
                        message_type=MessageType.CommandResponse,
                        request_id=command.request_id,
                        service_id=command.target_service_id,  # We're responding
                        origin_service_id=command.service_id,
                        data=result,
                    )
                    await self.pub_client.publish(response)

            except Exception as e:
                self.logger.error(f"Error in command handler {handler.__name__}: {e}")

                # Send error response
                if command.require_response and command.service_id:
                    error_response = CommandResponseMessage(
                        message_type=MessageType.CommandResponse,
                        request_id=command.request_id,
                        service_id=command.target_service_id,  # We're responding
                        origin_service_id=command.service_id,
                        error=str(e),
                    )
                    await self.pub_client.publish(error_response)

    async def _handle_command_response(self, response: CommandResponseMessage) -> None:
        """Handle command response for our outgoing commands."""
        if response.request_id in self._command_responses:
            future = self._command_responses[response.request_id]
            if not future.done():
                if response.error:
                    future.set_exception(Exception(response.error))
                else:
                    future.set_result(response.data)

    def _create_message(
        self,
        message_type: MessageTypeT,
        content: Any = None,
        service_id: str | None = None,
        service_type: ServiceType | None = None,
        **kwargs,
    ) -> Message:
        """Create the appropriate real aiperf message based on type."""
        # Create specific message classes based on the message type
        if message_type == MessageType.Heartbeat:
            return HeartbeatMessage(
                service_id=service_id, service_type=service_type, **kwargs
            )
        elif message_type == MessageType.Registration:
            return RegistrationMessage(
                service_id=service_id, service_type=service_type, **kwargs
            )
        elif message_type == MessageType.Status:
            return StatusMessage(
                service_id=service_id,
                service_type=service_type,
                # Add status-specific fields as needed
                **kwargs,
            )
        else:
            # For other message types, we need to create the appropriate message class
            # This is where we'd extend with other specific message types as needed
            return Message(message_type=message_type, **kwargs)

    # =================================================================
    # Convenience Properties and Methods
    # =================================================================

    @property
    def is_running(self) -> bool:
        """True if message bus is running."""
        return self._running

    def get_subscription_info(self) -> dict:
        """Get information about current subscriptions (debugging)."""
        return {
            "message_handlers": {
                str(msg_type): len(handlers)
                for msg_type, handlers in self._message_handlers.items()
            },
            "command_handlers": {
                str(cmd_type): len(handlers)
                for cmd_type, handlers in self._command_handlers.items()
            },
            "service_handlers": list(self._service_handlers.keys()),
            "pending_responses": len(self._command_responses),
        }


# Global message bus instance for convenience
_global_bus: MessageBus | None = None


def get_message_bus() -> MessageBus | None:
    """Get the global message bus instance."""
    return _global_bus


def set_message_bus(bus: MessageBus) -> None:
    """Set the global message bus instance."""
    global _global_bus
    _global_bus = bus


# Aliases for backward compatibility
MessageType = MessageType  # Re-export for convenience
CommandType = CommandType  # Re-export for convenience
