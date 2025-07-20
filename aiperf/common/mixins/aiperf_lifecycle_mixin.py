# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

import asyncio
import inspect
from collections.abc import Callable
from typing import Protocol, runtime_checkable

from aiperf.common.constants import DEFAULT_LIFECYCLE_SHUTDOWN_TIMEOUT_SECONDS
from aiperf.common.hooks import (
    AIPerfHook,
    AIPerfHookParams,
    AIPerfTaskHook,
    on_start,
    on_stop,
    supports_hooks,
)
from aiperf.common.mixins.aiperf_logger_mixin import AIPerfLoggerMixin
from aiperf.common.mixins.async_task_manager_mixin import (
    AsyncTaskManagerMixin,
    AsyncTaskManagerProtocol,
)
from aiperf.common.mixins.hooks_mixin import HooksMixin


@supports_hooks(
    AIPerfTaskHook.AIPERF_TASK,
    AIPerfTaskHook.AIPERF_AUTO_TASK,
    AIPerfHook.ON_INIT,
    AIPerfHook.ON_START,
    AIPerfHook.ON_STOP,
    AIPerfHook.ON_CLEANUP,
)
class AIPerfLifecycleMixin(HooksMixin, AsyncTaskManagerMixin, AIPerfLoggerMixin):
    """Mixin to add task support to a class. It abstracts away the details of the
    :class:`AIPerfTask` and provides a simple interface for registering and running tasks.
    It hooks into the :meth:`HooksMixin.on_start` and :meth:`HooksMixin.on_stop` hooks to
    start and stop the tasks.
    """

    def __init__(self, **kwargs):
        self.stop_requested: asyncio.Event = asyncio.Event()
        self.initialized_event: asyncio.Event = asyncio.Event()
        self.started_event: asyncio.Event = asyncio.Event()
        self.shutdown_event: asyncio.Event = asyncio.Event()
        self.lifecycle_task: asyncio.Task | None = None

        super().__init__(**kwargs)

    def is_initialized(self) -> bool:
        """Check if the lifecycle has been initialized."""
        return self.initialized_event.is_set()

    def cancelled(self) -> bool:
        """Check if the lifecycle has been cancelled."""
        return self.lifecycle_task is None or self.lifecycle_task.cancelled()

    async def _run_lifecycle(self) -> None:
        """Run the internal lifecycle."""
        # Run all the initialization hooks and set the initialize_event
        await self.run_hooks(AIPerfHook.ON_INIT)
        self.initialized_event.set()

        # Run all the start hooks and set the start_event
        await self.run_hooks_async(AIPerfHook.ON_START)
        self.started_event.set()

        try:
            # Wait forever until the stop_requested event is set
            while True:
                await asyncio.sleep(100_000)
        except asyncio.CancelledError:
            self.info("Lifecycle cancelled by user")

            try:
                # Run all the stop hooks
                await self.run_hooks_async(AIPerfHook.ON_STOP)
            except Exception as e:
                self.exception(
                    f"Unhandled exception in lifecycle: {e.__class__.__name__} {e}"
                )

            try:
                # Run all the cleanup hooks and set the shutdown_event
                await self.run_hooks(AIPerfHook.ON_CLEANUP)
            except Exception as e:
                self.exception(
                    f"Unhandled exception in lifecycle: {e.__class__.__name__} {e}"
                )
        finally:
            self.shutdown_event.set()

    async def run_async(self) -> None:
        """Start the lifecycle in the background. Will call the :meth:`HooksMixin.on_init` hooks,
        followed by the :meth:`HooksMixin.on_start` hooks. Will return immediately."""
        # NOTE: Do not use execute_async here, as we want to track the lifecycle task
        # differently, so we can properly run cleanup hooks.
        self.lifecycle_task = asyncio.create_task(self._run_lifecycle())

    async def run_and_wait_for_start(self) -> None:
        """Start the lifecycle in the background and wait until the lifecycle is initialized and started.
        Will call the :meth:`HooksMixin.on_init` hooks, followed by the :meth:`HooksMixin.on_start` hooks."""
        await self.run_async()

        await self.initialized_event.wait()
        await self.started_event.wait()

    async def wait_for_initialize(self) -> None:
        """Wait for the lifecycle to be initialized. Will wait until the :meth:`HooksMixin.on_init` hooks have been called.
        Will return immediately if the lifecycle is already initialized."""
        await self.initialized_event.wait()

    async def wait_for_start(self) -> None:
        """Wait for the lifecycle to be started. Will wait until the :meth:`HooksMixin.on_start` hooks have been called.
        Will return immediately if the lifecycle is already started."""
        await self.started_event.wait()

    async def wait_for_shutdown(self) -> None:
        """Wait for the lifecycle to be shutdown. Will wait until the :meth:`HooksMixin.on_stop` hooks have been called.
        Will return immediately if the lifecycle is already shutdown."""
        await self.shutdown_event.wait()

    async def shutdown(self) -> None:
        """Shutdown the lifecycle. Will call the :meth:`HooksMixin.on_stop` hooks,
        followed by the :meth:`HooksMixin.on_cleanup` hooks."""
        self.stop_requested.set()

        if self.lifecycle_task and not self.cancelled():
            self.lifecycle_task.cancel()
            await asyncio.wait_for(
                self.lifecycle_task,
                timeout=DEFAULT_LIFECYCLE_SHUTDOWN_TIMEOUT_SECONDS,
            )
        else:
            self.debug("Lifecycle already cancelled or not running")

    @on_start
    async def _start_tasks(self):
        """Start all the registered tasks in the background."""

        # Start all the non-auto tasks
        for hook in self.get_hooks(AIPerfTaskHook.AIPERF_TASK):
            if inspect.iscoroutinefunction(hook):
                self.execute_async(hook())
            else:
                self.execute_async(asyncio.to_thread(hook))

        # Start all the auto tasks
        for hook in self.get_hooks(AIPerfTaskHook.AIPERF_AUTO_TASK):
            interval = getattr(
                hook, AIPerfHookParams.AIPERF_AUTO_TASK_INTERVAL_SEC, None
            )
            self.execute_async(self._auto_task_wrapper(hook, interval))

    @on_stop
    async def _stop_tasks(self):
        """Stop all the background tasks. This will wait for all the tasks to complete."""
        await self.cancel_all_tasks()

    async def _auto_task_wrapper(
        self,
        func: Callable,
        interval: float | Callable[["AIPerfLifecycleMixin"], float] | None = None,
    ) -> None:
        """Wrapper to run a task in a loop until cancelled."""
        while not self.stop_requested.is_set():
            try:
                if inspect.iscoroutinefunction(func):
                    await func()
                else:
                    await asyncio.to_thread(func)
            except (asyncio.CancelledError, StopAsyncIteration):
                break
            except Exception:
                self.logger.exception("Unhandled exception in task: %s", func.__name__)

            if interval is None:
                break

            if callable(interval):
                # Call the interval function with the self instance to get the interval
                # This allows the interval function to access the self instance and its attributes
                # in order to dynamically determine the interval.
                await asyncio.sleep(interval(self))
            else:
                await asyncio.sleep(interval)


