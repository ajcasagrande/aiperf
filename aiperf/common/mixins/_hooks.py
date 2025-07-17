# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

from collections.abc import Callable
from typing import ClassVar

from aiperf.common.hooks import AIPERF_HOOK_TYPE, HookSystem, HookType


class HooksMixin:
    """
    Mixin to add hook support to a class. It abstracts away the details of the
    :class:`HookSystem` and provides a simple interface for registering and running hooks.
    """

    # Class attributes that are set by the :func:`supports_hooks` decorator
    supported_hooks: ClassVar[set[HookType]] = set()

    def __init__(self, **kwargs):
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
                if callable(attr) and hasattr(attr, AIPERF_HOOK_TYPE):
                    # Get the hook type from the function
                    hook_type = getattr(attr, AIPERF_HOOK_TYPE)
                    # Bind the method to the instance
                    bound_method = attr.__get__(self, cls)
                    # Register the function with the hook type
                    self.register_hook(hook_type, bound_method)

        super().__init__(**kwargs)

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


def supports_hooks(*supported_hook_types: HookType) -> Callable[[type], type]:
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
