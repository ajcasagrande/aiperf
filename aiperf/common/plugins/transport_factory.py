# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Transport factory for handling different transport types automatically."""

import json
import time
from typing import TYPE_CHECKING, Any

import aiohttp

from aiperf.clients.http.aiohttp_client import create_tcp_connector
from aiperf.common.exceptions import FactoryCreationError
from aiperf.common.mixins import AIPerfLoggerMixin
from aiperf.common.models import ErrorDetails, RequestRecord, TextResponse
from aiperf.common.plugins.plugin_specs import (
    DynamicEndpoint,
    TransportType,
)

if TYPE_CHECKING:
    from aiperf.clients.model_endpoint_info import ModelEndpointInfo


class TransportClient(AIPerfLoggerMixin):
    """Base class for transport clients."""

    def __init__(
        self,
        model_endpoint: "ModelEndpointInfo",
        endpoint: DynamicEndpoint,
        transport_type: TransportType,
    ) -> None:
        """Initialize the transport client.

        Args:
            model_endpoint: The model endpoint configuration.
            endpoint: The dynamic endpoint instance.
            transport_type: The specific transport type to use.
        """
        super().__init__()
        self.model_endpoint = model_endpoint
        self.endpoint = endpoint
        self.endpoint_info = endpoint.get_endpoint_info()
        self.transport_type = transport_type
        self.transport_config = (
            self.endpoint_info.transport_config.get_transport_config(transport_type)
        )

        if self.transport_config is None:
            raise ValueError(
                f"Transport type {transport_type} not supported by endpoint"
            )

    async def send_request(self, payload: dict[str, Any]) -> RequestRecord:
        """Send a request using this transport.

        Args:
            payload: The formatted payload from the endpoint.

        Returns:
            RequestRecord: The request record with response data.
        """
        raise NotImplementedError("Subclasses must implement send_request()")

    async def close(self) -> None:
        """Clean up transport resources."""
        pass


class HttpTransportClient(TransportClient):
    """HTTP transport client using aiohttp."""

    def __init__(
        self,
        model_endpoint: "ModelEndpointInfo",
        endpoint: DynamicEndpoint,
        transport_type: TransportType,
    ) -> None:
        """Initialize the HTTP transport client."""
        super().__init__(model_endpoint, endpoint, transport_type)
        self.tcp_connector = None
        self.session = None

    async def send_request(self, payload: dict[str, Any]) -> RequestRecord:
        """Send HTTP request to the API server.

        Args:
            payload: The formatted request payload.

        Returns:
            RequestRecord: The request record with response data.
        """
        if not self.session:
            await self._initialize_session()

        url = self._build_url()
        headers = self._build_headers()
        method = self.transport_config.http_method.value

        # Serialize payload based on content type
        data = self._serialize_payload(payload)

        start_time = time.perf_counter_ns()

        try:
            timeout = aiohttp.ClientTimeout(total=self.model_endpoint.endpoint.timeout)

            async with self.session.request(
                method,
                url,
                headers=headers,
                data=data,
                timeout=timeout,
            ) as response:
                end_time = time.perf_counter_ns()

                if response.status == 200:
                    response_text = await response.text()
                    text_response = TextResponse(
                        text=response_text,
                        perf_ns=end_time - start_time,
                    )

                    return RequestRecord(
                        request_time_ns=start_time,
                        model_name=payload.get("model"),
                        responses=[text_response],
                        error_details=None,
                    )
                else:
                    error_text = await response.text()
                    return RequestRecord(
                        request_time_ns=start_time,
                        model_name=payload.get("model"),
                        responses=[],
                        error_details=ErrorDetails(
                            error_type="HTTPError",
                            error_message=f"HTTP {response.status}: {error_text}",
                        ),
                    )

        except Exception as e:
            end_time = time.perf_counter_ns()
            return RequestRecord(
                request_time_ns=start_time,
                model_name=payload.get("model"),
                responses=[],
                error_details=ErrorDetails(
                    error_type=type(e).__name__,
                    error_message=str(e),
                ),
            )

    def _build_url(self) -> str:
        """Build the complete URL for the request."""
        base_url = self.model_endpoint.endpoint.base_url
        if not base_url:
            raise ValueError("Base URL is required for HTTP transport")

        url = base_url.rstrip("/")
        if not url.startswith("http"):
            url = f"http://{url}"

        # Add endpoint path
        path = self.endpoint.get_url_path()
        if path:
            url += "/" + path.lstrip("/")
        elif self.model_endpoint.endpoint.custom_endpoint:
            url += "/" + self.model_endpoint.endpoint.custom_endpoint.lstrip("/")
        elif self.endpoint_info.endpoint_path:
            url += "/" + self.endpoint_info.endpoint_path.lstrip("/")

        # Add query parameters
        url_params = self.endpoint.get_url_params()
        if self.model_endpoint.endpoint.url_params:
            url_params.update(self.model_endpoint.endpoint.url_params)

        if url_params:
            from urllib.parse import urlencode

            url += "?" + urlencode(url_params)

        return url

    def _build_headers(self) -> dict[str, str]:
        """Build HTTP headers for the request."""
        headers = {
            "User-Agent": "aiperf/1.0",
            "Content-Type": self.transport_config.content_type,
        }

        # Set Accept header based on streaming
        if self.model_endpoint.endpoint.streaming:
            headers["Accept"] = self.transport_config.streaming_accept_type
        else:
            headers["Accept"] = self.transport_config.accept_type

        # Add API key if available
        if self.model_endpoint.endpoint.api_key:
            headers["Authorization"] = f"Bearer {self.model_endpoint.endpoint.api_key}"

        # Add custom headers from endpoint config
        if self.model_endpoint.endpoint.headers:
            headers.update(dict(self.model_endpoint.endpoint.headers))

        # Add endpoint-specific custom headers
        custom_headers = self.endpoint.get_custom_headers()
        if custom_headers:
            headers.update(custom_headers)

        return headers

    def _serialize_payload(self, payload: dict[str, Any]) -> str:
        """Serialize payload based on content type."""
        content_type = self.transport_config.content_type

        if content_type == "application/json":
            return json.dumps(payload)
        elif content_type == "application/x-www-form-urlencoded":
            from urllib.parse import urlencode

            return urlencode(payload)
        else:
            # Default to JSON
            return json.dumps(payload)

    async def _initialize_session(self) -> None:
        """Initialize the HTTP session."""
        if not self.tcp_connector:
            self.tcp_connector = create_tcp_connector()

        self.session = aiohttp.ClientSession(connector=self.tcp_connector)

    async def close(self) -> None:
        """Clean up HTTP resources."""
        if self.session:
            await self.session.close()
            self.session = None

        if self.tcp_connector:
            await self.tcp_connector.close()
            self.tcp_connector = None


