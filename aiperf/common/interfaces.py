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
from typing import Protocol

from aiperf.common.models.message import Message


class SupportsRun(Protocol):
    """Protocol for services that support running."""

    def run(self) -> None:
        """Run the service."""
        ...


class SupportsStop(Protocol):
    """Protocol for services that support stopping."""

    def stop(self) -> None:
        """Stop the service."""
        ...


class SupportsInitialize(Protocol):
    """Protocol for services that support initialization."""

    def initialize(self) -> None:
        """Initialize the service."""
        ...


class SupportsCleanup(Protocol):
    """Protocol for services that support cleanup."""

    def cleanup(self) -> None:
        """Clean up the service."""
        ...


class SupportsId(Protocol):
    """Protocol for services that support getting an ID."""

    @property
    def id(self) -> str:
        """Get the ID of the service."""
        ...


class SupportsLifecycle(SupportsInitialize, SupportsRun, SupportsStop, SupportsCleanup):
    """Protocol for services that support full lifecycle."""


class SupportsProcessMessage(Protocol):
    """Protocol for services that support processing messages."""

    def process_message(self, message: Message) -> Message:
        """Process the data."""
        ...


class WorkerProtocol(SupportsLifecycle, SupportsId, SupportsProcessMessage):
    """Protocol for worker services."""


class WorkerManagerProtocol(SupportsLifecycle, SupportsId, SupportsProcessMessage):
    """Protocol for worker manager services."""
