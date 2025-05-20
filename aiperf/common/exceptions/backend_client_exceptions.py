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

from aiperf.common.exceptions.base_exceptions import AIPerfError


class BackendClientError(AIPerfError):
    """Base class for all backend client exceptions."""

    message: str = "Backend client exception occurred"


class BackendClientInitializationError(BackendClientError):
    """Exception raised when an error occurs when initializing the backend client."""

    message: str = "Failed to initialize backend client channels"


class BackendClientNotInitializedError(BackendClientError):
    """Exception raised when the backend client is not initialized."""

    message: str = "Backend client not initialized"


class BackendClientRequestError(BackendClientError):
    """Exception raised when an error occurs when sending a request to the backend client."""

    message: str = "Failed to send a request"


class BackendClientResponseError(BackendClientError):
    """Exception raised when an error occurs when receiving a response from the backend client."""

    message: str = "Failed to receive a response"


class BackendClientCreationError(BackendClientError):
    """Exception raised when an error occurs when creating a backend client."""

    message: str = "Failed to create a backend client"


class BackendClientNotFoundError(BackendClientError):
    """Exception raised when a backend client is not found."""

    message: str = "Backend client not found"


class BackendClientTypeUnknownError(BackendClientError):
    """Exception raised when the backend client type is unknown."""

    message: str = "Backend client type is unknown"


class BackendClientTypeAlreadyRegisteredError(BackendClientError):
    """Exception raised when the backend client type is already registered."""

    message: str = "Backend client type is already registered"
