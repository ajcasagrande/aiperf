# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""
Plugin Integration for MetricRegistry (AIP-001)

Discovers and registers metric plugins via entry points.
Separated from metric_registry.py to avoid circular imports.
"""

from aiperf.common.aiperf_logger import AIPerfLogger

logger = AIPerfLogger(__name__)


def discover_and_register_metric_plugins(metric_registry_class):
    """
    Discover and register metric plugins.

    Args:
        metric_registry_class: The MetricRegistry class to register plugins with
    """
    try:
        from aiperf.plugins.discovery import PluginDiscovery, PluginLoader
        from aiperf.plugins.validator import PluginValidator

        logger.info("Discovering metric plugins via entry points (AIP-001)...")

        # Initialize plugin system
        loader = PluginLoader()
        validator = PluginValidator()

        # Discover metric plugins
        discovered = PluginDiscovery.discover_plugins_by_group("aiperf.metric")

        if not discovered:
            logger.debug("No metric plugins found")
            return

        # Load and register each plugin
        registered = 0
        failed = 0

        for metadata in discovered:
            try:
                # Load plugin
                plugin_class = loader.load_plugin(metadata)
                if plugin_class is None:
                    failed += 1
                    continue

                # Validate plugin
                if not validator.validate_plugin(plugin_class, "aiperf.metric"):
                    logger.warning(f"Plugin '{metadata.name}' failed validation")
                    failed += 1
                    continue

                # Check for tag conflicts
                if hasattr(plugin_class, "tag"):
                    existing = metric_registry_class._metrics_map.get(plugin_class.tag)
                    if existing:
                        logger.warning(
                            f"Plugin metric tag '{plugin_class.tag}' conflicts with "
                            f"existing metric {existing.__name__}. Skipping plugin."
                        )
                        failed += 1
                        continue

                # Register plugin with MetricRegistry
                metric_registry_class.register_metric(plugin_class)
                registered += 1
                logger.info(f"Registered plugin metric: {plugin_class.tag}")

            except Exception as e:
                logger.error(f"Error loading plugin '{metadata.name}': {e}")
                failed += 1

        logger.info(
            f"Plugin discovery complete: {registered} registered, {failed} failed"
        )

    except ImportError:
        # Plugin system not available (optional dependency)
        logger.debug("Plugin system not available")
    except Exception as e:
        logger.error(f"Error in plugin discovery: {e}")
