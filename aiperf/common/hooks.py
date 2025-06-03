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

import asyncio
import inspect
import logging
from collections.abc import Awaitable, Callable
from typing import Any

from aiperf.common.enums import AIPerfHook, HookType, ServiceState
from aiperf.common.exceptions import AIPerfMultiError, UnsupportedHookError
from aiperf.common.models import AIPerfTaskOptions


################################################################################
# Hook Types
################################################################################
class HookConstants:
    """Constants for the hook system."""

    AIPERF_HOOK_TYPE = "__aiperf_hook_type__"
    """Constant attribute name that marks a function's hook type."""

    AIPERF_TASK_OPTIONS = "__aiperf_task_options__"
    """Constant attribute name that marks a function's task options."""


################################################################################
# Hook System
################################################################################

logger = logging.getLogger(__name__)


class HookSystem:
    """
    System for managing hooks.

    This class is responsible for managing the hooks for a class. It will
    store the hooks in a dictionary, and provide methods to register and run
    the hooks.
    """

    def __init__(self, supported_hooks: set[HookType]):
        """
        Initialize the hook system.

        Args:
            supported_hooks: The hook types that the class supports.
        """

        self.supported_hooks: set[HookType] = supported_hooks
        self._hooks: dict[HookType, list[Callable]] = {}

    def register_hook(self, hook_type: HookType, func: Callable):
        """Register a hook function for a given hook type.

        Args:
            hook_type: The hook type to register the function for.
            func: The function to register.
        """
        if hook_type not in self.supported_hooks:
            raise UnsupportedHookError(f"Hook {hook_type} is not supported by class.")

        self._hooks.setdefault(hook_type, []).append(func)

    def get_hooks(self, hook_type: HookType) -> list[Callable]:
        """Get all the registered hooks for the given hook type.

        Args:
            hook_type: The hook type to get the hooks for.

        Returns:
            A list of the hooks for the given hook type.
        """
        return self._hooks.get(hook_type, [])

    async def run_hooks(self, hook_type: HookType, *args, **kwargs):
        """
        Run all the hooks for a given hook type serially. This will wait for each
        hook to complete before running the next one.

        Args:
            hook_type: The hook type to run.
            *args: The arguments to pass to the hooks.
            **kwargs: The keyword arguments to pass to the hooks.
        """
        if hook_type not in self.supported_hooks:
            raise UnsupportedHookError(f"Hook {hook_type} is not supported by class.")

        exceptions: list[Exception] = []
        for func in self.get_hooks(hook_type):
            try:
                if inspect.iscoroutinefunction(func):
                    await func(*args, **kwargs)
                else:
                    await asyncio.to_thread(func, *args, **kwargs)
            except Exception as e:
                logger.error(f"Error running hook {func.__name__}: {e}")
                exceptions.append(e)

        if exceptions:
            raise AIPerfMultiError("Errors running hooks", exceptions)

    async def run_hooks_async(self, hook_type: HookType, *args, **kwargs):
        """
        Run all the hooks for a given hook type concurrently. This will run all
        the hooks at the same time and return when all the hooks have completed.

        Args:
            hook_type: The hook type to run.
            *args: The arguments to pass to the hooks.
            **kwargs: The keyword arguments to pass to the hooks.
        """
        if hook_type not in self.supported_hooks:
            raise UnsupportedHookError(f"Hook {hook_type} is not supported by class.")

        coroutines: list[Awaitable] = []
        for func in self.get_hooks(hook_type):
            if inspect.iscoroutinefunction(func):
                coroutines.append(func(*args, **kwargs))
            else:
                coroutines.append(asyncio.to_thread(func, *args, **kwargs))

        if coroutines:
            results = await asyncio.gather(*coroutines, return_exceptions=True)

            exceptions = [result for result in results if isinstance(result, Exception)]
            if exceptions:
                raise AIPerfMultiError("Errors running hooks", exceptions)


################################################################################
# Hooks Mixin
################################################################################


