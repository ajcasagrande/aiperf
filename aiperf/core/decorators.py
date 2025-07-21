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
from typing import TYPE_CHECKING

from aiperf.common.enums import MessageType

if TYPE_CHECKING:
    from aiperf.core.background_tasks import BackgroundTasksMixin


def message_handler(*message_types: MessageType | str) -> Callable:
    """
    Decorator to mark a method as a message handler. The decorated method will be called
    whenever a message of the specified type(s) is received.

    Args:
        *message_types: One or more MessageType enums, or message type strings to handle
    """

    def decorator(func: Callable) -> Callable:
        setattr(func, attrs.message_handler_types, list(message_types))
        return func

    return decorator


def command_handler(*message_types: MessageType | str) -> Callable:
    """
    Decorator to mark a method as a command handler. The decorated method will be called
    whenever a command of the specified type(s) is received.

    Command handlers can return data that will be automatically sent as a response.
    If the handler raises an exception, an error response will be sent in response.

    Args:
        *message_types: One or more MessageType enums, or message type strings to handle
    """

    def decorator(func: Callable) -> Callable:
        setattr(func, attrs.command_handler_types, list(message_types))
        return func

    return decorator


def request_handler(*message_types: MessageType | str) -> Callable:
    """
    Decorator to mark a method as a request handler. The decorated method will be called
    whenever a request of the specified type(s) is received.

    Request handlers can return data that will be automatically sent as a response.
    If the handler raises an exception, an error response will be sent to the requester.

    Args:
        *message_types: One or more MessageType enums, or message type strings to handle
    """

    def decorator(func: Callable) -> Callable:
        setattr(func, attrs.request_handler_types, list(message_types))
        return func

    return decorator


def background_task(
    interval: float | Callable[["BackgroundTasksMixin"], float] | None = None,
    immediate: bool = False,
    stop_on_error: bool = False,
) -> Callable:
    """
    Decorator to mark a method as a background task with automatic management.

    Tasks are automatically started when the service starts and stopped when the service stops.
    The decorated method will be run periodically in the background when the service is running.

    Args:
        interval: Time between task executions in seconds. If None, the task will run once.
        Can be a callable that returns the interval, and will be called with 'self' as the argument.
        immediate: If True, run the task immediately on start, otherwise wait for the interval first
        stop_on_error: If True, stop the task on any exception (default: log and continue)
    """

    def decorator(func: Callable) -> Callable:
        setattr(func, attrs.is_background_task, True)
        setattr(func, attrs.background_task_interval, interval)
        setattr(func, attrs.background_task_immediate, immediate)
        setattr(func, attrs.background_task_stop_on_error, stop_on_error)
        return func

    return decorator


class attrs:
    """Attributes for the decorators."""

    is_background_task = "_is_background_task"
    background_task_interval = "_background_task_interval"
    background_task_immediate = "_background_task_immediate"
    background_task_stop_on_error = "_background_task_stop_on_error"

    message_handler_types = "_message_handler_types"
    command_handler_types = "_command_handler_types"
    request_handler_types = "_request_handler_types"
