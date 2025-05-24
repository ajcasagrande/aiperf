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


from http.client import HTTPResponse
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
# HTTP Backend Client Models
################################################################################


class HTTPBackendClientConfig(BaseModel):
    """Configuration specific to an HTTP backend client."""


class HTTPRequest(BaseModel):
    """Request specific to an HTTP backend client."""


class HttpResponse(BaseModel):
    """Response specific to an HTTP backend client."""


################################################################################
# HTTP Backend Client Mixins
################################################################################


class HTTPBackendClientConfigMixin(BackendClientConfigMixin[HTTPBackendClientConfig]):
    """Mixin for HTTP backend client configuration."""


################################################################################
# HTTP Backend Client
################################################################################


@BackendClientFactory.register(BackendClientType.HTTP)
class HTTPBackendClient(
    HTTPBackendClientConfigMixin, BackendClientProtocol[HTTPRequest, HTTPResponse]
):
    """A backend client for HTTP communication.

    This class is responsible for formatting payloads, sending requests, and parsing responses for HTTP communication.
    """

    def __init__(self, client_config: BackendClientConfig[HTTPBackendClientConfig]):
        super().__init__(client_config)
        # TODO: Implement
        raise NotImplementedError("HttpBackendClient is not implemented")

    def format_payload(self, payload: Any) -> HTTPRequest:
        # TODO: Implement
        raise NotImplementedError(
            "HttpBackendClient does not support formatting payloads"
        )

    def send_request(self, endpoint: str, payload: HTTPRequest) -> HTTPResponse:
        # TODO: Implement
        raise NotImplementedError("HttpBackendClient does not support sending requests")

    def parse_response(
        self, response: HTTPResponse
    ) -> BackendClientResponse[HTTPResponse]:
        # TODO: Implement
        raise NotImplementedError(
            "HttpBackendClient does not support parsing responses"
        )
