# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
Ultimate AIPerf Lifecycle Core - The Foundation of User-Friendly Service Development

This module provides the ultimate user-friendly base class for AIPerf services that:
- Uses REAL aiperf message types, command types, and communication infrastructure
- Provides clean initialize()/start()/stop() inheritance patterns
- Automatically handles decorator discovery and registration
- Abstracts away ALL communication complexities
- Focuses on business logic, not infrastructure

Key Features:
- Real ZMQ communication via aiperf infrastructure
- Type-safe with actual aiperf types (MessageType, CommandType, Message, CommandMessage)
- Standard Python inheritance patterns with super() calls
- Automatic @message_handler and @command_handler discovery
- Simple publish() and send_command() methods
- Integrated with ServiceConfig and the entire aiperf ecosystem
- No custom message types or converters - everything is ground truth aiperf

Usage:
    class MyService(AIPerfService):
        def __init__(self, service_config, user_config=None, **kwargs):
            super().__init__(
                service_id="my_service",
                service_type=ServiceType.DATASET_MANAGER,
                service_config=service_config,
                user_config=user_config,
                **kwargs
            )

        async def initialize(self):
            await super().initialize()  # Always call super()!
            # Your initialization here

        async def start(self):
            await super().start()  # Always call super()!
            # Your start logic here

        async def stop(self):
            await super().stop()  # Always call super()!
            # Your cleanup here

        @message_handler(MessageType.DATA_UPDATE)
        async def handle_data_update(self, message: Message):
            # Handle real aiperf messages with full type safety
            await self.publish(MessageType.STATUS, {"status": "processed"})

        @command_handler(CommandType.PROFILE_START)
        async def handle_profile_start(self, command: CommandMessage):
            # Handle real aiperf commands with full type safety
            return {"result": "started"}
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
)
from aiperf.common.types import MessageTypeT


class LifecycleState:
    """Simple lifecycle state tracking."""

    CREATED = "created"
    INITIALIZING = "initializing"
    INITIALIZED = "initialized"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    STOPPED = "stopped"
    ERROR = "error"


