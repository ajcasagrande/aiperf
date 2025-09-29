# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Example multi-transport endpoint plugin for AIPerf.

This demonstrates how to create an endpoint plugin that supports multiple
transport types (HTTP, gRPC, WebSocket) with different configurations for each.
"""

from typing import Any

from aiperf.common.models import ParsedResponse, RequestRecord, TextResponse, Turn
from aiperf.common.plugins import DynamicEndpoint, EndpointPluginInfo
from aiperf.common.plugins.plugin_specs import (
    HttpMethod,
    MultiTransportConfig,
    TransportConfig,
    TransportType,
)
from aiperf.common.utils import load_json_str


class MultiTransportChatEndpoint(DynamicEndpoint):
    """Example endpoint that supports multiple transport types.

    This endpoint can communicate via HTTP (REST), gRPC, or WebSocket,
    allowing users to choose their preferred transport method.
    """

    def get_endpoint_info(self) -> EndpointPluginInfo:
        """Return endpoint information with multiple transport options."""
        return EndpointPluginInfo(
            endpoint_tag="multi-transport-chat",
            service_kind="flexible",
            transport_config=MultiTransportConfig(
                supported_transports=[
                    # HTTP/REST - Most common, good for simple request/response
                    TransportConfig(
                        transport_type=TransportType.HTTP,
                        http_method=HttpMethod.POST,
                        content_type="application/json",
                        accept_type="application/json",
                        streaming_accept_type="text/event-stream",
                    ),
                    # gRPC - High performance, good for internal services
                    TransportConfig(
                        transport_type=TransportType.GRPC,
                        content_type="application/grpc",
                        accept_type="application/grpc",
                        grpc_service_name="ChatService",
                    ),
                    # WebSocket - Real-time, good for interactive applications
                    TransportConfig(
                        transport_type=TransportType.WEBSOCKET,
                        content_type="application/json",
                        accept_type="application/json",
                        websocket_subprotocol="chat-v1",
                    ),
                ],
                default_transport=TransportType.HTTP,  # Default to HTTP
            ),
            supports_streaming=True,
            produces_tokens=True,
            supports_audio=True,
            supports_images=True,
            endpoint_path="/v1/chat/completions",
            metrics_title="Multi-Transport Chat Metrics",
            description="Flexible chat endpoint supporting HTTP, gRPC, and WebSocket",
            version="1.0.0",
        )

    async def format_payload(self, turn: Turn) -> dict[str, Any]:
        """Format payload that works across all transport types.

        The payload format is transport-agnostic. Each transport will
        serialize it appropriately (JSON for HTTP/WebSocket, protobuf for gRPC).
        """
        # Build messages with multi-modal support
        messages = []

        # Handle text content
        for text in turn.texts:
            for content in text.contents:
                if content:
                    messages.append(
                        {
                            "role": turn.role or "user",
                            "content": content,
                            "type": "text",
                        }
                    )

        # Handle image content
        if turn.images:
            for image in turn.images:
                for content in image.contents:
                    if content:
                        messages.append(
                            {
                                "role": turn.role or "user",
                                "content": content,
                                "type": "image_url",
                            }
                        )

        # Handle audio content
        if turn.audios:
            for audio in turn.audios:
                for content in audio.contents:
                    if content:
                        messages.append(
                            {
                                "role": turn.role or "user",
                                "content": content,
                                "type": "audio",
                            }
                        )

        # Build the main payload
        payload = {
            "model": turn.model or self.model_endpoint.primary_model_name,
            "messages": messages,
            "stream": self.model_endpoint.endpoint.streaming,
            "max_tokens": turn.max_tokens,
        }

        # Add extra parameters
        if self.model_endpoint.endpoint.extra:
            payload.update(dict(self.model_endpoint.endpoint.extra))

        return payload

    async def extract_response_data(
        self, record: RequestRecord
    ) -> list[ParsedResponse]:
        """Extract response data that works across transport types."""
        results = []

        for response in record.responses:
            if isinstance(response, TextResponse):
                parsed_data = self._parse_response(response.text)
                if parsed_data:
                    results.append(
                        ParsedResponse(
                            perf_ns=response.perf_ns,
                            data=parsed_data,
                        )
                    )

        return results

    def get_custom_headers(self) -> dict[str, str]:
        """Get custom headers that apply to all transport types."""
        return {
            "X-Multi-Transport-Version": "1.0",
            "X-Supported-Transports": "http,grpc,websocket",
        }

    def get_url_path(self) -> str | None:
        """Custom URL path for HTTP transport."""
        # This only affects HTTP transport
        return "/api/v2/chat/multi-transport"

    def get_url_params(self) -> dict[str, str]:
        """Query parameters for HTTP transport."""
        return {
            "transport": "multi",
            "version": "v2",
        }

    def _parse_response(self, response_text: str) -> Any:
        """Parse response that could come from any transport type."""
        if not response_text:
            return None

        try:
            # Try JSON parsing (HTTP/WebSocket responses)
            json_data = load_json_str(response_text)

            # Handle standard chat completion format
            if "choices" in json_data and json_data["choices"]:
                choice = json_data["choices"][0]
                if "message" in choice and "content" in choice["message"]:
                    from aiperf.common.models import TextResponseData

                    return TextResponseData(text=choice["message"]["content"])

            # Handle streaming format
            if "delta" in json_data and "content" in json_data["delta"]:
                from aiperf.common.models import TextResponseData

                return TextResponseData(text=json_data["delta"]["content"])

            # Handle transport-specific formats
            if "transport_type" in json_data:
                transport_type = json_data["transport_type"]
                content = json_data.get("content", "")
                from aiperf.common.models import TextResponseData

                return TextResponseData(text=f"[{transport_type}] {content}")

            # Fallback
            from aiperf.common.models import TextResponseData

            return TextResponseData(text=response_text)

        except Exception:
            # Handle non-JSON responses (e.g., from gRPC as text)
            from aiperf.common.models import TextResponseData

            return TextResponseData(text=response_text)


class FlexibleAPIEndpoint(DynamicEndpoint):
    """Another example showing different transport configurations."""

    def get_endpoint_info(self) -> EndpointPluginInfo:
        """Endpoint with different transport preferences and configurations."""
        return EndpointPluginInfo(
            endpoint_tag="flexible-api",
            service_kind="adaptive",
            transport_config=MultiTransportConfig(
                supported_transports=[
                    # Prefer gRPC for performance
                    TransportConfig(
                        transport_type=TransportType.GRPC,
                        content_type="application/grpc+proto",
                        accept_type="application/grpc+proto",
                        grpc_service_name="FlexibleService",
                    ),
                    # HTTP as fallback
                    TransportConfig(
                        transport_type=TransportType.HTTP,
                        http_method=HttpMethod.POST,
                        content_type="application/json",
                        accept_type="application/json",
                    ),
                ],
                default_transport=TransportType.GRPC,  # Prefer gRPC
            ),
            supports_streaming=False,
            produces_tokens=True,
            supports_audio=False,
            supports_images=False,
            endpoint_path="/v1/flexible",
            metrics_title="Flexible API Metrics",
            description="API that prefers gRPC but falls back to HTTP",
            version="1.0.0",
        )

    async def format_payload(self, turn: Turn) -> dict[str, Any]:
        """Format payload optimized for gRPC but compatible with HTTP."""
        # Simple payload format
        text_content = []
        for text in turn.texts:
            text_content.extend(text.contents)

        return {
            "input": " ".join(filter(None, text_content)),
            "model": turn.model or self.model_endpoint.primary_model_name,
            "parameters": {
                "max_tokens": turn.max_tokens or 100,
                "temperature": 0.7,
            },
        }

    async def extract_response_data(
        self, record: RequestRecord
    ) -> list[ParsedResponse]:
        """Extract response data from either gRPC or HTTP."""
        results = []

        for response in record.responses:
            if isinstance(response, TextResponse):
                # Simple text extraction
                from aiperf.common.models import TextResponseData

                results.append(
                    ParsedResponse(
                        perf_ns=response.perf_ns,
                        data=TextResponseData(text=response.text),
                    )
                )

        return results

    def get_custom_headers(self) -> dict[str, str]:
        """Headers for HTTP fallback."""
        return {
            "X-Preferred-Transport": "grpc",
            "X-Fallback-Transport": "http",
        }
