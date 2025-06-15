#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0

from typing import Any

from openai.types.chat.chat_completion import ChatCompletion
from openai.types.completion import Completion
from openai.types.embedding import Embedding
from openai.types.responses.response import Response
from pydantic import BaseModel, Field

from aiperf.common.interfaces import InferenceClientProtocol
from aiperf.common.record_models import (
    GenericHTTPClientConfig,
)

################################################################################
# OpenAI Inference Client Models
################################################################################


class OpenAIClientConfig(GenericHTTPClientConfig):
    """Configuration specific to an OpenAI inference client."""

    organization: str | None = Field(
        default=None,
        description="The organization to use for the OpenAI inference client.",
    )
    api_version: str | None = Field(
        default=None,
        description="The API version to use for the OpenAI inference client.",
    )
    endpoint: str = Field(
        default="v1/chat/completions",
        description="The endpoint to use for the OpenAI inference client.",
    )
    model: str = Field(
        default="deepseek-ai/DeepSeek-R1-Distill-Llama-8B",
        description="The model to use for the OpenAI inference client.",
    )
    max_tokens: int = Field(
        default=100,
        description="The maximum number of tokens to use for the OpenAI inference client.",
    )
    temperature: float = Field(
        default=0.7,
        description="The temperature to use for the OpenAI inference client.",
    )
    top_p: float = Field(
        default=1.0, description="The top P to use for the OpenAI inference client."
    )
    stop: list[str] | None = Field(
        default=None,
        description="The stop sequence to use for the OpenAI inference client.",
    )
    frequency_penalty: float = Field(
        default=0.0,
        description="The frequency penalty to use for the OpenAI inference client.",
    )
    presence_penalty: float = Field(
        default=0.0,
        description="The presence penalty to use for the OpenAI inference client.",
    )
    socket_options: list[tuple[int, int, int]] | None = Field(
        default=None,
        description="Socket options to apply for performance optimization. Format: [(family, option, value), ...]",
    )


################################################################################
# OpenAI Inference Client Requests
################################################################################


class OpenAIBaseRequest(BaseModel):
    """Base request specific to an OpenAI inference client."""

    model: str
    kwargs: dict[str, Any] | None = None


class OpenAIChatCompletionRequest(OpenAIBaseRequest):
    """Request specific to an OpenAI chat completion."""

    messages: list[Any] = Field(
        default_factory=list,
        description="The messages to use for the OpenAI inference client.",
    )
    max_tokens: int = Field(
        default=100,
        description="The maximum number of tokens to use for the OpenAI inference client.",
    )
    stream: bool = Field(
        default=True,  # TODO: default to True
        description="Whether to stream the response.",
    )


class OpenAIResponsesRequest(OpenAIBaseRequest):
    """Request specific to OpenAI Responses API."""

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
# OpenAI Inference Client Responses
################################################################################


class OpenAIBaseResponse(BaseModel):
    """Response specific to an OpenAI inference client."""


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
# OpenAI Inference Client Mixins / Protocols
################################################################################

OpenAIClientProtocol = InferenceClientProtocol[
    OpenAIClientConfig, OpenAIBaseRequest, OpenAIBaseResponse
]
"""Type alias for a inference client protocol that supports OpenAI."""
