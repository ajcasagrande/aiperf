#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0

import logging

from rich.console import Console
from rich.live import Live

from aiperf.common.hooks import (
    AIPerfHook,
    HooksMixin,
    supports_hooks,
)

logger = logging.getLogger(__name__)


@supports_hooks(AIPerfHook.ON_INIT, AIPerfHook.ON_START, AIPerfHook.ON_STOP)
class ConsoleUIMixin(HooksMixin):
    """Mixin for updating the console UI."""

    def __init__(self) -> None:
        super().__init__()
        self.console = Console()
        self.live: Live = Live(console=self.console)

    async def initialize(self) -> None:
        """Initialize the console UI."""
        await self.run_hooks_async(AIPerfHook.ON_INIT)

    async def start(self) -> None:
        """Start the console UI."""
        self.live.start()
        await self.run_hooks_async(AIPerfHook.ON_START)

    async def stop(self) -> None:
        """Stop the console UI."""
        await self.run_hooks_async(AIPerfHook.ON_STOP)
        self.live.stop()
