# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""
Plugin Discovery and Loading (AIP-001)

Implements entry point based plugin discovery using importlib.metadata.
Supports lazy loading and caching for optimal performance.
"""

from dataclasses import dataclass
from functools import cache, lru_cache
from importlib.metadata import EntryPoint, entry_points
from typing import Any

from aiperf.common.aiperf_logger import AIPerfLogger

logger = AIPerfLogger(__name__)


# Entry point groups defined by AIP-001
PLUGIN_GROUPS = {
    "metric": "aiperf.metric",
    "endpoint": "aiperf.endpoint",
    "data_exporter": "aiperf.data_exporter",
    "transport": "aiperf.transport",
    "processor": "aiperf.processor",
    "collector": "aiperf.collector",
}


@dataclass
class PluginMetadata:
    """
    Metadata for a discovered plugin.

    Attributes:
        name: Plugin identifier
        entry_point: Original EntryPoint object
        group: Entry point group (e.g., 'aiperf.metric')
        module_name: Python module containing plugin
        attr_name: Class/function name in module
        is_loaded: Whether plugin has been loaded
    """

    name: str
    entry_point: EntryPoint
    group: str
    module_name: str
    attr_name: str
    is_loaded: bool = False


class PluginDiscovery:
    """
    Plugin discovery system using entry points (AIP-001).

    This class handles discovery of all AIPerf plugins via Python entry points
    defined in plugin packages' pyproject.toml files.

    Thread-safe with LRU caching for performance.
    """

    @staticmethod
    @lru_cache(maxsize=1)
    def discover_all_plugins() -> dict[str, list[PluginMetadata]]:
        """
        Discover all AIPerf plugins via entry points.

        Returns:
            Dict mapping group names to lists of plugin metadata

        Example:
            >>> plugins = PluginDiscovery.discover_all_plugins()
            >>> metric_plugins = plugins.get('aiperf.metric', [])
            >>> for plugin in metric_plugins:
            ...     print(f"Found metric plugin: {plugin.name}")
        """
        discovered = {}

        for _group_key, group_name in PLUGIN_GROUPS.items():
            try:
                # Discover plugins for this group
                eps = entry_points(group=group_name)

                plugins = []
                for ep in eps:
                    metadata = PluginMetadata(
                        name=ep.name,
                        entry_point=ep,
                        group=group_name,
                        module_name=ep.value.split(":")[0],
                        attr_name=ep.value.split(":")[1]
                        if ":" in ep.value
                        else ep.name,
                    )
                    plugins.append(metadata)

                    logger.debug(
                        f"Discovered plugin '{ep.name}' in group '{group_name}' "
                        f"from {ep.value}"
                    )

                if plugins:
                    discovered[group_name] = plugins
                    logger.info(
                        f"Discovered {len(plugins)} plugin(s) for '{group_name}'"
                    )

            except Exception as e:
                logger.warning(
                    f"Error discovering plugins for group '{group_name}': {e}"
                )

        return discovered

    @staticmethod
    def discover_plugins_by_group(group: str) -> list[PluginMetadata]:
        """
        Discover plugins for a specific entry point group.

        Args:
            group: Entry point group name (e.g., 'aiperf.metric')

        Returns:
            List of plugin metadata for the group
        """
        all_plugins = PluginDiscovery.discover_all_plugins()
        return all_plugins.get(group, [])

    @staticmethod
    def get_plugin_by_name(group: str, name: str) -> PluginMetadata | None:
        """
        Get specific plugin by name within a group.

        Args:
            group: Entry point group
            name: Plugin name

        Returns:
            Plugin metadata if found, None otherwise
        """
        plugins = PluginDiscovery.discover_plugins_by_group(group)
        return next((p for p in plugins if p.name == name), None)


class PluginLoader:
    """
    Plugin loader with lazy loading support (AIP-001).

    Loads plugins only when needed and caches loaded instances.
    Thread-safe implementation.
    """

    def __init__(self):
        self._loaded_plugins: dict[str, Any] = {}
        self._load_errors: dict[str, Exception] = {}

    def load_plugin(self, metadata: PluginMetadata) -> Any | None:
        """
        Load a plugin from its metadata (lazy loading).

        Args:
            metadata: Plugin metadata from discovery

        Returns:
            Loaded plugin class/function, or None if loading failed

        Example:
            >>> loader = PluginLoader()
            >>> metadata = PluginDiscovery.get_plugin_by_name('aiperf.metric', 'my_metric')
            >>> plugin_class = loader.load_plugin(metadata)
            >>> instance = plugin_class()  # Instantiate
        """
        cache_key = f"{metadata.group}:{metadata.name}"

        # Return cached if already loaded
        if cache_key in self._loaded_plugins:
            return self._loaded_plugins[cache_key]

        # Return None if previous load failed
        if cache_key in self._load_errors:
            logger.debug(
                f"Plugin '{metadata.name}' previously failed to load: "
                f"{self._load_errors[cache_key]}"
            )
            return None

        try:
            # Lazy load via entry point
            logger.debug(
                f"Loading plugin '{metadata.name}' from {metadata.entry_point.value}"
            )
            plugin = metadata.entry_point.load()

            # Cache the loaded plugin
            self._loaded_plugins[cache_key] = plugin
            metadata.is_loaded = True

            logger.info(
                f"Successfully loaded plugin '{metadata.name}' from group '{metadata.group}'"
            )
            return plugin

        except Exception as e:
            logger.error(f"Failed to load plugin '{metadata.name}': {e}")
            self._load_errors[cache_key] = e
            return None

    def load_all_for_group(self, group: str) -> dict[str, Any]:
        """
        Load all plugins for a specific group.

        Args:
            group: Entry point group name

        Returns:
            Dict mapping plugin names to loaded plugins
        """
        plugins = PluginDiscovery.discover_plugins_by_group(group)
        loaded = {}

        for metadata in plugins:
            plugin = self.load_plugin(metadata)
            if plugin is not None:
                loaded[metadata.name] = plugin

        return loaded

    def get_load_errors(self) -> dict[str, Exception]:
        """Get all plugin loading errors."""
        return self._load_errors.copy()


# Convenience functions
@cache
def discover_plugins(group: str) -> list[PluginMetadata]:
    """
    Discover plugins for a group (cached).

    Args:
        group: Entry point group name

    Returns:
        List of discovered plugins
    """
    return PluginDiscovery.discover_plugins_by_group(group)


def load_plugin(group: str, name: str) -> Any | None:
    """
    Load a specific plugin by name.

    Args:
        group: Entry point group
        name: Plugin name

    Returns:
        Loaded plugin or None
    """
    metadata = PluginDiscovery.get_plugin_by_name(group, name)
    if metadata is None:
        return None

    loader = PluginLoader()
    return loader.load_plugin(metadata)
