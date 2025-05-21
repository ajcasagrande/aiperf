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

from aiperf.core.comm.zmq.client.enum import ClientType
from aiperf.core.message.model import Message
from aiperf.core.service.enum import ServiceState, ServiceType


class ServiceProtocol(Protocol):
    """Defines the contract for all services. It is used to ensure that all
    services implement the required methods and properties.
    """

    @property
    def required_clients(self) -> list[ClientType]:
        """The communication clients required by the service."""
        ...

    @property
    def service_type(self) -> ServiceType:
        """The type/name of the service."""
        # TODO: Can we do this better by using a decorator to set the service type
        ...

    async def set_state(self, state: ServiceState) -> None:
        """Set the state of the service."""
        ...

    async def initialize(self) -> None:
        """Initialize the service."""
        ...

    async def start(self) -> None:
        """Start the service. It should be called after the service has been initialized
        and configured."""
        ...

    async def stop(self) -> None:
        """Stop the service."""
        ...

    async def configure(self, message: Message) -> None:
        """Configure the service with the given configuration."""
        ...

    async def run_forever(self) -> None:
        """Run the service. This method will be the primary entry point for the service
        and will be called by the bootstrap script. It should not return until the
        service is completely shutdown.
        """
        ...