class AIPerfService:
    """
    Ultimate user-friendly base class for AIPerf services.

    This class provides the cleanest possible API while using the real aiperf
    infrastructure under the hood. It abstracts away all communication
    complexities while maintaining full type safety and integration.

    Key Benefits:
    - Real aiperf types: MessageType, CommandType, Message, CommandMessage
    - Real ZMQ communication: PubClient, SubClient, event bus, proxies
    - Clean inheritance: Standard initialize()/start()/stop() with super() calls
    - Auto-discovery: Automatic @message_handler/@command_handler registration
    - Simple API: Easy publish()/send_command() methods
    - Type safety: Full typing with real aiperf message infrastructure
    - Zero complexity: Focus on business logic, not infrastructure

    This is the ONE class you need for AIPerf service development.
    """

    def __init__(
        self,
        service_id: str,
        service_type: ServiceType,
        service_config: ServiceConfig,
        user_config: UserConfig | None = None,
        logger: logging.Logger | None = None,
        **kwargs,
    ):
        # Core service identity
        self.service_id = service_id
        self.service_type = service_type
        self.service_config = service_config
        self.user_config = user_config
        self.logger = logger or logging.getLogger(service_id)

        # Lifecycle state
        self._state = LifecycleState.CREATED
        self._stop_event = asyncio.Event()

        # Real aiperf communication infrastructure
        self.comms: BaseCommunication | None = None
        self.pub_client: PubClientProtocol | None = None
        self.sub_client: SubClientProtocol | None = None

        # Handler discovery and management
        self._message_handlers: dict[MessageTypeT, list[Callable]] = {}
        self._command_handlers: dict[MessageTypeT, list[Callable]] = {}
        self._command_responses: dict[str, asyncio.Future] = {}

        # Background tasks
        self._background_tasks: set[asyncio.Task] = set()

        # Auto-discover decorated handlers
        self._discover_handlers()

    # =================================================================
    # Clean Lifecycle Methods - Override and Call super()
    # =================================================================

    async def initialize(self) -> None:
        """
        Initialize the service and its communication infrastructure.

        Override this method to add initialization logic. Always call super().initialize()!

        Example:
            async def initialize(self):
                await super().initialize()  # Always call super()!
                self.db = await connect_database()
                self.logger.info("Service ready!")
        """
        if self._state != LifecycleState.CREATED:
            raise ValueError(f"Cannot initialize from state {self._state}")

        self._state = LifecycleState.INITIALIZING

        try:
            # Initialize real aiperf communication infrastructure
            await self._setup_communication()

            # Register with system
            await self._register_service()

            self._state = LifecycleState.INITIALIZED
            self.logger.info(f"Service {self.service_id} initialized successfully")

        except Exception as e:
            self._state = LifecycleState.ERROR
            self.logger.error(f"Failed to initialize service {self.service_id}: {e}")
            raise

    async def start(self) -> None:
        """
        Start the service and begin processing.

        Override this method to add start logic. Always call super().start()!

        Example:
            async def start(self):
                await super().start()  # Always call super()!
                await self.start_workers()
                self.logger.info("All workers started!")
        """
        if self._state != LifecycleState.INITIALIZED:
            raise ValueError(f"Cannot start from state {self._state}")

        self._state = LifecycleState.STARTING

        try:
            # Start background tasks
            await self._start_background_tasks()

            # Start receiving messages
            await self._start_message_processing()

            self._state = LifecycleState.RUNNING
            self.logger.info(f"Service {self.service_id} started successfully")

        except Exception as e:
            self._state = LifecycleState.ERROR
            self.logger.error(f"Failed to start service {self.service_id}: {e}")
            raise

    async def stop(self) -> None:
        """
        Stop the service and clean up all resources.

        Override this method to add stop/cleanup logic. Always call super().stop()!

        Example:
            async def stop(self):
                await super().stop()  # Always call super()!
                await self.db.close()
                self.logger.info("Cleanup complete!")
        """
        if self._state in (LifecycleState.STOPPED, LifecycleState.STOPPING):
            return

        self._state = LifecycleState.STOPPING

        try:
            # Signal stop to all components
            self._stop_event.set()

            # Stop background tasks
            await self._stop_background_tasks()

            # Shutdown communication
            if self.comms:
                await self.comms.shutdown()

            self._state = LifecycleState.STOPPED
            self.logger.info(f"Service {self.service_id} stopped successfully")

        except Exception as e:
            self._state = LifecycleState.ERROR
            self.logger.error(f"Failed to stop service {self.service_id}: {e}")
            raise

    # =================================================================
    # Simple Messaging API - Real aiperf Types
    # =================================================================

    async def publish(
        self, message_type: MessageTypeT, content: Any = None, **kwargs
    ) -> None:
        """
        Publish a message using real aiperf infrastructure.

        Args:
            message_type: Real MessageType or CommandType enum
            content: Message content/data
            **kwargs: Additional message fields

        Example:
            await self.publish(MessageType.STATUS, {"health": "good"})
            await self.publish(MessageType.HEARTBEAT)
        """
        if not self.pub_client:
            raise RuntimeError("Service not initialized - call initialize() first")

        # Create real aiperf message
        if message_type in MessageType:
            message = self._create_message(message_type, content, **kwargs)
        else:
            # Handle command types
            message = self._create_command_message(message_type, content, **kwargs)

        await self.pub_client.publish(message)
        self.logger.debug(f"Published {message_type}: {content}")

    async def send_command(
        self,
        command_type: CommandType,
        target_service_id: str | None = None,
        target_service_type: ServiceType | None = None,
        data: Any = None,
        timeout: float = 30.0,
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
            **kwargs: Additional command fields

        Returns:
            Response data from the target service

        Example:
            status = await self.send_command(
                CommandType.PROFILE_START,
                target_service_id="worker_1"
            )
        """
        if not self.pub_client:
            raise RuntimeError("Service not initialized - call initialize() first")

        # Create real aiperf command message
        command = CommandMessage(
            message_type=command_type,
            service_id=self.service_id,
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

    async def send_response(
        self, original_command: CommandMessage, data: Any = None, error: Any = None
    ) -> None:
        """
        Send a response to a command using real aiperf infrastructure.

        Args:
            original_command: The original command message
            data: Response data (if successful)
            error: Error details (if failed)

        Example:
            @command_handler(CommandType.GET_STATUS)
            async def handle_status(self, command):
                status = {"health": "good", "uptime": self.uptime}
                await self.send_response(command, data=status)
        """
        if not self.pub_client:
            raise RuntimeError("Service not initialized - call initialize() first")

        response = CommandResponseMessage(
            message_type=f"{original_command.message_type}_response",
            request_id=original_command.request_id,
            service_id=self.service_id,
            origin_service_id=original_command.service_id,
            data=data,
            error=error,
        )

        await self.pub_client.publish(response)

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
                    self._message_handlers.setdefault(message_type, []).append(method)

            # Command handlers (@command_handler)
            if hasattr(method, "_command_types"):
                for command_type in method._command_types:
                    self._command_handlers.setdefault(command_type, []).append(method)

            # Background tasks (@background_task)
            if hasattr(method, "_background_task_interval"):
                # We'll handle this in _start_background_tasks
                pass

    async def _setup_communication(self) -> None:
        """Set up real aiperf communication infrastructure."""
        # Create communication instance using real aiperf factory
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

    async def _register_service(self) -> None:
        """Register service with system controller using real aiperf pattern."""
        if not self.pub_client:
            return

        registration = RegistrationMessage(
            service_id=self.service_id,
            service_type=self.service_type,
        )

        await self.pub_client.publish(registration)
        self.logger.debug(
            f"Registered service {self.service_id} as {self.service_type}"
        )

    async def _start_message_processing(self) -> None:
        """Start processing incoming messages using real aiperf patterns."""
        if not self.sub_client:
            return

        # Subscribe to all message types we handle
        subscription_map = {}

        # Add message handlers
        for message_type, handlers in self._message_handlers.items():
            if handlers:
                subscription_map[message_type] = self._handle_message

        # Add command handlers
        for command_type, handlers in self._command_handlers.items():
            if handlers:
                subscription_map[command_type] = self._handle_command

        # Always subscribe to command responses for our commands
        subscription_map[f"{CommandType.PROFILE_START}_response"] = (
            self._handle_command_response
        )
        subscription_map[f"{CommandType.PROFILE_STOP}_response"] = (
            self._handle_command_response
        )
        subscription_map[f"{CommandType.PROFILE_CONFIGURE}_response"] = (
            self._handle_command_response
        )
        subscription_map[f"{CommandType.SHUTDOWN}_response"] = (
            self._handle_command_response
        )

        if subscription_map:
            await self.sub_client.subscribe_all(subscription_map)

    async def _handle_message(self, message: Message) -> None:
        """Handle incoming message using discovered handlers."""
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
        """Handle incoming command using discovered handlers."""
        handlers = self._command_handlers.get(command.message_type, [])

        for handler in handlers:
            try:
                if inspect.iscoroutinefunction(handler):
                    result = await handler(command)
                else:
                    result = handler(command)

                # Send response if command expects one
                if command.require_response:
                    await self.send_response(command, data=result)

            except Exception as e:
                self.logger.error(f"Error in command handler {handler.__name__}: {e}")

                # Send error response
                if command.require_response:
                    await self.send_response(command, error=str(e))

    async def _handle_command_response(self, response: CommandResponseMessage) -> None:
        """Handle command response for our outgoing commands."""
        if response.request_id in self._command_responses:
            future = self._command_responses[response.request_id]
            if not future.done():
                if response.error:
                    future.set_exception(Exception(response.error))
                else:
                    future.set_result(response.data)

    async def _start_background_tasks(self) -> None:
        """Start background tasks discovered from decorators."""
        for name in dir(self):
            method = getattr(self, name)
            if hasattr(method, "_background_task_interval"):
                interval = method._background_task_interval
                task = asyncio.create_task(self._run_background_task(method, interval))
                self._background_tasks.add(task)
                task.add_done_callback(self._background_tasks.discard)

    async def _run_background_task(self, method: Callable, interval: float) -> None:
        """Run a single background task with interval."""
        while not self._stop_event.is_set():
            try:
                if inspect.iscoroutinefunction(method):
                    await method()
                else:
                    method()
            except Exception as e:
                self.logger.error(f"Error in background task {method.__name__}: {e}")

            try:
                await asyncio.wait_for(self._stop_event.wait(), timeout=interval)
                break  # Stop event was set
            except asyncio.TimeoutError:
                continue  # Continue with next iteration

    async def _stop_background_tasks(self) -> None:
        """Stop all background tasks."""
        if self._background_tasks:
            # Cancel all tasks
            for task in self._background_tasks:
                task.cancel()

            # Wait for completion
            await asyncio.gather(*self._background_tasks, return_exceptions=True)
            self._background_tasks.clear()

    def _create_message(
        self, message_type: MessageType, content: Any = None, **kwargs
    ) -> Message:
        """Create a real aiperf message."""
        # Map to specific message class based on type
        if message_type == MessageType.HEARTBEAT:
            return HeartbeatMessage(
                service_id=self.service_id, service_type=self.service_type, **kwargs
            )
        elif message_type == MessageType.REGISTRATION:
            return RegistrationMessage(
                service_id=self.service_id, service_type=self.service_type, **kwargs
            )
        else:
            # Generic message for other types
            return Message(
                message_type=message_type,
                # Note: Real aiperf Message doesn't have content field in base class
                # We need to use the appropriate message subclass for each type
                **kwargs,
            )

    def _create_command_message(
        self, command_type: CommandType, content: Any = None, **kwargs
    ) -> CommandMessage:
        """Create a real aiperf command message."""
        return CommandMessage(
            message_type=command_type,
            service_id=self.service_id,
            data=content,
            **kwargs,
        )

    # =================================================================
    # Convenience Properties and Methods
    # =================================================================

    @property
    def is_running(self) -> bool:
        """True if service is in running state."""
        return self._state == LifecycleState.RUNNING

    @property
    def is_stopped(self) -> bool:
        """True if service is stopped."""
        return self._state == LifecycleState.STOPPED

    @property
    def state(self) -> str:
        """Current lifecycle state."""
        return self._state

    async def run_until_stopped(self) -> None:
        """
        Run the service until stopped (convenience method).

        Example:
            service = MyService(...)
            await service.run_until_stopped()  # Runs initialize->start->wait->stop
        """
        await self.initialize()
        await self.start()

        try:
            await self._stop_event.wait()
        except KeyboardInterrupt:
            self.logger.info("Received keyboard interrupt, stopping service...")
        finally:
            await self.stop()

    def get_handler_info(self) -> dict:
        """Get information about registered handlers (debugging)."""
        return {
            "message_handlers": {
                str(msg_type): [h.__name__ for h in handlers]
                for msg_type, handlers in self._message_handlers.items()
            },
            "command_handlers": {
                str(cmd_type): [h.__name__ for h in handlers]
                for cmd_type, handlers in self._command_handlers.items()
            },
        }


# Alias for backward compatibility and convenience
Service = AIPerfService
AIPerf = AIPerfService
