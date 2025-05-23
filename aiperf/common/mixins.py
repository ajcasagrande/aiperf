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
import uuid

from aiperf.common.interfaces import (
    SupportsCleanup,
    SupportsId,
    SupportsInitialize,
    SupportsRun,
    SupportsStop,
)


class SupportsIdMixin(SupportsId):
    """Mixin for services that support getting an ID.

    This mixin is used to provide a default implementation of the id property.
    """

    def __init__(self, service_id: str | None = None) -> None:
        """Initialize the service."""
        self.service_id = service_id or uuid.uuid4().hex

    @property
    def id(self) -> str:
        """Get the ID of the service."""
        return self.service_id


class SupportsRunMixin(SupportsRun):
    """Mixin for services that support running."""

    def run(self) -> None:
        """Run the service."""
        ...


class SupportsStopMixin(SupportsStop):
    """Mixin for services that support stopping."""

    def stop(self) -> None:
        """Stop the service."""
        ...


class SupportsCleanupMixin(SupportsCleanup):
    """Mixin for services that support cleanup."""

    def cleanup(self) -> None:
        """Clean up the service."""
        ...


class SupportsInitializeMixin(SupportsInitialize):
    """Mixin for services that support initialization."""

    def initialize(self) -> None:
        """Initialize the service."""
        ...
