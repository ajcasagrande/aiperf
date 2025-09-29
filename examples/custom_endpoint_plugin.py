# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Example custom endpoint plugin for AIPerf.

This demonstrates how to create a transport-agnostic endpoint plugin that integrates
with AIPerf's plugin system. This example implements a simple custom chat endpoint
that focuses on data formatting while letting AIPerf handle the transport layer.
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


class CustomChatEndpoint(DynamicEndpoint):
    """Example custom chat endpoint implementation.

    This endpoint demonstrates how to implement a transport-agnostic API endpoint
    that focuses on data formatting while AIPerf handles the actual communication.
    """

    def get_endpoint_info(self) -> EndpointPluginInfo:
        """Return endpoint information for this plugin."""
        return EndpointPluginInfo(
            endpoint_tag="custom-chat",
            service_kind="custom",
            transport_config=MultiTransportConfig(
                supported_transports=[
                    TransportConfig(
                        transport_type=TransportType.HTTP,
                        http_method=HttpMethod.POST,
                        content_type="application/json",
                        accept_type="application/json",
                        streaming_accept_type="text/event-stream",
                    ),
                ],
                default_transport=TransportType.HTTP,
            ),
            supports_streaming=True,  # Now supports streaming via transport layer
            produces_tokens=True,
            supports_audio=False,
            supports_images=True,  # Example: now supports images
            endpoint_path="/v1/chat/completions",
            metrics_title="Custom Chat Metrics",
            description="Custom chat completion endpoint with transport abstraction",
            version="2.0.0",
        )

    async def format_payload(self, turn: Turn) -> dict[str, Any]:
        """Format a conversation turn into a payload for the custom API.

        This method converts AIPerf's Turn object into the specific format
        expected by the custom API. The transport layer will handle the actual
        HTTP request based on the transport configuration.

        Args:
            turn: The conversation turn to format.

        Returns:
            dict[str, Any]: Formatted payload for the custom API.
        """
        # Build messages array with support for multiple content types
        messages = []

        # Handle text content
        for text in turn.texts:
            for content in text.contents:
                if content:
                    messages.append(
                        {
                            "role": turn.role or "user",
                            "content": content,
                        }
                    )

        # Handle image content (if supported)
        if turn.images and self.get_endpoint_info().supports_images:
            for image in turn.images:
                for content in image.contents:
                    if content:
                        messages.append(
                            {
                                "role": turn.role or "user",
                                "content": [
                                    {"type": "image_url", "image_url": {"url": content}}
                                ],
                            }
                        )

        # Build the main payload
        payload = {
            "model": turn.model or self.model_endpoint.primary_model_name,
            "messages": messages,
            "stream": self.model_endpoint.endpoint.streaming,
        }

        # Add optional parameters
        if turn.max_tokens is not None:
            payload["max_tokens"] = turn.max_tokens

        # Add extra parameters from endpoint config
        if self.model_endpoint.endpoint.extra:
            payload.update(dict(self.model_endpoint.endpoint.extra))

        return payload

    async def extract_response_data(
        self, record: RequestRecord
    ) -> list[ParsedResponse]:
        """Extract and parse response data from a request record.

        This method parses the raw response data received by the transport layer
        and converts it into AIPerf's structured response format.

        Args:
            record: The request record containing raw responses from transport layer.

        Returns:
            list[ParsedResponse]: List of parsed and structured responses.
        """
        results = []

        for response in record.responses:
            if isinstance(response, TextResponse):
                parsed_data = self._parse_custom_response(response.text)
                if parsed_data:
                    results.append(
                        ParsedResponse(
                            perf_ns=response.perf_ns,
                            data=parsed_data,
                        )
                    )

        return results

    def get_custom_headers(self) -> dict[str, str]:
        """Get custom headers specific to this endpoint.

        These headers will be combined with standard headers by the transport layer.

        Returns:
            dict[str, str]: Custom headers for this endpoint.
        """
        return {
            "X-Custom-API-Version": "2.0",
            "X-Custom-Client": "aiperf-plugin",
        }

    def get_url_path(self) -> str | None:
        """Get custom URL path for this endpoint.

        Returns None to use the default endpoint_path from EndpointPluginInfo.

        Returns:
            str | None: Custom URL path or None for default.
        """
        # Use default path from endpoint_info
        return None

    def get_url_params(self) -> dict[str, str]:
        """Get URL query parameters for this endpoint.

        Returns:
            dict[str, str]: Query parameters to append to the URL.
        """
        return {
            "version": "2.0",
            "format": "json",
        }

    def _parse_custom_response(self, response_text: str) -> Any:
        """Parse a custom API response.

        Args:
            response_text: Raw response text from the API.

        Returns:
            Parsed response data or None if parsing fails.
        """
        if not response_text or response_text.strip() == "":
            return None

        try:
            json_data = load_json_str(response_text)

            # Extract the text content from the response
            # This is a simple example - adapt based on your API's response format
            if "choices" in json_data and json_data["choices"]:
                choice = json_data["choices"][0]
                if "message" in choice and "content" in choice["message"]:
                    from aiperf.common.models import TextResponseData

                    return TextResponseData(text=choice["message"]["content"])
                elif "text" in choice:
                    from aiperf.common.models import TextResponseData

                    return TextResponseData(text=choice["text"])

            # Handle streaming response chunks
            if "delta" in json_data and "content" in json_data["delta"]:
                from aiperf.common.models import TextResponseData

                return TextResponseData(text=json_data["delta"]["content"])

            # Fallback: return the entire response as text
            from aiperf.common.models import TextResponseData

            return TextResponseData(text=response_text)

        except Exception:
            # If JSON parsing fails, treat as plain text
            from aiperf.common.models import TextResponseData

            return TextResponseData(text=response_text)


