# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

import asyncio
from contextlib import suppress

from aiperf.common.constants import DEFAULT_LIFECYCLE_SHUTDOWN_TIMEOUT_SECONDS
from aiperf.common.enums.base_enums import CaseInsensitiveStrEnum
from aiperf.common.exceptions import InvalidStateError
from aiperf.core.lifecycle import LifecycleMixin


class ProfileLifecycleState(CaseInsensitiveStrEnum):
    """States for the profile lifecycle."""

    PENDING = "pending"
    CONFIGURING = "configuring"
    CONFIGURED = "configured"
    PROFILING = "profiling"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    FAILED = "failed"


class ProfileLifecycle(LifecycleMixin):
    """Lifecycle for a service that handles profiling lifecycle."""

    def __init__(self, **kwargs):
        self.profiling_state = ProfileLifecycleState.PENDING
        self.profiling_task: asyncio.Task | None = None
        self.profiling_configured_event = asyncio.Event()
        self.profiling_started_event = asyncio.Event()
        self.profiling_stopped_event = asyncio.Event()
        self.profiling_was_cancelled = False
        super().__init__(**kwargs)

    ###########################################################################
    # Public methods - call these externally, but do not override
    ###########################################################################

    async def configure_profiling(self):
        self.profiling_state = ProfileLifecycleState.CONFIGURING
        self.debug(lambda: f"Configuring profiling for {self}")
        try:
            await self._configure_profiling()
            self.profiling_state = ProfileLifecycleState.CONFIGURED
            self.debug(lambda: f"Configured profiling for {self}")
            self.profiling_configured_event.set()
        except Exception as e:
            self._fail(e)

    async def start_profiling(self):
        if self.profiling_state != ProfileLifecycleState.CONFIGURED:
            raise InvalidStateError(
                f"Cannot start profiling from state {self.profiling_state}"
            )

        self.profiling_state = ProfileLifecycleState.PROFILING
        self.debug(lambda: f"Starting profiling for {self}")
        try:
            await self._start_profiling()
            self.profiling_state = ProfileLifecycleState.COMPLETED
            self.debug(lambda: f"Started profiling for {self}")
            self.profiling_started_event.set()
        except Exception as e:
            self._fail(e)

    async def stop_profiling(self):
        """Cancel the profiling task and wait for it to complete."""
        if self.profiling_task:
            self.profiling_task.cancel()
            await asyncio.wait_for(
                self.profiling_task, timeout=DEFAULT_LIFECYCLE_SHUTDOWN_TIMEOUT_SECONDS
            )
            self.profiling_task = None

    async def _execute_stop_profiling(self):
        if self.profiling_state != ProfileLifecycleState.PROFILING:
            self.warning(
                f"Attempted to stop profiling for {self} in state {self.profiling_state}"
            )
            return
        self.debug(lambda: f"Stopping profiling for {self}")
        try:
            await asyncio.shield(self._stop_profiling())
            self.profiling_state = (
                ProfileLifecycleState.COMPLETED
                if not self.profiling_was_cancelled
                else ProfileLifecycleState.CANCELLED
            )
            self.debug(lambda: f"Stopped profiling for {self}")
            self.profiling_stopped_event.set()
        except Exception as e:
            self._fail_profiling(e)

    async def cancel_profiling(self):
        self.profiling_was_cancelled = True
        await self.stop_profiling()

    async def _profile_until_stopped(self):
        try:
            while True:
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            self.debug(lambda: f"Stop requested for {self}")
        finally:
            with suppress(asyncio.CancelledError):
                await self._execute_stop_profiling()

    def _fail_profiling(self, e: Exception) -> None:
        self.profiling_state = ProfileLifecycleState.FAILED
        self.exception(f"Failed profiling for {self}: {e}")
        self.profiling_stopped_event.set()

    ###########################################################################
    # Implementation methods - override these in subclasses
    ###########################################################################

    async def _configure_profiling(self):
        """Hook method for configuring profiling. Make sure to call super()._configure_profiling()"""
        pass  # Base implementation does nothing

    async def _start_profiling(self):
        """Hook method for starting profiling. Make sure to call super()._start_profiling()"""
        pass  # Base implementation does nothing

    async def _stop_profiling(self):
        """Hook method for stopping profiling. Make sure to call super()._stop_profiling()"""
        pass  # Base implementation does nothing
