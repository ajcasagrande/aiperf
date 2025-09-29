# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Plugin manager for request converter plugins."""

import importlib.util
from pathlib import Path
from typing import Any

import pluggy

from aiperf.clients.model_endpoint_info import ModelEndpointInfo
from aiperf.common.enums import EndpointType
from aiperf.common.exceptions import AIPerfError
from aiperf.common.mixins import AIPerfLoggerMixin
from aiperf.common.models import Turn

from .hookspecs import PROJECT_NAME, RequestConverterHookSpec


class PluginNotFoundError(AIPerfError):
    """Raised when no plugin can handle the requested endpoint type."""


class RequestConverterPluginManager(AIPerfLoggerMixin):
    """Plugin manager for request converter plugins using pluggy."""

    def __init__(self) -> None:
        """Initialize the plugin manager."""
        super().__init__()
        self.pm = pluggy.PluginManager(PROJECT_NAME)
        self.pm.add_hookspecs(RequestConverterHookSpec)
        self._plugin_cache: dict[EndpointType, Any] = {}
        self._plugins_loaded = False

    def register_plugin(self, plugin: Any) -> None:
        """Register a plugin instance with the manager.

        Args:
            plugin: Plugin instance that implements RequestConverterHookSpec.
        """
        self.pm.register(plugin)
        self._invalidate_cache()
        self.debug(f"Registered plugin: {plugin}")

    def register_plugin_class(self, plugin_class: type) -> Any:
        """Register a plugin class by instantiating it.

        Args:
            plugin_class: Plugin class that implements RequestConverterHookSpec.

        Returns:
            The instantiated plugin.
        """
        plugin_instance = plugin_class()
        self.register_plugin(plugin_instance)
        return plugin_instance

    def unregister_plugin(self, plugin: Any) -> None:
        """Unregister a plugin from the manager.

        Args:
            plugin: Plugin instance to unregister.
        """
        self.pm.unregister(plugin)
        self._invalidate_cache()
        self.debug(f"Unregistered plugin: {plugin}")

    def discover_and_load_plugins(self, plugin_dirs: list[Path] | None = None) -> None:
        """Discover and load plugins from specified directories.

        Args:
            plugin_dirs: List of directories to search for plugins.
                        If None, uses default plugin locations.
        """
        if plugin_dirs is None:
            # Default plugin directories
            plugin_dirs = [
                Path(__file__).parent.parent.parent / "clients",  # Built-in clients
            ]

        for plugin_dir in plugin_dirs:
            if not plugin_dir.exists():
                self.warning(f"Plugin directory does not exist: {plugin_dir}")
                continue

            self._discover_plugins_in_directory(plugin_dir)

        self._plugins_loaded = True
        self.info(f"Loaded {len(self.pm.list_name_plugin())} plugins")

    def _discover_plugins_in_directory(self, plugin_dir: Path) -> None:
        """Discover plugins in a specific directory.

        Args:
            plugin_dir: Directory to search for plugins.
        """
        for py_file in plugin_dir.rglob("*.py"):
            if py_file.name.startswith("_"):
                continue

            try:
                self._load_plugin_from_file(py_file)
            except Exception as e:
                self.warning(f"Failed to load plugin from {py_file}: {e}")

    def _load_plugin_from_file(self, py_file: Path) -> None:
        """Load a plugin from a Python file.

        Args:
            py_file: Path to the Python file containing the plugin.
        """
        module_name = py_file.stem
        spec = importlib.util.spec_from_file_location(module_name, py_file)
        if spec is None or spec.loader is None:
            return

        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        # Look for classes that might be plugins
        for attr_name in dir(module):
            attr = getattr(module, attr_name)
            if (
                isinstance(attr, type)
                and hasattr(attr, "get_supported_endpoint_types")
                and hasattr(attr, "format_payload")
            ):
                try:
                    self.register_plugin_class(attr)
                    self.debug(
                        f"Auto-registered plugin class: {attr.__name__} from {py_file}"
                    )
                except Exception as e:
                    self.warning(f"Failed to register plugin {attr.__name__}: {e}")

    def get_plugin_for_endpoint_type(self, endpoint_type: EndpointType) -> Any:
        """Get the best plugin for the specified endpoint type.

        Args:
            endpoint_type: The endpoint type to find a plugin for.

        Returns:
            The plugin instance that can handle the endpoint type.

        Raises:
            PluginNotFoundError: If no plugin can handle the endpoint type.
        """
        if not self._plugins_loaded:
            self.discover_and_load_plugins()

        # Check cache first
        if endpoint_type in self._plugin_cache:
            return self._plugin_cache[endpoint_type]

        # Find all plugins that can handle this endpoint type
        compatible_plugins = []

        for plugin in self.pm.get_plugins():
            try:
                if hasattr(plugin, "can_handle_endpoint_type"):
                    can_handle = plugin.can_handle_endpoint_type(endpoint_type)
                elif hasattr(plugin, "get_supported_endpoint_types"):
                    can_handle = endpoint_type in plugin.get_supported_endpoint_types()
                else:
                    continue

                if can_handle:
                    priority = getattr(plugin, "get_plugin_priority", lambda: 0)()
                    compatible_plugins.append((priority, plugin))
            except Exception as e:
                self.warning(f"Error checking plugin {plugin} compatibility: {e}")

        if not compatible_plugins:
            raise PluginNotFoundError(
                f"No plugin found that can handle endpoint type: {endpoint_type}"
            )

        # Sort by priority (highest first) and get the best plugin
        compatible_plugins.sort(key=lambda x: x[0], reverse=True)
        best_plugin = compatible_plugins[0][1]

        # Cache the result
        self._plugin_cache[endpoint_type] = best_plugin

        self.debug(f"Selected plugin {best_plugin} for endpoint type {endpoint_type}")
        return best_plugin

    async def format_payload(
        self,
        endpoint_type: EndpointType,
        model_endpoint: ModelEndpointInfo,
        turn: Turn,
    ) -> dict[str, Any]:
        """Format a payload using the appropriate plugin.

        Args:
            endpoint_type: The endpoint type to format for.
            model_endpoint: Information about the model endpoint.
            turn: The turn data to format.

        Returns:
            The formatted payload.

        Raises:
            PluginNotFoundError: If no plugin can handle the endpoint type.
        """
        plugin = self.get_plugin_for_endpoint_type(endpoint_type)

        try:
            result = await plugin.format_payload(endpoint_type, model_endpoint, turn)
            if result is None:
                raise PluginNotFoundError(
                    f"Plugin {plugin} returned None for endpoint type {endpoint_type}"
                )
            return result
        except Exception as e:
            self.error(f"Error formatting payload with plugin {plugin}: {e}")
            raise

    def list_plugins(self) -> list[tuple[str, list[EndpointType]]]:
        """List all registered plugins and their supported endpoint types.

        Returns:
            List of tuples containing (plugin_name, supported_endpoint_types).
        """
        if not self._plugins_loaded:
            self.discover_and_load_plugins()

        plugins_info = []
        for plugin in self.pm.get_plugins():
            try:
                name = getattr(plugin, "get_plugin_name", lambda: str(plugin))()
                supported_types = getattr(
                    plugin, "get_supported_endpoint_types", lambda: []
                )()
                plugins_info.append((name, supported_types))
            except Exception as e:
                self.warning(f"Error getting info for plugin {plugin}: {e}")

        return plugins_info

    def _invalidate_cache(self) -> None:
        """Invalidate the plugin cache."""
        self._plugin_cache.clear()


# Global plugin manager instance
_plugin_manager: RequestConverterPluginManager | None = None


def get_plugin_manager() -> RequestConverterPluginManager:
    """Get the global plugin manager instance.

    Returns:
        The global RequestConverterPluginManager instance.
    """
    global _plugin_manager
    if _plugin_manager is None:
        _plugin_manager = RequestConverterPluginManager()
    return _plugin_manager
