# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
import os

from aiperf.common import aiperf_logger
from aiperf.common.exceptions import AIPerfMultiError, UnsupportedHookError
from aiperf.common.hooks import (
    AIPERF_HOOK_PARAMS,
    AIPERF_HOOK_TYPE,
    PROVIDES_HOOKS,
    Hook,
    HookType,
)
from aiperf.common.mixins.aiperf_logger_mixin import AIPerfLoggerMixin


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
                            f"Hook {method_hook_type} is not provided by any base class of {self.__class__.__name__}. "
                            f"(Provided Hooks: {[f'{hook_type}' for hook_type in self._provided_hook_types]})"
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

    def get_hooks(self, *hook_types: HookType, reversed: bool = False) -> list[Hook]:
        """Get the hooks for the given hook type."""
        hooks = [
            hook
            for hook_type, hooks in self._hooks.items()
            if not hook_types or hook_type in hook_types
            for hook in hooks
        ]
        if reversed:
            hooks.reverse()
        return hooks

    async def run_hooks(
        self, *hook_types: HookType, reversed: bool = False, **kwargs
    ) -> None:
        """Run the hooks for the given hook type, waiting for each hook to complete before running the next one.
        If reversed is True, the hooks will be run in reverse order. This is useful for stop/cleanup starting with
        the children and ending with the parent.
        """
        exceptions: list[Exception] = []
        for hook in self.get_hooks(*hook_types, reversed=reversed):
            self.debug(lambda hook=hook: f"Running hook: {hook!r}")
            try:
                await hook(**kwargs)
            except Exception as e:
                exceptions.append(e)
                self.exception(f"Error running hook: {e!r}")
        if exceptions:
            raise AIPerfMultiError("Errors running hooks", exceptions)


# Add this file as one to be ignored when finding the caller of aiperf_logger.
# This helps to make it more transparent where the actual function is being called from.
_srcfile = os.path.normcase(HooksMixin.get_hooks.__code__.co_filename)
aiperf_logger._ignored_files.append(_srcfile)
