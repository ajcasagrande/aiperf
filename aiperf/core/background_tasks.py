#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
import asyncio
import inspect

from aiperf.common.mixins.async_task_manager_mixin import AsyncTaskManagerMixin
from aiperf.core.decorators import attrs
from aiperf.core.lifecycle import LifecycleMixin


class BackgroundTasksMixin(LifecycleMixin, AsyncTaskManagerMixin):
    """Background task management with decorators."""

    def __init__(self, **kwargs) -> None:
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
                run_once = getattr(method, attrs.background_task_run_once, False)

                if run_once:
                    self.execute_async(self._run_once_task(method))
                else:
                    self.execute_async(
                        self._run_interval_task(
                            method,
                            interval,
                            immediate=immediate,
                            stop_on_error=stop_on_error,
                        )
                    )

    async def _stop(self) -> None:
        await self.cancel_all_tasks()

    async def _run_once_task(self, method) -> None:
        try:
            if inspect.iscoroutinefunction(method):
                await method()
            else:
                method()
        except Exception as e:
            self.exception(f"Error in one-time task {method.__name__}: {e}")

    async def _run_interval_task(
        self, method, interval, immediate=False, stop_on_error=False
    ) -> None:
        while True:
            try:
                if interval is None or immediate:
                    await asyncio.sleep(0)  # Yield to other tasks
                    immediate = False  # Reset immediate flag for next iteration
                else:
                    sleep_time = interval() if callable(interval) else float(interval)
                    await asyncio.sleep(sleep_time)

                if inspect.iscoroutinefunction(method):
                    await method()
                else:
                    method()

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
