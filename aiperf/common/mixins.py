#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
import asyncio
import contextlib
import inspect
import logging
import time
from collections.abc import Callable

from aiperf.common.hooks import (
    AIPerfHook,
    HookConstants,
    HooksMixin,
    on_init,
    on_start,
    on_stop,
    supports_hooks,
)
from aiperf.common.models import AIPerfTaskOptions

################################################################################
# Base Mixins
################################################################################

logger = logging.getLogger(__name__)


@supports_hooks(AIPerfHook.ON_INIT)
class InitializableMixin(HooksMixin):
    """Mixin to add initializable support to a class. It provides the base public method
    for initializing the class, which will call the appropriate hooks, as well as an
    event that is set when initialization is complete.
    """

    def __init__(self):
        super().__init__()
        self.initialized_event = asyncio.Event()

    async def initialize(self):
        """Initialize the class. This should be called before the class is started."""
        await self.run_hooks(AIPerfHook.ON_INIT)
        self.initialized_event.set()

    @property
    def is_initialized(self) -> bool:
        """Whether the class is initialized."""
        return self.initialized_event.is_set()


@supports_hooks(AIPerfHook.ON_START)
class StartableMixin(HooksMixin):
    """Mixin to add start support to a class. It provides the base public method
    for starting the class, which will call the appropriate hooks, as well as an
    event that will trigger when starting is complete.
    """

    def __init__(self):
        super().__init__()
        self.started_event = asyncio.Event()

    async def start(self):
        """Start the class. This should be called after the class is initialized."""
        await self.run_hooks_async(AIPerfHook.ON_START)
        self.started_event.set()

    @property
    def is_started(self) -> bool:
        """Whether the class is started."""
        return self.started_event.is_set()


@supports_hooks(AIPerfHook.ON_STOP)
class StoppableMixin(HooksMixin):
    """Mixin to add stop support to a class. It provides the base public method
    for stopping the class, which will call the appropriate hooks, as well as an
    event that will trigger to let async tasks know that the class is stopping.
    """

    def __init__(self):
        super().__init__()
        self.stop_event = asyncio.Event()

    async def stop(self):
        """Stop the class. This should be called before the class is cleaned up."""
        self.stop_event.set()
        await self.run_hooks_async(AIPerfHook.ON_STOP)

    @property
    def is_stopped(self) -> bool:
        """Whether the class is stopped."""
        return self.stop_event.is_set()


@supports_hooks(AIPerfHook.ON_CLEANUP)
class CleanableMixin(HooksMixin):
    """Mixin to add cleanable support to a class. It provides the base public method
    for cleaning up the class, which will call the appropriate hooks, as well as an
    event that will trigger when cleanup is complete.
    """

    def __init__(self):
        super().__init__()
        self.cleaned_up_event = asyncio.Event()

    async def cleanup(self):
        """Cleanup the class. This should be called after the class is stopped."""
        await self.run_hooks(AIPerfHook.ON_CLEANUP)
        self.cleaned_up_event.set()

    @property
    def is_cleaned_up(self) -> bool:
        """Whether the class is cleaned up."""
        return self.cleaned_up_event.is_set()


################################################################################
# LifecycleMixin
################################################################################


class LifecycleMixin(
    InitializableMixin, StartableMixin, StoppableMixin, CleanableMixin
):
    """Mixin to add lifecycle support to a class. It provides the base public methods
    for initializing, starting, stopping, and cleaning up the class, which will call
    the appropriate hooks.

    This mixin is not meant to be used directly, but rather to be inherited by other mixins.
    """

    ...


################################################################################
# AIPerfTaskMixin
################################################################################


@supports_hooks(AIPerfHook.AIPERF_TASK)
class AIPerfTaskMixin(InitializableMixin, StartableMixin, StoppableMixin):
    """Mixin to add task support to a class. It abstracts away the details of the
    :class:`AIPerfTask` and provides a simple interface for registering and running tasks.
    It hooks into the :meth:`HooksMixin.on_init` and :meth:`HooksMixin.on_stop` hooks to
    start and stop the tasks.
    """

    def __init__(self):
        super().__init__()
        self.registered_tasks: dict[str, asyncio.Task] = {}

    async def _run_async_task(self, hook: Callable, options: AIPerfTaskOptions):
        """Run an asynchronous task (expected to be run in an event loop)."""

        if options.interval is None:
            return await hook()
        else:
            if options.delay_first_run:
                await asyncio.sleep(options.interval)

            while not self.is_stopped:
                try:
                    await hook()
                    await asyncio.sleep(options.interval)
                except asyncio.CancelledError:
                    break

    def _run_sync_task(self, hook: Callable, options: AIPerfTaskOptions):
        """Run a synchronous task (expected to be run in a thread)."""
        if options.interval is None:
            return hook()
        else:
            if options.delay_first_run:
                time.sleep(options.interval)

            while not self.is_stopped:
                try:
                    hook()
                    time.sleep(options.interval)
                except asyncio.CancelledError:
                    break

    async def _run_task(self, hook: Callable, options: AIPerfTaskOptions):
        """Run a task in the background. Either in an event loop or in a thread based
        on whether the function is a coroutine.
        """
        logger.info(f"Running task {hook.__name__} with options {options}")
        if inspect.iscoroutinefunction(hook):
            task = asyncio.create_task(self._run_async_task(hook, options))
        else:
            task = asyncio.create_task(
                asyncio.to_thread(self._run_sync_task, hook, options)
            )

        self.registered_tasks[hook.__name__] = task

    @on_init
    async def _run_initialize_tasks(self):
        """Run all the registered tasks that should be run at initialization.

        This is called after the class is initialized, and will start all the tasks
        that were registered with start_hook=AIPerfHook.ON_INIT.
        """
        for hook in self.get_hooks(AIPerfHook.AIPERF_TASK):
            options = getattr(
                hook, HookConstants.AIPERF_TASK_OPTIONS, AIPerfTaskOptions()
            )
            if options.start_hook == AIPerfHook.ON_INIT:
                await self._run_task(hook, options)

    @on_start
    async def _run_start_tasks(self):
        """Run all the registered tasks that should be run at start.

        This is called after the class is started, and will start all the tasks
        that were registered with start_hook=AIPerfHook.ON_START.
        """
        for hook in self.get_hooks(AIPerfHook.AIPERF_TASK):
            options = getattr(
                hook, HookConstants.AIPERF_TASK_OPTIONS, AIPerfTaskOptions()
            )
            if options.start_hook == AIPerfHook.ON_START:
                await self._run_task(hook, options)

    @on_stop
    async def _stop_tasks(self):
        """Stop all the registered tasks. This will wait for all the tasks to complete."""
        for task in self.registered_tasks.values():
            task.cancel()

        # Wait for all tasks to complete
        with contextlib.suppress(asyncio.CancelledError):
            await asyncio.gather(*self.registered_tasks.values())

        self.registered_tasks.clear()
