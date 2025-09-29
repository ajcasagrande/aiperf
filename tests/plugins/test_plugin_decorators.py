# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Tests for plugin decorators and base classes."""

import pytest

from aiperf.common.enums import EndpointType
from aiperf.common.plugins.base import (
    BaseRequestConverterPlugin,
    request_converter_plugin,
)


class TestRequestConverterPluginDecorator:
    """Test the request_converter_plugin decorator."""

    def test_single_endpoint_type_decorator(self):
        """Test decorator with single endpoint type."""

        @request_converter_plugin(
            endpoint_types=EndpointType.CHAT,
            name="Test Single Plugin",
            priority=10,
            auto_register=False,
        )
        class TestSinglePlugin:
            async def format_payload(self, endpoint_type, model_endpoint, turn):
                return {"test": True}

        plugin = TestSinglePlugin()

        assert plugin.get_plugin_name() == "Test Single Plugin"
        assert plugin.get_plugin_priority() == 10
        assert plugin.get_supported_endpoint_types() == [EndpointType.CHAT]
        assert plugin.can_handle_endpoint_type(EndpointType.CHAT) is True
        assert plugin.can_handle_endpoint_type(EndpointType.EMBEDDINGS) is False

    def test_multiple_endpoint_types_decorator(self):
        """Test decorator with multiple endpoint types."""

        @request_converter_plugin(
            endpoint_types=[EndpointType.CHAT, EndpointType.COMPLETIONS],
            name="Test Multi Plugin",
            priority=20,
            auto_register=False,
        )
        class TestMultiPlugin:
            async def format_payload(self, endpoint_type, model_endpoint, turn):
                return {"test": True}

        plugin = TestMultiPlugin()

        assert plugin.get_plugin_name() == "Test Multi Plugin"
        assert plugin.get_plugin_priority() == 20

        supported_types = plugin.get_supported_endpoint_types()
        assert EndpointType.CHAT in supported_types
        assert EndpointType.COMPLETIONS in supported_types
        assert len(supported_types) == 2

        assert plugin.can_handle_endpoint_type(EndpointType.CHAT) is True
        assert plugin.can_handle_endpoint_type(EndpointType.COMPLETIONS) is True
        assert plugin.can_handle_endpoint_type(EndpointType.EMBEDDINGS) is False

    def test_decorator_defaults(self):
        """Test decorator with default values."""

        @request_converter_plugin(endpoint_types=EndpointType.CHAT, auto_register=False)
        class TestDefaultsPlugin:
            async def format_payload(self, endpoint_type, model_endpoint, turn):
                return {"test": True}

        plugin = TestDefaultsPlugin()

        assert plugin.get_plugin_name() == "TestDefaultsPlugin"  # Uses class name
        assert plugin.get_plugin_priority() == 0  # Default priority

    def test_auto_register_flag(self):
        """Test the auto_register flag."""

        @request_converter_plugin(endpoint_types=EndpointType.CHAT, auto_register=True)
        class TestAutoRegisterPlugin:
            async def format_payload(self, endpoint_type, model_endpoint, turn):
                return {"test": True}

        # Check that auto-register attributes are set
        assert hasattr(TestAutoRegisterPlugin, "_aiperf_plugin_auto_register")
        assert TestAutoRegisterPlugin._aiperf_plugin_auto_register is True
        assert TestAutoRegisterPlugin._aiperf_plugin_endpoint_types == [
            EndpointType.CHAT
        ]


class TestBaseRequestConverterPlugin:
    """Test the BaseRequestConverterPlugin base class."""

    def test_abstract_methods(self):
        """Test that abstract methods must be implemented."""

        with pytest.raises(TypeError):
            # Should fail because abstract methods are not implemented
            BaseRequestConverterPlugin()

    def test_concrete_implementation(self):
        """Test a concrete implementation of the base class."""

        class ConcretePlugin(BaseRequestConverterPlugin):
            def get_supported_endpoint_types(self):
                return [EndpointType.CHAT]

            async def format_payload(self, endpoint_type, model_endpoint, turn):
                return {"concrete": True}

        plugin = ConcretePlugin()

        assert plugin.get_plugin_name() == "ConcretePlugin"
        assert plugin.get_plugin_priority() == 0
        assert plugin.get_supported_endpoint_types() == [EndpointType.CHAT]
        assert plugin.can_handle_endpoint_type(EndpointType.CHAT) is True
        assert plugin.can_handle_endpoint_type(EndpointType.EMBEDDINGS) is False

    async def test_format_payload_integration(self, sample_model_endpoint, sample_turn):
        """Test format_payload method integration."""

        class TestPlugin(BaseRequestConverterPlugin):
            def get_supported_endpoint_types(self):
                return [EndpointType.CHAT]

            async def format_payload(self, endpoint_type, model_endpoint, turn):
                if endpoint_type != EndpointType.CHAT:
                    return None
                return {
                    "messages": [{"role": "user", "content": "test"}],
                    "model": model_endpoint.primary_model_name,
                    "max_tokens": turn.max_tokens,
                }

        plugin = TestPlugin()

        result = await plugin.format_payload(
            EndpointType.CHAT, sample_model_endpoint, sample_turn
        )

        assert result is not None
        assert "messages" in result
        assert result["max_tokens"] == 100

    async def test_format_payload_unsupported_type(
        self, sample_model_endpoint, sample_turn
    ):
        """Test format_payload with unsupported endpoint type."""

        class TestPlugin(BaseRequestConverterPlugin):
            def get_supported_endpoint_types(self):
                return [EndpointType.CHAT]

            async def format_payload(self, endpoint_type, model_endpoint, turn):
                if endpoint_type != EndpointType.CHAT:
                    return None
                return {"test": True}

        plugin = TestPlugin()

        result = await plugin.format_payload(
            EndpointType.EMBEDDINGS, sample_model_endpoint, sample_turn
        )

        assert result is None
