#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
import asyncio

import pytest

from aiperf.common.hooks import AIPerfHook, aiperf_task
from aiperf.common.mixins import AIPerfTaskMixin
from aiperf.common.models import AIPerfTaskOptions


class ExampleTaskClass(AIPerfTaskMixin):
    def __init__(self):
        self.running = False
        super().__init__()

    @aiperf_task(
        AIPerfTaskOptions(
            interval=None,
            start_hook=AIPerfHook.ON_START,
            delay_first_run=False,
        )
    )
    async def _run_task_(self):
        self.running = True

        while True:
            try:
                await asyncio.sleep(0.1)
            except asyncio.CancelledError:
                break

        self.running = False


@pytest.mark.asyncio
async def test_aiperf_task():
    task_class = ExampleTaskClass()

    assert not task_class.running, "Task should not be running before starting"
    await task_class.start()
    await asyncio.sleep(0.1)  # avoid race condition
    assert task_class.running, "Task should be running after starting"

    await task_class.stop()
    await asyncio.sleep(0.01)  # avoid race condition
    assert not task_class.running, "Task should not be running after stopping"


class ExampleTaskClass2(AIPerfTaskMixin):
    def __init__(self):
        self.running = False
        super().__init__()

    @aiperf_task(
        AIPerfTaskOptions(
            interval=0.1,
            start_hook=AIPerfHook.ON_INIT,
            delay_first_run=False,
        )
    )
    async def _run_task_(self):
        self.running = True

        while True:
            try:
                await asyncio.sleep(0.1)
            except asyncio.CancelledError:
                break

        self.running = False


@pytest.mark.asyncio
async def test_aiperf_task_will_run_on_init_and_stop():
    task_class = ExampleTaskClass2()
    await task_class.initialize()
    await asyncio.sleep(0.01)  # avoid race condition
    assert task_class.running, "Task should be running after initialization"

    await task_class.stop()
    await asyncio.sleep(0.01)  # avoid race condition
    assert not task_class.running, "Task should not be running after stopping"
