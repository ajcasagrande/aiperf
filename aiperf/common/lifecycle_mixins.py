#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
import asyncio
import inspect
import logging
from collections.abc import Callable

from aiperf.common.enums import CaseInsensitiveStrEnum
from aiperf.common.exceptions import InvalidStateError
from aiperf.common.hooks import (
    AIPerfHook,
    AIPerfTaskHook,
    HooksMixin,
    on_start,
    supports_hooks,
)
from aiperf.common.mixins import AsyncTaskManagerMixin


class LifecycleState(CaseInsensitiveStrEnum):
    """Enum for the various lifecycle states."""

    # NOTE: The order of these states is important for the lifecycle flow.
    # The lifecycle states are ordered to reflect the typical lifecycle flow.
    # They can be used to track the current state of the lifecycle.
    NOT_INITIALIZED = "not_initialized"
    INITIALIZING = "initializing"
    INITIALIZED = "initialized"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    CLEANING_UP = "cleaning_up"
    STOPPED = "stopped"

    INITIALIZATION_FAILED = "initialization_failed"
    START_FAILED = "start_failed"

    def is_error(self) -> bool:
        """Check if the lifecycle state is an error state."""
        return self in (
            LifecycleState.INITIALIZATION_FAILED,
            LifecycleState.START_FAILED,
        )


