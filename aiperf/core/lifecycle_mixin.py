# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

import asyncio
import contextlib
import uuid

from aiperf.common.enums.base_enums import CaseInsensitiveStrEnum
from aiperf.common.exceptions import InvalidStateError
from aiperf.common.hooks import AIPerfHook, AIPerfTaskHook, supports_hooks
from aiperf.common.mixins.aiperf_logger_mixin import AIPerfLoggerMixin
from aiperf.common.mixins.hooks_mixin import HooksMixin
from aiperf.common.mixins.task_manager_mixin import AsyncTaskManagerMixin


class LifecycleState(CaseInsensitiveStrEnum):
    """Simple lifecycle state tracking."""

    CREATED = "created"
    INITIALIZING = "initializing"
    INITIALIZED = "initialized"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    STOPPED = "stopped"
    FAILED = "failed"


@supports_hooks(
    AIPerfHook.ON_INIT,
    AIPerfHook.ON_START,
    AIPerfHook.ON_STOP,
    AIPerfHook.ON_SET_STATE,
    AIPerfHook.ON_CLEANUP,
    AIPerfTaskHook.AIPERF_TASK,
    AIPerfTaskHook.AIPERF_AUTO_TASK,
)
class LifecycleMixin(HooksMixin, AIPerfLoggerMixin, AsyncTaskManagerMixin):
    """Mixin to manage the lifecycle of a component/service."""

    def __init__(self, id: str | None = None, **kwargs) -> None:
        self.id = id or f"{self.__class__.__name__}-{uuid.uuid4().hex[:8]}"
        self._state = LifecycleState.CREATED
        self.initialized_event = asyncio.Event()
        self.started_event = asyncio.Event()
        self.stopped_event = asyncio.Event()  # set on stop or failure
        super().__init__(logger_name=self.id, **kwargs)

    @property
    def state(self) -> LifecycleState:
        return self._state

    @state.setter
    def state(self, state: LifecycleState) -> None:
        if state == self._state:
            return
        old_state = self._state
        self._state = state
        self.debug(lambda: f"State changed from {old_state} to {state} for {self}")
        self.execute_async(
            self.run_hooks(
                AIPerfHook.ON_SET_STATE, old_state=old_state, new_state=state
            )
        )

    async def initialize(self) -> None:
        if self.state != LifecycleState.CREATED:
            raise InvalidStateError(f"Cannot initialize from state {self.state}")
        self.state = LifecycleState.INITIALIZING
        self.debug(lambda: f"Initializing {self}")
        try:
            await self.run_hooks(AIPerfHook.ON_INIT)
            self.state = LifecycleState.INITIALIZED
            self.debug(lambda: f"Initialized {self}")
            self.initialized_event.set()
        except Exception as e:
            self._fail(e)

    async def start(self) -> None:
        if self.state != LifecycleState.INITIALIZED:
            raise InvalidStateError(f"Cannot start from state {self.state}")
        self.state = LifecycleState.STARTING
        self.debug(lambda: f"Starting {self}")
        try:
            await self.run_hooks(AIPerfHook.ON_START)
            self.state = LifecycleState.RUNNING
            self.debug(lambda: f"Started {self}")
            self.started_event.set()
        except Exception as e:
            self._fail(e)

    async def stop(self) -> None:
        """Stop the lifecycle."""
        if self.state != LifecycleState.RUNNING:
            self.warning(f"Attempted to stop {self} in state {self.state}")
            return

        self.state = LifecycleState.STOPPING
        self.debug(lambda: f"Stopping {self}")
        try:
            with contextlib.suppress(asyncio.CancelledError, asyncio.TimeoutError):
                await asyncio.shield(self.run_hooks(AIPerfHook.ON_STOP))
        except Exception as e:
            self._fail(e)

        try:
            with contextlib.suppress(asyncio.CancelledError, asyncio.TimeoutError):
                await asyncio.shield(self.run_hooks(AIPerfHook.ON_CLEANUP))
        except Exception as e:
            self._fail(e)

        self.state = LifecycleState.STOPPED
        self.debug(lambda: f"Stopped {self}")
        self.stopped_event.set()

    def _fail(self, e: Exception) -> None:
        """Set the state to failed and raise an asyncio.CancelledError."""
        self.state = LifecycleState.FAILED
        self.exception(f"Failed for {self}: {e}")
        self.stopped_event.set()
        # TODO: Should we actually raise an asyncio.CancelledError?
        raise asyncio.CancelledError(f"Failed for {self}: {e}") from e

    def __str__(self) -> str:
        state = self.state
        return f"{self.__class__.__name__} {self.id} ({state=})"

    def __repr__(self) -> str:
        state = self.state
        return f"<{self.__class__.__qualname__} {self.id} ({state=})>"
