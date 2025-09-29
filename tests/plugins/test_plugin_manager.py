# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Tests for the plugin manager."""

import pytest

from aiperf.common.enums import EndpointType
from aiperf.common.plugins.manager import PluginNotFoundError


class TestRequestConverterPluginManager:
    """Test the RequestConverterPluginManager."""

    def test_register_plugin(self, plugin_manager, test_chat_plugin):
        """Test registering a plugin."""
        plugin_manager.register_plugin(test_chat_plugin)

        plugins = plugin_manager.pm.get_plugins()
        assert test_chat_plugin in plugins

    def test_register_plugin_class(self, plugin_manager):
        """Test registering a plugin class."""
        from .conftest import TestChatPlugin

        instance = plugin_manager.register_plugin_class(TestChatPlugin)
        assert isinstance(instance, TestChatPlugin)

        plugins = plugin_manager.pm.get_plugins()
        assert instance in plugins

    def test_unregister_plugin(self, plugin_manager, test_chat_plugin):
        """Test unregistering a plugin."""
        plugin_manager.register_plugin(test_chat_plugin)
        plugin_manager.unregister_plugin(test_chat_plugin)

        plugins = plugin_manager.pm.get_plugins()
        assert test_chat_plugin not in plugins

    def test_get_plugin_for_endpoint_type(self, plugin_manager, test_chat_plugin):
        """Test getting a plugin for an endpoint type."""
        plugin_manager.register_plugin(test_chat_plugin)

        plugin = plugin_manager.get_plugin_for_endpoint_type(EndpointType.CHAT)
        assert plugin == test_chat_plugin

    def test_get_plugin_for_unsupported_endpoint_type(self, plugin_manager):
        """Test getting a plugin for an unsupported endpoint type."""
        with pytest.raises(PluginNotFoundError):
            plugin_manager.get_plugin_for_endpoint_type(EndpointType.CHAT)

    def test_plugin_priority_selection(self, plugin_manager):
        """Test that higher priority plugins are selected."""
        from .conftest import TestChatPlugin

        # Create two plugins with different priorities
        low_priority_plugin = TestChatPlugin()
        low_priority_plugin.get_plugin_priority = lambda: 10

        high_priority_plugin = TestChatPlugin()
        high_priority_plugin.get_plugin_priority = lambda: 20

        plugin_manager.register_plugin(low_priority_plugin)
        plugin_manager.register_plugin(high_priority_plugin)

        selected_plugin = plugin_manager.get_plugin_for_endpoint_type(EndpointType.CHAT)
        assert selected_plugin == high_priority_plugin

    def test_multi_endpoint_plugin(self, plugin_manager, test_multi_endpoint_plugin):
        """Test a plugin that supports multiple endpoint types."""
        plugin_manager.register_plugin(test_multi_endpoint_plugin)

        # Test both supported endpoint types
        plugin1 = plugin_manager.get_plugin_for_endpoint_type(EndpointType.EMBEDDINGS)
        plugin2 = plugin_manager.get_plugin_for_endpoint_type(EndpointType.RANKINGS)

        assert plugin1 == test_multi_endpoint_plugin
        assert plugin2 == test_multi_endpoint_plugin

    async def test_format_payload(
        self, plugin_manager, test_chat_plugin, sample_model_endpoint, sample_turn
    ):
        """Test formatting a payload through the plugin manager."""
        plugin_manager.register_plugin(test_chat_plugin)

        result = await plugin_manager.format_payload(
            EndpointType.CHAT, sample_model_endpoint, sample_turn
        )

        assert result is not None
        assert result["test_plugin"] is True
        assert "messages" in result

    async def test_format_payload_no_plugin(
        self, plugin_manager, sample_model_endpoint, sample_turn
    ):
        """Test formatting a payload when no plugin is available."""
        with pytest.raises(PluginNotFoundError):
            await plugin_manager.format_payload(
                EndpointType.CHAT, sample_model_endpoint, sample_turn
            )

    def test_list_plugins(
        self, plugin_manager, test_chat_plugin, test_multi_endpoint_plugin
    ):
        """Test listing plugins."""
        plugin_manager.register_plugin(test_chat_plugin)
        plugin_manager.register_plugin(test_multi_endpoint_plugin)

        plugins_info = plugin_manager.list_plugins()

        assert len(plugins_info) == 2

        # Check that we have the expected plugin names and endpoint types
        plugin_names = [name for name, _ in plugins_info]
        assert "Test Chat Plugin" in plugin_names
        assert "Test Multi-Endpoint Plugin" in plugin_names

    def test_cache_invalidation(self, plugin_manager, test_chat_plugin):
        """Test that cache is properly invalidated when plugins change."""
        plugin_manager.register_plugin(test_chat_plugin)

        # First call should cache the result
        plugin1 = plugin_manager.get_plugin_for_endpoint_type(EndpointType.CHAT)
        assert plugin1 == test_chat_plugin

        # Unregister plugin should invalidate cache
        plugin_manager.unregister_plugin(test_chat_plugin)

        # Should raise error since no plugin available
        with pytest.raises(PluginNotFoundError):
            plugin_manager.get_plugin_for_endpoint_type(EndpointType.CHAT)
