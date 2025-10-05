# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Pydantic models for integration test internal data."""

from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field


class AIPerfRunResult(BaseModel):
    """Result from running AIPerf subprocess."""

    returncode: int
    stdout: str
    stderr: str
    output_dir: Path


class ValidatedOutput(BaseModel):
    """Validated AIPerf output with all artifact paths."""

    json_results: dict  # Keep as dict - will be parsed by BenchmarkResult
    csv_content: str
    actual_dir: Path
    log_file: Path
    json_file: Path
    csv_file: Path


class MockServerInfo(BaseModel):
    """Mock server connection information."""

    model_config = {"arbitrary_types_allowed": True}

    host: str
    port: int
    url: str
    process: object = Field(exclude=True)  # Subprocess


# OpenAI Chat Message Structure Models
# These models match the OpenAI chat completion API format used in payloads


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

    messages: list[ChatMessage]
    model: str | None = None
    stream: bool | None = None
    max_completion_tokens: int | None = None

    # Allow extra fields for flexibility
    model_config = {"extra": "allow"}
