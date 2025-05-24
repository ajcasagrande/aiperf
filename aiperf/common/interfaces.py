#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#  http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
import logging
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:  # prevent circular import
    from aiperf.common.comms.zmq.clients.dealer_router import DealerRouterBroker

from aiperf.common.logging import TraceLogger
from aiperf.common.models.comms import ZMQCommunicationConfig
from aiperf.common.models.message import Message


class SupportsRun(Protocol):
    """Protocol for classes that support running."""

    async def run(self) -> None:
        """Run the service."""
        ...


class SupportsStop(Protocol):
    """Protocol for classes that support stopping."""

    async def stop(self) -> None:
        """Stop the service."""
        ...


class SupportsInitialize(Protocol):
    """Protocol for classes that support initialization."""

    async def initialize(self) -> None:
        """Initialize the service."""
        ...


class SupportsCleanup(Protocol):
    """Protocol for classes that support cleanup."""

    async def cleanup(self) -> None:
        """Clean up the service."""
        ...


class SupportsId(Protocol):
    """Protocol for classes that support getting an ID."""

    @property
    def id(self) -> str:
        """Get the ID of the class."""
        ...


class SupportsLogging(Protocol):
    """Protocol for classes that support logging."""

    @property
    def logger(self) -> logging.Logger:
        """Get the logger for the class."""
        ...


class SupportsZMQConfig(Protocol):
    """Protocol for classes that contain ZMQ configuration."""

    @property
    def zmq_config(self) -> ZMQCommunicationConfig:
        """Get the ZMQ configuration for the class."""
        ...


class SupportsLifecycle(SupportsInitialize, SupportsRun, SupportsStop, SupportsCleanup):
    """Protocol for classes that support full lifecycle."""


class SupportsProcessMessage(Protocol):
    """Protocol for classes that support processing messages."""

    async def process_message(self, message: Message) -> Message:
        """Process the data."""
        ...


class WorkerProtocol(SupportsLifecycle, SupportsId, SupportsProcessMessage):
    """Protocol for worker classes."""


class WorkerManagerProtocol(SupportsLifecycle, SupportsId, SupportsProcessMessage):
    """Protocol for worker manager classes."""


class SupportsDealerRouterBroker(SupportsZMQConfig, SupportsRun, SupportsStop):
    """Protocol for dealer router broker classes."""

    @property
    def broker(self) -> "DealerRouterBroker":
        """Get the dealer router broker for the class."""
        ...


class SupportsTraceLogging:
    """Protocol for classes that support TRACE level logging."""

    @property
    def logger(self) -> TraceLogger:
        """Get the logger for this class."""
        ...
