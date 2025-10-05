# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""
Tests for Plugin Registry (AIP-001)

WHY TEST THIS:
- Registry is central plugin management hub
- Singleton pattern must work correctly
- Enable/disable functionality controls plugin usage
- Thread safety ensures correctness
- Integration with discovery and loading must be seamless

WHAT WE TEST:
- Singleton pattern implementation
- Discovery integration on initialization
- Loading plugins through registry
- Enable/disable functionality
- Plugin metadata retrieval
- Thread safety of registry operations
- Error handling and reporting

TESTING PHILOSOPHY:
We test the REGISTRY'S BEHAVIOR as an orchestrator, not the underlying
discovery/loading mechanisms (those have their own tests).
"""

import threading
from unittest.mock import MagicMock, patch

import pytest

from aiperf.plugins.registry import PluginRegistry, get_plugin_registry


class TestSingletonPattern:
    """
    Test singleton implementation.

    WHY TEST THIS: Registry must be singleton to maintain consistent
    state across application.
    """

    def test_registry_is_singleton(self, clear_registry_singleton):
        """
        WHY: Only one registry instance should exist.

        WHAT: Multiple instantiations return same object.
        """
        registry1 = PluginRegistry()
        registry2 = PluginRegistry()

        assert registry1 is registry2

    def test_registry_initialized_once(self, clear_registry_singleton):
        """
        WHY: Initialization should happen only once.

        WHAT: __init__ doesn't re-run on subsequent calls.
        """
        with patch("aiperf.plugins.discovery.PluginDiscovery.discover_all_plugins") as mock_discover:
            mock_discover.return_value = {}

            registry1 = PluginRegistry()
            registry2 = PluginRegistry()

            # Should only discover once
            assert mock_discover.call_count == 1

    def test_get_plugin_registry_returns_singleton(self, clear_registry_singleton):
        """
        WHY: Global function provides convenient access.

        WHAT: get_plugin_registry() returns singleton instance.
        """
        registry1 = get_plugin_registry()
        registry2 = get_plugin_registry()

        assert registry1 is registry2

    def test_singleton_thread_safe(self, clear_registry_singleton):
        """
        WHY: Multiple threads may access registry simultaneously.

        WHAT: Thread-safe singleton creation.
        """
        registries = []
        errors = []

        def create_registry():
            try:
                reg = PluginRegistry()
                registries.append(reg)
            except Exception as e:
                errors.append(e)

        # Create registry from multiple threads
        threads = [threading.Thread(target=create_registry) for _ in range(10)]

        for t in threads:
            t.start()

        for t in threads:
            t.join()

        # No errors
        assert len(errors) == 0

        # All registries are the same instance
        assert len(registries) == 10
        assert all(r is registries[0] for r in registries)


class TestRegistryInitialization:
    """
    Test registry initialization and discovery integration.

    WHY TEST THIS: Registry auto-discovers plugins on init.
    """

    def test_registry_discovers_plugins_on_init(
        self, clear_registry_singleton, clear_discovery_cache
    ):
        """
        WHY: Registry should discover plugins automatically.

        WHAT: Calls discover_all_plugins during initialization.
        """
        with patch("aiperf.plugins.discovery.PluginDiscovery.discover_all_plugins") as mock_discover:
            mock_discover.return_value = {}

            registry = PluginRegistry()

            mock_discover.assert_called_once()

    def test_registry_stores_discovered_plugins(
        self, clear_registry_singleton, clear_discovery_cache, mock_metric_entry_point
    ):
        """
        WHY: Registry must maintain discovered plugins.

        WHAT: get_discovered_plugins returns discovered plugins.
        """
        from aiperf.plugins.discovery import PluginMetadata

        mock_metadata = PluginMetadata(
            name="mock_metric",
            entry_point=mock_metric_entry_point,
            group="aiperf.metric",
            module_name="mock_plugin.metric",
            attr_name="MockMetricPlugin",
        )

        with patch("aiperf.plugins.discovery.PluginDiscovery.discover_all_plugins") as mock_discover:
            mock_discover.return_value = {"aiperf.metric": [mock_metadata]}

            registry = PluginRegistry()

            plugins = registry.get_discovered_plugins("aiperf.metric")
            assert len(plugins) == 1
            assert plugins[0].name == "mock_metric"


class TestLoadingPlugins:
    """
    Test plugin loading through registry.

    WHY TEST THIS: Registry orchestrates loading and validation.
    """

    def test_load_plugin_success(
        self,
        isolated_plugin_environment,
        mock_metric_entry_point,
        mock_plugin_classes,
    ):
        """
        WHY: Registry must load and validate plugins.

        WHAT: load_plugin returns validated plugin.
        """
        from aiperf.plugins.discovery import PluginMetadata

        mock_metadata = PluginMetadata(
            name="mock_metric",
            entry_point=mock_metric_entry_point,
            group="aiperf.metric",
            module_name="mock_plugin.metric",
            attr_name="MockMetricPlugin",
        )

        with patch("aiperf.plugins.discovery.PluginDiscovery.discover_all_plugins") as mock_discover:
            mock_discover.return_value = {"aiperf.metric": [mock_metadata]}

            registry = PluginRegistry()
            plugin = registry.load_plugin("aiperf.metric", "mock_metric")

            assert plugin is not None
            assert plugin == mock_plugin_classes["MockMetricPlugin"]

    def test_load_plugin_not_found(self, isolated_plugin_environment):
        """
        WHY: Should handle missing plugins gracefully.

        WHAT: Returns None when plugin not found.
        """
        with patch("aiperf.plugins.discovery.PluginDiscovery.discover_all_plugins") as mock_discover:
            mock_discover.return_value = {}

            registry = PluginRegistry()
            plugin = registry.load_plugin("aiperf.metric", "nonexistent")

            assert plugin is None

    def test_load_plugin_validation_failure(
        self, isolated_plugin_environment, invalid_plugin_entry_point
    ):
        """
        WHY: Invalid plugins should be rejected.

        WHAT: Returns None when validation fails.
        """
        from aiperf.plugins.discovery import PluginMetadata

        mock_metadata = PluginMetadata(
            name="invalid_metric",
            entry_point=invalid_plugin_entry_point,
            group="aiperf.metric",
            module_name="mock_plugin.invalid",
            attr_name="InvalidMetricPlugin",
        )

        with patch("aiperf.plugins.discovery.PluginDiscovery.discover_all_plugins") as mock_discover:
            mock_discover.return_value = {"aiperf.metric": [mock_metadata]}

            registry = PluginRegistry()
            plugin = registry.load_plugin("aiperf.metric", "invalid_metric")

            # Should fail validation
            assert plugin is None

    def test_load_all_plugins(
        self, isolated_plugin_environment, multiple_plugins_same_group
    ):
        """
        WHY: Need to load all plugins for a group.

        WHAT: load_all_plugins loads entire group.
        """
        with patch("aiperf.plugins.discovery.entry_points") as mock_ep:
            import sys

            if sys.version_info >= (3, 10):
                mock_ep.return_value = multiple_plugins_same_group
            else:
                mock_ep_obj = MagicMock()
                mock_ep_obj.select.return_value = multiple_plugins_same_group
                mock_ep.return_value = mock_ep_obj

            registry = PluginRegistry()
            plugins = registry.load_all_plugins("aiperf.metric")

            assert len(plugins) >= 1  # At least some plugins loaded


class TestEnableDisable:
    """
    Test enable/disable functionality.

    WHY TEST THIS: Enable/disable controls which plugins are active.
    """

    def test_plugins_enabled_by_default(
        self, isolated_plugin_environment, mock_metric_entry_point
    ):
        """
        WHY: Plugins should be usable by default.

        WHAT: is_enabled returns True without explicit enable.
        """
        from aiperf.plugins.discovery import PluginMetadata

        mock_metadata = PluginMetadata(
            name="mock_metric",
            entry_point=mock_metric_entry_point,
            group="aiperf.metric",
            module_name="mock_plugin.metric",
            attr_name="MockMetricPlugin",
        )

        with patch("aiperf.plugins.discovery.PluginDiscovery.discover_all_plugins") as mock_discover:
            mock_discover.return_value = {"aiperf.metric": [mock_metadata]}

            registry = PluginRegistry()

            assert registry.is_enabled("aiperf.metric", "mock_metric") is True

    def test_enable_plugin(self, isolated_plugin_environment):
        """
        WHY: Explicit enabling should work.

        WHAT: enable_plugin marks plugin as enabled.
        """
        with patch("aiperf.plugins.discovery.PluginDiscovery.discover_all_plugins") as mock_discover:
            mock_discover.return_value = {}

            registry = PluginRegistry()
            registry.enable_plugin("aiperf.metric", "test_plugin")

            assert registry.is_enabled("aiperf.metric", "test_plugin") is True

    def test_disable_plugin(self, isolated_plugin_environment):
        """
        WHY: Must be able to disable plugins.

        WHAT: disable_plugin marks plugin as disabled.
        """
        with patch("aiperf.plugins.discovery.PluginDiscovery.discover_all_plugins") as mock_discover:
            mock_discover.return_value = {}

            registry = PluginRegistry()

            # Enable then disable
            registry.enable_plugin("aiperf.metric", "test_plugin")
            assert registry.is_enabled("aiperf.metric", "test_plugin") is True

            registry.disable_plugin("aiperf.metric", "test_plugin")
            assert registry.is_enabled("aiperf.metric", "test_plugin") is False

    def test_enable_disable_multiple_plugins(self, isolated_plugin_environment):
        """
        WHY: Multiple plugins can be enabled/disabled independently.

        WHAT: Each plugin tracks its own enabled state.
        """
        with patch("aiperf.plugins.discovery.PluginDiscovery.discover_all_plugins") as mock_discover:
            mock_discover.return_value = {}

            registry = PluginRegistry()

            registry.enable_plugin("aiperf.metric", "plugin1")
            registry.enable_plugin("aiperf.metric", "plugin2")

            assert registry.is_enabled("aiperf.metric", "plugin1") is True
            assert registry.is_enabled("aiperf.metric", "plugin2") is True

            registry.disable_plugin("aiperf.metric", "plugin1")

            assert registry.is_enabled("aiperf.metric", "plugin1") is False
            assert registry.is_enabled("aiperf.metric", "plugin2") is True

    def test_get_enabled_plugins(self, isolated_plugin_environment):
        """
        WHY: Need to list which plugins are enabled.

        WHAT: get_enabled_plugins returns list of enabled names.
        """
        with patch("aiperf.plugins.discovery.PluginDiscovery.discover_all_plugins") as mock_discover:
            mock_discover.return_value = {}

            registry = PluginRegistry()

            registry.enable_plugin("aiperf.metric", "plugin1")
            registry.enable_plugin("aiperf.metric", "plugin2")
            registry.enable_plugin("aiperf.metric", "plugin3")
            registry.disable_plugin("aiperf.metric", "plugin2")

            enabled = registry.get_enabled_plugins("aiperf.metric")

            assert "plugin1" in enabled
            assert "plugin2" not in enabled
            assert "plugin3" in enabled

    def test_get_enabled_plugins_all_by_default(
        self, isolated_plugin_environment, mock_metric_entry_point
    ):
        """
        WHY: Without explicit enable list, all should be enabled.

        WHAT: Returns all discovered plugins when none explicitly enabled.
        """
        from aiperf.plugins.discovery import PluginMetadata

        mock_metadata = PluginMetadata(
            name="mock_metric",
            entry_point=mock_metric_entry_point,
            group="aiperf.metric",
            module_name="mock_plugin.metric",
            attr_name="MockMetricPlugin",
        )

        with patch("aiperf.plugins.discovery.PluginDiscovery.discover_all_plugins") as mock_discover:
            mock_discover.return_value = {"aiperf.metric": [mock_metadata]}

            registry = PluginRegistry()

            enabled = registry.get_enabled_plugins("aiperf.metric")

            assert "mock_metric" in enabled


class TestMetadataRetrieval:
    """
    Test plugin metadata retrieval.

    WHY TEST THIS: Metadata provides plugin information.
    """

    def test_get_plugin_metadata(
        self, isolated_plugin_environment, mock_metric_entry_point
    ):
        """
        WHY: Need to inspect plugin metadata.

        WHAT: get_plugin_metadata returns metadata dict.
        """
        from aiperf.plugins.discovery import PluginMetadata

        mock_metadata = PluginMetadata(
            name="mock_metric",
            entry_point=mock_metric_entry_point,
            group="aiperf.metric",
            module_name="mock_plugin.metric",
            attr_name="MockMetricPlugin",
        )

        with patch("aiperf.plugins.discovery.PluginDiscovery.discover_all_plugins") as mock_discover:
            mock_discover.return_value = {"aiperf.metric": [mock_metadata]}

            registry = PluginRegistry()
            metadata = registry.get_plugin_metadata("aiperf.metric", "mock_metric")

            assert metadata is not None
            assert metadata["name"] == "mock_metric"
            assert metadata["aip_version"] == "001"

    def test_get_plugin_metadata_not_found(self, isolated_plugin_environment):
        """
        WHY: Should handle missing plugins gracefully.

        WHAT: Returns None when plugin not found.
        """
        with patch("aiperf.plugins.discovery.PluginDiscovery.discover_all_plugins") as mock_discover:
            mock_discover.return_value = {}

            registry = PluginRegistry()
            metadata = registry.get_plugin_metadata("aiperf.metric", "nonexistent")

            assert metadata is None

    def test_get_plugin_metadata_no_metadata_method(
        self, isolated_plugin_environment, no_metadata_plugin_entry_point
    ):
        """
        WHY: Plugins without metadata should be handled.

        WHAT: Returns None when plugin lacks metadata method.
        """
        from aiperf.plugins.discovery import PluginMetadata

        mock_metadata = PluginMetadata(
            name="no_metadata",
            entry_point=no_metadata_plugin_entry_point,
            group="aiperf.metric",
            module_name="mock_plugin.nometadata",
            attr_name="NoMetadataPlugin",
        )

        with patch("aiperf.plugins.discovery.PluginDiscovery.discover_all_plugins") as mock_discover:
            mock_discover.return_value = {"aiperf.metric": [mock_metadata]}

            registry = PluginRegistry()
            # Plugin won't load due to validation failure
            metadata = registry.get_plugin_metadata("aiperf.metric", "no_metadata")

            assert metadata is None


class TestErrorHandling:
    """
    Test error handling in registry.

    WHY TEST THIS: Registry must handle errors gracefully.
    """

    def test_get_load_errors(
        self, isolated_plugin_environment, failing_entry_point
    ):
        """
        WHY: Need visibility into load failures.

        WHAT: get_load_errors returns error dict.
        """
        from aiperf.plugins.discovery import PluginMetadata

        mock_metadata = PluginMetadata(
            name="failing_plugin",
            entry_point=failing_entry_point,
            group="aiperf.metric",
            module_name="nonexistent.module",
            attr_name="NonexistentClass",
        )

        with patch("aiperf.plugins.discovery.PluginDiscovery.discover_all_plugins") as mock_discover:
            mock_discover.return_value = {"aiperf.metric": [mock_metadata]}

            registry = PluginRegistry()
            registry.load_plugin("aiperf.metric", "failing_plugin")

            errors = registry.get_load_errors()

            assert "aiperf.metric:failing_plugin" in errors


class TestThreadSafety:
    """
    Test thread safety of registry operations.

    WHY TEST THIS: Registry accessed from multiple threads.
    """

    def test_concurrent_plugin_loads(
        self, isolated_plugin_environment, mock_metric_entry_point
    ):
        """
        WHY: Multiple threads may load plugins simultaneously.

        WHAT: Concurrent loads work correctly.
        """
        from aiperf.plugins.discovery import PluginMetadata

        mock_metadata = PluginMetadata(
            name="mock_metric",
            entry_point=mock_metric_entry_point,
            group="aiperf.metric",
            module_name="mock_plugin.metric",
            attr_name="MockMetricPlugin",
        )

        with patch("aiperf.plugins.discovery.PluginDiscovery.discover_all_plugins") as mock_discover:
            mock_discover.return_value = {"aiperf.metric": [mock_metadata]}

            registry = PluginRegistry()

            results = []
            errors = []

            def load_plugin():
                try:
                    plugin = registry.load_plugin("aiperf.metric", "mock_metric")
                    results.append(plugin)
                except Exception as e:
                    errors.append(e)

            threads = [threading.Thread(target=load_plugin) for _ in range(10)]

            for t in threads:
                t.start()

            for t in threads:
                t.join()

            assert len(errors) == 0
            assert len(results) == 10
            # All should be same instance (cached)
            assert all(r is results[0] for r in results)

    def test_concurrent_enable_disable(self, isolated_plugin_environment):
        """
        WHY: Enable/disable may happen from multiple threads.

        WHAT: Concurrent enable/disable operations work correctly.
        """
        with patch("aiperf.plugins.discovery.PluginDiscovery.discover_all_plugins") as mock_discover:
            mock_discover.return_value = {}

            registry = PluginRegistry()

            errors = []

            def enable_plugins():
                try:
                    for i in range(10):
                        registry.enable_plugin("aiperf.metric", f"plugin_{i}")
                except Exception as e:
                    errors.append(e)

            def disable_plugins():
                try:
                    for i in range(10):
                        registry.disable_plugin("aiperf.metric", f"plugin_{i}")
                except Exception as e:
                    errors.append(e)

            threads = []
            for _ in range(5):
                threads.append(threading.Thread(target=enable_plugins))
                threads.append(threading.Thread(target=disable_plugins))

            for t in threads:
                t.start()

            for t in threads:
                t.join()

            # Should complete without errors
            assert len(errors) == 0


class TestRegistryDiscoveryIntegration:
    """
    Test integration between registry and discovery.

    WHY TEST THIS: Registry builds on discovery system.
    """

    def test_registry_uses_discovery_cache(
        self, isolated_plugin_environment, mock_metric_entry_point
    ):
        """
        WHY: Should leverage discovery caching for performance.

        WHAT: Uses cached discovery results.
        """
        from aiperf.plugins.discovery import PluginMetadata

        mock_metadata = PluginMetadata(
            name="mock_metric",
            entry_point=mock_metric_entry_point,
            group="aiperf.metric",
            module_name="mock_plugin.metric",
            attr_name="MockMetricPlugin",
        )

        with patch("aiperf.plugins.discovery.PluginDiscovery.discover_all_plugins") as mock_discover:
            mock_discover.return_value = {"aiperf.metric": [mock_metadata]}

            registry = PluginRegistry()

            # Access discovered plugins multiple times
            plugins1 = registry.get_discovered_plugins("aiperf.metric")
            plugins2 = registry.get_discovered_plugins("aiperf.metric")

            # Discovery should only happen once (during init)
            assert mock_discover.call_count == 1
