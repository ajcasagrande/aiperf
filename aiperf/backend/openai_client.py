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

import time
from typing import TYPE_CHECKING, Any

from openai import AsyncAzureOpenAI, AsyncOpenAI
from openai.types.chat.chat_completion_stream_options_param import (
    ChatCompletionStreamOptionsParam,
)
from pydantic import BaseModel, Field

from aiperf.backend.client_factory import (
    BackendClientFactory,
)
from aiperf.backend.client_mixins import BackendClientConfigMixin
from aiperf.common.enums import BackendClientType, StrEnum
from aiperf.common.interfaces import BackendClientProtocol
from aiperf.common.models import (
    BackendClientConfig,
    BackendClientResponse,
    BaseBackendClientConfig,
    RequestRecord,
)

if TYPE_CHECKING:
    from openai.types.chat.chat_completion import ChatCompletion

__all__ = [
    "OpenAIBackendClientConfig",
    "OpenAIRequest",
    "OpenAIResponse",
    "OpenAIBackendClientConfigMixin",
    "OpenAIBackendClientProtocol",
    "OpenAIBackendClient",
]

################################################################################
# OpenAI Backend Client Models
################################################################################


class OpenAIAPIType(StrEnum):
    """The type of API to use for the OpenAI backend client."""

    OPENAI = "openai"
    AZURE = "azure"


class OpenAIBackendClientConfig(BaseBackendClientConfig):
    """Configuration specific to an OpenAI backend client."""

    organization: str | None = Field(
        default=None,
        description="The organization to use for the OpenAI backend client.",
    )
    api_type: OpenAIAPIType = Field(
        default=OpenAIAPIType.OPENAI,
        description="The API type to use for the OpenAI backend client.",
    )
    api_version: str | None = Field(
        default=None,
        description="The API version to use for the OpenAI backend client.",
    )
    endpoint: str = Field(
        default="v1/chat/completions",
        description="The endpoint to use for the OpenAI backend client.",
    )
    model: str = Field(
        default="gpt-3.5-turbo",
        description="The model to use for the OpenAI backend client.",
    )
    max_tokens: int = Field(
        default=100,
        description="The maximum number of tokens to use for the OpenAI backend client.",
    )
    temperature: float = Field(
        default=0.7, description="The temperature to use for the OpenAI backend client."
    )
    top_p: float = Field(
        default=1.0, description="The top P to use for the OpenAI backend client."
    )
    stop: list[str] | None = Field(
        default=None,
        description="The stop sequence to use for the OpenAI backend client.",
    )
    frequency_penalty: float = Field(
        default=0.0,
        description="The frequency penalty to use for the OpenAI backend client.",
    )
    presence_penalty: float = Field(
        default=0.0,
        description="The presence penalty to use for the OpenAI backend client.",
    )


class OpenAIRequest(BaseModel):
    """Request specific to an OpenAI backend client."""


class OpenAIChatCompletionRequest(OpenAIRequest):
    """Request specific to an OpenAI chat completion."""

    messages: list[Any]
    model: str
    max_tokens: int
    temperature: float
    top_p: float
    stop: list[str]
    frequency_penalty: float
    presence_penalty: float


class OpenAICompletionRequest(OpenAIRequest):
    """Request specific to an OpenAI completion."""

    prompt: str
    model: str
    max_tokens: int
    temperature: float
    top_p: float
    stop: list[str]
    frequency_penalty: float
    presence_penalty: float


class OpenAIEmbeddingsRequest(OpenAIRequest):
    """Request specific to an OpenAI embeddings."""

    input: str
    model: str
    dimensions: int
    encoding_format: str
    user: str


class OpenAIResponse(BaseModel):
    """Response specific to an OpenAI backend client."""


class OpenAIChatResponsesRequest(OpenAIRequest):
    """Request specific to an OpenAI responses."""

    input: str
    model: str
    max_output_tokens: int


class OpenAIChatResponsesResponse(OpenAIResponse):
    """Response specific to an OpenAI responses."""

    response: "ChatResponse"


class OpenAIEmbeddingsResponse(OpenAIResponse):
    """Response specific to an OpenAI embeddings."""

    response: "Embeddings"


class OpenAICompletionResponse(OpenAIResponse):
    """Response specific to an OpenAI completion."""

    response: "Completion"
    status_code: int
    headers: dict[str, str]
    body: dict[str, Any]


class OpenAIChatCompletionResponse(OpenAIResponse):
    """Response specific to an OpenAI chat completion."""

    response: "ChatCompletion"


################################################################################
# OpenAI Backend Client Mixins / Protocols
################################################################################

