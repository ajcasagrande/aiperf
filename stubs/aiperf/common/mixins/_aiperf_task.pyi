#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
from aiperf.common.hooks import AIPerfHook as AIPerfHook
from aiperf.common.hooks import AIPerfTaskHook as AIPerfTaskHook
from aiperf.common.hooks import on_init as on_init
from aiperf.common.hooks import on_stop as on_stop
from aiperf.common.mixins._async_task_manager import (
    AsyncTaskManagerMixin as AsyncTaskManagerMixin,
)
from aiperf.common.mixins._hooks import HooksMixin as HooksMixin
from aiperf.common.mixins._hooks import supports_hooks as supports_hooks

class AIPerfTaskMixin(HooksMixin, AsyncTaskManagerMixin):
    def __init__(self, **kwargs) -> None: ...
    async def initialize(self) -> None: ...
    async def start(self) -> None: ...
    async def stop(self) -> None: ...