class HooksMixin:
    """
    Mixin to add hook support to a class. It abstracts away the details of the
    :class:`HookSystem` and provides a simple interface for registering and running hooks.
    """

    # Class attributes that are set by the :func:`supports_hooks` decorator
    supported_hooks: set[HookType] = set()

    def __init__(self):
        """
        Initialize the hook system and register all functions that are decorated with a hook decorator.
        """
        # Initialize the hook system
        self._hook_system = HookSystem(self.supported_hooks)

        # Register all functions that are decorated with a hook decorator
        # Iterate through MRO in reverse order to ensure base class hooks are registered first
        for cls in reversed(self.__class__.__mro__):
            # Skip object and other non-hook classes
            if not issubclass(cls, HooksMixin):
                continue

            # Get methods defined directly in this class (not inherited)
            for _, attr in cls.__dict__.items():
                if callable(attr) and hasattr(attr, HookConstants.AIPERF_HOOK_TYPE):
                    # Get the hook type from the function
                    hook_type = getattr(attr, HookConstants.AIPERF_HOOK_TYPE)
                    # Bind the method to the instance
                    bound_method = attr.__get__(self, cls)
                    # Register the function with the hook type
                    self.register_hook(hook_type, bound_method)

    def register_hook(self, hook_type: HookType, func: Callable):
        """Register a hook function for a given hook type.

        Args:
            hook_type: The hook type to register the function for.
            func: The function to register.
        """
        self._hook_system.register_hook(hook_type, func)

    async def run_hooks(self, hook_type: HookType, *args, **kwargs):
        """Run all the hooks serially. See :meth:`HookSystem.run_hooks`."""
        await self._hook_system.run_hooks(hook_type, *args, **kwargs)

    async def run_hooks_async(self, hook_type: HookType, *args, **kwargs):
        """Run all the hooks concurrently. See :meth:`HookSystem.run_hooks_async`."""
        await self._hook_system.run_hooks_async(hook_type, *args, **kwargs)

    def get_hooks(self, hook_type: HookType) -> list[Callable]:
        """Get all the registered hooks for the given hook type. See :meth:`HookSystem.get_hooks`."""
        return self._hook_system.get_hooks(hook_type)


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
        # Ensure the class inherits from HooksMixin
        if not issubclass(cls, HooksMixin):
            raise TypeError(f"Class {cls.__name__} does not inherit from HooksMixin.")

        # Inherit any hooks defined by base classes in the MRO (Method Resolution Order).
        base_hooks = [
            base.supported_hooks
            for base in cls.__mro__[1:]  # Skip this class itself (cls)
            if issubclass(
                base, HooksMixin
            )  # Only include classes that inherit from HooksMixin
        ]

        # Set the supported hooks to be the union of the existing base hooks and the new supported hook types.
        cls.supported_hooks = set.union(*base_hooks, set(supported_hook_types))
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
    setattr(func, HookConstants.AIPERF_HOOK_TYPE, hook_type)
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


def on_set_state(
    func: Callable[[Any, ServiceState], None],
) -> Callable[[Any, ServiceState], None]:
    """Decorator to specify that the function should be called when the service state is set.
    See :func:`aiperf.common.hooks.hook_decorator`."""
    return hook_decorator(AIPerfHook.ON_SET_STATE, func)


def aiperf_task(
    options: AIPerfTaskOptions | None = None,
    func: Callable | None = None,
) -> Callable:
    """Decorator to indicate that the function is a task function. It will be started
    and stopped automatically by the base class lifecycle.

    Args:
        options: The options for the task.
        func: The function to decorate.

    Returns:
        The decorated function.
    """
    if options is None:
        options = AIPerfTaskOptions()

    def decorator(func: Callable) -> Callable:
        func = hook_decorator(AIPerfHook.AIPERF_TASK, func)
        setattr(func, HookConstants.AIPERF_TASK_OPTIONS, options)
        return func

    return decorator
