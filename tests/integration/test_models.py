# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Pydantic models for integration test internal data."""

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, ModelConfig


class AIPerfRunResult(BaseModel):
    """Result from running AIPerf subprocess."""

    returncode: int
    stdout: str
    stderr: str
    output_dir: Path


class ValidatedOutput(BaseModel):
    """Validated AIPerf output with all artifact paths."""

    json_results: dict
    csv_content: str
    artifact_dir: Path
    csv_file: Path
    json_file: Path
    log_file: Path


class FakeAIServer(BaseModel):
    """FakeAI server connection information."""

    model_config = ModelConfig(arbitrary_types_allowed=True)

    host: str
    port: int
    url: str
    process: object = Field(exclude=True)


class ImageUrl(BaseModel):
    """Image URL content for OpenAI chat messages."""

    url: str


class ImageContent(BaseModel):
    """Image content item in a chat message."""

    type: Literal["image_url"]
    image_url: ImageUrl


class InputAudio(BaseModel):
    """Input audio data for OpenAI chat messages."""

    data: str
    format: str


class AudioContent(BaseModel):
    """Audio content item in a chat message."""

    type: Literal["input_audio"]
    input_audio: InputAudio


class TextContent(BaseModel):
    """Text content item in a chat message."""

    type: Literal["text"]
    text: str


# Union of all content types
MessageContentItem = ImageContent | AudioContent | TextContent


class ChatMessage(BaseModel):
    """A single message in an OpenAI chat completion request.

    Can contain either:
    - Simple string content (for text-only messages)
    - List of content items (for multimodal messages with text/images/audio)
    """

    role: str
    content: str | list[MessageContentItem]
    name: str | None = None


class ChatCompletionPayload(BaseModel):
    """Complete OpenAI chat completion request payload."""

    model_config = ModelConfig(extra="allow")

    messages: list[ChatMessage]
    model: str | None = None
    stream: bool | None = None
    max_completion_tokens: int | None = None
