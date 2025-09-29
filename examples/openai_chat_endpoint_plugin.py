# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Fully featured OpenAI Chat Completions endpoint plugin for AIPerf.

This plugin provides a complete implementation of the OpenAI Chat Completions API
with support for all features including streaming, multi-modal content (text, images, audio),
and comprehensive response parsing. It's based on the existing EndpointType.CHAT implementation
but adapted to the new plugin architecture.
"""

from typing import Any

import orjson

from aiperf.common.enums import OpenAIObjectType
from aiperf.common.factories import OpenAIObjectParserFactory
from aiperf.common.models import (
    ParsedResponse,
    ReasoningResponseData,
    RequestRecord,
    SSEMessage,
    TextResponse,
    Turn,
)
from aiperf.common.plugins import DynamicEndpoint, EndpointPluginInfo
from aiperf.common.plugins.plugin_specs import (
    HttpMethod,
    MultiTransportConfig,
    TransportConfig,
    TransportType,
)
from aiperf.common.utils import load_json_str

# Constants from the original implementation
DEFAULT_ROLE = "user"


class OpenAIChatEndpoint(DynamicEndpoint):
    """OpenAI Chat Completions endpoint plugin.

    This plugin provides full compatibility with the OpenAI Chat Completions API,
    including support for:
    - Text, image, and audio content
    - Streaming and non-streaming responses
    - All OpenAI chat completion parameters
    - Comprehensive response parsing with reasoning support
    - Multiple transport options (HTTP primary, with extensibility)
    """

    def get_endpoint_info(self) -> EndpointPluginInfo:
        """Return comprehensive endpoint information for OpenAI Chat Completions."""
        return EndpointPluginInfo(
            endpoint_tag="openai-chat",
            service_kind="openai",
            transport_config=MultiTransportConfig(
                supported_transports=[
                    # Primary HTTP transport for OpenAI API
                    TransportConfig(
                        transport_type=TransportType.HTTP,
                        http_method=HttpMethod.POST,
                        content_type="application/json",
                        accept_type="application/json",
                        streaming_accept_type="text/event-stream",
                    ),
                    # Future: gRPC support for high-performance scenarios
                    # TransportConfig(
                    #     transport_type=TransportType.GRPC,
                    #     content_type="application/grpc+proto",
                    #     grpc_service_name="ChatCompletionService",
                    # ),
                ],
                default_transport=TransportType.HTTP,
            ),
            supports_streaming=True,
            produces_tokens=True,
            supports_audio=True,
            supports_images=True,
            endpoint_path="/v1/chat/completions",
            metrics_title="OpenAI Chat Metrics",
            description="OpenAI Chat Completions API with full multi-modal support",
            version="1.0.0",
        )

    async def format_payload(self, turn: Turn) -> dict[str, Any]:
        """Format a conversation turn into an OpenAI Chat Completions payload.

        This method replicates the logic from OpenAIChatCompletionRequestConverter
        with full support for text, images, audio, and all OpenAI parameters.

        Args:
            turn: The conversation turn to format.

        Returns:
            dict[str, Any]: OpenAI Chat Completions API payload.
        """
        messages = self._create_messages(turn)

        payload = {
            "messages": messages,
            "model": turn.model or self.model_endpoint.primary_model_name,
            "stream": self.model_endpoint.endpoint.streaming,
        }

        # Add max_tokens parameter with OpenAI's specific naming
        if turn.max_tokens is not None:
            payload["max_completion_tokens"] = turn.max_tokens

        # Add extra parameters from endpoint configuration
        if self.model_endpoint.endpoint.extra:
            payload.update(dict(self.model_endpoint.endpoint.extra))

        return payload

    def _create_messages(self, turn: Turn) -> list[dict[str, Any]]:
        """Create OpenAI messages format from a Turn.

        This method handles the complexity of OpenAI's message format, including:
        - Simple text messages
        - Multi-modal content (text, images, audio)
        - Special handling for single-content messages (Dynamo API compatibility)

        Args:
            turn: The conversation turn to convert.

        Returns:
            list[dict[str, Any]]: OpenAI messages format.
        """
        message = {
            "role": turn.role or DEFAULT_ROLE,
        }

        # Handle simple single-text case (Dynamo API compatibility)
        if (
            len(turn.texts) == 1
            and len(turn.texts[0].contents) == 1
            and len(turn.images) == 0
            and len(turn.audios) == 0
        ):
            message["name"] = turn.texts[0].name
            message["content"] = (
                turn.texts[0].contents[0] if turn.texts[0].contents else ""
            )
            return [message]

        # Handle multi-modal content
        message_content = []

        # Add text content
        for text in turn.texts:
            for content in text.contents:
                if not content:
                    continue
                message_content.append({"type": "text", "text": content})

        # Add image content
        for image in turn.images:
            for content in image.contents:
                if not content:
                    continue
                message_content.append(
                    {"type": "image_url", "image_url": {"url": content}}
                )

        # Add audio content
        for audio in turn.audios:
            for content in audio.contents:
                if not content:
                    continue
                if "," not in content:
                    raise ValueError(
                        "Audio content must be in the format 'format,b64_audio'."
                    )
                format_type, b64_audio = content.split(",", 1)
                message_content.append(
                    {
                        "type": "input_audio",
                        "input_audio": {
                            "data": b64_audio,
                            "format": format_type,
                        },
                    }
                )

        message["content"] = message_content
        return [message]

    async def extract_response_data(
        self, record: RequestRecord
    ) -> list[ParsedResponse]:
        """Extract and parse OpenAI response data from a request record.

        This method replicates the logic from OpenAIResponseExtractor with full
        support for both streaming and non-streaming responses, including all
        OpenAI object types and response formats.

        Args:
            record: The request record containing raw responses.

        Returns:
            list[ParsedResponse]: List of parsed OpenAI responses.
        """
        results = []

        for response in record.responses:
            parsed_response = self._parse_response(response)
            if parsed_response is not None:
                results.append(parsed_response)

        return results

    def _parse_response(self, response) -> ParsedResponse | None:
        """Parse a single response into a ParsedResponse object.

        Args:
            response: The raw response from the transport layer.

        Returns:
            ParsedResponse | None: Parsed response or None if parsing failed.
        """
        parsed_data = None

        # Handle different response types using pattern matching
        match response:
            case TextResponse():
                parsed_data = self._parse_raw_text(response.text)
            case SSEMessage():
                parsed_data = self._parse_raw_text(response.extract_data_content())
            case _:
                self.warning(f"Unsupported response type: {type(response)}")

        if not parsed_data:
            return None

        return ParsedResponse(
            perf_ns=response.perf_ns,
            data=parsed_data,
        )

    def _parse_raw_text(self, raw_text: str):
        """Parse raw response text using OpenAI object parsers.

        This method handles the full complexity of OpenAI response parsing,
        including object type detection, streaming markers, and error handling.

        Args:
            raw_text: Raw response text from the API.

        Returns:
            BaseResponseData | None: Parsed response data or None if parsing failed.
        """
        # Handle empty responses and streaming end markers
        if raw_text in ("", None, "[DONE]"):
            return None

        try:
            json_data = load_json_str(raw_text)
        except orjson.JSONDecodeError as e:
            self.warning(f"Invalid JSON in OpenAI response: {raw_text} - {e!r}")
            return None

        # Determine OpenAI object type
        if "object" in json_data:
            try:
                object_type = OpenAIObjectType(json_data["object"])
            except ValueError:
                self.warning(f"Unsupported OpenAI object type: {json_data['object']}")
                return None
        else:
            # Infer object type for responses without explicit object field
            object_type = self._infer_object_type(json_data)
            if object_type is None:
                return None

        # Parse using the appropriate OpenAI object parser
        try:
            parser = OpenAIObjectParserFactory.get_or_create_instance(object_type)
            return parser.parse(json_data)
        except Exception as e:
            self.warning(f"Failed to parse OpenAI object {object_type}: {e!r}")
            return None

    def _infer_object_type(self, json_obj: dict[str, Any]) -> OpenAIObjectType | None:
        """Infer OpenAI object type from JSON structure.

        Args:
            json_obj: Parsed JSON response object.

        Returns:
            OpenAIObjectType | None: Inferred object type or None if unknown.
        """
        # Handle chat completion responses without explicit object type
        if "choices" in json_obj:
            choices = json_obj["choices"]
            if choices and isinstance(choices, list):
                choice = choices[0]
                if "delta" in choice:
                    return OpenAIObjectType.CHAT_COMPLETION_CHUNK
                elif "message" in choice:
                    return OpenAIObjectType.CHAT_COMPLETION
                elif "text" in choice:
                    return OpenAIObjectType.TEXT_COMPLETION

        # Handle embeddings responses
        if "data" in json_obj and "embedding" in str(json_obj.get("data", [])):
            return OpenAIObjectType.EMBEDDING

        # Handle rankings responses
        if "rankings" in json_obj:
            return OpenAIObjectType.RANKINGS

        # Handle list responses
        if json_obj.get("object") == "list":
            return OpenAIObjectType.LIST

        self.warning(f"Could not infer OpenAI object type from response: {json_obj}")
        return None

    def get_custom_headers(self) -> dict[str, str]:
        """Get OpenAI-specific headers.

        Returns:
            dict[str, str]: Custom headers for OpenAI API requests.
        """
        headers = {
            "OpenAI-Beta": "assistants=v2",  # Enable beta features
            "User-Agent": "aiperf-openai-plugin/1.0",
        }

        # Add organization header if available in extra config
        if self.model_endpoint.endpoint.extra:
            extra = dict(self.model_endpoint.endpoint.extra)
            if "organization" in extra:
                headers["OpenAI-Organization"] = extra["organization"]

        return headers

    def get_url_params(self) -> dict[str, str]:
        """Get URL parameters for OpenAI API requests.

        Returns:
            dict[str, str]: URL query parameters.
        """
        return {
            "version": "2024-12-17",  # OpenAI API version
        }


class OpenAIChatStreamingEndpoint(OpenAIChatEndpoint):
    """Specialized OpenAI Chat endpoint optimized for streaming.

    This variant is specifically configured for streaming use cases
    with optimized settings and parsing for real-time applications.
    """

    def get_endpoint_info(self) -> EndpointPluginInfo:
        """Return endpoint info optimized for streaming."""
        info = super().get_endpoint_info()
        info.endpoint_tag = "openai-chat-streaming"
        info.description = (
            "OpenAI Chat Completions API optimized for streaming responses"
        )
        info.version = "1.0.0-streaming"
        return info

    async def format_payload(self, turn: Turn) -> dict[str, Any]:
        """Format payload with streaming-optimized settings."""
        payload = await super().format_payload(turn)

        # Force streaming enabled
        payload["stream"] = True

        # Add streaming-specific parameters
        payload.update(
            {
                "stream_options": {"include_usage": True},
                "temperature": payload.get("temperature", 0.7),
                "max_completion_tokens": payload.get("max_completion_tokens", 2048),
            }
        )

        return payload

    def get_custom_headers(self) -> dict[str, str]:
        """Get headers optimized for streaming."""
        headers = super().get_custom_headers()
        headers.update(
            {
                "Accept": "text/event-stream",
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
            }
        )
        return headers


class OpenAIChatReasoningEndpoint(OpenAIChatEndpoint):
    """OpenAI Chat endpoint with enhanced reasoning support.

    This variant includes special handling for OpenAI's reasoning models
    (like o1-preview) with support for reasoning tokens and enhanced parsing.
    """

    def get_endpoint_info(self) -> EndpointPluginInfo:
        """Return endpoint info with reasoning capabilities."""
        info = super().get_endpoint_info()
        info.endpoint_tag = "openai-chat-reasoning"
        info.description = (
            "OpenAI Chat Completions API with enhanced reasoning model support"
        )
        info.version = "1.0.0-reasoning"
        return info

    async def format_payload(self, turn: Turn) -> dict[str, Any]:
        """Format payload optimized for reasoning models."""
        payload = await super().format_payload(turn)

        # Add reasoning-specific parameters
        if "o1" in payload.get("model", "").lower():
            # o1 models don't support some parameters
            payload.pop("temperature", None)
            payload.pop("top_p", None)
            payload.pop("frequency_penalty", None)
            payload.pop("presence_penalty", None)

            # Set reasoning-specific parameters
            payload["reasoning_effort"] = payload.get("reasoning_effort", "medium")

        return payload

    def _parse_raw_text(self, raw_text: str):
        """Enhanced parsing with reasoning support."""
        parsed_data = super()._parse_raw_text(raw_text)

        # If we got reasoning data, ensure it's properly typed
        if isinstance(parsed_data, dict) and ("reasoning" in str(parsed_data).lower()):
            try:
                json_data = load_json_str(raw_text)
                choices = json_data.get("choices", [])
                if choices:
                    choice = choices[0]
                    message = choice.get("message", {})

                    return ReasoningResponseData(
                        content=message.get("content"),
                        reasoning=message.get("reasoning", message.get("refusal")),
                    )
            except Exception:
                pass

        return parsed_data
