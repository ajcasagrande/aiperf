# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

import asyncio
import inspect
from collections.abc import Awaitable, Callable
from typing import ClassVar

from aiperf.common.exceptions import AIPerfError, AIPerfMultiError, UnsupportedHookError
from aiperf.common.hooks import AIPERF_HOOK_TYPE, HookType
from aiperf.common.mixins.aiperf_logger_mixin import AIPerfLoggerMixin

################################################################################
# Hook System
################################################################################


class HooksMixin(AIPerfLoggerMixin):
    """
    System for managing hooks.

    This class is responsible for managing the hooks for a class. It will
    store the hooks in a dictionary, and provide methods to register and run
    the hooks.
    """

    # Class attributes that are set by the :func:`supports_hooks` decorator
    _supported_hooks: ClassVar[set[HookType]]
    _class_hooks: ClassVar[dict[HookType, list[Callable]]]

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)

        # Step 1: Initialize _supported_hooks if not already set by @supports_hooks decorator
        if not hasattr(cls, "_supported_hooks"):
            cls._supported_hooks = set()

        # Step 2: Always create a new _class_hooks dictionary for this specific class
        cls._class_hooks = {}

        # Step 3: Collect all hook methods from the entire class hierarchy
        # Process in MRO order (base classes first) to ensure proper execution order
        for super_cls in reversed(cls.__mro__):
            if not issubclass(super_cls, HooksMixin):
                continue

            # Check each method defined directly in this class
            for name, attr in super_cls.__dict__.items():
                if callable(attr) and hasattr(attr, AIPERF_HOOK_TYPE):
                    hook_type = getattr(attr, AIPERF_HOOK_TYPE)
                    # Aggregate all hook methods (don't override, add to list)
                    cls._class_hooks.setdefault(hook_type, []).append(attr)

    def __init__(self, **kwargs):
        """
        Initialize the hook system.

        Args:
            supported_hooks: The hook types that the class supports.
            **kwargs: Passthrough kwargs for composability.
        """
        # Step 1: Inherit supported hook types from parent classes after decorators have run
        inherited_supported_hooks = set()
        for super_cls in self.__class__.__mro__[1:]:  # Skip self.__class__
            if hasattr(super_cls, "_supported_hooks"):
                inherited_supported_hooks.update(super_cls._supported_hooks)

        # Merge inherited supported hooks with any explicitly declared ones
        self.__class__._supported_hooks = self.__class__._supported_hooks.union(
            inherited_supported_hooks
        )

        # Step 2: Register hooks and validate support
        self._hooks: dict[HookType, list[Callable]] = {}
        for hook_type, hooks in self.__class__._class_hooks.items():
            for hook in hooks:
                if hook_type not in self.__class__._supported_hooks:
                    raise UnsupportedHookError(
                        f"Hook '@{hook_type.name.lower()}' is not supported by class '{self.__class__.__name__}' for func '{hook.__qualname__}'."
                    )
                self.register_hook(hook_type, hook)
        super().__init__(**kwargs)

    @property
    def supported_hooks(self) -> set[HookType]:
        """Get the supported hook types for this instance."""
        return self.__class__._supported_hooks

    @classmethod
    def get_class_hooks(cls, hook_type: HookType) -> list[Callable]:
        """Get the class hooks."""
        return cls._class_hooks.get(hook_type, [])

    def register_hook(self, hook_type: HookType, func: Callable):
        """Register a hook function for a given hook type.

        Args:
            hook_type: The hook type to register the function for.
            func: The function to register.
        """
        # Check if the hook type is supported
        if hook_type not in self._supported_hooks:
            raise UnsupportedHookError(
                f"Hook {hook_type} is not supported by class {self.__class__.__name__}."
            )

        # Handle binding properly:
        # - If it's already a bound method, use it as-is
        # - If it's an unbound method from our class hierarchy, bind it to the instance
        # - Otherwise (standalone functions, lambdas, etc.), use it as-is
        if hasattr(func, "__self__"):
            # Already a bound method
            bound_method = func
        elif (
            hasattr(func, "__qualname__")
            and hasattr(self.__class__, func.__name__)
            and getattr(self.__class__, func.__name__) is func
        ):
            # This is an unbound method from our class, bind it to the instance
            bound_method = func.__get__(self, self.__class__)
        else:
            # This is a standalone function, lambda, or local function - use it as-is
            bound_method = func

        # Register the function with the hook type
        self._hooks.setdefault(hook_type, []).append(bound_method)

    def get_hooks(self, hook_type: HookType) -> list[Callable]:
        """Get all the registered hooks for the given hook type."""
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
        if hook_type not in self.__class__._supported_hooks:
            raise UnsupportedHookError(
                f"Hook {hook_type} is not supported by class for {self.__qualname__}."
            )

        exceptions: list[Exception] = []
        for func in self.get_hooks(hook_type):
            try:
                if inspect.iscoroutinefunction(func):
                    await func(*args, **kwargs)
                else:
                    await asyncio.to_thread(func, *args, **kwargs)
            except Exception as e:
                self.exception(f"Error running hook {func.__qualname__}: {e}")
                exceptions.append(
                    AIPerfError(f"Error running hook {func.__qualname__}: {e}")
                )

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
        if hook_type not in self.__class__._supported_hooks:
            raise UnsupportedHookError(
                f"Hook {hook_type} is not supported by class for {self.__qualname__}."
            )

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


