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
from typing import Any, Generic, Protocol, TypeVar

from aiperf.common.models import BackendClientConfig, BackendClientResponse, ConfigT

RequestT = TypeVar("RequestT", bound=Any, infer_variance=True)
ResponseT = TypeVar("ResponseT", bound=Any, infer_variance=True)


################################################################################
# Backend Client Protocols
################################################################################


class BackendClientConfigProtocol(Protocol, Generic[ConfigT]):
    """Protocol for a backend client configuration."""

    def __init__(self, client_config: BackendClientConfig[ConfigT]) -> None:
        """Create a new backend client based on the provided configuration."""
        ...

    @property
    def client_config(self) -> BackendClientConfig[ConfigT]:
        """Get the client configuration."""
        ...


class BackendClientProtocol(BackendClientConfigProtocol, Generic[RequestT, ResponseT]):
    """Protocol for a backend client.

    This protocol defines the methods that must be implemented by any backend client
    implementation that is compatible with the AIPerf framework.
    """

    def format_payload(self, payload: RequestT) -> RequestT:
        """Format the payload for the backend client.

        This method is used to format the payload for the backend client.

        Args:
            payload: The payload to format.

        Returns:
            The formatted payload.
        """
        ...

    def send_request(self, endpoint: str, payload: RequestT) -> ResponseT:
        """Send a request to the backend client.

        This method is used to send a request to the backend client.

        Args:
            endpoint: The endpoint to send the request to.
            payload: The payload to send to the backend client.

        Returns:
            The raw response from the backend client.
        """
        ...

    def parse_response(self, response: ResponseT) -> BackendClientResponse[ResponseT]:
        """Parse the response from the backend client.

        This method is used to parse the response from the backend client.

        Args:
            response: The raw response from the backend client.

        Returns:
            The parsed response from the backend client.
        """
        ...
