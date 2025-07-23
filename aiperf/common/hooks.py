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

from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, Field

from aiperf.common.enums import CaseInsensitiveStrEnum, LifecycleState
from aiperf.common.types import HooksMixinT

if TYPE_CHECKING:
    from aiperf.common.mixins.task_manager_mixin import TaskManagerProtocol


class AIPerfHook(CaseInsensitiveStrEnum):
    BACKGROUND_TASK = "@background_task"
    ON_INIT = "@on_init"
    ON_START = "@on_start"
    ON_STOP = "@on_stop"
    ON_STATE_CHANGE = "@on_state_change"
    ON_COMMAND = "@on_command"
    ON_MESSAGE = "@on_message"
    ON_REQUEST = "@on_request"
    ON_RESPONSE = "@on_response"


HookType = AIPerfHook | str
"""Type alias for valid hook types. This is a union of the AIPerfHook enum and any user-defined custom strings."""

AIPERF_HOOK_TYPE = "__aiperf_hook_type__"
"""Constant attribute name that marks a function's hook type."""

AIPERF_HOOK_PARAMS = "__aiperf_hook_params__"
"""Constant attribute name that marks a function's hook parameters."""

PROVIDES_HOOKS = "__provides_hooks__"


class BackgroundTaskParams(BaseModel):
    interval: float | Callable[[Any], float] | None = Field(default=None)
    immediate: bool = Field(default=False)
    stop_on_error: bool = Field(default=False)


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


def hook_decorator_with_params(
    hook_type: HookType, params: BaseModel
) -> Callable[[Callable], Callable]:
    """Generic decorator to specify that the function should be called during
    a specific hook, and with the provided parameters. The parameters are set on
    the function as an attribute.

    Args:
        hook_type: The hook type to decorate the function with.
        params: The parameters to set on the function.
    """

    def decorator(func: Callable) -> Callable:
        setattr(func, AIPERF_HOOK_TYPE, hook_type)
        setattr(func, AIPERF_HOOK_PARAMS, params)
        return func

    return decorator


def provides_hooks(
    *hook_types: HookType,
) -> Callable[[type[HooksMixinT]], type[HooksMixinT]]:
    """Decorator to specify that the class provides a hook of the given type."""

    def decorator(cls: type[HooksMixinT]) -> type[HooksMixinT]:
        setattr(cls, PROVIDES_HOOKS, set(hook_types))
        return cls

    return decorator


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


def on_state_change(
    func: Callable[["HooksMixinT", LifecycleState, LifecycleState], Awaitable],
) -> Callable[["HooksMixinT", LifecycleState, LifecycleState], Awaitable]:
    """Decorator to specify that the function should be called during the service state change.
    See :func:`aiperf.common.hooks.hook_decorator`."""
    return hook_decorator(AIPerfHook.ON_STATE_CHANGE, func)


def background_task(
    interval: float | Callable[["TaskManagerProtocol"], float] | None = None,
    immediate: bool = True,
    stop_on_error: bool = False,
) -> Callable:
    """
    Decorator to mark a method as a background task with automatic management.

    Tasks are automatically started when the service starts and stopped when the service stops.
    The decorated method will be run periodically in the background when the service is running.

    Args:
        interval: Time between task executions in seconds. If None, the task will run once.
            Can be a callable that returns the interval, and will be called with 'self' as the argument.
        immediate: If True, run the task immediately on start, otherwise wait for the interval first.
        stop_on_error: If True, stop the task on any exception, otherwise log and continue.
    """
    return hook_decorator_with_params(
        AIPerfHook.BACKGROUND_TASK,
        BackgroundTaskParams(
            interval=interval, immediate=immediate, stop_on_error=stop_on_error
        ),
    )
