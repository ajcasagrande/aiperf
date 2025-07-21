#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
import asyncio
import contextlib
import inspect
from collections.abc import Callable, Coroutine
from typing import TypeVar

from typing_extensions import Self

from aiperf.common.constants import TASK_CANCEL_TIMEOUT_SHORT
from aiperf.core.decorators import attrs
from aiperf.core.lifecycle import LifecycleMixin

BackgroundTaskT = TypeVar("BackgroundTaskT", bound="BackgroundTasksMixin")


def background_task(
    interval: float | Callable[[BackgroundTaskT], float] | None = None,
    immediate: bool = False,
    stop_on_error: bool = False,
) -> Callable:
    """
    Decorator to mark a method as a background task with automatic management.

    Tasks are automatically started when the service starts and stopped when the service stops.
    The decorated method will be run periodically in the background when the service is running.

    Args:
        interval: Time between task executions in seconds. If None, the task will run once.
        Can be a callable that returns the interval, and will be called with 'self' as the argument.
        immediate: If True, run the task immediately on start, otherwise wait for the interval first
        stop_on_error: If True, stop the task on any exception (default: log and continue)
    """

    def decorator(func: Callable) -> Callable:
        setattr(func, attrs.is_background_task, True)
        setattr(func, attrs.background_task_interval, interval)
        setattr(func, attrs.background_task_immediate, immediate)
        setattr(func, attrs.background_task_stop_on_error, stop_on_error)
        return func

    return decorator


class BackgroundTasksMixin(LifecycleMixin):
    """Background task management with decorators."""

    def __init__(self, **kwargs) -> None:
        self.background_tasks: set[asyncio.Task] = set()
        super().__init__(**kwargs)

    async def _start(self) -> None:
        """Discover and start all background tasks."""
        for name in dir(self):
            method = getattr(self, name)
            if hasattr(method, attrs.is_background_task):
                interval = getattr(method, attrs.background_task_interval, None)
                immediate = getattr(method, attrs.background_task_immediate, False)
                stop_on_error = getattr(
                    method, attrs.background_task_stop_on_error, False
                )

                self.execute_async(
                    self._run_background_task(
                        method,
                        interval=interval,
                        immediate=immediate,
                        stop_on_error=stop_on_error,
                    )
                )

    def execute_async(self, coro: Coroutine) -> asyncio.Task:
        """Create a task from a coroutine and add it to the set of background tasks, and return immediately.
        The task will be automatically cleaned up when it completes, or cancelled when the lifecycle stops.
        """
        task = asyncio.create_task(coro)
        self.background_tasks.add(task)
        task.add_done_callback(self.background_tasks.discard)
        return task

    async def _stop(self) -> None:
        await self._cancel_all_tasks()

    async def _cancel_all_tasks(
        self, timeout: float = TASK_CANCEL_TIMEOUT_SHORT
    ) -> None:
        """Cancel all tasks in the set and wait for up to timeout seconds for them to complete."""
        if not self.background_tasks:
            return

        for task in list(self.background_tasks):
            task.cancel()

        with contextlib.suppress(asyncio.TimeoutError, asyncio.CancelledError):
            await asyncio.wait_for(
                asyncio.gather(*self.background_tasks, return_exceptions=True),
                timeout=timeout,
            )

        # Clear the tasks set after cancellation to avoid memory leaks
        self.background_tasks.clear()

    async def _run_background_task(
        self,
        method,
        interval: float | Callable[[Self], float] | None = None,
        immediate: bool = False,
        stop_on_error: bool = False,
    ) -> None:
        while True:
            try:
                if interval is None or immediate:
                    await asyncio.sleep(0)  # Yield to other tasks
                    immediate = False  # Reset immediate flag for next iteration
                else:
                    sleep_time = interval(self) if callable(interval) else interval
                    await asyncio.sleep(sleep_time)

                if inspect.iscoroutinefunction(method):
                    await method()
                else:
                    await asyncio.to_thread(method)

                if interval is None:
                    break
            except asyncio.CancelledError:
                self.debug(f"Background task {method.__name__} cancelled")
                break
            except Exception as e:
                self.exception(f"Error in background task {method.__name__}: {e}")
                if stop_on_error:
                    self.exception(
                        f"Background task {method.__name__} stopped due to error"
                    )
                    break
                await asyncio.sleep(0.001)  # Give some time to recover, just in case
