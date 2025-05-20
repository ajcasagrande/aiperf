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
from abc import ABC, abstractmethod
from typing import Any

from aiperf.common.models.backend_clients.backend_client_models import (
    BackendClientConfig,
)


class BackendClientInterface(ABC):
    """Interface for a backend client.

    This interface defines the methods that must be implemented by a backend client.
    """

    @abstractmethod
    def __init__(self, client_config: BackendClientConfig) -> None:
        """Create a new backend client based on the provided configuration."""
        pass

    @abstractmethod
    def format_payload(self, payload: Any) -> Any:
        """Format the payload for the backend client.

        This method is used to format the payload for the backend client.

        Args:
            payload: The payload to format.

        Returns:
            The formatted payload.
        """
        pass

    @abstractmethod
    def send_request(self, endpoint: str, payload: Any) -> Any:
        """Send a request to the backend client.

        This method is used to send a request to the backend client.

        Args:
            endpoint: The endpoint to send the request to.
            payload: The payload to send to the backend client.

        Returns:
            The raw response from the backend client.
        """
        pass

    @abstractmethod
    def parse_response(self, response: Any) -> Any:
        """Parse the response from the backend client.

        This method is used to parse the response from the backend client.

        Args:
            response: The raw response from the backend client.

        Returns:
            The parsed response from the backend client.
        """
        pass
