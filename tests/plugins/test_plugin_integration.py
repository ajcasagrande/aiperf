# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""
Integration Tests for Plugin System (AIP-001)

WHY TEST THIS:
- Integration tests verify the entire plugin system works together
- Real-world plugin workflows must function correctly
- Performance characteristics must meet requirements
- Multiple plugins must coexist without interference

WHAT WE TEST:
- End-to-end plugin discovery, loading, and execution
- Real plugin usage in AIPerf context
- Multiple plugins of same and different types
- Plugin discovery performance
- Full lifecycle: discover -> load -> validate -> use

TESTING PHILOSOPHY:
Integration tests verify COMPLETE WORKFLOWS, not isolated components.
We test the plugin system AS A USER would experience it.
"""

import time
from unittest.mock import MagicMock, patch

import pytest

from aiperf.plugins import (
    PluginDiscovery,
    PluginLoader,
    PluginRegistry,
    discover_plugins,
    load_plugin,
)


class TestEndToEndPluginLifecycle:
    """
    Test complete plugin lifecycle from discovery to execution.

    WHY TEST THIS: Users need the full workflow to work seamlessly.
    """

    def test_discover_load_execute_metric_plugin(
        self, isolated_plugin_environment, mock_metric_entry_point
    ):
        """
        WHY: Most common workflow is discover -> load -> use.

        WHAT: Complete lifecycle works for metric plugin.
        """
        from aiperf.plugins.discovery import PluginMetadata

        mock_metadata = PluginMetadata(
            name="mock_metric",
            entry_point=mock_metric_entry_point,
            group="aiperf.metric",
            module_name="mock_plugin.metric",
            attr_name="MockMetricPlugin",
        )

        with patch(
            "aiperf.plugins.discovery.PluginDiscovery.discover_all_plugins"
        ) as mock_discover:
            mock_discover.return_value = {"aiperf.metric": [mock_metadata]}

            # 1. Discover
            discovered = PluginDiscovery.discover_all_plugins()
            assert "aiperf.metric" in discovered

            # 2. Load
            loader = PluginLoader()
            plugin_class = loader.load_plugin(discovered["aiperf.metric"][0])
            assert plugin_class is not None

            # 3. Instantiate and use
            plugin_instance = plugin_class()
            assert plugin_instance.tag == "mock_metric"

            # 4. Get metadata
            metadata = plugin_class.plugin_metadata()
            assert metadata["name"] == "mock_metric"
            assert metadata["aip_version"] == "001"

    def test_registry_provides_complete_workflow(
        self, isolated_plugin_environment, mock_metric_entry_point
    ):
        """
        WHY: Registry simplifies plugin usage.

        WHAT: Registry handles discover -> load -> validate automatically.
        """
        from aiperf.plugins.discovery import PluginMetadata

        mock_metadata = PluginMetadata(
            name="mock_metric",
            entry_point=mock_metric_entry_point,
            group="aiperf.metric",
            module_name="mock_plugin.metric",
            attr_name="MockMetricPlugin",
        )

        with patch(
            "aiperf.plugins.discovery.PluginDiscovery.discover_all_plugins"
        ) as mock_discover:
            mock_discover.return_value = {"aiperf.metric": [mock_metadata]}

            # Registry does everything
            registry = PluginRegistry()

            # Get discovered plugins
            discovered = registry.get_discovered_plugins("aiperf.metric")
            assert len(discovered) == 1

            # Load and validate
            plugin = registry.load_plugin("aiperf.metric", "mock_metric")
            assert plugin is not None

            # Get metadata
            metadata = registry.get_plugin_metadata("aiperf.metric", "mock_metric")
            assert metadata["aip_version"] == "001"

    def test_convenience_functions_workflow(
        self, clear_discovery_cache, mock_metric_entry_point
    ):
        """
        WHY: Convenience functions provide simplest API.

        WHAT: Module-level functions work for common cases.
        """
        with patch("aiperf.plugins.discovery.entry_points") as mock_ep:
            mock_ep.return_value = [mock_metric_entry_point]

            # Discover
            plugins = discover_plugins("aiperf.metric")
            assert len(plugins) == 1

            # Load
            plugin = load_plugin("aiperf.metric", "mock_metric")
            assert plugin is not None

            # Use
            instance = plugin()
            assert instance.tag == "mock_metric"


class TestMultiplePluginsCoexistence:
    """
    Test multiple plugins working together.

    WHY TEST THIS: Real systems have many plugins. They must not interfere.
    """

    def test_multiple_plugins_same_group(
        self, isolated_plugin_environment, multiple_plugins_same_group
    ):
        """
        WHY: Multiple metrics (or other plugin type) common.

        WHAT: All plugins in group load and work independently.
        """
        with patch("aiperf.plugins.discovery.entry_points") as mock_ep:
            mock_ep.return_value = multiple_plugins_same_group

            registry = PluginRegistry()

            # Load all
            plugins = registry.load_all_plugins("aiperf.metric")

            # All should load
            assert len(plugins) >= 1

            # Each should be independent
            plugin_tags = set()
            for _name, plugin_class in plugins.items():
                instance = plugin_class()
                plugin_tags.add(instance.tag)

            # All tags should be unique
            assert len(plugin_tags) == len(plugins)

    def test_multiple_plugin_types_coexist(
        self, isolated_plugin_environment, all_mock_entry_points
    ):
        """
        WHY: Full system has all plugin types active.

        WHAT: Different plugin types don't interfere.
        """
        with patch("aiperf.plugins.discovery.entry_points") as mock_ep:

            def mock_entry_points_call(group=None):
                if group:
                    return all_mock_entry_points.get(group, [])
                mock_obj = MagicMock()
                mock_obj.select = lambda group: all_mock_entry_points.get(group, [])
                return mock_obj

            mock_ep.side_effect = mock_entry_points_call

            registry = PluginRegistry()

            # Load plugins from different groups
            metric_plugins = registry.load_all_plugins("aiperf.metric")
            endpoint_plugins = registry.load_all_plugins("aiperf.endpoint")
            exporter_plugins = registry.load_all_plugins("aiperf.data_exporter")

            # Each group should have plugins
            assert len(metric_plugins) >= 1
            assert len(endpoint_plugins) >= 1
            assert len(exporter_plugins) >= 1

            # Plugins from different groups are different
            metric_plugin = list(metric_plugins.values())[0]
            endpoint_plugin = list(endpoint_plugins.values())[0]

            assert metric_plugin is not endpoint_plugin

    def test_enable_disable_selective_loading(
        self, isolated_plugin_environment, multiple_plugins_same_group
    ):
        """
        WHY: Users may want to enable only certain plugins.

        WHAT: Enable/disable controls which plugins are active.
        """
        with patch("aiperf.plugins.discovery.entry_points") as mock_ep:
            mock_ep.return_value = multiple_plugins_same_group

            registry = PluginRegistry()

            # Enable only specific plugins
            registry.enable_plugin("aiperf.metric", "mock_metric")
            registry.enable_plugin("aiperf.metric", "mock_metric_2")
            # mock_metric_3 not enabled

            enabled = registry.get_enabled_plugins("aiperf.metric")

            assert "mock_metric" in enabled
            assert "mock_metric_2" in enabled
            # Note: get_enabled_plugins returns the whitelist when explicitly set


class TestPluginExecutionInContext:
    """
    Test plugins executing in AIPerf context.

    WHY TEST THIS: Plugins must work within AIPerf's architecture.
    """

    def test_metric_plugin_computes_values(
        self, isolated_plugin_environment, mock_metric_entry_point
    ):
        """
        WHY: Metric plugins must compute values correctly.

        WHAT: Plugin _parse_record method works.
        """
        from aiperf.plugins.discovery import PluginMetadata

        mock_metadata = PluginMetadata(
            name="mock_metric",
            entry_point=mock_metric_entry_point,
            group="aiperf.metric",
            module_name="mock_plugin.metric",
            attr_name="MockMetricPlugin",
        )

        with patch(
            "aiperf.plugins.discovery.PluginDiscovery.discover_all_plugins"
        ) as mock_discover:
            mock_discover.return_value = {"aiperf.metric": [mock_metadata]}

            registry = PluginRegistry()
            plugin_class = registry.load_plugin("aiperf.metric", "mock_metric")

            # Instantiate and use
            plugin = plugin_class()

            # Create mock record
            from aiperf.metrics.metric_dicts import MetricRecordDict

            mock_record = MagicMock()
            record_metrics = MetricRecordDict()

            # Compute value
            value = plugin._parse_record(mock_record, record_metrics)

            assert value == 42.0

    @pytest.mark.asyncio
    async def test_endpoint_plugin_sends_requests(
        self, isolated_plugin_environment, mock_endpoint_entry_point
    ):
        """
        WHY: Endpoint plugins must handle requests.

        WHAT: Plugin send_request method works.
        """
        from aiperf.plugins.discovery import PluginMetadata

        mock_metadata = PluginMetadata(
            name="mock_endpoint",
            entry_point=mock_endpoint_entry_point,
            group="aiperf.endpoint",
            module_name="mock_plugin.endpoint",
            attr_name="MockEndpointPlugin",
        )

        with patch(
            "aiperf.plugins.discovery.PluginDiscovery.discover_all_plugins"
        ) as mock_discover:
            mock_discover.return_value = {"aiperf.endpoint": [mock_metadata]}

            registry = PluginRegistry()
            plugin_class = registry.load_plugin("aiperf.endpoint", "mock_endpoint")

            # Instantiate and use
            plugin = plugin_class()

            # Send request
            response = await plugin.send_request(
                endpoint_info="http://test", payload={"test": "data"}
            )

            assert response["status"] == "success"

    @pytest.mark.asyncio
    async def test_transport_plugin_lifecycle(
        self, isolated_plugin_environment, mock_transport_entry_point
    ):
        """
        WHY: Transport plugins have connect/send/close lifecycle.

        WHAT: Full lifecycle methods work.
        """
        from aiperf.plugins.discovery import PluginMetadata

        mock_metadata = PluginMetadata(
            name="mock_transport",
            entry_point=mock_transport_entry_point,
            group="aiperf.transport",
            module_name="mock_plugin.transport",
            attr_name="MockTransportPlugin",
        )

        with patch(
            "aiperf.plugins.discovery.PluginDiscovery.discover_all_plugins"
        ) as mock_discover:
            mock_discover.return_value = {"aiperf.transport": [mock_metadata]}

            registry = PluginRegistry()
            plugin_class = registry.load_plugin("aiperf.transport", "mock_transport")

            # Instantiate
            plugin = plugin_class()

            # Lifecycle
            await plugin.connect("tcp://localhost:5555")
            response = await plugin.send({"test": "request"})
            await plugin.close()

            assert response["response"] == "mock_data"


class TestPluginDiscoveryPerformance:
    """
    Test plugin discovery performance.

    WHY TEST THIS: Discovery must have minimal overhead (AIP-001 requirement).
    """

    @pytest.mark.performance
    def test_discovery_is_fast(self, clear_discovery_cache):
        """
        WHY: Discovery should not slow down startup.

        WHAT: Discovery completes quickly.
        """
        with patch("aiperf.plugins.discovery.entry_points") as mock_ep:
            # Simulate moderate number of plugins
            mock_plugins = []
            for i in range(50):
                ep = MagicMock()
                ep.name = f"plugin_{i}"
                ep.value = f"module_{i}:Plugin_{i}"
                mock_plugins.append(ep)

            mock_ep.return_value = mock_plugins

            start_time = time.time()
            PluginDiscovery.discover_all_plugins()
            end_time = time.time()

            discovery_time = end_time - start_time

            # Discovery should be very fast (< 100ms even with many plugins)
            assert discovery_time < 0.1

    @pytest.mark.performance
    def test_cached_discovery_is_instant(
        self, clear_discovery_cache, mock_metric_entry_point
    ):
        """
        WHY: Caching should make repeated discovery nearly instant.

        WHAT: Second discovery much faster than first.
        """
        with patch("aiperf.plugins.discovery.entry_points") as mock_ep:
            mock_ep.return_value = [mock_metric_entry_point]

            # First discovery
            start_time = time.time()
            PluginDiscovery.discover_all_plugins()
            first_time = time.time() - start_time

            # Second discovery (cached)
            start_time = time.time()
            PluginDiscovery.discover_all_plugins()
            second_time = time.time() - start_time

            # Cached access should be much faster
            assert second_time < first_time / 10  # At least 10x faster


class TestErrorRecovery:
    """
    Test error handling and recovery.

    WHY TEST THIS: System must be resilient to plugin failures.
    """

    def test_one_failing_plugin_doesnt_break_others(
        self, isolated_plugin_environment, mock_metric_entry_point, failing_entry_point
    ):
        """
        WHY: One bad plugin shouldn't break the system.

        WHAT: Other plugins continue working.
        """
        from aiperf.plugins.discovery import PluginMetadata

        valid_metadata = PluginMetadata(
            name="mock_metric",
            entry_point=mock_metric_entry_point,
            group="aiperf.metric",
            module_name="mock_plugin.metric",
            attr_name="MockMetricPlugin",
        )

        failing_metadata = PluginMetadata(
            name="failing_plugin",
            entry_point=failing_entry_point,
            group="aiperf.metric",
            module_name="nonexistent.module",
            attr_name="NonexistentClass",
        )

        with patch(
            "aiperf.plugins.discovery.PluginDiscovery.discover_all_plugins"
        ) as mock_discover:
            mock_discover.return_value = {
                "aiperf.metric": [valid_metadata, failing_metadata]
            }

            registry = PluginRegistry()

            # Load all plugins
            plugins = registry.load_all_plugins("aiperf.metric")

            # Valid plugin should load
            assert "mock_metric" in plugins

            # Failing plugin should not be in results
            assert "failing_plugin" not in plugins

            # Can still use valid plugin
            valid_plugin = plugins["mock_metric"]
            instance = valid_plugin()
            assert instance.tag == "mock_metric"

    def test_validation_failure_tracked(
        self, isolated_plugin_environment, invalid_plugin_entry_point
    ):
        """
        WHY: Need visibility into why plugins fail.

        WHAT: Validation failures are tracked.
        """
        from aiperf.plugins.discovery import PluginMetadata

        mock_metadata = PluginMetadata(
            name="invalid_metric",
            entry_point=invalid_plugin_entry_point,
            group="aiperf.metric",
            module_name="mock_plugin.invalid",
            attr_name="InvalidMetricPlugin",
        )

        with patch(
            "aiperf.plugins.discovery.PluginDiscovery.discover_all_plugins"
        ) as mock_discover:
            mock_discover.return_value = {"aiperf.metric": [mock_metadata]}

            registry = PluginRegistry()

            # Try to load invalid plugin
            plugin = registry.load_plugin("aiperf.metric", "invalid_metric")

            # Should fail
            assert plugin is None


class TestPluginSystemAPI:
    """
    Test public API of plugin system.

    WHY TEST THIS: Public API must be stable and documented.
    """

    def test_all_public_exports_available(self):
        """
        WHY: Documented API must be importable.

        WHAT: All __all__ exports work.
        """
        from aiperf.plugins import (
            CollectorPluginProtocol,
            DataExporterPluginProtocol,
            EndpointPluginProtocol,
            MetricPluginProtocol,
            PluginDiscovery,
            PluginLoader,
            PluginMetadata,
            PluginRegistry,
            ProcessorPluginProtocol,
            TransportPluginProtocol,
            discover_plugins,
            load_plugin,
        )

        # All should be importable
        assert PluginDiscovery is not None
        assert PluginLoader is not None
        assert PluginMetadata is not None
        assert discover_plugins is not None
        assert load_plugin is not None
        assert PluginRegistry is not None
        assert MetricPluginProtocol is not None
        assert EndpointPluginProtocol is not None
        assert DataExporterPluginProtocol is not None
        assert TransportPluginProtocol is not None
        assert ProcessorPluginProtocol is not None
        assert CollectorPluginProtocol is not None

    def test_plugin_groups_constant_available(self):
        """
        WHY: Plugin authors need to know valid groups.

        WHAT: PLUGIN_GROUPS constant is accessible.
        """
        from aiperf.plugins.discovery import PLUGIN_GROUPS

        assert "metric" in PLUGIN_GROUPS
        assert "endpoint" in PLUGIN_GROUPS
        assert "data_exporter" in PLUGIN_GROUPS
        assert "transport" in PLUGIN_GROUPS
        assert "processor" in PLUGIN_GROUPS
        assert "collector" in PLUGIN_GROUPS


class TestRealWorldScenarios:
    """
    Test realistic usage scenarios.

    WHY TEST THIS: Verify system works for actual use cases.
    """

    def test_user_adds_custom_metric(
        self, isolated_plugin_environment, mock_metric_entry_point
    ):
        """
        WHY: Adding custom metrics is primary use case.

        WHAT: End-to-end workflow for custom metric.
        """
        from aiperf.plugins.discovery import PluginMetadata

        # User installs package with custom metric
        mock_metadata = PluginMetadata(
            name="custom_latency",
            entry_point=mock_metric_entry_point,
            group="aiperf.metric",
            module_name="user_plugin.metrics",
            attr_name="CustomLatencyMetric",
        )

        with patch(
            "aiperf.plugins.discovery.PluginDiscovery.discover_all_plugins"
        ) as mock_discover:
            mock_discover.return_value = {"aiperf.metric": [mock_metadata]}

            # AIPerf discovers it automatically
            registry = PluginRegistry()
            discovered = registry.get_discovered_plugins("aiperf.metric")

            assert any(p.name == "custom_latency" for p in discovered)

            # User can load and use it
            plugin = registry.load_plugin("aiperf.metric", "custom_latency")
            assert plugin is not None

            # Instantiate and use
            metric = plugin()
            assert hasattr(metric, "_parse_record")

    def test_user_lists_available_plugins(self, isolated_plugin_environment):
        """
        WHY: Users need to see what plugins are installed.

        WHAT: Can enumerate all available plugins.
        """
        with patch(
            "aiperf.plugins.discovery.PluginDiscovery.discover_all_plugins"
        ) as mock_discover:
            mock_discover.return_value = {}

            registry = PluginRegistry()

            # List all plugin types
            from aiperf.plugins.discovery import PLUGIN_GROUPS

            for group in PLUGIN_GROUPS.values():
                plugins = registry.get_discovered_plugins(group)
                # Should return list (may be empty)
                assert isinstance(plugins, list)

    def test_programmatic_plugin_control(
        self, isolated_plugin_environment, multiple_plugins_same_group
    ):
        """
        WHY: Advanced users may want programmatic control.

        WHAT: Can enable/disable plugins programmatically.
        """
        with patch("aiperf.plugins.discovery.entry_points") as mock_ep:
            mock_ep.return_value = multiple_plugins_same_group

            registry = PluginRegistry()

            # Disable all but one
            all_plugins = registry.get_discovered_plugins("aiperf.metric")
            for plugin_meta in all_plugins:
                if plugin_meta.name != "mock_metric":
                    registry.disable_plugin("aiperf.metric", plugin_meta.name)

            # Enable the one we want
            registry.enable_plugin("aiperf.metric", "mock_metric")

            # Check what's enabled
            enabled = registry.get_enabled_plugins("aiperf.metric")
            assert "mock_metric" in enabled
