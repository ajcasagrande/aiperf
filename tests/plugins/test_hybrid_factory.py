# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Tests for the hybrid factory."""

from unittest.mock import Mock, patch

import pytest

from aiperf.common.enums import EndpointType
from aiperf.common.exceptions import AIPerfError
from aiperf.common.plugins.hybrid_factory import HybridRequestConverterFactory


class TestHybridRequestConverterFactory:
    """Test the HybridRequestConverterFactory."""

    def test_prefer_pluggy_success(self, test_chat_plugin):
        """Test that pluggy is preferred when prefer_pluggy=True."""
        factory = HybridRequestConverterFactory(prefer_pluggy=True)
        factory.pluggy_factory.register_plugin(test_chat_plugin)

        converter = factory.create_instance(EndpointType.CHAT)
        assert converter is not None
        assert hasattr(converter, "format_payload")

    def test_prefer_original_fallback_to_pluggy(self, test_chat_plugin):
        """Test falling back to pluggy when original factory fails."""
        factory = HybridRequestConverterFactory(prefer_pluggy=False)
        factory.pluggy_factory.register_plugin(test_chat_plugin)

        with patch(
            "aiperf.common.factories.RequestConverterFactory.create_instance"
        ) as mock_original:
            mock_original.side_effect = Exception("Original factory failed")

            converter = factory.create_instance(EndpointType.CHAT)
            assert converter is not None

    def test_prefer_pluggy_fallback_to_original(self):
        """Test falling back to original when pluggy fails."""
        factory = HybridRequestConverterFactory(prefer_pluggy=True)

        with patch(
            "aiperf.common.factories.RequestConverterFactory.create_instance"
        ) as mock_original:
            mock_converter = Mock()
            mock_original.return_value = mock_converter

            converter = factory.create_instance(EndpointType.CHAT)
            assert converter == mock_converter

    def test_both_systems_fail(self):
        """Test when both systems fail to create a converter."""
        factory = HybridRequestConverterFactory(prefer_pluggy=True)

        with patch(
            "aiperf.common.factories.RequestConverterFactory.create_instance"
        ) as mock_original:
            mock_original.side_effect = Exception("Original factory failed")

            with pytest.raises(AIPerfError, match="No request converter found"):
                factory.create_instance(EndpointType.CHAT)

    def test_list_all_supported_types(
        self, test_chat_plugin, test_multi_endpoint_plugin
    ):
        """Test listing all supported types from both systems."""
        factory = HybridRequestConverterFactory()
        factory.pluggy_factory.register_plugin(test_chat_plugin)
        factory.pluggy_factory.register_plugin(test_multi_endpoint_plugin)

        with patch(
            "aiperf.common.factories.RequestConverterFactory.get_all_classes_and_types"
        ) as mock_original:
            mock_original.return_value = [(Mock, EndpointType.COMPLETIONS)]

            supported_types = factory.list_all_supported_types()

            assert "pluggy" in supported_types
            assert "original" in supported_types

            pluggy_types = supported_types["pluggy"]
            assert EndpointType.CHAT in pluggy_types
            assert EndpointType.EMBEDDINGS in pluggy_types
            assert EndpointType.RANKINGS in pluggy_types

            original_types = supported_types["original"]
            assert EndpointType.COMPLETIONS in original_types

    def test_get_detailed_info(self, test_chat_plugin):
        """Test getting detailed information about both systems."""
        factory = HybridRequestConverterFactory()
        factory.pluggy_factory.register_plugin(test_chat_plugin)

        with patch(
            "aiperf.common.factories.RequestConverterFactory.get_all_classes_and_types"
        ) as mock_original:
            mock_class = Mock()
            mock_class.__name__ = "TestOriginalClass"
            mock_original.return_value = [(mock_class, EndpointType.COMPLETIONS)]

            info = factory.get_detailed_info()

            assert "pluggy_plugins" in info
            assert "original_classes" in info
            assert "supported_types" in info

            # Check pluggy plugins info
            pluggy_plugins = info["pluggy_plugins"]
            assert len(pluggy_plugins) == 1
            assert pluggy_plugins[0][0] == "Test Chat Plugin"

            # Check original classes info
            original_classes = info["original_classes"]
            assert len(original_classes) == 1
            assert original_classes[0][1] == EndpointType.COMPLETIONS

    def test_error_handling_in_list_supported_types(self):
        """Test error handling when getting supported types fails."""
        factory = HybridRequestConverterFactory()

        with patch(
            "aiperf.common.factories.RequestConverterFactory.get_all_classes_and_types"
        ) as mock_original:
            mock_original.side_effect = Exception("Error getting original types")

            # Should not raise exception, just log warning
            supported_types = factory.list_all_supported_types()

            assert "pluggy" in supported_types
            assert "original" in supported_types
            assert supported_types["original"] == []  # Empty due to error

    def test_error_handling_in_detailed_info(self):
        """Test error handling when getting detailed info fails."""
        factory = HybridRequestConverterFactory()

        with patch(
            "aiperf.common.factories.RequestConverterFactory.get_all_classes_and_types"
        ) as mock_original:
            mock_original.side_effect = Exception("Error getting original info")

            # Should not raise exception, just log warning
            info = factory.get_detailed_info()

            assert "pluggy_plugins" in info
            assert "original_classes" in info
            assert info["original_classes"] == []  # Empty due to error
