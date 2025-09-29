# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Plugin specifications and interfaces for AIPerf endpoint plugins."""

from enum import Enum
from typing import TYPE_CHECKING, Any

import pluggy
from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from aiperf.clients.model_endpoint_info import ModelEndpointInfo
    from aiperf.common.models import ParsedResponse, RequestRecord, Turn


class TransportType(str, Enum):
    """Supported transport types for endpoints."""

    HTTP = "http"
    GRPC = "grpc"
    WEBSOCKET = "websocket"


class HttpMethod(str, Enum):
    """HTTP methods for HTTP transport."""

    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    PATCH = "PATCH"
    DELETE = "DELETE"


class TransportConfig(BaseModel):
    """Configuration for a specific transport type."""

    transport_type: TransportType = Field(...)
    http_method: HttpMethod = Field(default=HttpMethod.POST)
    content_type: str = Field(default="application/json")
    accept_type: str = Field(default="application/json")
    streaming_accept_type: str = Field(default="text/event-stream")
    # Transport-specific configuration can be added here
    grpc_service_name: str | None = Field(default=None, description="gRPC service name")
    websocket_subprotocol: str | None = Field(
        default=None, description="WebSocket subprotocol"
    )


class MultiTransportConfig(BaseModel):
    """Configuration supporting multiple transport types for an endpoint."""

    supported_transports: list[TransportConfig] = Field(
        ...,
        description="List of supported transport configurations, in order of preference",
    )
    default_transport: TransportType = Field(
        ..., description="Default transport type to use if not specified by user"
    )

    def get_transport_config(
        self, transport_type: TransportType
    ) -> TransportConfig | None:
        """Get configuration for a specific transport type.

        Args:
            transport_type: The transport type to get config for.

        Returns:
            TransportConfig | None: The transport config or None if not supported.
        """
        for config in self.supported_transports:
            if config.transport_type == transport_type:
                return config
        return None

    def get_default_config(self) -> TransportConfig:
        """Get the default transport configuration.

        Returns:
            TransportConfig: The default transport configuration.

        Raises:
            ValueError: If default transport is not in supported transports.
        """
        default_config = self.get_transport_config(self.default_transport)
        if default_config is None:
            raise ValueError(
                f"Default transport {self.default_transport} not found in supported transports"
            )
        return default_config

    def get_supported_transport_types(self) -> list[TransportType]:
        """Get list of supported transport types.

        Returns:
            list[TransportType]: List of supported transport types.
        """
        return [config.transport_type for config in self.supported_transports]


# Hook specifications for endpoint plugins
hookspec = pluggy.HookspecMarker("aiperf")


class EndpointPluginSpec:
    """Hook specifications for endpoint plugins."""

    @hookspec
    def aiperf_get_endpoint_info(self) -> "EndpointPluginInfo":
        """Return endpoint information for this plugin.

        Returns:
            EndpointPluginInfo: Metadata about the endpoint this plugin provides.
        """


class EndpointPluginInfo(BaseModel):
    """Information about an endpoint plugin."""

    endpoint_tag: str = Field(
        ...,
        description="Unique identifier for the endpoint (e.g., 'custom-chat', 'anthropic-messages')",
    )
    service_kind: str = Field(
        ..., description="Service kind identifier (e.g., 'anthropic', 'custom')"
    )
    transport_config: MultiTransportConfig = Field(
        ..., description="Transport configuration supporting multiple transport types"
    )
    supports_streaming: bool = Field(
        default=False, description="Whether the endpoint supports streaming responses"
    )
    produces_tokens: bool = Field(
        default=True, description="Whether the endpoint produces token-based responses"
    )
    supports_audio: bool = Field(
        default=False, description="Whether the endpoint supports audio input"
    )
    supports_images: bool = Field(
        default=False, description="Whether the endpoint supports image input"
    )
    endpoint_path: str | None = Field(
        default=None, description="Default endpoint path (e.g., '/v1/chat/completions')"
    )
    metrics_title: str = Field(
        default="Custom Metrics", description="Title for metrics display"
    )
    description: str = Field(
        default="", description="Human-readable description of the endpoint"
    )
    version: str = Field(default="1.0.0", description="Plugin version")


class DynamicEndpoint:
    """Transport-agnostic endpoint handler for data formatting and parsing.

    This class focuses purely on data transformation - converting AIPerf data structures
    to/from API formats. The actual transport (HTTP, gRPC, etc.) is handled automatically
    by AIPerf's transport layer based on the endpoint's transport configuration.
    """

    def __init__(self, model_endpoint: "ModelEndpointInfo") -> None:
        """Initialize the dynamic endpoint.

        Args:
            model_endpoint: The model endpoint configuration.
        """
        self.model_endpoint = model_endpoint

    def get_endpoint_info(self) -> EndpointPluginInfo:
        """Get endpoint information for this endpoint.

        Returns:
            EndpointPluginInfo: Metadata about the endpoint including transport config.
        """
        raise NotImplementedError("Subclasses must implement get_endpoint_info()")

    async def format_payload(self, turn: "Turn") -> dict[str, Any]:
        """Format a conversation turn into a payload for the API.

        This method converts AIPerf's internal Turn representation into the specific
        format expected by the target API. The transport layer will handle serialization
        and transmission based on the endpoint's transport configuration.

        Args:
            turn: The conversation turn to format.

        Returns:
            dict[str, Any]: Formatted payload ready for the API.
        """
        raise NotImplementedError("Subclasses must implement format_payload()")

    async def extract_response_data(
        self, record: "RequestRecord"
    ) -> list["ParsedResponse"]:
        """Extract and parse response data from a request record.

        This method parses the raw response data received by the transport layer
        and converts it into AIPerf's structured response format.

        Args:
            record: The request record containing raw responses from transport layer.

        Returns:
            list[ParsedResponse]: List of parsed and structured responses.
        """
        raise NotImplementedError("Subclasses must implement extract_response_data()")

    def get_custom_headers(self) -> dict[str, str]:
        """Get custom headers specific to this endpoint.

        The transport layer will combine these with standard headers (User-Agent,
        Content-Type, Accept, Authorization) based on the endpoint configuration.

        Returns:
            dict[str, str]: Custom headers to include in requests.
        """
        return {}

    def get_url_path(self) -> str | None:
        """Get the URL path for this endpoint.

        If None, uses the endpoint_path from EndpointPluginInfo.
        If both are None, uses only the base URL.

        Returns:
            str | None: Custom URL path for this endpoint.
        """
        return None

    def get_url_params(self) -> dict[str, str]:
        """Get URL query parameters for this endpoint.

        Returns:
            dict[str, str]: Query parameters to append to the URL.
        """
        return {}
