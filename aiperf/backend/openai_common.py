#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0

import os
from typing import Any

from openai import AsyncAzureOpenAI, AsyncOpenAI
from openai.types.chat.chat_completion import ChatCompletion
from openai.types.completion import Completion
from openai.types.embedding import Embedding
from openai.types.responses.response import Response
from pydantic import BaseModel, Field

from aiperf.backend.client_mixins import BackendClientConfigMixin
from aiperf.common.enums import (
    CaseInsensitiveStrEnum,
)
from aiperf.common.interfaces import BackendClientProtocol
from aiperf.common.record_models import (
    GenericHTTPBackendClientConfig,
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
        default="deepseek-ai/DeepSeek-R1-Distill-Llama-8B",
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
