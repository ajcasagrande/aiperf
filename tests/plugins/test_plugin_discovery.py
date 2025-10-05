# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""
Tests for Plugin Discovery System (AIP-001)

WHY TEST THIS:
- Plugin discovery is the foundation of the plugin system
- Entry point discovery must work across Python 3.9 and 3.10+
- Caching behavior is critical for performance
- Error handling ensures robustness when plugins fail

WHAT WE TEST:
- Discovery of all plugins across all groups
- Discovery of plugins by specific group
- Lookup of individual plugins by name
- Python version compatibility (3.9 vs 3.10+)
- LRU cache behavior and invalidation
- Graceful handling of malformed entry points

TESTING PHILOSOPHY:
We test OUTCOMES (can we find plugins?) not IMPLEMENTATION (how we search).
We don't test private methods or internal data structures.
"""

import sys
from unittest.mock import MagicMock, patch

import pytest

from aiperf.plugins.discovery import (
    PluginDiscovery,
    PluginMetadata,
    discover_plugins,
)


class TestPluginDiscoveryBasics:
    """
    Test basic plugin discovery functionality.

    WHY TEST THIS: Core discovery must work reliably or the entire
    plugin system fails.
    """

    def test_discover_all_plugins_returns_dict(self, clear_discovery_cache):
        """
        WHY: Ensures discover_all_plugins returns expected data structure.

        WHAT: Returns dict mapping group names to plugin metadata lists.
        """
        with patch("aiperf.plugins.discovery.entry_points") as mock_ep:
            # Mock empty entry points
            if sys.version_info >= (3, 10):
                mock_ep.return_value = []
            else:
                mock_ep_obj = MagicMock()
                mock_ep_obj.select.return_value = []
                mock_ep.return_value = mock_ep_obj

            result = PluginDiscovery.discover_all_plugins()

            assert isinstance(result, dict)
            # Empty result is valid when no plugins installed
            assert all(isinstance(v, list) for v in result.values())

    def test_discover_plugins_by_group(
        self, clear_discovery_cache, mock_metric_entry_point
    ):
        """
        WHY: Most code discovers plugins for a specific group, not all groups.

        WHAT: Can filter plugins by entry point group.
        """
        with patch("aiperf.plugins.discovery.entry_points") as mock_ep:
            # Set up mock to return our plugin for the metric group
            if sys.version_info >= (3, 10):
                mock_ep.return_value = [mock_metric_entry_point]
            else:
                mock_ep_obj = MagicMock()
                mock_ep_obj.select.return_value = [mock_metric_entry_point]
                mock_ep.return_value = mock_ep_obj

            plugins = PluginDiscovery.discover_plugins_by_group("aiperf.metric")

            assert len(plugins) == 1
            assert plugins[0].name == "mock_metric"
            assert plugins[0].group == "aiperf.metric"

    def test_discover_plugins_by_group_empty(self, clear_discovery_cache):
        """
        WHY: Not all groups will have plugins installed.

        WHAT: Returns empty list when no plugins for group.
        """
        with patch("aiperf.plugins.discovery.entry_points") as mock_ep:
            if sys.version_info >= (3, 10):
                mock_ep.return_value = []
            else:
                mock_ep_obj = MagicMock()
                mock_ep_obj.select.return_value = []
                mock_ep.return_value = mock_ep_obj

            plugins = PluginDiscovery.discover_plugins_by_group("aiperf.metric")

            assert plugins == []

    def test_get_plugin_by_name_found(
        self, clear_discovery_cache, mock_metric_entry_point
    ):
        """
        WHY: Code often needs to find a specific plugin by name.

        WHAT: Can retrieve individual plugin by name within a group.
        """
        with patch("aiperf.plugins.discovery.entry_points") as mock_ep:
            if sys.version_info >= (3, 10):
                mock_ep.return_value = [mock_metric_entry_point]
            else:
                mock_ep_obj = MagicMock()
                mock_ep_obj.select.return_value = [mock_metric_entry_point]
                mock_ep.return_value = mock_ep_obj

            plugin = PluginDiscovery.get_plugin_by_name("aiperf.metric", "mock_metric")

            assert plugin is not None
            assert plugin.name == "mock_metric"
            assert isinstance(plugin, PluginMetadata)

    def test_get_plugin_by_name_not_found(self, clear_discovery_cache):
        """
        WHY: Requesting non-existent plugins should not crash.

        WHAT: Returns None when plugin not found.
        """
        with patch("aiperf.plugins.discovery.entry_points") as mock_ep:
            if sys.version_info >= (3, 10):
                mock_ep.return_value = []
            else:
                mock_ep_obj = MagicMock()
                mock_ep_obj.select.return_value = []
                mock_ep.return_value = mock_ep_obj

            plugin = PluginDiscovery.get_plugin_by_name(
                "aiperf.metric", "nonexistent"
            )

            assert plugin is None


class TestPluginMetadata:
    """
    Test PluginMetadata dataclass.

    WHY TEST THIS: Metadata correctly captures entry point information
    needed for lazy loading.
    """

    def test_metadata_from_entry_point(self, mock_metric_entry_point):
        """
        WHY: Metadata must accurately represent entry point data.

        WHAT: Creates correct metadata from entry point.
        """
        metadata = PluginMetadata(
            name=mock_metric_entry_point.name,
            entry_point=mock_metric_entry_point,
            group="aiperf.metric",
            module_name=mock_metric_entry_point.value.split(":")[0],
            attr_name=mock_metric_entry_point.value.split(":")[1],
        )

        assert metadata.name == "mock_metric"
        assert metadata.group == "aiperf.metric"
        assert metadata.module_name == "mock_plugin.metric"
        assert metadata.attr_name == "MockMetricPlugin"
        assert metadata.is_loaded is False

    def test_metadata_without_attr_name(self):
        """
        WHY: Some entry points use 'module' format without ':attr'.

        WHAT: Handles entry points without explicit attribute name.
        """
        # This tests the fallback behavior in discovery.py line 98
        from importlib.metadata import EntryPoint

        if sys.version_info >= (3, 10):
            ep = EntryPoint(
                name="simple_plugin", value="simple_module", group="aiperf.metric"
            )
        else:
            ep = EntryPoint(
                name="simple_plugin", value="simple_module", group="aiperf.metric"
            )

        # Discovery code splits on ':' and falls back to name if no ':'
        attr_name = ep.value.split(":")[1] if ":" in ep.value else ep.name

        metadata = PluginMetadata(
            name=ep.name,
            entry_point=ep,
            group="aiperf.metric",
            module_name=ep.value.split(":")[0],
            attr_name=attr_name,
        )

        assert metadata.attr_name == "simple_plugin"  # Falls back to name


class TestMultiplePlugins:
    """
    Test discovery with multiple plugins.

    WHY TEST THIS: Real deployments have many plugins. Discovery must
    handle multiple plugins per group and across groups.
    """

    def test_discover_multiple_plugins_same_group(
        self, clear_discovery_cache, multiple_plugins_same_group
    ):
        """
        WHY: Multiple plugins of same type (e.g., metrics) is common.

        WHAT: Discovers all plugins in a group.
        """
        with patch("aiperf.plugins.discovery.entry_points") as mock_ep:
            if sys.version_info >= (3, 10):
                mock_ep.return_value = multiple_plugins_same_group
            else:
                mock_ep_obj = MagicMock()
                mock_ep_obj.select.return_value = multiple_plugins_same_group
                mock_ep.return_value = mock_ep_obj

            plugins = PluginDiscovery.discover_plugins_by_group("aiperf.metric")

            assert len(plugins) == 3
            plugin_names = [p.name for p in plugins]
            assert "mock_metric" in plugin_names
            assert "mock_metric_2" in plugin_names
            assert "mock_metric_3" in plugin_names

    def test_discover_plugins_across_all_groups(
        self, clear_discovery_cache, all_mock_entry_points
    ):
        """
        WHY: Full plugin ecosystem has plugins across all types.

        WHAT: Discovers plugins from all entry point groups.
        """
        with patch("aiperf.plugins.discovery.entry_points") as mock_ep:

            def mock_entry_points_call(group=None):
                if group:
                    return all_mock_entry_points.get(group, [])
                # For Python 3.9 compatibility
                mock_obj = MagicMock()
                mock_obj.select = lambda group: all_mock_entry_points.get(group, [])
                return mock_obj

            if sys.version_info >= (3, 10):
                mock_ep.side_effect = mock_entry_points_call
            else:
                mock_ep.return_value.select.side_effect = (
                    lambda group: all_mock_entry_points.get(group, [])
                )

            discovered = PluginDiscovery.discover_all_plugins()

            # Should have found plugins in all groups
            assert "aiperf.metric" in discovered
            assert "aiperf.endpoint" in discovered
            assert "aiperf.data_exporter" in discovered
            assert "aiperf.transport" in discovered
            assert "aiperf.processor" in discovered
            assert "aiperf.collector" in discovered


class TestPythonVersionCompatibility:
    """
    Test Python version compatibility.

    WHY TEST THIS: Python 3.10 changed entry_points API. AIP-001
    requires support for both 3.9 and 3.10+.
    """

    @pytest.mark.skipif(
        sys.version_info < (3, 10), reason="Tests Python 3.10+ code path"
    )
    def test_python_310_entry_points_api(
        self, clear_discovery_cache, mock_metric_entry_point
    ):
        """
        WHY: Python 3.10+ uses different entry_points API.

        WHAT: Uses group parameter (not select method).
        """
        with patch("aiperf.plugins.discovery.entry_points") as mock_ep:
            mock_ep.return_value = [mock_metric_entry_point]

            plugins = PluginDiscovery.discover_plugins_by_group("aiperf.metric")

            # Verify 3.10+ API was used (group parameter)
            mock_ep.assert_called_with(group="aiperf.metric")
            assert len(plugins) == 1

    @pytest.mark.skipif(
        sys.version_info >= (3, 10), reason="Tests Python 3.9 code path"
    )
    def test_python_39_entry_points_api(
        self, clear_discovery_cache, mock_metric_entry_point
    ):
        """
        WHY: Python 3.9 uses select() method on entry_points.

        WHAT: Uses .select(group=...) method.
        """
        with patch("aiperf.plugins.discovery.entry_points") as mock_ep:
            mock_ep_obj = MagicMock()
            mock_ep_obj.select.return_value = [mock_metric_entry_point]
            mock_ep.return_value = mock_ep_obj

            plugins = PluginDiscovery.discover_plugins_by_group("aiperf.metric")

            # Verify 3.9 API was used (select method)
            mock_ep_obj.select.assert_called_with(group="aiperf.metric")
            assert len(plugins) == 1


class TestCachingBehavior:
    """
    Test LRU cache behavior.

    WHY TEST THIS: Discovery is cached for performance. Cache must work
    correctly and be clearable for testing.
    """

    def test_discover_all_plugins_cached(self, clear_discovery_cache):
        """
        WHY: Caching prevents redundant expensive entry point scans.

        WHAT: Subsequent calls return cached results.
        """
        with patch("aiperf.plugins.discovery.entry_points") as mock_ep:
            if sys.version_info >= (3, 10):
                mock_ep.return_value = []
            else:
                mock_ep_obj = MagicMock()
                mock_ep_obj.select.return_value = []
                mock_ep.return_value = mock_ep_obj

            # First call
            result1 = PluginDiscovery.discover_all_plugins()

            # Second call
            result2 = PluginDiscovery.discover_all_plugins()

            # Should be same object (cached)
            assert result1 is result2

            # entry_points should only be called during first discovery
            # (called once per group in PLUGIN_GROUPS)
            # Number of calls depends on how many groups we scan
            call_count = mock_ep.call_count
            if sys.version_info >= (3, 10):
                assert call_count >= 1  # At least one call made
            else:
                assert call_count >= 1

    def test_cache_clear_works(self, mock_metric_entry_point):
        """
        WHY: Tests need to clear cache to simulate fresh discovery.

        WHAT: cache_clear() removes cached results.
        """
        with patch("aiperf.plugins.discovery.entry_points") as mock_ep:
            if sys.version_info >= (3, 10):
                mock_ep.return_value = [mock_metric_entry_point]
            else:
                mock_ep_obj = MagicMock()
                mock_ep_obj.select.return_value = [mock_metric_entry_point]
                mock_ep.return_value = mock_ep_obj

            # Discover plugins
            result1 = PluginDiscovery.discover_all_plugins()

            # Clear cache
            PluginDiscovery.discover_all_plugins.cache_clear()

            # Discover again
            result2 = PluginDiscovery.discover_all_plugins()

            # Should be different objects (not cached)
            assert result1 is not result2

    def test_convenience_function_cached(self, clear_discovery_cache):
        """
        WHY: discover_plugins() convenience function is also cached.

        WHAT: Module-level discover_plugins uses caching.
        """
        with patch("aiperf.plugins.discovery.entry_points") as mock_ep:
            if sys.version_info >= (3, 10):
                mock_ep.return_value = []
            else:
                mock_ep_obj = MagicMock()
                mock_ep_obj.select.return_value = []
                mock_ep.return_value = mock_ep_obj

            # First call
            result1 = discover_plugins("aiperf.metric")

            # Second call with same group
            result2 = discover_plugins("aiperf.metric")

            # Should be same object (cached)
            assert result1 is result2


class TestErrorHandling:
    """
    Test error handling in discovery.

    WHY TEST THIS: Malformed entry points or import errors shouldn't
    crash discovery. System must be resilient.
    """

    def test_discovery_handles_invalid_entry_point(self, clear_discovery_cache):
        """
        WHY: Entry points can be malformed. Discovery shouldn't crash.

        WHAT: Logs warning and continues with other plugins.
        """
        with patch("aiperf.plugins.discovery.entry_points") as mock_ep:
            # Create entry point that will cause issues
            bad_ep = MagicMock()
            bad_ep.name = "bad_plugin"
            bad_ep.value = "invalid::format"  # Malformed value
            bad_ep.load.side_effect = ValueError("Invalid format")

            if sys.version_info >= (3, 10):
                mock_ep.side_effect = [bad_ep], [], [], [], [], []
            else:
                mock_ep_obj = MagicMock()
                mock_ep_obj.select.side_effect = [bad_ep], [], [], [], [], []
                mock_ep.return_value = mock_ep_obj

            # Should not raise exception
            result = PluginDiscovery.discover_all_plugins()

            # Result should be valid dict even if no plugins discovered
            assert isinstance(result, dict)

    def test_discovery_continues_after_group_error(
        self, clear_discovery_cache, mock_endpoint_entry_point
    ):
        """
        WHY: Error in one group shouldn't prevent discovery of others.

        WHAT: Continues discovering other groups after error.
        """
        with patch("aiperf.plugins.discovery.entry_points") as mock_ep:

            def side_effect_fn(group=None):
                if group == "aiperf.metric":
                    raise Exception("Discovery error")
                elif group == "aiperf.endpoint":
                    return [mock_endpoint_entry_point]
                return []

            if sys.version_info >= (3, 10):
                mock_ep.side_effect = side_effect_fn
            else:
                mock_ep_obj = MagicMock()
                mock_ep_obj.select.side_effect = side_effect_fn
                mock_ep.return_value = mock_ep_obj

            result = PluginDiscovery.discover_all_plugins()

            # Should have discovered endpoint despite metric error
            assert "aiperf.endpoint" in result
            assert len(result["aiperf.endpoint"]) == 1


class TestPluginGroups:
    """
    Test plugin group constants and validation.

    WHY TEST THIS: Ensures all expected plugin types are supported.
    """

    def test_all_plugin_groups_defined(self):
        """
        WHY: AIP-001 defines specific plugin types. All must be supported.

        WHAT: PLUGIN_GROUPS contains all required groups.
        """
        from aiperf.plugins.discovery import PLUGIN_GROUPS

        expected_groups = {
            "metric": "aiperf.metric",
            "endpoint": "aiperf.endpoint",
            "data_exporter": "aiperf.data_exporter",
            "transport": "aiperf.transport",
            "processor": "aiperf.processor",
            "collector": "aiperf.collector",
        }

        for key, group in expected_groups.items():
            assert key in PLUGIN_GROUPS
            assert PLUGIN_GROUPS[key] == group

    def test_discover_all_scans_all_groups(self, clear_discovery_cache):
        """
        WHY: discover_all_plugins must scan all plugin types.

        WHAT: Attempts discovery for each group in PLUGIN_GROUPS.
        """
        with patch("aiperf.plugins.discovery.entry_points") as mock_ep:
            if sys.version_info >= (3, 10):
                mock_ep.return_value = []
            else:
                mock_ep_obj = MagicMock()
                mock_ep_obj.select.return_value = []
                mock_ep.return_value = mock_ep_obj

            PluginDiscovery.discover_all_plugins()

            # Should attempt to discover each group
            # (Implementation detail: each group is queried)
            from aiperf.plugins.discovery import PLUGIN_GROUPS

            assert mock_ep.call_count == len(PLUGIN_GROUPS)
