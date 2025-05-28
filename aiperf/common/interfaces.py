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
from typing import TYPE_CHECKING, Generic, Protocol

if TYPE_CHECKING:
    from aiperf.common.models import (
        BackendClientResponse,
        RequestRecord,
    )

from aiperf.common.enums import BackendClientType
from aiperf.common.types import ConfigT, InputT, OutputT, RequestT, ResponseT

__all__ = [
    "BackendClientConfigProtocol",
    "BackendClientProtocol",
]


################################################################################
# Converter Protocols
################################################################################


class InputConverterProtocol(Protocol, Generic[InputT, RequestT]):
    """Protocol for an input converter."""

    async def convert(self, input: InputT) -> RequestT:
        """Convert the input to the expected format."""
        ...


class OutputConverterProtocol(Protocol, Generic[OutputT, ResponseT]):
    """Protocol for an output converter."""

    async def convert(self, output: OutputT) -> ResponseT:
        """Convert the output to the expected format."""
        ...


################################################################################
# Backend Client Protocols
################################################################################


class BackendClientConfigProtocol(Protocol, Generic[ConfigT]):
    """Protocol for a backend client configuration."""

    def __init__(self, client_config: ConfigT) -> None:
        """Create a new backend client based on the provided configuration."""
        ...

    @property
    def client_config(self) -> ConfigT:
        """Get the client configuration."""
        ...


class BackendClientProtocol(Protocol, Generic[ConfigT, RequestT, ResponseT]):
    """Protocol for a backend client.

    This protocol defines the methods that must be implemented by any backend client
    implementation that is compatible with the AIPerf framework.
    """

    def __init__(self, client_config: ConfigT) -> None:
        """Create a new backend client based on the provided configuration."""
        ...

    @property
    def client_config(self) -> ConfigT:
        """Get the client configuration."""
        ...

    @property
    def client_type(self) -> BackendClientType | str:
        """Get the client type."""
        ...

    async def format_payload(self, endpoint: str, payload: RequestT) -> RequestT:
        """Format the payload for the backend client.

        This method is used to format the payload for the backend client.

        Args:
            payload: The payload to format.

        Returns:
            The formatted payload.
        """
        ...

    async def send_request(self, endpoint: str, payload: RequestT) -> "RequestRecord":
        """Send a request to the backend client.

        This method is used to send a request to the backend client.

        Args:
            endpoint: The endpoint to send the request to.
            payload: The payload to send to the backend client.

        Returns:
            The raw response from the backend client.
        """
        ...

    async def parse_response(
        self, response: ResponseT
    ) -> "BackendClientResponse[ResponseT]":
        """Parse the response from the backend client.

        This method is used to parse the response from the backend client.

        Args:
            response: The raw response from the backend client.

        Returns:
            The parsed response from the backend client.
        """
        ...
