# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Pydantic models for OpenAI-compatible chat completions API."""

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field


class ConfigureMessage(BaseModel):
    """Configuration for the server."""

    ttft: int | None = Field(
        default=None, description="Time to first token in milliseconds"
    )
    itl: int | None = Field(
        default=None, description="Inter-token latency in milliseconds"
    )
    tokenizer_models: list[str] | None = Field(
        default=None, description="List of tokenizer models to load"
    )


class Role(str, Enum):
    """Message roles in chat completion."""

    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"


class InputAudio(BaseModel):
    """An input audio part of a chat message."""

    format: str
    data: str


class File(BaseModel):
    """A file part of a chat message."""

    file_data: str
    file_id: str
    filename: str


class TextPart(BaseModel):
    """A text part of a chat message."""

    type: Literal["text"] = "text"
    text: str


class ImagePart(BaseModel):
    """An image part of a chat message."""

    type: Literal["image_url"] = "image_url"
    image_url: str


class AudioPart(BaseModel):
    """An audio part of a chat message."""

    type: Literal["input_audio"] = "input_audio"
    input_audio: InputAudio


class FilePart(BaseModel):
    """A file part of a chat message."""

    type: Literal["file"] = "file"
    file: File


class ChatMessage(BaseModel):
    """A single chat message."""

    role: Role
    content: str | list[TextPart | ImagePart | AudioPart | FilePart]


class ChatCompletionRequest(BaseModel):
    """Request model for chat completions."""

    model: str
    messages: list[ChatMessage]
    max_tokens: int | None = Field(default=None, ge=1)
    temperature: float | None = Field(default=1.0, ge=0, le=2)
    top_p: float | None = Field(default=1.0, ge=0, le=1)
    stream: bool | None = Field(default=False)
    stop: str | list[str] | None = None
    presence_penalty: float | None = Field(default=0, ge=-2, le=2)
    frequency_penalty: float | None = Field(default=0, ge=-2, le=2)


class ChatCompletionChoice(BaseModel):
    """A single choice in chat completion response."""

    index: int
    message: ChatMessage
    finish_reason: str | None = None


class Usage(BaseModel):
    """Token usage information."""

    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


class ChatCompletionResponse(BaseModel):
    """Response model for chat completions."""

    id: str
    object: str = "chat.completion"
    created: int
    model: str
    choices: list[ChatCompletionChoice]
    usage: Usage


class ChatCompletionStreamChoice(BaseModel):
    """A single choice in streaming chat completion response."""

    index: int
    delta: dict[str, Any]
    finish_reason: str | None = None


class ChatCompletionStreamResponse(BaseModel):
    """Streaming response model for chat completions."""

    id: str
    object: str = "chat.completion.chunk"
    created: int
    model: str
    choices: list[ChatCompletionStreamChoice]
