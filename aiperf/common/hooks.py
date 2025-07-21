# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""
This module provides an extensive hook system for AIPerf. It is designed to be
used as a mixin for classes that support hooks. It provides a simple interface
for registering and running hooks.

Classes should inherit from the :class:`HooksMixin`, and specify the supported
hook types by decorating the class with the :func:`supports_hooks` decorator.

The hook functions are registered by decorating functions with the various hook
decorators such as :func:`on_init`, :func:`on_start`, :func:`on_stop`, etc.

The hooks are run by calling the :meth:`HooksMixin.run_hooks` or
:meth:`HooksMixin.run_hooks_async` methods on the class.

More than one hook can be registered for a given hook type, and classes that inherit from
classes with existing hooks will inherit the hooks from the base classes as well.
"""

from collections.abc import Callable
from functools import wraps
from typing import TYPE_CHECKING

from aiperf.common.enums import CaseInsensitiveStrEnum, MessageType

if TYPE_CHECKING:
    # Prevent circular import
    from aiperf.common.mixins import AIPerfLifecycleMixin

################################################################################
# Hook Types
################################################################################


class AIPerfHook(CaseInsensitiveStrEnum):
    """Enum for the various AIPerf hooks.

    Note: If you add a new hook, you must also add it to the @supports_hooks
    decorator of the class you wish to use the hook in.
    """

    ON_INIT = "__aiperf_on_init__"
    ON_RUN = "__aiperf_on_run__"
    ON_CONFIGURE = "__aiperf_on_configure__"
    ON_PROFILE_CONFIGURE = "__aiperf_on_profile_configure__"
    ON_PROFILE_START = "__aiperf_on_profile_start__"
    ON_PROFILE_STOP = "__aiperf_on_profile_stop__"
    ON_START = "__aiperf_on_start__"
    ON_STOP = "__aiperf_on_stop__"
    ON_CLEANUP = "__aiperf_on_cleanup__"

    ON_SET_STATE = "__aiperf_on_set_state__"

    ON_MESSAGE = "__aiperf_on_message__"
    ON_COMMAND_MESSAGE = "__aiperf_on_command_message__"


class AIPerfTaskHook(CaseInsensitiveStrEnum):
    """Enum for the various AIPerf task hooks."""

    AIPERF_TASK = "__aiperf_task__"
    """A task that is run by the base class.
    It will be started and stopped automatically by the base class lifecycle."""

    AIPERF_AUTO_TASK = "__aiperf_auto_task__"
    """Converts a function into a task that is run by the base class at a regular interval.
    Batteries included, error handling, and exit conditions. Simply write the inner functionality, n
    It will be started and stopped automatically by the base class lifecycle."""


class AIPerfHookParams:
    AIPERF_AUTO_TASK_INTERVAL_SEC = "__aiperf_auto_task_interval_sec__"
    ON_MESSAGE_MESSAGE_TYPES = "__aiperf_message_handler_message_types__"
    ON_COMMAND_MESSAGE_MESSAGE_TYPES = (
        "__aiperf_command_message_handler_message_types__"
    )


HookType = AIPerfHook | AIPerfTaskHook | str
"""Type alias for valid hook types. This is a union of the AIPerfHook enum, the AIPerfTaskHook enum, and any user-defined custom strings."""


AIPERF_HOOK_TYPE = "__aiperf_hook_type__"
"""Constant attribute name that marks a function's hook type."""


################################################################################
# Hook Decorators
################################################################################


def supports_hooks(
    *supported_hook_types: HookType,
) -> Callable[[type], type]:
    """Decorator to indicate that a class supports hooks and sets the
    supported hook types.

    Args:
        supported_hook_types: The hook types that the class supports.

    Returns:
        The decorated class
    """

    def decorator(cls: type) -> type:
        # TODO: We can consider creating a HooksMixinProtocol, but it would still
        #       need to exist somewhere both hooks.py and mixins module can access.
        # Import this here to prevent circular imports. Also make sure you use
        # fully qualified import name to avoid partial loaded module errors.
        from aiperf.common.mixins.hooks_mixin import HooksMixin

        # Ensure the class inherits from HooksMixin
        if not issubclass(cls, HooksMixin):
            raise TypeError(f"Class {cls.__name__} does not inherit from HooksMixin.")

        # Inherit any hooks defined by base classes in the MRO (Method Resolution Order).
        base_hooks = [
            base._supported_hooks
            for base in cls.__mro__[1:]  # Skip this class itself (cls)
            if hasattr(base, "_supported_hooks")
        ]

        # Set the supported hooks to be the union of the existing base hooks and the new supported hook types.
        cls._supported_hooks = set.union(*base_hooks, set(supported_hook_types))
        return cls

    return decorator


def hook_decorator(hook_type: HookType, func: Callable) -> Callable:
    """Generic decorator to specify that the function should be called during
    a specific hook.

    Args:
        hook_type: The hook type to decorate the function with.
        func: The function to decorate.
    Returns:
        The decorated function.
    """
    setattr(func, AIPERF_HOOK_TYPE, hook_type)
    return func


