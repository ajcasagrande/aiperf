#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
from typing import Protocol, runtime_checkable

from aiperf.common.enums import AIPerfUIType
from aiperf.common.factories import FactoryMixin
from aiperf.common.messages import (
    Message,
)
from aiperf.progress.progress_tracker import ProgressTracker


@runtime_checkable
class AIPerfUIProtocol(Protocol):
    """Protocol for the AIPerf UI."""

    def __init__(self, progress_tracker: ProgressTracker, **kwargs): ...

    async def on_message(self, message: Message) -> None:
        """Handle a message from the system controller."""
        ...

    def is_initialized(self) -> bool:
        """Check if the lifecycle has been initialized."""
        ...

    async def run_async(self) -> None:
        """Start the lifecycle in the background. Will call the :meth:`HooksMixin.on_init` hooks,
        followed by the :meth:`HooksMixin.on_start` hooks. Will return immediately."""

    async def run_and_wait_for_start(self) -> None:
        """Start the lifecycle in the background and wait until the lifecycle is initialized and started.
        Will call the :meth:`HooksMixin.on_init` hooks, followed by the :meth:`HooksMixin.on_start` hooks."""

    async def wait_for_initialize(self) -> None:
        """Wait for the lifecycle to be initialized. Will wait until the :meth:`HooksMixin.on_init` hooks have been called.
        Will return immediately if the lifecycle is already initialized."""

    async def wait_for_start(self) -> None:
        """Wait for the lifecycle to be started. Will wait until the :meth:`HooksMixin.on_start` hooks have been called.
        Will return immediately if the lifecycle is already started."""

    async def wait_for_shutdown(self) -> None:
        """Wait for the lifecycle to be shutdown. Will wait until the :meth:`HooksMixin.on_stop` hooks have been called.
        Will return immediately if the lifecycle is already shutdown."""

    async def shutdown(self) -> None:
        """Shutdown the lifecycle. Will call the :meth:`HooksMixin.on_stop` hooks,
        followed by the :meth:`HooksMixin.on_cleanup` hooks."""


class AIPerfUIFactory(FactoryMixin[AIPerfUIType, AIPerfUIProtocol]):
    pass
