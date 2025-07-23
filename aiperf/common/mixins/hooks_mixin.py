# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
import asyncio
import os
from collections.abc import Callable
from typing import Protocol, runtime_checkable

from pydantic import BaseModel

from aiperf.common import aiperf_logger
from aiperf.common.exceptions import AIPerfMultiError, UnsupportedHookError
from aiperf.common.hooks import (
    AIPERF_HOOK_PARAMS,
    AIPERF_HOOK_TYPE,
    PROVIDES_HOOKS,
    HookType,
)
from aiperf.common.mixins.aiperf_logger_mixin import AIPerfLoggerMixin


class Hook(BaseModel):
    """A hook is a function that is decorated with a hook type and optional parameters."""

    func: Callable
    params: BaseModel | None = None

    @property
    def hook_type(self) -> HookType:
        return getattr(self.func, AIPERF_HOOK_TYPE)

    @property
    def func_name(self) -> str:
        return self.func.__name__

    @property
    def qual_name(self) -> str:
        return f"{self.func.__module__}.{self.func_name}"

    async def __call__(self, **kwargs) -> None:
        if asyncio.iscoroutinefunction(self.func):
            await self.func(**kwargs)
        else:
            await asyncio.to_thread(self.func, **kwargs)

    def __str__(self) -> str:
        return f"{self.qual_name} ({self.hook_type})"


class HooksMixin(AIPerfLoggerMixin):
    """Mixin for a class to be able to provide hooks to its subclasses, and to be able to run them.

    In order to provide hooks, a class must:
    1. Use the @provides_hooks decorator to declare the hook types it provides.
    2, Call get_hooks or run_hooks to get or run the hooks.
    """

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._provided_hook_types: set[HookType] = set()

        self._hooks: dict[HookType, list[Hook]] = {}
        for cls in reversed(self.__class__.__mro__):
            if hasattr(cls, PROVIDES_HOOKS):
                self._provided_hook_types.update(getattr(cls, PROVIDES_HOOKS))

            for method in cls.__dict__.values():
                if not callable(method):
                    continue

                if hasattr(method, AIPERF_HOOK_TYPE):
                    method_hook_type = getattr(method, AIPERF_HOOK_TYPE)
                    if method_hook_type not in self._provided_hook_types:
                        raise UnsupportedHookError(
                            f"Hook {method_hook_type} is not provided by any base class of {self.__class__.__name__}. (Provided Hooks: {[f'{hook_type}' for hook_type in self._provided_hook_types]})"
                        )

                    bound_method = method.__get__(self)
                    self._hooks.setdefault(method_hook_type, []).append(
                        Hook(
                            func=bound_method,
                            params=getattr(method, AIPERF_HOOK_PARAMS, None),
                        ),
                    )

        self.debug(
            lambda: f"Provided hook types: {self._provided_hook_types} for {self.__class__.__name__}"
        )

    def get_hooks(self, *hook_types: HookType) -> list[Hook]:
        """Get the hooks for the given hook type."""
        return [
            hook
            for hook_type, hooks in self._hooks.items()
            if not hook_types or hook_type in hook_types
            for hook in hooks
        ]

    async def run_hooks(self, *hook_types: HookType, **kwargs) -> None:
        """Run the hooks for the given hook type, waiting for each hook to complete before running the next one."""
        exceptions: list[Exception] = []
        for hook in self.get_hooks(*hook_types):
            self.debug(lambda hook=hook: f"Running hook: {hook!r}")
            try:
                await hook(**kwargs)
            except Exception as e:
                exceptions.append(e)
                self.exception(f"Error running hook: {e!r}")
        if exceptions:
            raise AIPerfMultiError("Errors running hooks", exceptions)


@runtime_checkable
class HooksProtocol(Protocol):
    """Protocol for hooks methods."""

    def get_hooks(self, *hook_types: HookType) -> list[Hook]:
        """Get the hooks for the given hook type."""
        ...

    async def run_hooks(self, *hook_types: HookType, **kwargs) -> None:
        """Run the hooks for the given hook type, waiting for each hook to complete before running the next one."""
        ...


# Add this file as one to be ignored when finding the caller of aiperf_logger.
# This helps to make it more transparent where the actual function is being called from.
_srcfile = os.path.normcase(HooksMixin.get_hooks.__code__.co_filename)
aiperf_logger._ignored_files.append(_srcfile)