class CustomEmbeddingsEndpoint(DynamicEndpoint):
    """Example custom embeddings endpoint implementation.

    This demonstrates a different endpoint type that uses the same transport
    abstraction but with different data formatting.
    """

    def get_endpoint_info(self) -> EndpointPluginInfo:
        """Return endpoint information for this plugin."""
        return EndpointPluginInfo(
            endpoint_tag="custom-embeddings",
            service_kind="custom",
            transport_config=MultiTransportConfig(
                supported_transports=[
                    TransportConfig(
                        transport_type=TransportType.HTTP,
                        http_method=HttpMethod.POST,
                        content_type="application/json",
                        accept_type="application/json",
                    ),
                ],
                default_transport=TransportType.HTTP,
            ),
            supports_streaming=False,  # Embeddings typically don't stream
            produces_tokens=False,  # Embeddings produce vectors, not tokens
            supports_audio=False,
            supports_images=False,
            endpoint_path="/v1/embeddings",
            metrics_title="Custom Embeddings Metrics",
            description="Custom embeddings endpoint",
            version="1.0.0",
        )

    async def format_payload(self, turn: Turn) -> dict[str, Any]:
        """Format a conversation turn into an embeddings payload."""
        # Extract text content for embeddings
        input_texts = []
        for text in turn.texts:
            for content in text.contents:
                if content:
                    input_texts.append(content)

        payload = {
            "model": turn.model or self.model_endpoint.primary_model_name,
            "input": input_texts,
            "encoding_format": "float",
        }

        # Add extra parameters from endpoint config
        if self.model_endpoint.endpoint.extra:
            payload.update(dict(self.model_endpoint.endpoint.extra))

        return payload

    async def extract_response_data(
        self, record: RequestRecord
    ) -> list[ParsedResponse]:
        """Extract embeddings response data."""
        results = []

        for response in record.responses:
            if isinstance(response, TextResponse):
                parsed_data = self._parse_embeddings_response(response.text)
                if parsed_data:
                    results.append(
                        ParsedResponse(
                            perf_ns=response.perf_ns,
                            data=parsed_data,
                        )
                    )

        return results

    def _parse_embeddings_response(self, response_text: str) -> Any:
        """Parse embeddings API response."""
        if not response_text:
            return None

        try:
            json_data = load_json_str(response_text)

            if "data" in json_data and json_data["data"]:
                # Extract embedding vectors
                embeddings = [item["embedding"] for item in json_data["data"]]
                from aiperf.common.models import TextResponseData

                return TextResponseData(text=f"Generated {len(embeddings)} embeddings")

        except Exception:
            pass

        return None
