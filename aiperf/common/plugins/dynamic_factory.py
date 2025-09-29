# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Dynamic factory that integrates plugin-based endpoints with existing factories."""

from typing import TYPE_CHECKING, Any

from aiperf.common.exceptions import FactoryCreationError
from aiperf.common.mixins import AIPerfLoggerMixin
from aiperf.common.plugins.plugin_manager import PluginManager
from aiperf.common.plugins.plugin_specs import DynamicEndpoint

if TYPE_CHECKING:
    from aiperf.clients.model_endpoint_info import ModelEndpointInfo
    from aiperf.common.models import ParsedResponse, RequestRecord, Turn
    from aiperf.common.protocols import (
        InferenceClientProtocol,
        RequestConverterProtocol,
        ResponseExtractorProtocol,
    )


class DynamicEndpointWrapper:
    """Wrapper that adapts DynamicEndpoint to individual protocol interfaces.

    This allows the unified DynamicEndpoint to work with existing factory patterns
    that expect separate request converters, response extractors, and clients.
    """

    def __init__(self, dynamic_endpoint: DynamicEndpoint) -> None:
        """Initialize the wrapper.

        Args:
            dynamic_endpoint: The unified endpoint instance to wrap.
        """
        self.dynamic_endpoint = dynamic_endpoint


class DynamicRequestConverter(DynamicEndpointWrapper, AIPerfLoggerMixin):
    """Request converter adapter for DynamicEndpoint."""

    async def format_payload(
        self, model_endpoint: "ModelEndpointInfo", turn: "Turn"
    ) -> dict[str, Any]:
        """Format payload using the dynamic endpoint.

        Args:
            model_endpoint: The model endpoint configuration.
            turn: The conversation turn to format.

        Returns:
            dict[str, Any]: Formatted payload.
        """
        return await self.dynamic_endpoint.format_payload(turn)


class DynamicResponseExtractor(DynamicEndpointWrapper, AIPerfLoggerMixin):
    """Response extractor adapter for DynamicEndpoint."""

    async def extract_response_data(
        self, record: "RequestRecord"
    ) -> list["ParsedResponse"]:
        """Extract response data using the dynamic endpoint.

        Args:
            record: The request record containing responses.

        Returns:
            list[ParsedResponse]: List of parsed responses.
        """
        return await self.dynamic_endpoint.extract_response_data(record)


class DynamicInferenceClient(DynamicEndpointWrapper, AIPerfLoggerMixin):
    """Inference client adapter for DynamicEndpoint."""

    def __init__(
        self, dynamic_endpoint: DynamicEndpoint, model_endpoint: "ModelEndpointInfo"
    ) -> None:
        """Initialize the client adapter.

        Args:
            dynamic_endpoint: The unified endpoint instance.
            model_endpoint: The model endpoint configuration.
        """
        super().__init__(dynamic_endpoint)
        self.model_endpoint = model_endpoint

    async def send_request(
        self, model_endpoint: "ModelEndpointInfo", payload: dict[str, Any]
    ) -> "RequestRecord":
        """Send request using the dynamic endpoint.

        Args:
            model_endpoint: The model endpoint configuration.
            payload: The request payload.

        Returns:
            RequestRecord: The request record with response data.
        """
        return await self.dynamic_endpoint.send_request(payload)

    async def close(self) -> None:
        """Close the client."""
        await self.dynamic_endpoint.close()


class DynamicEndpointFactory(AIPerfLoggerMixin):
    """Factory that creates components from both static and dynamic endpoints.

    This factory extends the existing factory pattern to support plugin-based
    dynamic endpoints while maintaining compatibility with existing static endpoints.
    """

    def __init__(self) -> None:
        """Initialize the dynamic factory."""
        super().__init__()
        self._plugin_manager = PluginManager()

    def has_endpoint(self, endpoint_tag: str) -> bool:
        """Check if an endpoint is available (static or dynamic).

        Args:
            endpoint_tag: The endpoint tag to check.

        Returns:
            bool: True if the endpoint is available.
        """
        # Check if it's a plugin-based endpoint
        return self._plugin_manager.has_endpoint(endpoint_tag)

    def create_request_converter(
        self, endpoint_tag: str, model_endpoint: "ModelEndpointInfo"
    ) -> "RequestConverterProtocol":
        """Create a request converter for the specified endpoint.

        Args:
            endpoint_tag: The endpoint tag.
            model_endpoint: The model endpoint configuration.

        Returns:
            RequestConverterProtocol: The request converter instance.

        Raises:
            FactoryCreationError: If the endpoint is not found or creation fails.
        """
        if self._plugin_manager.has_endpoint(endpoint_tag):
            dynamic_endpoint = self._plugin_manager.create_endpoint(
                endpoint_tag, model_endpoint
            )
            return DynamicRequestConverter(dynamic_endpoint)

        raise FactoryCreationError(
            f"No request converter available for endpoint '{endpoint_tag}'"
        )

    def create_response_extractor(
        self, endpoint_tag: str, model_endpoint: "ModelEndpointInfo"
    ) -> "ResponseExtractorProtocol":
        """Create a response extractor for the specified endpoint.

        Args:
            endpoint_tag: The endpoint tag.
            model_endpoint: The model endpoint configuration.

        Returns:
            ResponseExtractorProtocol: The response extractor instance.

        Raises:
            FactoryCreationError: If the endpoint is not found or creation fails.
        """
        if self._plugin_manager.has_endpoint(endpoint_tag):
            dynamic_endpoint = self._plugin_manager.create_endpoint(
                endpoint_tag, model_endpoint
            )
            return DynamicResponseExtractor(dynamic_endpoint)

        raise FactoryCreationError(
            f"No response extractor available for endpoint '{endpoint_tag}'"
        )

    def create_inference_client(
        self, endpoint_tag: str, model_endpoint: "ModelEndpointInfo", **kwargs: Any
    ) -> "InferenceClientProtocol":
        """Create an inference client for the specified endpoint.

        Args:
            endpoint_tag: The endpoint tag.
            model_endpoint: The model endpoint configuration.
            **kwargs: Additional keyword arguments.

        Returns:
            InferenceClientProtocol: The inference client instance.

        Raises:
            FactoryCreationError: If the endpoint is not found or creation fails.
        """
        if self._plugin_manager.has_endpoint(endpoint_tag):
            dynamic_endpoint = self._plugin_manager.create_endpoint(
                endpoint_tag, model_endpoint
            )
            return DynamicInferenceClient(dynamic_endpoint, model_endpoint)

        raise FactoryCreationError(
            f"No inference client available for endpoint '{endpoint_tag}'"
        )

    def get_available_endpoints(self) -> list[str]:
        """Get all available endpoint tags.

        Returns:
            list[str]: List of available endpoint tags.
        """
        endpoints = []

        # Add plugin-based endpoints
        plugin_endpoints = self._plugin_manager.get_available_endpoints()
        endpoints.extend(plugin_endpoints.keys())

        return sorted(endpoints)

    def get_plugin_manager(self) -> PluginManager:
        """Get the plugin manager instance.

        Returns:
            PluginManager: The plugin manager.
        """
        return self._plugin_manager
