# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

import pytest

from aiperf.common.enums.service_enums import LifecycleState
from aiperf.common.exceptions import InvalidStateError
from aiperf.common.hooks import on_init, on_start, on_stop
from aiperf.common.mixins.aiperf_lifecycle_mixin import AIPerfLifecycleMixin


class MyLifecycle(AIPerfLifecycleMixin):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.initialize_called = False
        self.start_called = False
        self.stop_called = False

    @on_init
    async def _initialize(self):
        self.initialize_called = True
        assert self.state == LifecycleState.INITIALIZING, "state should be initializing"

    @on_start
    async def _start(self):
        self.start_called = True
        assert self.state == LifecycleState.STARTING, "state should be starting"

    @on_stop
    async def _stop(self):
        self.stop_called = True
        assert self.state == LifecycleState.STOPPING, "state should be stopping"


@pytest.mark.asyncio
class TestAIPerfLifecycleMixin:
    """Test suite for AIPerfLifecycleMixin class."""

    async def test_lifecycle_mixin_basic_functionality(self):
        lifecycle = MyLifecycle()
        assert not lifecycle.initialize_called, "initialize should not have been called"
        assert lifecycle.state == LifecycleState.CREATED, "state should be created"

        await lifecycle.initialize()
        assert lifecycle.initialize_called, "initialize should have been called"
        assert lifecycle.state == LifecycleState.INITIALIZED, (
            "state should be initialized"
        )

        await lifecycle.start()
        assert lifecycle.start_called, "start should have been called"
        assert lifecycle.state == LifecycleState.RUNNING, "state should be running"

        await lifecycle.stop()
        assert lifecycle.stop_called, "stop should have been called"
        assert lifecycle.state == LifecycleState.STOPPED, "state should be stopped"

    @pytest.mark.parametrize(
        "existing_state,function,exception",
        [
            # Created state
            (LifecycleState.CREATED, "initialize", None),
            (LifecycleState.CREATED, "start", InvalidStateError),
            (LifecycleState.CREATED, "stop", InvalidStateError),
            # Initializing state
            (LifecycleState.INITIALIZING, "initialize", None),
            (LifecycleState.INITIALIZING, "start", InvalidStateError),
            (LifecycleState.INITIALIZING, "stop", InvalidStateError),
            # Initialized state
            (LifecycleState.INITIALIZED, "initialize", None),
            (LifecycleState.INITIALIZED, "start", None),
            (LifecycleState.INITIALIZED, "stop", None),
            # Starting state
            (LifecycleState.STARTING, "initialize", None),
            (LifecycleState.STARTING, "start", None),
            (LifecycleState.STARTING, "stop", None),
            # Running state
            (LifecycleState.RUNNING, "initialize", None),
            (LifecycleState.RUNNING, "start", None),
            (LifecycleState.RUNNING, "stop", None),
            # Stopping state
            (LifecycleState.STOPPING, "initialize", None),
            (LifecycleState.STOPPING, "start", InvalidStateError),
            (LifecycleState.STOPPING, "stop", None),
            # Stopped state
            (LifecycleState.STOPPED, "initialize", InvalidStateError),
            (LifecycleState.STOPPED, "start", InvalidStateError),
            (LifecycleState.STOPPED, "stop", None),
            # Failed state
            (LifecycleState.FAILED, "initialize", InvalidStateError),
            (LifecycleState.FAILED, "start", InvalidStateError),
            (LifecycleState.FAILED, "stop", None),
        ],
    )
    async def test_invalid_state_transitions(
        self,
        existing_state: LifecycleState,
        function: str,
        exception: type[Exception] | None,
    ):
        lifecycle = MyLifecycle()
        match existing_state:
            case LifecycleState.INITIALIZED | LifecycleState.STARTING:
                await lifecycle.initialize()
            case LifecycleState.RUNNING:
                await lifecycle.initialize()
                await lifecycle.start()
            case LifecycleState.STOPPING:
                await lifecycle.initialize()
                await lifecycle.start()
                lifecycle.stop_requested = True
            case LifecycleState.STOPPED:
                await lifecycle.initialize()
                await lifecycle.start()
                await lifecycle.stop()
            case _:
                pass

        lifecycle._state = existing_state

        if exception is not None:
            with pytest.raises(exception):
                await getattr(lifecycle, function)()
        else:
            await getattr(lifecycle, function)()
