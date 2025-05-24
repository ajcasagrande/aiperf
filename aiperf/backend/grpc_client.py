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
from aiperf.backend.client_interface import BackendClientProtocol
from aiperf.backend.client_mixins import BackendClientConfigMixin
from aiperf.common.enums import BackendClientType
from aiperf.common.models import BackendClientConfig, BackendClientResponse

################################################################################
# GRPC Backend Client Models
################################################################################


class GRPCBackendClientConfig(BaseModel):
    """Configuration specific to a GRPC backend client."""


class GRPCRequest(BaseModel):
    """Request specific to a GRPC backend client."""


class GRPCResponse(BaseModel):
    """Response specific to a GRPC backend client."""


################################################################################
# GRPC Backend Client Mixins
################################################################################


class GRPCBackendClientConfigMixin(BackendClientConfigMixin[GRPCBackendClientConfig]):
    """Mixin for GRPC backend client configuration."""


################################################################################
# GRPC Backend Client
################################################################################


@BackendClientFactory.register(BackendClientType.GRPC)
class GRPCBackendClient(
    GRPCBackendClientConfigMixin, BackendClientProtocol[GRPCRequest, GRPCResponse]
):
    """A backend client for GRPC communication.

    This class is responsible for formatting payloads, sending requests, and parsing responses for GRPC communication.
    """

    def __init__(self, client_config: BackendClientConfig[GRPCBackendClientConfig]):
        super().__init__(client_config)
        # TODO: Implement
        raise NotImplementedError("GRPCBackendClient is not implemented")

    def format_payload(self, payload: Any) -> GRPCRequest:
        # TODO: Implement
        raise NotImplementedError(
            "GRPCBackendClient does not support formatting payloads"
        )

    def send_request(self, endpoint: str, payload: GRPCRequest) -> GRPCResponse:
        # TODO: Implement
        raise NotImplementedError("GRPCBackendClient does not support sending requests")

    def parse_response(
        self, response: GRPCResponse
    ) -> BackendClientResponse[GRPCResponse]:
        # TODO: Implement
        raise NotImplementedError(
            "GRPCBackendClient does not support parsing responses"
        )
