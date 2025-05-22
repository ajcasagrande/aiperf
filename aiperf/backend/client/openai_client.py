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

from aiperf.backend.client.base import (
    BaseBackendClient,
)
from aiperf.backend.client.factory import (
    BackendClientFactory,
)
from aiperf.backend.client.model import (
    BackendClientConfig,
    OpenAIBackendClientConfig,
    OpenAIRequest,
    OpenAIResponse,
)
from aiperf.backend.enum import BackendClientType


@BackendClientFactory.register(BackendClientType.OPENAI)
class OpenAIBackendClient(
    BaseBackendClient[OpenAIBackendClientConfig, OpenAIRequest, OpenAIResponse]
):
    """A backend client for OpenAI communication.

    This class is responsible for formatting payloads, sending requests, and parsing responses for OpenAI communication.
    """

    def __init__(self, client_config: BackendClientConfig[OpenAIBackendClientConfig]):
        super().__init__(client_config)
        # TODO: Implement
        raise NotImplementedError("OpenAIBackendClient is not implemented")

    def format_payload(self, payload: Any) -> OpenAIRequest:
        # TODO: Implement
        raise NotImplementedError(
            "OpenAIBackendClient does not support formatting payloads"
        )

    def send_request(self, endpoint: str, payload: OpenAIRequest) -> OpenAIResponse:
        # TODO: Implement
        raise NotImplementedError(
            "OpenAIBackendClient does not support sending requests"
        )

    def parse_response(self, response: OpenAIResponse) -> Any:
        # TODO: Implement
        raise NotImplementedError(
            "OpenAIBackendClient does not support parsing responses"
        )