@supports_hooks(
    AIPerfHook.ON_PRE_INIT,
    AIPerfHook.ON_INIT,
    AIPerfHook.ON_POST_INIT,
    AIPerfHook.ON_PRE_START,
    AIPerfHook.ON_START,
    AIPerfHook.ON_POST_START,
    AIPerfHook.ON_PRE_STOP,
    AIPerfHook.ON_STOP,
    AIPerfHook.ON_POST_STOP,
    AIPerfHook.ON_CLEANUP,
    AIPerfHook.ON_SET_STATE,
    AIPerfHook.ON_LIFECYCLE_ERROR,
)
class AIPerfLifecycleMixin(HooksMixin, AsyncTaskManagerMixin):
    """Mixin to add task support to a class. It abstracts away the details of the
    :class:`AIPerfTask` and provides a simple interface for registering and running tasks.
    It hooks into the :meth:`HooksMixin.on_start` and :meth:`HooksMixin.on_stop` hooks to
    start and stop the tasks.
    """

    def __init__(self):
        super().__init__()
        self.logger = logging.getLogger(self.__class__.__name__)

        self._state = LifecycleState.NOT_INITIALIZED
        self._error: Exception | None = None

        # Events to signal various lifecycle states
        self._initialized_event: asyncio.Event = asyncio.Event()
        self._started_event: asyncio.Event = asyncio.Event()
        self._stop_request: asyncio.Event = asyncio.Event()
        self._stopped_event: asyncio.Event = asyncio.Event()

    @property
    def was_initialized(self) -> bool:
        """Check if the lifecycle has been initialized."""
        return self._initialized_event.is_set()

    @property
    def was_started(self) -> bool:
        """Check if the lifecycle has been started."""
        return self._started_event.is_set()

    @property
    def is_running(self) -> bool:
        """Check if the lifecycle is currently in the RUNNING state."""
        return self._state == LifecycleState.RUNNING

    @property
    def stop_requested(self) -> bool:
        """Check if the lifecycle was requested to be stopped."""
        return self._stop_request.is_set()

    @property
    def state(self) -> LifecycleState:
        """Get the current lifecycle state."""
        return self._state

    @property
    def error(self) -> Exception | None:
        """Get the error that occurred during the lifecycle, if any."""
        return self._error

    def _set_error_state(self, state: LifecycleState, error: Exception) -> None:
        """Set the current lifecycle state to an error state."""
        # Set these first to ensure they are set before the hooks are run in case the hooks query the state or error
        self._state = state
        self._error = error

        self._set_state(state)
        self._set_error(error)

    def _set_state(self, state: LifecycleState) -> None:
        """Set the current lifecycle state and run the ON_SET_STATE hooks."""
        if state not in LifecycleState:
            raise ValueError(f"Invalid lifecycle state: {state}")

        if state == self._state:
            return

        self._state = state
        self.logger.debug("Setting lifecycle state to %s", state)
        self.execute_async(self.run_hooks_async(AIPerfHook.ON_SET_STATE, state=state))

    def _set_error(self, error: Exception) -> None:
        """Set the error that occurred during the lifecycle."""
        self._error = error
        self.logger.error("Setting lifecycle error to %s", error)
        self.execute_async(
            self.run_hooks_async(AIPerfHook.ON_LIFECYCLE_ERROR, error=error)
        )

    async def _run_initialization_hooks(self) -> bool:
        """Run the internal initialization lifecycle."""
        if self.state != LifecycleState.NOT_INITIALIZED:
            raise InvalidStateError(
                "Lifecycle is in an invalid state for initialization: %s",
                self.state.name,
            )

        self.logger.debug("Running lifecycle initialization hooks")
        self._set_state(LifecycleState.INITIALIZING)

        try:
            # Single try-except block because we want to stop as soon as any error occurs
            await self.run_hooks(AIPerfHook.ON_PRE_INIT)
            await self.run_hooks(AIPerfHook.ON_INIT)
            await self.run_hooks(AIPerfHook.ON_POST_INIT)
        except Exception as e:
            self.logger.exception("Error during lifecycle initialization: %s", e)
            self._set_error_state(LifecycleState.INITIALIZATION_FAILED, e)
            return False

        self.logger.debug("Lifecycle initialization complete")
        self._set_state(LifecycleState.INITIALIZED)
        # Set the initialized event to signal to external listeners that the lifecycle is initialized
        self._initialized_event.set()
        return True

    async def start(self) -> bool:
        """Start the lifecycle. Will initialize the lifecycle, start the lifecycle,
        and then run the lifecycle in the background until it is stopped."""
        if self.state != LifecycleState.INITIALIZED:
            raise InvalidStateError(
                "Lifecycle is in an invalid state for starting: %s", self.state.name
            )

        if not await self._start_lifecycle():
            return False

        # Run the managed lifecycle loop in the background
        self.execute_async(self._run_lifecycle_loop())
        return True

    async def _start_lifecycle(self) -> bool:
        """Run the internal lifecycle. This is a blocking function that will run until the lifecycle is stopped."""

        # Run all the initialization hooks and set the initialized_event
        if not await self._run_initialization_hooks():
            # If initialization failed, we should not proceed to start the lifecycle
            self.logger.error("Lifecycle initialization failed, aborting start")
            # Run the cleanup hooks to ensure the lifecycle is cleaned up
            await self._run_cleanup_hooks()
            return False

        # Run all the start hooks and set the started_event
        if not await self._run_start_hooks():
            # If start failed, we should not proceed to run the lifecycle
            self.logger.error("Lifecycle start failed, aborting run")
            # Run the stop hooks to ensure the lifecycle is properly stopped
            await self._run_stop_hooks()
            return False

        return True

    async def _run_start_hooks(self) -> bool:
        """Internally startup the lifecycle."""
        if self.state != LifecycleState.INITIALIZED:
            raise InvalidStateError(
                f"Lifecycle is in an invalid state for starting: {self.state.name}",
            )

        self.logger.debug("Running lifecycle start hooks")
        self._set_state(LifecycleState.STARTING)

        try:
            # Single try-except block because we want to stop as soon as any error occurs
            await self.run_hooks(AIPerfHook.ON_PRE_START)
            await self.run_hooks(AIPerfHook.ON_START)
            await self.run_hooks(AIPerfHook.ON_POST_START)
        except Exception as e:
            self.logger.exception("Error starting lifecycle: %s", e)
            self._set_error_state(LifecycleState.START_FAILED, e)
            return False

        self.logger.debug("Lifecycle startup complete")
        self._set_state(LifecycleState.RUNNING)
        # Set the started event to signal to external listeners that the lifecycle is started
        self._started_event.set()
        return True

    async def _run_lifecycle_loop(self) -> None:
        """Run the lifecycle loop. This is a blocking function that will run until the lifecycle is stopped."""
        while True:
            try:
                # This will block forever until the _stop_request event is set
                await self._stop_request.wait()
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.exception("Unhandled exception in lifecycle: %s", e)
                await asyncio.sleep(
                    0
                )  # Yield to the event loop to allow other tasks to run
                continue

        await self._run_stop_hooks()

    async def stop(self) -> None:
        """Stop the lifecycle and wait for it to be stopped."""
        self._stop_request.set()
        await self._stopped_event.wait()

    async def _run_stop_hooks(self) -> None:
        """Run the internal stop lifecycle."""
        if not self.was_started:
            raise InvalidStateError(
                "Lifecycle was not started, cannot stop",
            )

        # NOTE: We are swallowing all exceptions that occur during the stop process, as we
        # want to ensure that the lifecycle is shutdown gracefully, and properly cleaned up
        # even if an exception occurs during this process.

        self.logger.debug("Running lifecycle stop hooks")
        self._set_state(LifecycleState.STOPPING)

        try:
            await self.run_hooks(AIPerfHook.ON_PRE_STOP)
        except Exception as e:
            self.logger.exception("Error during pre-stop hooks: %s", e)
            self._set_error(e)

        try:
            await self.run_hooks_async(AIPerfHook.ON_STOP)
        except Exception as e:
            self.logger.exception("Error during stop hooks: %s", e)
            self._set_error(e)

        # Cancel all tasks from the AsyncTaskManagerMixin
        await self.cancel_all_tasks()

        try:
            await self.run_hooks(AIPerfHook.ON_POST_STOP)
        except Exception as e:
            self.logger.exception("Error during post-stop hooks: %s", e)
            self._set_error(e)

        await self._run_cleanup_hooks()

    async def _run_cleanup_hooks(self) -> None:
        """Run the internal cleanup lifecycle."""
        if self.state != LifecycleState.STOPPING:
            raise InvalidStateError(
                "Lifecycle is in an invalid state for cleanup: %s",
                self.state.name,
            )

        self.logger.debug("Running lifecycle cleanup hooks")
        self._set_state(LifecycleState.CLEANING_UP)
        try:
            await self.run_hooks(AIPerfHook.ON_CLEANUP)
        except Exception as e:
            self.logger.exception("Error during cleanup hooks: %s", e)
            self._set_error(e)

        self.logger.debug("Lifecycle cleanup complete")
        self._set_state(LifecycleState.STOPPED)
        # Set the stopped event to signal to external listeners that the lifecycle has been stopped
        self._stopped_event.set()


