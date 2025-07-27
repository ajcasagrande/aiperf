#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
from typing import Protocol, runtime_checkable

from aiperf.common.enums import AIPerfUIType
from aiperf.common.factories import AIPerfFactory
from aiperf.common.protocols import MessageBusClientProtocol
from aiperf.progress.progress_tracker import ProgressTracker


@runtime_checkable
class AIPerfUIProtocol(MessageBusClientProtocol, Protocol):
    """Protocol interface definition for AIPerf UI implementations.

    NOTE: The simplest way to implement this protocol is to inherit from the :class:`MessageBusClientMixin`
    and then implement the :meth:`AIPerfUIProtocol.on_message` method.
    """

    def __init__(self, progress_tracker: ProgressTracker, **kwargs): ...


class AIPerfUIFactory(AIPerfFactory[AIPerfUIType, AIPerfUIProtocol]):
    """Factory for defining the various UI implementations for the AIPerf System."""
