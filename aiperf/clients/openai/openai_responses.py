# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""OpenAI Responses API converter for o1 reasoning models.

This module provides a modern, comprehensive converter for OpenAI's o1 reasoning models
that use the responses API format with 'input' instead of 'messages' and 'max_output_tokens'
instead of 'max_tokens'.
"""

import logging
from typing import Any, Union

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


class ReasoningEffort(CaseInsensitiveStrEnum):
    """Reasoning effort levels for o1 models."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class ResponsesInputType(CaseInsensitiveStrEnum):
    """Input content types for responses API."""

    TEXT = "text"
    IMAGE_URL = "image_url"
    INPUT_AUDIO = "input_audio"


class ResponsesContentBase(AIPerfBaseModel):
    """Base class for responses input content."""

    type: ResponsesInputType = Field(..., description="Content type")


class ResponsesTextContent(ResponsesContentBase):
    """Text content for responses input."""

    type: ResponsesInputType = Field(
        ResponsesInputType.TEXT, description="Content type"
    )
    text: str = Field(..., description="Text content")


class ResponsesImageUrlContent(ResponsesContentBase):
    """Image URL content for responses input."""

    type: ResponsesInputType = Field(
        ResponsesInputType.IMAGE_URL, description="Content type"
    )
    image_url: dict[str, Any] = Field(..., description="Image URL configuration")

    @field_validator("image_url")
    def validate_image_url(cls, v):
        """Validate image URL structure."""
        if not isinstance(v, dict):
            raise ValueError("image_url must be a dictionary")

        if "url" not in v:
            raise ValueError("image_url must contain 'url' field")

        return v


class ResponsesInputAudioContent(ResponsesContentBase):
    """Input audio content for responses input."""

    type: ResponsesInputType = Field(
        ResponsesInputType.INPUT_AUDIO, description="Content type"
    )
    input_audio: dict[str, Any] = Field(..., description="Audio input configuration")

    @field_validator("input_audio")
    def validate_input_audio(cls, v):
        """Validate audio input structure."""
        if not isinstance(v, dict):
            raise ValueError("input_audio must be a dictionary")

        if "data" not in v:
            raise ValueError("input_audio must contain 'data' field")

        if "format" not in v:
            raise ValueError("input_audio must contain 'format' field")

        return v


# Union type for all content types
ResponsesContent = Union[
    ResponsesTextContent, ResponsesImageUrlContent, ResponsesInputAudioContent
]


class ResponsesRequest(AIPerfBaseModel):
    """OpenAI Responses API request model for o1 reasoning models."""

    model: str = Field(..., description="Model name")
    input: str | list[ResponsesContent] = Field(
        ..., description="Input content - can be a string or array of content objects"
    )
    max_output_tokens: int | None = Field(
        None, description="Maximum number of tokens to generate"
    )
    reasoning_effort: ReasoningEffort | None = Field(
        None, description="Effort level for reasoning (o1 models only)"
    )
    stream: bool = Field(False, description="Whether to stream responses")
    store: bool | None = Field(None, description="Whether to store the completion")
    metadata: dict[str, Any] | None = Field(None, description="Request metadata")

    @field_validator("input")
    def validate_input(cls, v):
        """Validate input structure."""
        if isinstance(v, str):
            if not v.strip():
                raise ValueError("Input string cannot be empty")
            return v

        if isinstance(v, list):
            if not v:
                raise ValueError("Input array cannot be empty")
            return v

        raise ValueError("Input must be a string or array of content objects")


