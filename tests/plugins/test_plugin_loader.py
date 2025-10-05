# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""
Tests for Plugin Loader (AIP-001)

WHY TEST THIS:
- Lazy loading is critical for performance (don't load unused plugins)
- Caching prevents redundant loads
- Error tracking helps debug plugin issues
- Thread safety ensures correctness in concurrent scenarios

WHAT WE TEST:
- Lazy loading of individual plugins
- Loading all plugins for a group
- Caching of successfully loaded plugins
- Error tracking for failed loads
- Thread safety of loader operations
- Convenience functions work correctly

TESTING PHILOSOPHY:
We test BEHAVIORS (does it load the plugin?) not IMPLEMENTATION.
We verify the plugin is callable/usable, not internal state.
"""

import threading
from unittest.mock import patch

from aiperf.plugins.discovery import PluginLoader, PluginMetadata, load_plugin


class TestBasicLoading:
    """
    Test basic plugin loading functionality.

    WHY TEST THIS: Core loading must work or plugins are useless.
    """

    def test_load_plugin_success(self, mock_metric_entry_point):
        """
        WHY: Must successfully load valid plugins.

        WHAT: load_plugin returns the plugin class/function.
        """
        loader = PluginLoader()
        metadata = PluginMetadata(
            name="mock_metric",
            entry_point=mock_metric_entry_point,
            group="aiperf.metric",
            module_name="mock_plugin.metric",
            attr_name="MockMetricPlugin",
        )

        result = loader.load_plugin(metadata)

        assert result is not None
        # Should return the class itself
        assert hasattr(result, "plugin_metadata")
        # Can instantiate it
        instance = result()
        assert instance.tag == "mock_metric"

    def test_load_plugin_returns_none_on_failure(self, failing_entry_point):
        """
        WHY: Failed loads should return None, not crash.

        WHAT: Returns None when entry point fails to load.
        """
        loader = PluginLoader()
        metadata = PluginMetadata(
            name="failing_plugin",
            entry_point=failing_entry_point,
            group="aiperf.metric",
            module_name="nonexistent.module",
            attr_name="NonexistentClass",
        )

        result = loader.load_plugin(metadata)

        assert result is None

    def test_load_plugin_tracks_errors(self, failing_entry_point):
        """
        WHY: Error tracking helps debug plugin issues.

        WHAT: Stores exceptions for failed loads.
        """
        loader = PluginLoader()
        metadata = PluginMetadata(
            name="failing_plugin",
            entry_point=failing_entry_point,
            group="aiperf.metric",
            module_name="nonexistent.module",
            attr_name="NonexistentClass",
        )

        loader.load_plugin(metadata)

        errors = loader.get_load_errors()
        assert "aiperf.metric:failing_plugin" in errors
        assert isinstance(errors["aiperf.metric:failing_plugin"], ImportError)

    def test_load_plugin_marks_metadata_as_loaded(self, mock_metric_entry_point):
        """
        WHY: Tracking loaded state helps debugging and inspection.

        WHAT: Sets is_loaded=True on successful load.
        """
        loader = PluginLoader()
        metadata = PluginMetadata(
            name="mock_metric",
            entry_point=mock_metric_entry_point,
            group="aiperf.metric",
            module_name="mock_plugin.metric",
            attr_name="MockMetricPlugin",
        )

        assert metadata.is_loaded is False

        loader.load_plugin(metadata)

        assert metadata.is_loaded is True


class TestLazyLoading:
    """
    Test lazy loading behavior.

    WHY TEST THIS: Lazy loading is a key AIP-001 requirement for
    minimal startup overhead.
    """

    def test_plugin_not_loaded_on_discovery(self, mock_metric_entry_point):
        """
        WHY: Discovery should not trigger loading (lazy loading).

        WHAT: Entry point .load() not called during discovery.
        """
        metadata = PluginMetadata(
            name="mock_metric",
            entry_point=mock_metric_entry_point,
            group="aiperf.metric",
            module_name="mock_plugin.metric",
            attr_name="MockMetricPlugin",
        )

        # Entry point should not have been loaded yet
        # (metadata creation doesn't trigger load)
        assert metadata.is_loaded is False

    def test_plugin_loaded_only_when_requested(self, mock_metric_entry_point):
        """
        WHY: Plugins should load only when explicitly requested.

        WHAT: .load() called only when load_plugin() invoked.
        """
        loader = PluginLoader()
        metadata = PluginMetadata(
            name="mock_metric",
            entry_point=mock_metric_entry_point,
            group="aiperf.metric",
            module_name="mock_plugin.metric",
            attr_name="MockMetricPlugin",
        )

        # Not loaded yet
        mock_metric_entry_point.load.assert_not_called()

        # Load it
        loader.load_plugin(metadata)

        # Now it should be loaded
        mock_metric_entry_point.load.assert_called_once()


class TestCachingBehavior:
    """
    Test plugin caching.

    WHY TEST THIS: Caching prevents redundant loads and ensures same
    instance is returned consistently.
    """

    def test_load_plugin_cached(self, mock_metric_entry_point):
        """
        WHY: Loading same plugin twice should return cached result.

        WHAT: Returns same object on subsequent loads.
        """
        loader = PluginLoader()
        metadata = PluginMetadata(
            name="mock_metric",
            entry_point=mock_metric_entry_point,
            group="aiperf.metric",
            module_name="mock_plugin.metric",
            attr_name="MockMetricPlugin",
        )

        # Load twice
        result1 = loader.load_plugin(metadata)
        result2 = loader.load_plugin(metadata)

        # Should be same object
        assert result1 is result2

        # Entry point load should only be called once
        assert mock_metric_entry_point.load.call_count == 1

    def test_different_plugins_not_cached_together(
        self, mock_metric_entry_point, mock_endpoint_entry_point
    ):
        """
        WHY: Different plugins must not interfere with each other.

        WHAT: Each plugin cached separately by group:name key.
        """
        loader = PluginLoader()

        metric_metadata = PluginMetadata(
            name="mock_metric",
            entry_point=mock_metric_entry_point,
            group="aiperf.metric",
            module_name="mock_plugin.metric",
            attr_name="MockMetricPlugin",
        )

        endpoint_metadata = PluginMetadata(
            name="mock_endpoint",
            entry_point=mock_endpoint_entry_point,
            group="aiperf.endpoint",
            module_name="mock_plugin.endpoint",
            attr_name="MockEndpointPlugin",
        )

        metric_plugin = loader.load_plugin(metric_metadata)
        endpoint_plugin = loader.load_plugin(endpoint_metadata)

        # Should be different classes
        assert metric_plugin is not endpoint_plugin
        assert hasattr(metric_plugin, "tag")
        assert hasattr(endpoint_plugin, "endpoint_metadata")

    def test_failed_load_cached_as_none(self, failing_entry_point):
        """
        WHY: Shouldn't retry failed loads on every call.

        WHAT: Failed loads return None immediately on retry.
        """
        loader = PluginLoader()
        metadata = PluginMetadata(
            name="failing_plugin",
            entry_point=failing_entry_point,
            group="aiperf.metric",
            module_name="nonexistent.module",
            attr_name="NonexistentClass",
        )

        # First load attempt
        result1 = loader.load_plugin(metadata)
        assert result1 is None

        # Second load attempt
        result2 = loader.load_plugin(metadata)
        assert result2 is None

        # Should only attempt load once (cached failure)
        assert failing_entry_point.load.call_count == 1


class TestLoadAllForGroup:
    """
    Test loading all plugins for a group.

    WHY TEST THIS: Common pattern is to load all plugins of a type.
    """

    def test_load_all_for_group(
        self, clear_discovery_cache, multiple_plugins_same_group
    ):
        """
        WHY: Need to load all plugins of a type at once.

        WHAT: Loads all discovered plugins for group.
        """
        loader = PluginLoader()

        with patch("aiperf.plugins.discovery.entry_points") as mock_ep:
            mock_ep.return_value = multiple_plugins_same_group

            result = loader.load_all_for_group("aiperf.metric")

            assert len(result) == 3
            assert "mock_metric" in result
            assert "mock_metric_2" in result
            assert "mock_metric_3" in result

            # All should be loaded
            for plugin in result.values():
                assert plugin is not None

    def test_load_all_for_group_empty(self, clear_discovery_cache):
        """
        WHY: Loading from empty group should not crash.

        WHAT: Returns empty dict when no plugins in group.
        """
        loader = PluginLoader()

        with patch("aiperf.plugins.discovery.entry_points") as mock_ep:
            mock_ep.return_value = []

            result = loader.load_all_for_group("aiperf.metric")

            assert result == {}

    def test_load_all_skips_failed_plugins(
        self, clear_discovery_cache, mock_metric_entry_point, failing_entry_point
    ):
        """
        WHY: Some plugins may fail to load. Shouldn't prevent loading others.

        WHAT: Returns only successfully loaded plugins.
        """
        loader = PluginLoader()

        with patch("aiperf.plugins.discovery.entry_points") as mock_ep:
            mock_ep.return_value = [mock_metric_entry_point, failing_entry_point]

            result = loader.load_all_for_group("aiperf.metric")

            # Should have loaded the working plugin
            assert "mock_metric" in result
            # Should not have the failing plugin
            assert "failing_plugin" not in result


class TestConvenienceFunction:
    """
    Test module-level convenience function.

    WHY TEST THIS: load_plugin() function provides simpler API.
    """

    def test_load_plugin_function(self, clear_discovery_cache, mock_metric_entry_point):
        """
        WHY: Convenience function simplifies common use case.

        WHAT: Module-level load_plugin() works correctly.
        """
        with patch("aiperf.plugins.discovery.entry_points") as mock_ep:
            mock_ep.return_value = [mock_metric_entry_point]

            result = load_plugin("aiperf.metric", "mock_metric")

            assert result is not None
            assert hasattr(result, "plugin_metadata")

    def test_load_plugin_function_not_found(self, clear_discovery_cache):
        """
        WHY: Should handle missing plugins gracefully.

        WHAT: Returns None when plugin not found.
        """
        with patch("aiperf.plugins.discovery.entry_points") as mock_ep:
            mock_ep.return_value = []

            result = load_plugin("aiperf.metric", "nonexistent")

            assert result is None


class TestThreadSafety:
    """
    Test thread safety of plugin loading.

    WHY TEST THIS: AIPerf may load plugins from multiple threads.
    Loader must handle concurrent access safely.
    """

    def test_concurrent_loads_same_plugin(self, mock_metric_entry_point):
        """
        WHY: Multiple threads may try to load same plugin.

        WHAT: Concurrent loads return same cached instance.
        """
        loader = PluginLoader()
        metadata = PluginMetadata(
            name="mock_metric",
            entry_point=mock_metric_entry_point,
            group="aiperf.metric",
            module_name="mock_plugin.metric",
            attr_name="MockMetricPlugin",
        )

        results = []
        errors = []

        def load_plugin_thread():
            try:
                result = loader.load_plugin(metadata)
                results.append(result)
            except Exception as e:
                errors.append(e)

        # Start multiple threads
        threads = [threading.Thread(target=load_plugin_thread) for _ in range(10)]

        for t in threads:
            t.start()

        for t in threads:
            t.join()

        # No errors
        assert len(errors) == 0

        # All results should be the same object (cached)
        assert len(results) == 10
        assert all(r is results[0] for r in results)

    def test_concurrent_loads_different_plugins(
        self, mock_metric_entry_point, mock_endpoint_entry_point
    ):
        """
        WHY: Multiple threads may load different plugins.

        WHAT: Concurrent loads of different plugins work correctly.
        """
        loader = PluginLoader()

        metric_metadata = PluginMetadata(
            name="mock_metric",
            entry_point=mock_metric_entry_point,
            group="aiperf.metric",
            module_name="mock_plugin.metric",
            attr_name="MockMetricPlugin",
        )

        endpoint_metadata = PluginMetadata(
            name="mock_endpoint",
            entry_point=mock_endpoint_entry_point,
            group="aiperf.endpoint",
            module_name="mock_plugin.endpoint",
            attr_name="MockEndpointPlugin",
        )

        metric_results = []
        endpoint_results = []
        errors = []

        def load_metric():
            try:
                result = loader.load_plugin(metric_metadata)
                metric_results.append(result)
            except Exception as e:
                errors.append(e)

        def load_endpoint():
            try:
                result = loader.load_plugin(endpoint_metadata)
                endpoint_results.append(result)
            except Exception as e:
                errors.append(e)

        # Start threads for both plugins
        threads = []
        for _ in range(5):
            threads.append(threading.Thread(target=load_metric))
            threads.append(threading.Thread(target=load_endpoint))

        for t in threads:
            t.start()

        for t in threads:
            t.join()

        # No errors
        assert len(errors) == 0

        # Each plugin loaded correctly
        assert len(metric_results) == 5
        assert len(endpoint_results) == 5

        # All metric results are same
        assert all(r is metric_results[0] for r in metric_results)

        # All endpoint results are same
        assert all(r is endpoint_results[0] for r in endpoint_results)

        # But metric and endpoint are different
        assert metric_results[0] is not endpoint_results[0]


class TestErrorRecording:
    """
    Test error recording and retrieval.

    WHY TEST THIS: Error information helps debug plugin issues.
    """

    def test_get_load_errors_empty_initially(self):
        """
        WHY: New loader should have no errors.

        WHAT: get_load_errors returns empty dict initially.
        """
        loader = PluginLoader()
        errors = loader.get_load_errors()

        assert errors == {}

    def test_get_load_errors_records_failures(self, failing_entry_point):
        """
        WHY: Need to see what went wrong with failed loads.

        WHAT: Records exception for each failed load.
        """
        loader = PluginLoader()
        metadata = PluginMetadata(
            name="failing_plugin",
            entry_point=failing_entry_point,
            group="aiperf.metric",
            module_name="nonexistent.module",
            attr_name="NonexistentClass",
        )

        loader.load_plugin(metadata)

        errors = loader.get_load_errors()
        assert len(errors) == 1
        assert "aiperf.metric:failing_plugin" in errors
        assert "Module not found" in str(errors["aiperf.metric:failing_plugin"])

    def test_get_load_errors_returns_copy(self, failing_entry_point):
        """
        WHY: Returned errors dict should be safe to modify.

        WHAT: Returns copy of errors, not internal dict.
        """
        loader = PluginLoader()
        metadata = PluginMetadata(
            name="failing_plugin",
            entry_point=failing_entry_point,
            group="aiperf.metric",
            module_name="nonexistent.module",
            attr_name="NonexistentClass",
        )

        loader.load_plugin(metadata)

        errors1 = loader.get_load_errors()
        errors2 = loader.get_load_errors()

        # Should be different objects
        assert errors1 is not errors2

        # Modifying one shouldn't affect the other
        errors1["test"] = Exception("test")
        assert "test" not in errors2


class TestPluginTypes:
    """
    Test loading different plugin types.

    WHY TEST THIS: Ensure loader works with all plugin types defined
    in AIP-001.
    """

    def test_load_metric_plugin(self, mock_metric_entry_point):
        """WHY: Metric plugins are most common type."""
        loader = PluginLoader()
        metadata = PluginMetadata(
            name="mock_metric",
            entry_point=mock_metric_entry_point,
            group="aiperf.metric",
            module_name="mock_plugin.metric",
            attr_name="MockMetricPlugin",
        )

        plugin = loader.load_plugin(metadata)
        assert plugin is not None
        assert hasattr(plugin, "tag")

    def test_load_endpoint_plugin(self, mock_endpoint_entry_point):
        """WHY: Endpoint plugins add API format support."""
        loader = PluginLoader()
        metadata = PluginMetadata(
            name="mock_endpoint",
            entry_point=mock_endpoint_entry_point,
            group="aiperf.endpoint",
            module_name="mock_plugin.endpoint",
            attr_name="MockEndpointPlugin",
        )

        plugin = loader.load_plugin(metadata)
        assert plugin is not None
        assert hasattr(plugin, "endpoint_metadata")

    def test_load_exporter_plugin(self, mock_exporter_entry_point):
        """WHY: Data exporter plugins add export formats."""
        loader = PluginLoader()
        metadata = PluginMetadata(
            name="mock_exporter",
            entry_point=mock_exporter_entry_point,
            group="aiperf.data_exporter",
            module_name="mock_plugin.exporter",
            attr_name="MockDataExporterPlugin",
        )

        plugin = loader.load_plugin(metadata)
        assert plugin is not None
        assert hasattr(plugin, "get_export_info")

    def test_load_transport_plugin(self, mock_transport_entry_point):
        """WHY: Transport plugins add communication protocols."""
        loader = PluginLoader()
        metadata = PluginMetadata(
            name="mock_transport",
            entry_point=mock_transport_entry_point,
            group="aiperf.transport",
            module_name="mock_plugin.transport",
            attr_name="MockTransportPlugin",
        )

        plugin = loader.load_plugin(metadata)
        assert plugin is not None
        assert hasattr(plugin, "connect")

    def test_load_processor_plugin(self, mock_processor_entry_point):
        """WHY: Processor plugins add data processing."""
        loader = PluginLoader()
        metadata = PluginMetadata(
            name="mock_processor",
            entry_point=mock_processor_entry_point,
            group="aiperf.processor",
            module_name="mock_plugin.processor",
            attr_name="MockProcessorPlugin",
        )

        plugin = loader.load_plugin(metadata)
        assert plugin is not None
        assert hasattr(plugin, "process")

    def test_load_collector_plugin(self, mock_collector_entry_point):
        """WHY: Collector plugins add metrics collection."""
        loader = PluginLoader()
        metadata = PluginMetadata(
            name="mock_collector",
            entry_point=mock_collector_entry_point,
            group="aiperf.collector",
            module_name="mock_plugin.collector",
            attr_name="MockCollectorPlugin",
        )

        plugin = loader.load_plugin(metadata)
        assert plugin is not None
        assert hasattr(plugin, "collect")
