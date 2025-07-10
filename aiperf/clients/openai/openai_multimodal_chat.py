# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
Modern multimodal chat completions request converter for AIPerf.

This module provides a comprehensive implementation of multimodal request handling
using AIPerf's modern architecture, Pydantic models, and async patterns.
"""

import base64
import logging
from typing import Any, Literal

from pydantic import Field, field_validator

from aiperf.clients.client_interfaces import (
    RequestConverterFactory,
    RequestConverterProtocol,
)
from aiperf.clients.model_endpoint_info import ModelEndpointInfo
from aiperf.common.dataset_models import Turn
from aiperf.common.enums import CaseInsensitiveStrEnum, EndpointType
from aiperf.common.exceptions import AIPerfError
from aiperf.common.pydantic_utils import AIPerfBaseModel


class MessageRole(CaseInsensitiveStrEnum):
    """Message roles for chat completions."""

    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class MediaType(CaseInsensitiveStrEnum):
    """Supported media types for multimodal content."""

    TEXT = "text"
    IMAGE_URL = "image_url"
    INPUT_AUDIO = "input_audio"


class ImageDetail(CaseInsensitiveStrEnum):
    """Image detail level for vision models."""

    LOW = "low"
    HIGH = "high"
    AUTO = "auto"


class AudioFormat(CaseInsensitiveStrEnum):
    """Supported audio formats."""

    WAV = "wav"
    MP3 = "mp3"
    FLAC = "flac"
    M4A = "m4a"
    OGG = "ogg"


class TextContent(AIPerfBaseModel):
    """Text content for chat messages."""

    type: Literal[MediaType.TEXT] = MediaType.TEXT
    text: str = Field(..., min_length=1, description="The text content")


class ImageUrlContent(AIPerfBaseModel):
    """Image URL content for chat messages."""

    type: Literal[MediaType.IMAGE_URL] = MediaType.IMAGE_URL
    image_url: dict[str, Any] = Field(..., description="Image URL configuration")

    @field_validator("image_url")
    def validate_image_url(cls, v):
        """Validate image URL structure."""
        if "url" not in v:
            raise ValueError("image_url must contain 'url' field")
        return v

    @classmethod
    def from_url(
        cls, url: str, detail: ImageDetail = ImageDetail.AUTO
    ) -> "ImageUrlContent":
        """Create from URL with optional detail level."""
        return cls(image_url={"url": url, "detail": detail})


class InputAudioContent(AIPerfBaseModel):
    """Input audio content for chat messages."""

    type: Literal[MediaType.INPUT_AUDIO] = MediaType.INPUT_AUDIO
    input_audio: dict[str, Any] = Field(..., description="Audio input configuration")

    @field_validator("input_audio")
    def validate_input_audio(cls, v):
        """Validate audio input structure."""
        required_fields = {"data", "format"}
        if not all(field in v for field in required_fields):
            raise ValueError(f"input_audio must contain fields: {required_fields}")
        return v

    @classmethod
    def from_base64(cls, data: str, format: AudioFormat) -> "InputAudioContent":
        """Create from base64 data and format."""
        return cls(input_audio={"data": data, "format": format})


class ChatMessage(AIPerfBaseModel):
    """A single chat message with multimodal content."""

    role: MessageRole = Field(..., description="Role of the message sender")
    content: list[TextContent | ImageUrlContent | InputAudioContent] = Field(
        ..., min_length=1, description="Message content (text, images, audio)"
    )
    name: str | None = Field(None, description="Optional name of the message sender")

    @classmethod
    def from_turn(
        cls, turn: Turn, role: MessageRole = MessageRole.USER
    ) -> "ChatMessage":
        """Create a ChatMessage from a Turn object."""
        content: list[TextContent | ImageUrlContent | InputAudioContent] = []

        # Add text content
        for text_data in turn.text:
            for text_content in text_data.content:
                if text_content.strip():
                    content.append(TextContent(text=text_content))

        # Add image content
        for image_data in turn.image:
            for image_content in image_data.content:
                if image_content.strip():
                    content.append(ImageUrlContent.from_url(image_content))

        # Add audio content
        for audio_data in turn.audio:
            for audio_content in audio_data.content:
                if audio_content.strip():
                    # Parse format and base64 data
                    if "," in audio_content:
                        format_str, b64_data = audio_content.split(",", 1)
                        try:
                            audio_format = AudioFormat(format_str.lower())
                            content.append(
                                InputAudioContent.from_base64(b64_data, audio_format)
                            )
                        except ValueError:
                            raise AIPerfError(f"Unsupported audio format: {format_str}")
                    else:
                        raise AIPerfError(
                            f"Invalid audio content format: {audio_content}"
                        )

        if not content:
            raise AIPerfError("Turn must contain at least one content item")

        return cls(role=role, content=content, name=turn.role)


class MultimodalChatCompletionsRequest(AIPerfBaseModel):
    """Complete multimodal chat completions request."""

    model: str = Field(..., description="The model to use for completion")
    messages: list[ChatMessage] = Field(
        ..., min_length=1, description="List of chat messages"
    )
    stream: bool = Field(False, description="Whether to stream the response")
    max_tokens: int | None = Field(None, gt=0, description="Maximum tokens to generate")
    temperature: float | None = Field(
        None, ge=0, le=2, description="Sampling temperature"
    )
    top_p: float | None = Field(
        None, ge=0, le=1, description="Top-p sampling parameter"
    )
    frequency_penalty: float | None = Field(
        None, ge=-2, le=2, description="Frequency penalty"
    )
    presence_penalty: float | None = Field(
        None, ge=-2, le=2, description="Presence penalty"
    )
    stop: list[str] | str | None = Field(None, description="Stop sequences")

    @field_validator("messages")
    def validate_messages(cls, v):
        """Validate messages structure."""
        if not v:
            raise ValueError("At least one message is required")
        return v


@RequestConverterFactory.register(EndpointType.OPENAI_MULTIMODAL)
class OpenAIMultimodalChatCompletionsRequestConverter(
    RequestConverterProtocol[dict[str, Any]]
):
    """Modern multimodal chat completions request converter for OpenAI-compatible APIs.

    This converter handles text, image, and audio inputs seamlessly using AIPerf's
    modern architecture with Pydantic models, async patterns, and comprehensive
    error handling.
    """

    def __init__(self) -> None:
        super().__init__()
        self.logger = logging.getLogger(self.__class__.__name__)
        self.logger.info("Initialized %s", self.__class__.__name__)

    async def format_payload(
        self,
        model_endpoint: ModelEndpointInfo,
        turn: Turn,
    ) -> dict[str, Any]:
        """
        Format a multimodal payload for OpenAI-compatible chat completions.

        Args:
            model_endpoint: Information about the model endpoint
            turn: The conversation turn containing multimodal content

        Returns:
            Formatted payload dictionary for the API request

        Raises:
            AIPerfError: If the turn contains invalid or unsupported content
        """
        try:
            # Create chat message from turn
            chat_message = ChatMessage.from_turn(turn)

            extra = model_endpoint.endpoint.extra or {}

            # Build the request
            request = MultimodalChatCompletionsRequest(
                model=model_endpoint.primary_model_name,
                messages=[chat_message],
                stream=model_endpoint.endpoint.streaming,
                max_tokens=extra.pop("max_tokens", None),
                temperature=extra.pop("temperature", None),
                top_p=extra.pop("top_p", None),
                frequency_penalty=extra.pop("frequency_penalty", None),
                presence_penalty=extra.pop("presence_penalty", None),
                stop=extra.pop("stop", None),
            )

            # Add extra parameters from endpoint configuration
            payload = request.model_dump(exclude_none=True)
            if extra:
                payload.update(extra)

            self.logger.debug(
                "Formatted multimodal payload for model %s with %d content items",
                model_endpoint.primary_model_name,
                len(chat_message.content),
            )

            return payload

        except Exception as e:
            self.logger.error("Failed to format multimodal payload: %s", str(e))
            raise AIPerfError(f"Failed to format multimodal payload: {str(e)}") from e

    def _validate_image_content(self, content: str) -> None:
        """Validate image content format."""
        if not content.startswith(("http://", "https://", "data:image/")):
            raise AIPerfError(f"Invalid image content format: {content}")

    def _validate_audio_content(self, content: str) -> None:
        """Validate audio content format."""
        if "," not in content:
            raise AIPerfError(f"Invalid audio content format: {content}")

        format_str, b64_data = content.split(",", 1)

        # Validate format
        try:
            AudioFormat(format_str.lower())
        except ValueError:
            raise AIPerfError(f"Unsupported audio format: {format_str}")

        # Validate base64 data
        try:
            base64.b64decode(b64_data, validate=True)
        except Exception:
            raise AIPerfError("Invalid base64 audio data")

    def _get_content_statistics(self, turn: Turn) -> dict[str, int]:
        """Get statistics about turn content for logging."""
        return {
            "text_items": sum(len(text.content) for text in turn.text),
            "image_items": sum(len(image.content) for image in turn.image),
            "audio_items": sum(len(audio.content) for audio in turn.audio),
        }
