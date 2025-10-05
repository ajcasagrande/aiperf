# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""
Plugin Registry (AIP-001)

Central registry for managing discovered and loaded plugins.
Provides thread-safe access to plugins with validation.
"""

import threading
from typing import Any, Optional

from aiperf.common.aiperf_logger import AIPerfLogger
from aiperf.plugins.discovery import (
    PluginDiscovery,
    PluginLoader,
    PluginMetadata,
)
from aiperf.plugins.validator import PluginValidator

logger = AIPerfLogger(__name__)


class PluginRegistry:
    """
    Thread-safe registry for AIPerf plugins.

    Manages plugin discovery, loading, validation, and access.
    Singleton pattern with lazy initialization.

    Example:
        >>> registry = PluginRegistry()
        >>> metric_plugins = registry.get_plugins('aiperf.metric')
        >>> my_plugin = registry.get_plugin('aiperf.metric', 'my_metric')
    """

    _instance: Optional["PluginRegistry"] = None
    _lock = threading.Lock()

    def __new__(cls):
        """Singleton instance creation."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        """Initialize registry (called once per singleton)."""
        if self._initialized:
            return

        self._discovered: dict[str, list[PluginMetadata]] = {}
        self._loader = PluginLoader()
        self._validator = PluginValidator()
        self._enabled_plugins: dict[
            str, list[str]
        ] = {}  # group -> enabled plugin names

        # Discover plugins on initialization
        self._discover_all()

        self._initialized = True

    def _discover_all(self):
        """Discover all plugins."""
        logger.info("Discovering AIPerf plugins (AIP-001)...")

        self._discovered = PluginDiscovery.discover_all_plugins()

        total_count = sum(len(plugins) for plugins in self._discovered.values())
        logger.info(
            f"Discovered {total_count} total plugin(s) across {len(self._discovered)} group(s)"
        )

        # Log details
        for group, plugins in self._discovered.items():
            plugin_names = [p.name for p in plugins]
            logger.debug(f"  {group}: {', '.join(plugin_names)}")

    def get_discovered_plugins(self, group: str) -> list[PluginMetadata]:
        """
        Get all discovered plugins for a group (not loaded).

        Args:
            group: Entry point group

        Returns:
            List of plugin metadata
        """
        return self._discovered.get(group, [])

    def load_plugin(self, group: str, name: str) -> Any | None:
        """
        Load a specific plugin by name.

        Args:
            group: Entry point group
            name: Plugin name

        Returns:
            Loaded plugin or None if not found/failed
        """
        metadata = PluginDiscovery.get_plugin_by_name(group, name)
        if metadata is None:
            logger.warning(f"Plugin '{name}' not found in group '{group}'")
            return None

        plugin = self._loader.load_plugin(metadata)
        if plugin is None:
            return None

        # Validate plugin
        if not self._validator.validate_plugin(plugin, group):
            logger.error(f"Plugin '{name}' failed validation")
            return None

        return plugin

    def load_all_plugins(self, group: str) -> dict[str, Any]:
        """
        Load all plugins for a group.

        Args:
            group: Entry point group

        Returns:
            Dict mapping plugin names to loaded plugins
        """
        return self._loader.load_all_for_group(group)

    def enable_plugin(self, group: str, name: str):
        """
        Enable a specific plugin.

        Args:
            group: Entry point group
            name: Plugin name
        """
        if group not in self._enabled_plugins:
            self._enabled_plugins[group] = []

        if name not in self._enabled_plugins[group]:
            self._enabled_plugins[group].append(name)
            logger.info(f"Enabled plugin '{name}' in group '{group}'")

    def disable_plugin(self, group: str, name: str):
        """
        Disable a specific plugin.

        Args:
            group: Entry point group
            name: Plugin name
        """
        if group in self._enabled_plugins and name in self._enabled_plugins[group]:
            self._enabled_plugins[group].remove(name)
            logger.info(f"Disabled plugin '{name}' in group '{group}'")

    def is_enabled(self, group: str, name: str) -> bool:
        """
        Check if a plugin is enabled.

        Args:
            group: Entry point group
            name: Plugin name

        Returns:
            True if enabled, False otherwise
        """
        # If no explicit enable list, all are enabled by default
        if group not in self._enabled_plugins:
            return True

        return name in self._enabled_plugins[group]

    def get_enabled_plugins(self, group: str) -> list[str]:
        """
        Get list of enabled plugin names for a group.

        Args:
            group: Entry point group

        Returns:
            List of enabled plugin names
        """
        if group not in self._enabled_plugins:
            # Return all discovered if no explicit enable list
            return [p.name for p in self.get_discovered_plugins(group)]

        return self._enabled_plugins[group].copy()

    def get_plugin_metadata(self, group: str, name: str) -> dict[str, Any] | None:
        """
        Get metadata for a loaded plugin.

        Args:
            group: Entry point group
            name: Plugin name

        Returns:
            Plugin metadata dict or None
        """
        plugin = self.load_plugin(group, name)
        if plugin is None:
            return None

        # Try to get metadata from plugin
        if hasattr(plugin, "plugin_metadata"):
            try:
                return plugin.plugin_metadata()
            except Exception as e:
                logger.warning(f"Failed to get metadata from plugin '{name}': {e}")

        return None

    def get_load_errors(self) -> dict[str, Exception]:
        """Get all plugin loading errors."""
        return self._loader.get_load_errors()


# Global registry instance
_global_registry: PluginRegistry | None = None
_registry_lock = threading.Lock()


def get_plugin_registry() -> PluginRegistry:
    """
    Get the global plugin registry instance.

    Returns:
        Singleton PluginRegistry instance
    """
    global _global_registry

    if _global_registry is None:
        with _registry_lock:
            if _global_registry is None:
                _global_registry = PluginRegistry()

    return _global_registry
