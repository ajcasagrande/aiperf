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

from typing import Any

from pydantic import BaseModel

from aiperf.backend.client_factory import (
    BackendClientFactory,
)
from aiperf.backend.client_mixins import BackendClientConfigMixin
from aiperf.common.enums import BackendClientType
from aiperf.common.interfaces import BackendClientProtocol
from aiperf.common.models import BackendClientConfig, BackendClientResponse

__all__ = [
    "DynamoBackendClientConfig",
    "DynamoRequest",
    "DynamoResponse",
    "DynamoBackendClientConfigMixin",
    "DynamoBackendClientProtocol",
    "DynamoBackendClient",
]

################################################################################
# Dynamo Backend Client Models
################################################################################


class DynamoBackendClientConfig(BaseModel):
    """Configuration specific to an Dynamo backend client."""


class DynamoRequest(BaseModel):
    """Request specific to an Dynamo backend client."""


class DynamoResponse(BaseModel):
    """Response specific to an Dynamo backend client."""


################################################################################
# Dynamo Backend Client Mixins / Protocols
################################################################################

DynamoBackendClientConfigMixin = BackendClientConfigMixin[DynamoBackendClientConfig]

DynamoBackendClientProtocol = BackendClientProtocol[DynamoRequest, DynamoResponse]

################################################################################
# Dynamo Backend Client
################################################################################


@BackendClientFactory.register(BackendClientType.OPENAI)
class DynamoBackendClient(DynamoBackendClientConfigMixin, DynamoBackendClientProtocol):
    """A backend client for communicating with Dynamo directly.

    This class is responsible for formatting payloads, sending requests, and parsing responses for communicating with Dynamo directly.
    """

    def __init__(self, client_config: BackendClientConfig[DynamoBackendClientConfig]):
        super().__init__(client_config)
        # TODO: Implement
        raise NotImplementedError("DynamoBackendClient is not implemented")

    def format_payload(self, payload: Any) -> DynamoRequest:
        # TODO: Implement
        raise NotImplementedError(
            "DynamoBackendClient does not support formatting payloads"
        )

    def send_request(self, endpoint: str, payload: DynamoRequest) -> DynamoResponse:
        # TODO: Implement
        raise NotImplementedError(
            "DynamoBackendClient does not support sending requests"
        )

    def parse_response(
        self, response: DynamoResponse
    ) -> BackendClientResponse[DynamoResponse]:
        # TODO: Implement
        raise NotImplementedError(
            "DynamoBackendClient does not support parsing responses"
        )
