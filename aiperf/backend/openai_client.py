#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0

import os
import time
from typing import Any

from openai import AsyncAzureOpenAI, AsyncOpenAI
from openai.types.chat.chat_completion import ChatCompletion
from openai.types.chat.chat_completion_stream_options_param import (
    ChatCompletionStreamOptionsParam,
)
from openai.types.completion import Completion
from openai.types.embedding import Embedding
from openai.types.responses.response import Response
from pydantic import BaseModel, Field

from aiperf.backend.client_mixins import BackendClientConfigMixin
from aiperf.backend.factory import BackendClientFactory
from aiperf.common.enums import BackendClientType, CaseInsensitiveStrEnum
from aiperf.common.interfaces import BackendClientProtocol
from aiperf.common.record_models import (
    BackendClientResponse,
    GenericHTTPBackendClientConfig,
    RequestRecord,
)

################################################################################
# OpenAI Backend Client Models
################################################################################


class OpenAIType(CaseInsensitiveStrEnum):
    """The type of API to use for the OpenAI backend client."""

    OPENAI = "openai"
    AZURE = "azure"


class OpenAIBackendClientConfig(GenericHTTPBackendClientConfig):
    """Configuration specific to an OpenAI backend client."""

    organization: str | None = Field(
        default=None,
        description="The organization to use for the OpenAI backend client.",
    )
    api_type: OpenAIType = Field(
        default=OpenAIType.OPENAI,
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


################################################################################
# OpenAI Backend Client Requests
################################################################################


class OpenAIBaseRequest(BaseModel):
    """Base request specific to an OpenAI backend client."""

    model: str
    kwargs: dict[str, Any] | None = None


class OpenAIChatCompletionRequest(OpenAIBaseRequest):
    """Request specific to an OpenAI chat completion."""

    messages: list[Any]
    max_tokens: int


class OpenAIChatResponsesRequest(OpenAIBaseRequest):
    """Response specific to an OpenAI responses ."""

    input: str
    max_output_tokens: int


class OpenAICompletionRequest(OpenAIBaseRequest):
    """Request specific to an OpenAI completion."""

    prompt: str
    max_tokens: int


class OpenAIEmbeddingsRequest(OpenAIBaseRequest):
    """Request specific to an OpenAI embeddings."""

    input: str
    dimensions: int
    encoding_format: str
    user: str


################################################################################
# OpenAI Backend Client Responses
################################################################################


class OpenAIBaseResponse(BaseModel):
    """Response specific to an OpenAI backend client."""


class OpenAIChatResponsesResponse(OpenAIBaseResponse):
    """Response specific to an OpenAI responses."""

    response: Response


class OpenAIEmbeddingsResponse(OpenAIBaseResponse):
    """Response specific to an OpenAI embeddings."""

    response: Embedding


class OpenAICompletionResponse(OpenAIBaseResponse):
    """Response specific to an OpenAI completion."""

    response: Completion
    status_code: int
    headers: dict[str, str]
    body: dict[str, Any]


class OpenAIChatCompletionResponse(OpenAIBaseResponse):
    """Response specific to an OpenAI chat completion."""

    response: ChatCompletion


################################################################################
# OpenAI Backend Client Mixins / Protocols
################################################################################

OpenAIBackendClientConfigMixin = BackendClientConfigMixin[OpenAIBackendClientConfig]
"""Type alias for a backend client config mixin that supports OpenAI configuration."""

OpenAIBackendClientProtocol = BackendClientProtocol[
    OpenAIBackendClientConfig, OpenAIBaseRequest, OpenAIBaseResponse
]
"""Type alias for a backend client protocol that supports OpenAI."""


class OpenAIClientMixin(OpenAIBackendClientConfigMixin):
    """Mixin to provide an OpenAI client based on the configuration.
    Currently supports OpenAI and Azure OpenAI."""

    def __init__(self, client_config: OpenAIBackendClientConfig):
        super().__init__(client_config)

        self.client_config.api_key = os.environ.get(
            "OPENAI_API_KEY", "sk-fakeai-1234567890abcdef"
        )

        base_url = (
            f"https://{self.client_config.url}"
            if not self.client_config.url.startswith(("http://", "https://"))
            else self.client_config.url
        )

        if self.client_config.api_type == OpenAIType.OPENAI:
            self._client = AsyncOpenAI(
                api_key=self.client_config.api_key,
                base_url=base_url,
                organization=self.client_config.organization,
                timeout=self.client_config.timeout_ms,
            )

        elif self.client_config.api_type == OpenAIType.AZURE:
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
    """A backend client for communicating with OpenAI based REST APIs.

    This class is responsible for formatting payloads, sending requests, and parsing responses for OpenAI based REST APIs.
    """

    def __init__(self, client_config: OpenAIBackendClientConfig):
        super().__init__(client_config)

    async def format_payload(
        self, endpoint: str, payload: dict[str, Any]
    ) -> OpenAIBaseRequest:
        # TODO: Is this actually an InputConverterProtocol?

        if endpoint == "v1/chat/completions":
            return OpenAIChatCompletionRequest(
                messages=payload["messages"],
                model=self.client_config.model,
                max_tokens=self.client_config.max_tokens,
                kwargs=payload.get("kwargs", {}),
            )

        elif endpoint == "v1/completions":
            return OpenAICompletionRequest(
                prompt=payload["prompt"],
                model=self.client_config.model,
                max_tokens=self.client_config.max_tokens,
                kwargs=payload.get("kwargs", {}),
            )

        elif endpoint == "v1/embeddings":
            return OpenAIEmbeddingsRequest(
                input=payload["input"],
                model=self.client_config.model,
                dimensions=payload["dimensions"],
                encoding_format=payload["encoding_format"],
                user=payload["user"],
                kwargs=payload.get("kwargs", {}),
            )

        elif endpoint == "v1/responses":
            return OpenAIChatResponsesRequest(
                input=payload["input"],
                model=self.client_config.model,
                max_output_tokens=self.client_config.max_tokens,
                kwargs=payload.get("kwargs", {}),
            )

        else:
            raise ValueError(f"Invalid endpoint: {endpoint}")

    @property
    def client_type(self) -> BackendClientType:
        return BackendClientType.OPENAI

    async def send_request(
        self, endpoint: str, payload: OpenAIBaseRequest
    ) -> RequestRecord:
        # TODO: Is this actually an OutputConverterProtocol?

        # return RequestRecord(
        #     start_time_ns=time.time_ns(),
        #     response_timestamps_ns=[time.time_ns()],
        #     responses=[BackendClientResponse(
        #             response=OpenAIChatCompletionResponse(
        #                 response=ChatCompletion(
        #                     id=uuid.uuid4().hex,
        #                     object="chat.completion",
        #                     created=int(time.time()),
        #                     model=self.client_config.model,
        #                     choices=[
        #                         Choice(
        #                             index=0,
        #                             message=ChatCompletionMessage(
        #                                 role="assistant",
        #                                 content="test",
        #                             ),
        #                             finish_reason="stop",
        #                             logprobs=None,
        #                         )
        #                     ],
        #                     usage=CompletionUsage(
        #                         completion_tokens=100,
        #                         prompt_tokens=100,
        #                         total_tokens=200,
        #                     ),
        #                 )
        #             )
        #         )
        #     ]
        # )

        record: RequestRecord[Any] = RequestRecord()

        if isinstance(payload, OpenAIChatCompletionRequest):
            record.start_time_ns = time.perf_counter_ns()

            async for response in await self.client.chat.completions.create(
                model=self.client_config.model,
                messages=payload.messages,
                max_tokens=self.client_config.max_tokens,
                stream=True,
                stream_options=ChatCompletionStreamOptionsParam(
                    include_usage=True,
                ),
                **payload.kwargs,
            ):
                record.responses.append(
                    BackendClientResponse[str | None](
                        timestamp_ns=time.perf_counter_ns(),
                        response=response.choices[0].delta.content,
                    )
                )

        elif isinstance(payload, OpenAICompletionRequest):
            record.start_time_ns = time.perf_counter_ns()
            response = await self.client.completions.create(
                model=self.client_config.model,
                prompt=payload.prompt,
                max_tokens=self.client_config.max_tokens,
                **payload.kwargs,
            )
            record.responses.append(
                BackendClientResponse(
                    timestamp_ns=time.perf_counter_ns(),
                    response=response,
                )
            )

        elif isinstance(payload, OpenAIEmbeddingsRequest):
            record.start_time_ns = time.perf_counter_ns()
            response = await self.client.embeddings.create(
                model=self.client_config.model,
                input=payload.input,
                dimensions=payload.dimensions,
                user=payload.user,
                **payload.kwargs,
            )
            record.responses.append(
                BackendClientResponse(
                    timestamp_ns=time.perf_counter_ns(),
                    response=response,
                )
            )

        elif isinstance(payload, OpenAIChatResponsesRequest):
            record.start_time_ns = time.perf_counter_ns()
            async for response in await self.client.responses.create(
                input=payload.input,
                model=self.client_config.model,
                stream=True,
                **payload.kwargs,
            ):
                record.responses.append(
                    BackendClientResponse(
                        timestamp_ns=time.perf_counter_ns(),
                        response=response,
                    )
                )

        else:
            raise ValueError(f"Invalid payload: {payload}")

        return record

    async def parse_response(
        self, response: OpenAIBaseResponse
    ) -> BackendClientResponse[OpenAIBaseResponse]:
        # TODO: Implement
        raise NotImplementedError(
            "OpenAIBackendClient does not support parsing responses"
        )