################################################################################
# Syntactic sugar for the hook decorators.
################################################################################


def on_init(func: Callable) -> Callable:
    """Decorator to specify that the function should be called during initialization.
    See :func:`aiperf.common.hooks.hook_decorator`."""
    return hook_decorator(AIPerfHook.ON_INIT, func)


def on_start(func: Callable) -> Callable:
    """Decorator to specify that the function should be called during start.
    See :func:`aiperf.common.hooks.hook_decorator`."""
    return hook_decorator(AIPerfHook.ON_START, func)


def on_stop(func: Callable) -> Callable:
    """Decorator to specify that the function should be called during stop.
    See :func:`aiperf.common.hooks.hook_decorator`."""
    return hook_decorator(AIPerfHook.ON_STOP, func)


def on_configure(func: Callable) -> Callable:
    """Decorator to specify that the function should be called during the service configuration.
    See :func:`aiperf.common.hooks.hook_decorator`."""
    return hook_decorator(AIPerfHook.ON_CONFIGURE, func)


def on_cleanup(func: Callable) -> Callable:
    """Decorator to specify that the function should be called during cleanup.
    See :func:`aiperf.common.hooks.hook_decorator`."""
    return hook_decorator(AIPerfHook.ON_CLEANUP, func)


def on_run(func: Callable) -> Callable:
    """Decorator to specify that the function should be called during run.
    See :func:`aiperf.common.hooks.hook_decorator`."""
    return hook_decorator(AIPerfHook.ON_RUN, func)


def on_set_state(func: Callable) -> Callable:
    """Decorator to specify that the function should be called when the service state is set.
    See :func:`aiperf.common.hooks.hook_decorator`."""
    return hook_decorator(AIPerfHook.ON_SET_STATE, func)


def on_profile_configure(func: Callable) -> Callable:
    """Decorator to specify that the function should be called during the service profile configuration.
    See :func:`aiperf.common.hooks.hook_decorator`."""
    return hook_decorator(AIPerfHook.ON_PROFILE_CONFIGURE, func)


def on_profile_start(func: Callable) -> Callable:
    """Decorator to specify that the function should be called during the service profile start.
    See :func:`aiperf.common.hooks.hook_decorator`."""
    return hook_decorator(AIPerfHook.ON_PROFILE_START, func)


def on_profile_stop(func: Callable) -> Callable:
    """Decorator to specify that the function should be called during the service profile stop.
    See :func:`aiperf.common.hooks.hook_decorator`."""
    return hook_decorator(AIPerfHook.ON_PROFILE_STOP, func)


def aiperf_task(func: Callable) -> Callable:
    """Decorator to indicate that the function is a task function. It will be started
    and stopped automatically by the base class lifecycle.
    See :func:`aiperf.common.hooks.hook_decorator`.
    """
    return hook_decorator(AIPerfTaskHook.AIPERF_TASK, func)


def aiperf_auto_task(
    interval_sec: float | Callable[["AIPerfLifecycleMixin"], float] | None,
) -> Callable[[Callable], Callable]:
    """Decorator to indicate that the function is an auto-managed task function. It will be started
    and stopped automatically by the base class lifecycle.
    See :func:`aiperf.common.hooks.hook_decorator`.

    Args:
        interval_sec: The interval in seconds to sleep between runs. Can be a callable that returns a float.
                    If None, the task will run once and then stop.
    """

    def decorator(func: Callable) -> Callable:
        setattr(func, AIPerfHookParams.AIPERF_AUTO_TASK_INTERVAL_SEC, interval_sec)
        wraps(func)
        return hook_decorator(AIPerfTaskHook.AIPERF_AUTO_TASK, func)

    return decorator


def on_message(*message_types: MessageType) -> Callable:
    """Decorator to indicate that the function is a message handler. It will be called
    when a message of the given type is received.
    See :func:`aiperf.common.hooks.hook_decorator`.

    Args:
        message_types: The message types to handle.
    """

    def decorator(func: Callable) -> Callable:
        setattr(func, AIPerfHookParams.ON_MESSAGE_MESSAGE_TYPES, message_types)
        wraps(func)
        return hook_decorator(AIPerfHook.ON_MESSAGE, func)

    return decorator


def on_command_message(*message_types: MessageType) -> Callable:
    """Decorator to indicate that the function is a command message handler. It will be called
    when a command message of the given type is received.
    See :func:`aiperf.common.hooks.hook_decorator`.

    Args:
        message_types: The message types to handle.
    """

    def decorator(func: Callable) -> Callable:
        setattr(func, AIPerfHookParams.ON_COMMAND_MESSAGE_MESSAGE_TYPES, message_types)
        wraps(func)
        return hook_decorator(AIPerfHook.ON_COMMAND_MESSAGE, func)

    return decorator
