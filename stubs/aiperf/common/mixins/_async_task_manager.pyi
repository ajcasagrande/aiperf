#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
import asyncio
from collections.abc import Coroutine
from typing import Protocol

from aiperf.common.constants import (
    TASK_CANCEL_TIMEOUT_SHORT as TASK_CANCEL_TIMEOUT_SHORT,
)

class AsyncTaskManagerMixin:
    tasks: set[asyncio.Task]
    def __init__(self, **kwargs) -> None: ...
    def execute_async(self, coro: Coroutine) -> asyncio.Task: ...
    async def cancel_all_tasks(self, timeout: float = ...) -> None: ...

class AsyncTaskManagerProtocol(Protocol):
    def execute_async(self, coro: Coroutine) -> asyncio.Task: ...
    async def stop(self) -> None: ...
    async def cancel_all_tasks(self, timeout: float = ...) -> None: ...