@supports_hooks(
    AIPerfTaskHook.AIPERF_TASK,
    AIPerfTaskHook.AIPERF_AUTO_TASK,
)
class AIPerfTaskLifecycleMixin(AIPerfLifecycleMixin):
    """Mixin to add aiperf task support to a class."""

    @on_start
    async def _start_aiperf_tasks(self):
        """Start all the non-auto tasks in the background."""
        for hook in self.get_hooks(AIPerfTaskHook.AIPERF_TASK):
            if inspect.iscoroutinefunction(hook):
                self.execute_async(hook())
            else:
                self.execute_async(asyncio.to_thread(hook))

    @on_start
    async def _start_auto_aiperf_tasks(self):
        """Start all the auto tasks in the background."""
        for hook in self.get_hooks(AIPerfTaskHook.AIPERF_AUTO_TASK):
            interval_sec = getattr(
                hook, AIPerfTaskHook.AIPERF_AUTO_TASK_INTERVAL_SEC, None
            )
            self.execute_async(self._aiperf_task_wrapper(hook, interval_sec))

    async def _aiperf_task_wrapper(
        self, func: Callable, interval_sec: float | None = None
    ) -> None:
        """Wrapper to run a task in a loop until the stop_requested event is set."""
        while not self.stop_requested:
            try:
                if inspect.iscoroutinefunction(func):
                    await func()
                else:
                    await asyncio.to_thread(func)
            except asyncio.CancelledError:
                break
            except Exception:
                self.logger.exception("Unhandled exception in task: %s", func.__name__)

            if interval_sec is None:
                break
            await asyncio.sleep(interval_sec)
