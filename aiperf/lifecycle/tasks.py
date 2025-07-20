# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
Simple task management for AIPerf services.

This module provides clean, straightforward task management without the
complexity of the current async task manager system.
"""

import asyncio
import logging
from collections.abc import Callable
from typing import Any


class TaskManager:
    """
    Simple, clean task manager for background tasks.

    This provides straightforward task lifecycle management without complex
    mixins or inheritance hierarchies.

    Features:
    - Easy task creation and management
    - Automatic cleanup on shutdown
    - Error handling and recovery
    - Task status monitoring

    Example:
        manager = TaskManager()

        # Create a simple task
        task = manager.create_task(my_coroutine())

        # Create a periodic task
        manager.create_periodic_task(
            lambda: print("Hello"),
            interval=5.0,
            name="hello_task"
        )

        # Shutdown all tasks
        await manager.shutdown()
    """

    def __init__(self, logger: logging.Logger | None = None):
        self.logger = logger or logging.getLogger(__name__)
        self._tasks: dict[str, asyncio.Task] = {}
        self._task_counter = 0
        self._shutdown_event = asyncio.Event()

    def create_task(
        self, coro: Any, name: str | None = None, auto_cleanup: bool = True
    ) -> asyncio.Task:
        """
        Create and track a background task.

        Args:
            coro: Coroutine to run as a task
            name: Optional name for the task
            auto_cleanup: If True, remove task from tracking when it completes

        Returns:
            The created asyncio.Task
        """
        if name is None:
            self._task_counter += 1
            name = f"task_{self._task_counter}"

        task = asyncio.create_task(coro, name=name)
        self._tasks[name] = task

        if auto_cleanup:
            task.add_done_callback(lambda t: self._cleanup_task(name))

        self.logger.debug(f"Created task: {name}")
        return task

    def create_periodic_task(
        self,
        func: Callable,
        interval: float,
        name: str | None = None,
        immediate: bool = False,
    ) -> asyncio.Task:
        """
        Create a periodic task that runs at regular intervals.

        Args:
            func: Function to call periodically (can be sync or async)
            interval: Time in seconds between calls
            name: Optional name for the task
            immediate: If True, run immediately before waiting for interval

        Returns:
            The created asyncio.Task
        """

        async def periodic_wrapper():
            if immediate:
                try:
                    if asyncio.iscoroutinefunction(func):
                        await func()
                    else:
                        func()
                except Exception as e:
                    self.logger.error(f"Error in periodic task {name}: {e}")

            while not self._shutdown_event.is_set():
                try:
                    await asyncio.sleep(interval)
                    if self._shutdown_event.is_set():
                        break

                    if asyncio.iscoroutinefunction(func):
                        await func()
                    else:
                        func()

                except asyncio.CancelledError:
                    break
                except Exception as e:
                    self.logger.error(f"Error in periodic task {name}: {e}")
                    # Continue running despite errors

        return self.create_task(periodic_wrapper(), name)

    def create_continuous_task(
        self, func: Callable, name: str | None = None
    ) -> asyncio.Task:
        """
        Create a task that runs continuously until stopped.

        Args:
            func: Function to call continuously (can be sync or async)
            name: Optional name for the task

        Returns:
            The created asyncio.Task
        """

        async def continuous_wrapper():
            while not self._shutdown_event.is_set():
                try:
                    if asyncio.iscoroutinefunction(func):
                        await func()
                    else:
                        func()
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    self.logger.error(f"Error in continuous task {name}: {e}")
                    await asyncio.sleep(0.1)  # Brief pause to prevent tight loop

        return self.create_task(continuous_wrapper(), name)

    def get_task(self, name: str) -> asyncio.Task | None:
        """Get a task by name."""
        return self._tasks.get(name)

    def cancel_task(self, name: str) -> bool:
        """
        Cancel a specific task.

        Args:
            name: Name of the task to cancel

        Returns:
            True if task was found and cancelled, False otherwise
        """
        task = self._tasks.get(name)
        if task and not task.done():
            task.cancel()
            self.logger.debug(f"Cancelled task: {name}")
            return True
        return False

    def get_running_tasks(self) -> dict[str, asyncio.Task]:
        """Get all currently running tasks."""
        return {name: task for name, task in self._tasks.items() if not task.done()}

    def get_task_status(self) -> dict[str, str]:
        """Get status of all tasks."""
        status = {}
        for name, task in self._tasks.items():
            if task.done():
                if task.cancelled():
                    status[name] = "cancelled"
                elif task.exception():
                    status[name] = f"failed: {task.exception()}"
                else:
                    status[name] = "completed"
            else:
                status[name] = "running"
        return status

    async def wait_for_task(self, name: str, timeout: float | None = None) -> Any:
        """
        Wait for a specific task to complete.

        Args:
            name: Name of the task to wait for
            timeout: Optional timeout in seconds

        Returns:
            Task result

        Raises:
            KeyError: If task not found
            asyncio.TimeoutError: If timeout exceeded
        """
        task = self._tasks.get(name)
        if not task:
            raise KeyError(f"Task not found: {name}")

        if timeout:
            return await asyncio.wait_for(task, timeout=timeout)
        else:
            return await task

    async def shutdown(self, timeout: float = 10.0) -> None:
        """
        Shutdown all tasks gracefully.

        Args:
            timeout: Maximum time to wait for tasks to finish
        """
        self.logger.debug("Shutting down task manager...")

        # Signal shutdown
        self._shutdown_event.set()

        # Get all running tasks
        running_tasks = [task for task in self._tasks.values() if not task.done()]

        if not running_tasks:
            self.logger.debug("No running tasks to shutdown")
            return

        self.logger.debug(f"Waiting for {len(running_tasks)} tasks to complete...")

        try:
            # Wait for tasks to complete gracefully
            await asyncio.wait_for(
                asyncio.gather(*running_tasks, return_exceptions=True), timeout=timeout
            )
        except asyncio.TimeoutError:
            self.logger.warning(
                f"Tasks did not complete within {timeout}s, cancelling..."
            )

            # Cancel remaining tasks
            for task in running_tasks:
                if not task.done():
                    task.cancel()

            # Wait for cancellation to complete
            await asyncio.gather(*running_tasks, return_exceptions=True)

        self.logger.debug("Task manager shutdown complete")

    def _cleanup_task(self, name: str) -> None:
        """Remove completed task from tracking."""
        if name in self._tasks:
            task = self._tasks[name]
            if task.done():
                del self._tasks[name]
                self.logger.debug(f"Cleaned up completed task: {name}")


# Global task manager instance (can be overridden)
_global_manager: TaskManager | None = None


def get_task_manager() -> TaskManager:
    """Get the global task manager instance."""
    global _global_manager
    if _global_manager is None:
        _global_manager = TaskManager()
    return _global_manager


def set_task_manager(manager: TaskManager) -> None:
    """Set the global task manager instance."""
    global _global_manager
    _global_manager = manager
