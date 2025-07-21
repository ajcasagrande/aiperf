# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
Ultimate type-safe decorators for AIPerf lifecycle system.

These decorators work with REAL aiperf MessageType and CommandType enums
for full type safety and integration with the actual aiperf infrastructure.

Key Features:
- Real aiperf types: MessageType, CommandType from aiperf.common.enums
- Full type safety and IDE support
- Automatic handler discovery and registration
- Clean, pythonic decorator patterns
- Integration with real aiperf message infrastructure

Usage:
    from aiperf.common.enums import MessageType, CommandType

    @message_handler(MessageType.STATUS, MessageType.HEARTBEAT)
    async def handle_status_messages(self, message: Message):
        # Handle real aiperf messages with full type safety
        pass

    @command_handler(CommandType.PROFILE_START)
    async def handle_profile_start(self, command: CommandMessage):
        # Handle real aiperf commands with full type safety
        return {"result": "started"}

    @background_task(interval=30.0)
    async def periodic_cleanup(self):
        # Automatic background task management
        pass
"""

from collections.abc import Callable

from aiperf.common.enums import CommandType, MessageType
from aiperf.common.types import MessageTypeT


def message_handler(*message_types: MessageType | MessageTypeT | str) -> Callable:
    """
    Decorator to mark a method as a message handler for real aiperf messages.

    The decorated method will be called whenever a message of the specified type(s)
    is received by the service. Uses REAL aiperf MessageType enums for type safety.

    Args:
        *message_types: One or more MessageType enums, MessageTypeT, or message type strings to handle

    Example:
        @message_handler(MessageType.STATUS, MessageType.HEARTBEAT)
        async def handle_status_messages(self, message: Message):
            if message.message_type == MessageType.STATUS:
                self.logger.info(f"Status: {message}")
            elif message.message_type == MessageType.HEARTBEAT:
                self.logger.debug("Heartbeat received")

        @message_handler(MessageType.DATASET_CONFIGURED_NOTIFICATION)
        def handle_dataset_ready(self, message: Message):  # Can be sync or async
            self.dataset_ready = True
    """

    def decorator(func: Callable) -> Callable:
        # Store the message types for discovery
        setattr(func, attrs.message_handler_types, list(message_types))
        return func

    return decorator


def command_handler(*command_types: CommandType | MessageTypeT | str) -> Callable:
    """
    Decorator to mark a method as a command handler for real aiperf commands.

    The decorated method will be called whenever a command of the specified type(s)
    is received by the service. Uses REAL aiperf CommandType enums for type safety.

    Command handlers can return data that will be automatically sent as a response.

    Args:
        *command_types: One or more CommandType enums, MessageTypeT, or command type strings to handle

    Example:
        @command_handler(CommandType.PROFILE_START)
        async def handle_profile_start(self, command: CommandMessage):
            # Start profiling logic
            await self.start_profiling(command.data)
            return {"status": "started", "timestamp": time.time()}

        @command_handler(CommandType.SHUTDOWN)
        async def handle_shutdown(self, command: CommandMessage):
            # Cleanup and shutdown
            await self.cleanup()
            return {"status": "shutting_down"}

        @command_handler(CommandType.PROFILE_CONFIGURE, CommandType.PROFILE_STOP)
        def handle_profile_commands(self, command: CommandMessage):  # Can be sync or async
            if command.message_type == CommandType.PROFILE_CONFIGURE:
                return self.configure_profile(command.data)
            elif command.message_type == CommandType.PROFILE_STOP:
                return self.stop_profile()
    """

    def decorator(func: Callable) -> Callable:
        # Store the command types for discovery
        setattr(func, attrs.command_handler_types, list(command_types))
        return func

    return decorator


def background_task(
    interval: float | None = None,
    immediate: bool = False,
    stop_on_error: bool = False,
    run_once: bool = False,
) -> Callable:
    """
    Decorator to mark a method as a background task with automatic management.

    The decorated method will be run periodically in the background when the
    service is running. Tasks are automatically started when the service starts
    and stopped when the service stops.

    Args:
        interval: Time between task executions in seconds
        immediate: If True, run the task immediately on start, otherwise wait for the interval first
        stop_on_error: If True, stop the task on any exception (default: log and continue)
        run_once: If True, run the task once and then stop (default: False)
    """

    def decorator(func: Callable) -> Callable:
        # Store task configuration for discovery
        setattr(func, attrs.is_background_task, True)
        setattr(func, attrs.background_task_interval, interval)
        setattr(func, attrs.background_task_immediate, immediate)
        setattr(func, attrs.background_task_stop_on_error, stop_on_error)
        setattr(func, attrs.background_task_run_once, run_once)
        return func

    return decorator


class attrs:
    """Attributes for the decorators."""

    is_background_task = "_is_background_task"
    background_task_interval = "_background_task_interval"
    background_task_immediate = "_background_task_immediate"
    background_task_stop_on_error = "_background_task_stop_on_error"
    background_task_run_once = "_background_task_run_once"

    message_handler_types = "_message_handler_types"
    command_handler_types = "_command_handler_types"