# class HooksMixin(BaseMixin):
#     """
#     Mixin to add hook support to a class. It abstracts away the details of the
#     :class:`HookSystem` and provides a simple interface for registering and running hooks.
#     """

#     def __init_subclass__(cls, **kwargs):
#         super().__init_subclass__(**kwargs)


#     def __init__(self, **kwargs):
#         """
#         Initialize the hook system and register all functions that are decorated with a hook decorator.
#         """
#         super().__init__(**kwargs)

#         # Initialize the hook system
#         self._hook_system = HookSystem(self.supported_hooks, **kwargs)

#         # Register all functions that are decorated with a hook decorator
#         # Iterate through MRO in reverse order to ensure base class hooks are registered first
#         for cls in reversed(self.__class__.__mro__):
#             # Skip object and other non-hook classes
#             if not issubclass(cls, HooksMixin):
#                 continue

#             # Get methods defined directly in this class (not inherited)
#             for _, attr in cls.__dict__.items():
#                 if callable(attr) and hasattr(attr, AIPERF_HOOK_TYPE):
#                     # Get the hook type from the function
#                     hook_type = getattr(attr, AIPERF_HOOK_TYPE)
#                     # Bind the method to the instance
#                     bound_method = attr.__get__(self, cls)
#                     # Register the function with the hook type
#                     self.register_hook(hook_type, bound_method)

#     # def register_hook(self, hook_type: HookType, func: Callable):
#     #     """Register a hook function for a given hook type.

#     #     Args:
#     #         hook_type: The hook type to register the function for.
#     #         func: The function to register.
#     #     """
#     #     self._hook_system.register_hook(hook_type, func)

#     # async def run_hooks(self, hook_type: HookType, *args, **kwargs):
#     #     """Run all the hooks serially. See :meth:`HookSystem.run_hooks`."""
#     #     await self._hook_system.run_hooks(hook_type, *args, **kwargs)

#     # async def run_hooks_async(self, hook_type: HookType, *args, **kwargs):
#     #     """Run all the hooks concurrently. See :meth:`HookSystem.run_hooks_async`."""
#     #     await self._hook_system.run_hooks_async(hook_type, *args, **kwargs)

#     # def get_hooks(self, hook_type: HookType) -> list[Callable]:
#     #     """Get all the registered hooks for the given hook type. See :meth:`HookSystem.get_hooks`."""
#     #     return self._hook_system.get_hooks(hook_type)