@RequestConverterFactory.register(EndpointType.OPENAI_RESPONSES)
class OpenAIResponsesRequestConverter(RequestConverterProtocol[dict[str, Any]]):
    """Request converter for OpenAI Responses API (o1 reasoning models)."""

    def __init__(self) -> None:
        super().__init__()
        self.logger = logging.getLogger(self.__class__.__name__)

    async def format_payload(
        self,
        model_endpoint: ModelEndpointInfo,
        turn: Turn,
    ) -> dict[str, Any]:
        """Format payload for a responses request.

        Args:
            model_endpoint: Model endpoint information
            turn: Turn data containing text, images, and audio

        Returns:
            Formatted payload dict for OpenAI Responses API

        Raises:
            AIPerfError: If payload formatting fails
        """
        try:
            # Convert turn data to responses input format
            input_content = self._convert_turn_to_input(turn)

            # Create base request
            request = ResponsesRequest(
                model=model_endpoint.primary_model_name,
                input=input_content,
                max_output_tokens=model_endpoint.endpoint.max_tokens,
                stream=model_endpoint.endpoint.streaming,
            )

            # Add extra parameters from endpoint configuration
            if model_endpoint.endpoint.extra:
                extra_params = {}

                # Handle reasoning effort for o1 models
                if "reasoning_effort" in model_endpoint.endpoint.extra:
                    effort = model_endpoint.endpoint.extra["reasoning_effort"]
                    if effort in [e.value for e in ReasoningEffort]:
                        extra_params["reasoning_effort"] = effort

                # Handle store parameter
                if "store" in model_endpoint.endpoint.extra:
                    extra_params["store"] = model_endpoint.endpoint.extra["store"]

                # Handle metadata
                if "metadata" in model_endpoint.endpoint.extra:
                    extra_params["metadata"] = model_endpoint.endpoint.extra["metadata"]

                # Update request with extra parameters
                if extra_params:
                    request = ResponsesRequest(**request.model_dump(), **extra_params)

            # Convert to dictionary for API request
            payload = request.model_dump(exclude_none=True)

            self.logger.debug("Formatted responses payload: %s", payload)
            return payload

        except Exception as e:
            error_msg = f"Failed to format responses payload: {str(e)}"
            self.logger.error(error_msg)
            raise AIPerfError(error_msg) from e

    def _convert_turn_to_input(self, turn: Turn) -> str | list[ResponsesContent]:
        """Convert Turn data to responses input format.

        Args:
            turn: Turn data containing text, images, and audio

        Returns:
            Input content in responses format

        Raises:
            ValueError: If turn data is invalid
        """
        if not turn.text and not turn.images and not turn.audio:
            raise ValueError("Turn must contain at least one type of content")

        content_items = []

        # Add text content
        if turn.text:
            for text_item in turn.text:
                if text_item.content:
                    for text_content in text_item.content:
                        if text_content.strip():
                            content_items.append(
                                ResponsesTextContent(text=text_content)
                            )

        # Add image content
        if turn.images:
            for image_item in turn.images:
                if image_item.url:
                    content_items.append(
                        ResponsesImageUrlContent(
                            image_url={
                                "url": image_item.url,
                                "detail": getattr(image_item, "detail", "auto"),
                            }
                        )
                    )
                elif image_item.base64:
                    content_items.append(
                        ResponsesImageUrlContent(
                            image_url={
                                "url": f"data:image/jpeg;base64,{image_item.base64}",
                                "detail": getattr(image_item, "detail", "auto"),
                            }
                        )
                    )

        # Add audio content
        if turn.audio:
            for audio_item in turn.audio:
                if audio_item.base64:
                    content_items.append(
                        ResponsesInputAudioContent(
                            input_audio={
                                "data": audio_item.base64,
                                "format": audio_item.format or "wav",
                            }
                        )
                    )

        # Return single string if only one text item, otherwise return array
        if len(content_items) == 1 and isinstance(
            content_items[0], ResponsesTextContent
        ):
            return content_items[0].text

        return content_items

    def _validate_o1_model_compatibility(self, model_name: str) -> None:
        """Validate that the model is compatible with responses API.

        Args:
            model_name: Name of the model

        Raises:
            ValueError: If model is not compatible with responses API
        """
        o1_models = ["o1", "o1-preview", "o1-mini", "o3-mini"]

        if not any(o1_model in model_name.lower() for o1_model in o1_models):
            self.logger.warning(
                "Model '%s' may not be optimized for responses API. "
                "Consider using o1, o1-preview, o1-mini, or o3-mini models.",
                model_name,
            )