OpenAIBackendClientConfigMixin = BackendClientConfigMixin[OpenAIBackendClientConfig]

OpenAIBackendClientProtocol = BackendClientProtocol[OpenAIRequest, OpenAIResponse]


class OpenAIClientMixin(OpenAIBackendClientConfigMixin):
    """Mixin to provide an OpenAI client based on the configuration."""

    def __init__(self, cfg: BackendClientConfig[OpenAIBackendClientConfig]):
        super().__init__(cfg)
        base_url = (
            f"https://{self.client_config.url}"
            if not self.client_config.url.startswith(("http://", "https://"))
            else self.client_config.url
        )
        if self.client_config.api_type == OpenAIAPIType.OPENAI:
            self._client = AsyncOpenAI(
                api_key=self.client_config.api_key,
                base_url=base_url,
                organization=self.client_config.organization,
                timeout=self.client_config.timeout_ms,
            )
        elif self.client_config.api_type == OpenAIAPIType.AZURE:
            self._client = AsyncAzureOpenAI(
                api_key=self.client_config.api_key,
                base_url=base_url,
                organization=self.client_config.organization,
                timeout=self.client_config.timeout_ms,
            )
        else:
            raise ValueError(f"Invalid OpenAI API type: {self.client_config.api_type}")

    @property
    def client(self) -> AsyncOpenAI | AsyncAzureOpenAI:
        """Get the OpenAI client."""
        return self._client


################################################################################
# OpenAI Backend Client
################################################################################


@BackendClientFactory.register(BackendClientType.OPENAI)
class OpenAIBackendClient(OpenAIClientMixin, OpenAIBackendClientProtocol):
    """A backend client for OpenAI communication.

    This class is responsible for formatting payloads, sending requests, and parsing responses for OpenAI communication.
    """

    def __init__(self, cfg: BackendClientConfig[OpenAIBackendClientConfig]):
        super().__init__(cfg)

    record: RequestRecord = RequestRecord()

    async def format_payload(self, endpoint: str, payload: Any) -> OpenAIRequest:
        if endpoint == "v1/chat/completions":
            return OpenAIChatCompletionRequest(
                messages=payload["messages"],
                model=self.client_config.model,
                max_tokens=self.client_config.max_tokens,
                temperature=self.client_config.temperature,
                top_p=self.client_config.top_p,
                stop=self.client_config.stop or [],
                frequency_penalty=self.client_config.frequency_penalty,
                presence_penalty=self.client_config.presence_penalty,
            )
        else:
            raise ValueError(f"Invalid endpoint: {endpoint}")

    async def send_request(
        self, endpoint: str, payload: OpenAIRequest
    ) -> RequestRecord:
        if isinstance(payload, OpenAIChatCompletionRequest):
            record: RequestRecord = RequestRecord()
            async for response in await self.client.chat.completions.create(
                model=self.client_config.model,
                messages=payload.messages,
                max_tokens=self.client_config.max_tokens,
                temperature=self.client_config.temperature,
                top_p=self.client_config.top_p,
                stop=self.client_config.stop,
                frequency_penalty=self.client_config.frequency_penalty,
                presence_penalty=self.client_config.presence_penalty,
                stream=True,
                stream_options=ChatCompletionStreamOptionsParam(
                    include_usage=True,
                ),
            ):
                record.response_timestamps_ns.append(time.time_ns())
                record.responses.append(response)

            return record

        elif isinstance(payload, OpenAICompletionRequest):
            response = await self.client.completions.create(
                model=self.client_config.model,
                prompt=payload.prompt,
                max_tokens=self.client_config.max_tokens,
                temperature=self.client_config.temperature,
                top_p=self.client_config.top_p,
                stop=self.client_config.stop,
                frequency_penalty=self.client_config.frequency_penalty,
                presence_penalty=self.client_config.presence_penalty,
            )
        elif isinstance(payload, OpenAIEmbeddingsRequest):
            response = await self.client.embeddings.create(
                model=self.client_config.model,
                input=payload.input,
                dimensions=payload.dimensions,
                encoding_format=payload.encoding_format,
                user=payload.user,
            )
        elif isinstance(payload, OpenAIChatResponsesRequest):
            response = await self.client.responses.create(
                input=payload.input,
                model=self.client_config.model,
                max_output_tokens=self.client_config.max_tokens,
            )
        else:
            raise ValueError(f"Invalid payload: {payload}")

        return OpenAIResponse(response=response)

    async def parse_response(
        self, response: OpenAIResponse
    ) -> BackendClientResponse[OpenAIResponse]:
        # TODO: Implement
        raise NotImplementedError(
            "OpenAIBackendClient does not support parsing responses"
        )
