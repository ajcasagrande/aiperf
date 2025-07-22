# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

from collections.abc import Callable

from aiperf.common.types import MessageTypeT


def message_handler(*message_types: MessageTypeT) -> Callable:
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


def command_handler(*message_types: MessageTypeT) -> Callable:
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


def request_handler(*message_types: MessageTypeT) -> Callable:
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


def pull_handler(*message_types: MessageTypeT) -> Callable:
    """
    Decorator to mark a method as a pull handler. The decorated method will be called
    whenever a pull message of the specified type(s) is received.

    Args:
        *message_types: One or more MessageType enums, or message type strings to handle
    """

    def decorator(func: Callable) -> Callable:
        setattr(func, attrs.pull_handler_types, list(message_types))
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
    pull_handler_types = "_pull_handler_types"
