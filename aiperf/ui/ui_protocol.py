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
    """Protocol interface definition for AIPerf UI implementations.

    NOTE: The simplest way to implement this protocol is to inherit from the :class:`AIPerfLifecycleMixin`
    and then implement the :meth:`AIPerfUIProtocol.on_message` method.
    """

    def __init__(self, progress_tracker: ProgressTracker, **kwargs): ...

    async def on_message(self, message: Message) -> None:
        """Handle a message from the system controller."""
        ...

    def is_initialized(self) -> bool:
        """Check if the UI has been initialized."""
        ...

    async def run_async(self) -> None:
        """Start the UI in the background."""

    async def run_and_wait_for_start(self) -> None:
        """Start the UI in the background and wait until the UI is initialized and started."""

    async def wait_for_initialize(self) -> None:
        """Wait for the UI to be initialized."""

    async def wait_for_start(self) -> None:
        """Wait for the UI to be started."""

    async def wait_for_shutdown(self) -> None:
        """Wait for the UI to be shutdown."""

    async def shutdown(self) -> None:
        """Shutdown the UI."""


class AIPerfUIFactory(FactoryMixin[AIPerfUIType, AIPerfUIProtocol]):
    """Factory for defining the various UI implementations for the AIPerf System."""
