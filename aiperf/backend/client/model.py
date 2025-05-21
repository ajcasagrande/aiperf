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
from typing import Generic, TypeVar

from pydantic import BaseModel, Field

from aiperf.core.enum import BackendClientType

ConfigT = TypeVar("ConfigT", bound=BaseModel)


class BackendClientConfig(BaseModel, Generic[ConfigT]):
    """Configuration for a backend client.

    This is a generic model that can be used to configure any backend client.
    The type of the backend client configuration is specified by the generic type `ConfigT`.
    """

    backend_client_type: BackendClientType | str = Field(
        ...,
        description="The type of backend client to use. This should be a valid backend client "
        "type that is registered in the backend client factory.",
    )
    client_config: ConfigT = Field(
        ...,
        description="Configuration for the backend client. This should be a Pydantic model that "
        "is specific to the backend client type.",
    )


class GrpcBackendClientConfig(BaseModel):
    """Configuration specific to a gRPC backend client."""


class GrpcRequest(BaseModel):
    """Request specific to a gRPC backend client."""


class GrpcResponse(BaseModel):
    """Response specific to a gRPC backend client."""


class HttpBackendClientConfig(BaseModel):
    """Configuration specific to an HTTP backend client."""


class HttpRequest(BaseModel):
    """Request specific to an HTTP backend client."""


class HttpResponse(BaseModel):
    """Response specific to an HTTP backend client."""


class OpenAIBackendClientConfig(BaseModel):
    """Configuration specific to an OpenAI backend client."""


class OpenAIRequest(BaseModel):
    """Request specific to an OpenAI backend client."""


class OpenAIResponse(BaseModel):
    """Response specific to an OpenAI backend client."""
