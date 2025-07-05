# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

from typing import Any

from openai.types.chat import ChatCompletionMessageParam
from pydantic import BaseModel, ConfigDict, Field

from aiperf.common.interfaces import InferenceClientProtocol
from aiperf.common.record_models import (
    GenericHTTPClientConfig,
)

################################################################################
# OpenAI Inference Client Models
################################################################################


class OpenAIClientConfig(GenericHTTPClientConfig):
    """Configuration specific to an OpenAI inference client."""

    project: str | None = Field(
        default=None,
        description="The project to use for the OpenAI inference client.",
    )
    webhook_secret: str | None = Field(
        default=None,
        description="The webhook secret to use for the OpenAI inference client.",
    )
    websocket_base_url: str | None = Field(
        default=None,
        description="The websocket base URL to use for the OpenAI inference client.",
    )
    default_query: dict[str, Any] | None = Field(
        default=None,
        description="The default query parameters to use for the OpenAI inference client.",
    )


################################################################################
# OpenAI Inference Client Requests
################################################################################


class OpenAIBaseRequest(BaseModel):
    """Base request specific to an OpenAI inference client."""

    model_config = ConfigDict(extra="allow")

    model: str


class OpenAIChatCompletionRequest(OpenAIBaseRequest):
    """Request specific to an OpenAI chat completion."""

    messages: list[ChatCompletionMessageParam] = Field(
        default_factory=list,
        description="The messages to use for the OpenAI inference client.",
    )
    max_tokens: int = Field(
        default=100,
        description="The maximum number of tokens to use for the OpenAI inference client.",
    )
    stream: bool = Field(
        default=True,
        description="Whether to stream the response.",
    )


class OpenAIResponsesRequest(OpenAIBaseRequest):
    """Request specific to OpenAI Responses API."""

    input: str
    max_output_tokens: int
    stream: bool = Field(
        default=True,
        description="Whether to stream the response.",
    )


class OpenAICompletionRequest(OpenAIBaseRequest):
    """Request specific to an OpenAI completion."""

    prompt: str
    max_tokens: int
    stream: bool = Field(
        default=True,
        description="Whether to stream the response.",
    )


class OpenAIEmbeddingsRequest(OpenAIBaseRequest):
    """Request specific to an OpenAI embeddings."""

    input: str
    dimensions: int
    encoding_format: str
    user: str


################################################################################
# OpenAI Inference Client Mixins / Protocols
################################################################################

OpenAIClientProtocol = InferenceClientProtocol[OpenAIClientConfig, OpenAIBaseRequest]
"""Type alias for a inference client protocol that supports OpenAI."""