class GrpcTransportClient(TransportClient):
    """gRPC transport client (placeholder for future implementation)."""

    async def send_request(self, payload: dict[str, Any]) -> RequestRecord:
        """Send gRPC request."""
        raise NotImplementedError("gRPC transport not yet implemented")


class WebSocketTransportClient(TransportClient):
    """WebSocket transport client (placeholder for future implementation)."""

    async def send_request(self, payload: dict[str, Any]) -> RequestRecord:
        """Send WebSocket request."""
        raise NotImplementedError("WebSocket transport not yet implemented")


class TransportFactory(AIPerfLoggerMixin):
    """Factory for creating appropriate transport clients based on transport type."""

    _transport_clients = {
        TransportType.HTTP: HttpTransportClient,
        TransportType.GRPC: GrpcTransportClient,
        TransportType.WEBSOCKET: WebSocketTransportClient,
    }

    def __init__(self) -> None:
        """Initialize the transport factory."""
        super().__init__()

    def create_transport_client(
        self,
        model_endpoint: "ModelEndpointInfo",
        endpoint: DynamicEndpoint,
        preferred_transport: TransportType | None = None,
    ) -> TransportClient:
        """Create a transport client for the endpoint.

        Args:
            model_endpoint: The model endpoint configuration.
            endpoint: The dynamic endpoint instance.
            preferred_transport: Preferred transport type, or None for default.

        Returns:
            TransportClient: The appropriate transport client.

        Raises:
            FactoryCreationError: If the transport type is not supported.
        """
        endpoint_info = endpoint.get_endpoint_info()
        transport_config = endpoint_info.transport_config

        # Determine which transport to use
        if preferred_transport is not None:
            # Check if preferred transport is supported
            if transport_config.get_transport_config(preferred_transport) is None:
                supported = transport_config.get_supported_transport_types()
                raise FactoryCreationError(
                    f"Preferred transport '{preferred_transport}' not supported by endpoint. "
                    f"Supported: {supported}"
                )
            transport_type = preferred_transport
        else:
            # Use default transport
            transport_type = transport_config.default_transport

        # Check if transport client is available
        if transport_type not in self._transport_clients:
            available = list(self._transport_clients.keys())
            raise FactoryCreationError(
                f"Transport type '{transport_type}' not supported by AIPerf. Available: {available}"
            )

        client_class = self._transport_clients[transport_type]

        try:
            return client_class(model_endpoint, endpoint, transport_type)
        except Exception as e:
            raise FactoryCreationError(
                f"Failed to create transport client for '{transport_type}': {e}"
            ) from e

    def get_supported_transports_for_endpoint(
        self, endpoint: DynamicEndpoint
    ) -> list[TransportType]:
        """Get supported transports for a specific endpoint.

        Args:
            endpoint: The dynamic endpoint instance.

        Returns:
            list[TransportType]: List of transport types supported by both endpoint and AIPerf.
        """
        endpoint_info = endpoint.get_endpoint_info()
        endpoint_transports = (
            endpoint_info.transport_config.get_supported_transport_types()
        )
        aiperf_transports = self.get_supported_transports()

        # Return intersection of endpoint and AIPerf supported transports
        return [t for t in endpoint_transports if t in aiperf_transports]

    @classmethod
    def register_transport(
        cls, transport_type: TransportType, client_class: type[TransportClient]
    ) -> None:
        """Register a new transport client type.

        Args:
            transport_type: The transport type to register.
            client_class: The transport client class.
        """
        cls._transport_clients[transport_type] = client_class

    def get_supported_transports(self) -> list[TransportType]:
        """Get list of supported transport types.

        Returns:
            list[TransportType]: List of supported transport types.
        """
        return list(self._transport_clients.keys())
