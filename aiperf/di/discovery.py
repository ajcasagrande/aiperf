# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Plugin discovery and registration utilities."""

import importlib.metadata
from typing import Dict, List, Optional, Type, Any
from dataclasses import dataclass

from aiperf.common.aiperf_logger import AIPerfLogger

logger = AIPerfLogger(__name__)


@dataclass
class PluginInfo:
    """Information about a discovered plugin."""
    name: str
    module_path: str
    class_name: str
    entry_point_group: str
    loaded_class: Optional[Type] = None


def discover_entry_points(group: str) -> Dict[str, PluginInfo]:
    """Discover all entry points for a given group."""
    plugins = {}

    try:
        entry_points = importlib.metadata.entry_points().select(group=group)

        for entry_point in entry_points:
            # Parse module and class from entry point value
            module_path, class_name = entry_point.value.rsplit(':', 1)

            plugin_info = PluginInfo(
                name=entry_point.name,
                module_path=module_path,
                class_name=class_name,
                entry_point_group=group
            )

            plugins[entry_point.name] = plugin_info
            logger.debug(f"Discovered plugin: {entry_point.name} -> {entry_point.value}")

    except Exception as e:
        logger.error(f"Error discovering entry points for group '{group}': {e}")

    return plugins


def discover_all_plugins() -> Dict[str, Dict[str, PluginInfo]]:
    """Discover all AIPerf plugins across all groups."""
    plugin_groups = [
        "aiperf.services",
        "aiperf.clients",
        "aiperf.inference_clients",
        "aiperf.communication_clients",
        "aiperf.exporters",
        "aiperf.console_exporters",
        "aiperf.processors",
        "aiperf.record_processors",
        "aiperf.results_processors",
        "aiperf.ui",
        "aiperf.composers",
        "aiperf.service_managers",
        "aiperf.zmq_proxies",
        "aiperf.rate_generators",
    ]

    all_plugins = {}
    for group in plugin_groups:
        plugins = discover_entry_points(group)
        if plugins:
            all_plugins[group] = plugins

    return all_plugins


def list_plugins(group: Optional[str] = None) -> Dict[str, List[str]]:
    """List available plugins, optionally filtered by group."""
    if group:
        plugins = discover_entry_points(group)
        return {group: list(plugins.keys())}

    all_plugins = discover_all_plugins()
    return {group: list(plugins.keys()) for group, plugins in all_plugins.items()}


def load_plugin(plugin_info: PluginInfo) -> Type:
    """Load a plugin class from PluginInfo."""
    if plugin_info.loaded_class is None:
        try:
            module = importlib.import_module(plugin_info.module_path)
            plugin_info.loaded_class = getattr(module, plugin_info.class_name)
            logger.info(f"Loaded plugin class: {plugin_info.name} -> {plugin_info.loaded_class}")
        except Exception as e:
            logger.error(f"Failed to load plugin {plugin_info.name}: {e}")
            raise

    return plugin_info.loaded_class


def register_plugin(
    name: str,
    plugin_class: Type,
    group: str = "aiperf.services"
) -> None:
    """Register a plugin programmatically (for testing/development)."""
    # This is mainly for testing - in production, plugins should be registered via entry points
    logger.info(f"Programmatically registering plugin: {name} -> {plugin_class}")

    # Create a synthetic PluginInfo
    plugin_info = PluginInfo(
        name=name,
        module_path=plugin_class.__module__,
        class_name=plugin_class.__name__,
        entry_point_group=group,
        loaded_class=plugin_class
    )

    # This would need to be integrated with the container system
    # For now, just log the registration
    logger.debug(f"Registered plugin info: {plugin_info}")


def validate_plugin_structure(plugin_info: PluginInfo) -> bool:
    """Validate that a plugin has the expected structure."""
    try:
        plugin_class = load_plugin(plugin_info)

        # Basic validation - plugin should be a class
        if not isinstance(plugin_class, type):
            logger.error(f"Plugin {plugin_info.name} is not a class")
            return False

        # Plugin should have __init__ method
        if not hasattr(plugin_class, '__init__'):
            logger.error(f"Plugin {plugin_info.name} missing __init__ method")
            return False

        logger.debug(f"Plugin {plugin_info.name} structure validation passed")
        return True

    except Exception as e:
        logger.error(f"Plugin structure validation failed for {plugin_info.name}: {e}")
        return False


def get_plugin_metadata(plugin_info: PluginInfo) -> Dict[str, Any]:
    """Get metadata about a plugin."""
    try:
        plugin_class = load_plugin(plugin_info)

        metadata = {
            'name': plugin_info.name,
            'class_name': plugin_class.__name__,
            'module': plugin_class.__module__,
            'group': plugin_info.entry_point_group,
            'doc': plugin_class.__doc__,
        }

        # Add service_type if available (for services)
        if hasattr(plugin_class, 'service_type'):
            metadata['service_type'] = plugin_class.service_type

        # Add version if available
        if hasattr(plugin_class, '__version__'):
            metadata['version'] = plugin_class.__version__

        return metadata

    except Exception as e:
        logger.error(f"Failed to get metadata for plugin {plugin_info.name}: {e}")
        return {'name': plugin_info.name, 'error': str(e)}


def discover_plugins() -> Dict[str, Dict[str, PluginInfo]]:
    """Main function to discover all plugins."""
    return discover_all_plugins()