@runtime_checkable
class AIPerfLifeCycleProtocol(AsyncTaskManagerProtocol, Protocol):
    """Protocol for the AIPerf lifecycle."""

    def is_initialized(self) -> bool:
        """Check if the lifecycle has been initialized."""
        ...

    async def run_async(self) -> None:
        """Start the lifecycle in the background. Will call the :meth:`HooksMixin.on_init` hooks,
        followed by the :meth:`HooksMixin.on_start` hooks. Will return immediately."""

    async def run_and_wait_for_start(self) -> None:
        """Start the lifecycle in the background and wait until the lifecycle is initialized and started.
        Will call the :meth:`HooksMixin.on_init` hooks, followed by the :meth:`HooksMixin.on_start` hooks."""

    async def wait_for_initialize(self) -> None:
        """Wait for the lifecycle to be initialized. Will wait until the :meth:`HooksMixin.on_init` hooks have been called.
        Will return immediately if the lifecycle is already initialized."""

    async def wait_for_start(self) -> None:
        """Wait for the lifecycle to be started. Will wait until the :meth:`HooksMixin.on_start` hooks have been called.
        Will return immediately if the lifecycle is already started."""

    async def wait_for_shutdown(self) -> None:
        """Wait for the lifecycle to be shutdown. Will wait until the :meth:`HooksMixin.on_stop` hooks have been called.
        Will return immediately if the lifecycle is already shutdown."""

    async def shutdown(self) -> None:
        """Shutdown the lifecycle. Will call the :meth:`HooksMixin.on_stop` hooks,
        followed by the :meth:`HooksMixin.on_cleanup` hooks."""

    def cancelled(self) -> bool:
        """Check if the lifecycle has been cancelled."""
        ...
