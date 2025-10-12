# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Pydantic models for OpenAI-compatible API using official openai package types."""

from openai.types import CompletionUsage
from openai.types.chat import (
    ChatCompletion,
    ChatCompletionChunk,
    ChatCompletionMessage,
)
from openai.types.completion import Completion
from openai.types.create_embedding_response import CreateEmbeddingResponse
from pydantic import BaseModel, Field

# Re-export OpenAI types for convenience
__all__ = [
    "ChatCompletion",
    "ChatCompletionChunk",
    "ChatCompletionMessage",
    "Completion",
    "CompletionUsage",
    "CreateEmbeddingResponse",
    "ConfigureMessage",
    "RankingsRequest",
    "RankingsResponse",
]


class ConfigureMessage(BaseModel):
    """Configuration for the server."""

    ttft: int | None = Field(
        default=None, description="Time to first token in milliseconds"
    )
    itl: int | None = Field(
        default=None, description="Inter-token latency in milliseconds"
    )


# Rankings models (NVIDIA-specific, not in standard OpenAI)
class RankingsQuery(BaseModel):
    """Query for rankings request."""

    text: str


class RankingsPassage(BaseModel):
    """Passage for rankings request."""

    text: str


class RankingsRequest(BaseModel):
    """Request model for rankings/reranking."""

    model: str
    query: RankingsQuery
    passages: list[RankingsPassage]


class RankingResult(BaseModel):
    """A single ranking result."""

    index: int
    relevance_score: float


class RankingsResponse(BaseModel):
    """Response model for rankings."""

    id: str
    object: str = "rankings"
    model: str
    rankings: list[RankingResult]
    usage: CompletionUsage | None = None
