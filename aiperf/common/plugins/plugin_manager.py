# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Plugin manager for AIPerf endpoint plugins."""

import importlib.metadata
from typing import TYPE_CHECKING

from aiperf.common.exceptions import FactoryCreationError
from aiperf.common.mixins import AIPerfLoggerMixin
from aiperf.common.plugins.plugin_specs import DynamicEndpoint, EndpointPluginInfo
from aiperf.common.plugins.transport_factory import TransportFactory

if TYPE_CHECKING:
    from aiperf.clients.model_endpoint_info import ModelEndpointInfo


class PluginManager(AIPerfLoggerMixin):
    """Manages AIPerf endpoint plugins using pluggy.

    This class handles discovery, loading, and management of endpoint plugins
    that extend AIPerf's capabilities with custom endpoint implementations.
    Each plugin provides a unified endpoint class that handles all operations.
    """

    def __init__(self) -> None:
        """Initialize the plugin manager."""
        super().__init__()
        self._plugins_loaded = False
        self._endpoint_registry: dict[str, type[DynamicEndpoint]] = {}
        self._endpoint_info_cache: dict[str, EndpointPluginInfo] = {}
        self._transport_factory = TransportFactory()

    def discover_and_load_plugins(self) -> None:
        """Discover and load plugins from entry points."""
        if self._plugins_loaded:
            self.debug("Plugins already loaded, skipping discovery")
            return

        self.info("Discovering and loading AIPerf endpoint plugins...")

        # Load plugins from entry points
        entry_points = importlib.metadata.entry_points()
        aiperf_plugins = entry_points.select(group="aiperf.plugins")

        loaded_count = 0
        for entry_point in aiperf_plugins:
            try:
                endpoint_class = entry_point.load()

                # Validate that it's a DynamicEndpoint subclass
                if not issubclass(endpoint_class, DynamicEndpoint):
                    self.error(
                        f"Plugin '{entry_point.name}' does not inherit from DynamicEndpoint"
                    )
                    continue

                # Create a temporary instance to get endpoint info
                # We'll use a dummy model_endpoint for this
                from aiperf.clients.model_endpoint_info import ModelEndpointInfo
                from aiperf.common.config import UserConfig

                # Create minimal config for info extraction
                dummy_config = UserConfig()
                dummy_model_endpoint = ModelEndpointInfo.from_user_config(dummy_config)

                temp_instance = endpoint_class(dummy_model_endpoint)
                endpoint_info = temp_instance.get_endpoint_info()

                # Register the class and cache the info
                self._endpoint_registry[endpoint_info.endpoint_tag] = endpoint_class
                self._endpoint_info_cache[endpoint_info.endpoint_tag] = endpoint_info

                self.info(
                    f"Loaded plugin '{entry_point.name}' providing endpoint '{endpoint_info.endpoint_tag}'"
                )
                loaded_count += 1

            except Exception as e:
                self.error(f"Failed to load plugin '{entry_point.name}': {e!r}")
                continue

        self.info(f"Successfully loaded {loaded_count} endpoint plugins")
        self._plugins_loaded = True

    def get_available_endpoints(self) -> dict[str, EndpointPluginInfo]:
        """Get all available endpoint plugins.

        Returns:
            dict[str, EndpointPluginInfo]: Mapping of endpoint tags to their info.
        """
        self.discover_and_load_plugins()
        return self._endpoint_info_cache.copy()

    def has_endpoint(self, endpoint_tag: str) -> bool:
        """Check if an endpoint plugin is available.

        Args:
            endpoint_tag: The endpoint tag to check.

        Returns:
            bool: True if the endpoint plugin is available.
        """
        self.discover_and_load_plugins()
        return endpoint_tag in self._endpoint_registry

    def get_endpoint_info(self, endpoint_tag: str) -> EndpointPluginInfo:
        """Get endpoint information for a specific endpoint.

        Args:
            endpoint_tag: The endpoint tag to get info for.

        Returns:
            EndpointPluginInfo: The endpoint information.

        Raises:
            FactoryCreationError: If the endpoint is not found.
        """
        self.discover_and_load_plugins()

        if endpoint_tag not in self._endpoint_info_cache:
            available = list(self._endpoint_info_cache.keys())
            raise FactoryCreationError(
                f"Endpoint '{endpoint_tag}' not found. Available endpoints: {available}"
            )

        return self._endpoint_info_cache[endpoint_tag]

    def create_endpoint(
        self, endpoint_tag: str, model_endpoint: "ModelEndpointInfo"
    ) -> DynamicEndpoint:
        """Create a dynamic endpoint instance for the specified endpoint.

        Args:
            endpoint_tag: The endpoint tag.
            model_endpoint: The model endpoint configuration.

        Returns:
            DynamicEndpoint: The unified endpoint instance.

        Raises:
            FactoryCreationError: If creation fails.
        """
        self.discover_and_load_plugins()

        if endpoint_tag not in self._endpoint_registry:
            available = list(self._endpoint_registry.keys())
            raise FactoryCreationError(
                f"Endpoint '{endpoint_tag}' not found. Available endpoints: {available}"
            )

        endpoint_class = self._endpoint_registry[endpoint_tag]

        try:
            return endpoint_class(model_endpoint)
        except Exception as e:
            raise FactoryCreationError(
                f"Failed to create endpoint instance for '{endpoint_tag}': {e}"
            ) from e

    def create_transport_client(
        self,
        endpoint_tag: str,
        model_endpoint: "ModelEndpointInfo",
        preferred_transport: "TransportType | None" = None,
    ):
        """Create a transport client for the specified endpoint.

        Args:
            endpoint_tag: The endpoint tag.
            model_endpoint: The model endpoint configuration.
            preferred_transport: Preferred transport type, or None for default.

        Returns:
            TransportClient: The transport client instance.

        Raises:
            FactoryCreationError: If creation fails.
        """
        endpoint = self.create_endpoint(endpoint_tag, model_endpoint)
        return self._transport_factory.create_transport_client(
            model_endpoint, endpoint, preferred_transport
        )

    def get_supported_transports(self, endpoint_tag: str) -> "list[TransportType]":
        """Get supported transports for a specific endpoint.

        Args:
            endpoint_tag: The endpoint tag.

        Returns:
            list[TransportType]: List of supported transport types.

        Raises:
            FactoryCreationError: If endpoint not found.
        """
        self.discover_and_load_plugins()

        if endpoint_tag not in self._endpoint_registry:
            available = list(self._endpoint_registry.keys())
            raise FactoryCreationError(
                f"Endpoint '{endpoint_tag}' not found. Available endpoints: {available}"
            )

        # Create a temporary endpoint instance to get transport info
        from aiperf.common.config import UserConfig

        dummy_config = UserConfig()
        dummy_model_endpoint = ModelEndpointInfo.from_user_config(dummy_config)

        endpoint_class = self._endpoint_registry[endpoint_tag]
        temp_endpoint = endpoint_class(dummy_model_endpoint)

        return self._transport_factory.get_supported_transports_for_endpoint(
            temp_endpoint
        )

    def list_plugins(self) -> list[tuple[str, EndpointPluginInfo]]:
        """List all loaded plugins with their information.

        Returns:
            list[tuple[str, EndpointPluginInfo]]: List of (endpoint_class_name, endpoint_info) tuples.
        """
        self.discover_and_load_plugins()

        result = []
        for endpoint_tag, endpoint_class in self._endpoint_registry.items():
            try:
                endpoint_info = self._endpoint_info_cache[endpoint_tag]
                result.append((endpoint_class.__name__, endpoint_info))
            except Exception as e:
                self.warning(f"Failed to get info for endpoint {endpoint_tag}: {e}")
                continue

        return result
