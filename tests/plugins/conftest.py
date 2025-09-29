# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Test fixtures for plugin tests."""

from typing import Any

import pytest

from aiperf.clients.model_endpoint_info import ModelEndpointInfo
from aiperf.common.enums import EndpointType
from aiperf.common.models import Turn
from aiperf.common.plugins import (
    RequestConverterPluginManager,
    request_converter_plugin,
)


@pytest.fixture
def plugin_manager():
    """Create a fresh plugin manager for testing."""
    return RequestConverterPluginManager()


@pytest.fixture
def sample_model_endpoint(user_config_with_endpoint_config):
    """Create a sample model endpoint for testing."""
    return ModelEndpointInfo.from_user_config(user_config_with_endpoint_config)


@pytest.fixture
def sample_turn():
    """Create a sample turn for testing."""
    from aiperf.common.models import Text

    return Turn(
        texts=[Text(contents=["Hello, world!"])],
        images=[],
        audios=[],
        role="user",
        max_tokens=100,
    )


@request_converter_plugin(
    endpoint_types=EndpointType.CHAT,
    name="Test Chat Plugin",
    priority=50,
    auto_register=False,
)
class TestChatPlugin:
    """Test plugin for chat endpoints."""

    async def format_payload(
        self,
        endpoint_type: EndpointType,
        model_endpoint: ModelEndpointInfo,
        turn: Turn,
    ) -> dict[str, Any] | None:
        if endpoint_type != EndpointType.CHAT:
            return None

        return {
            "messages": [{"role": "user", "content": "test"}],
            "model": "test-model",
            "test_plugin": True,
        }


@request_converter_plugin(
    endpoint_types=[EndpointType.EMBEDDINGS, EndpointType.RANKINGS],
    name="Test Multi-Endpoint Plugin",
    priority=75,
    auto_register=False,
)
class TestMultiEndpointPlugin:
    """Test plugin that supports multiple endpoint types."""

    async def format_payload(
        self,
        endpoint_type: EndpointType,
        model_endpoint: ModelEndpointInfo,
        turn: Turn,
    ) -> dict[str, Any] | None:
        if endpoint_type not in [EndpointType.EMBEDDINGS, EndpointType.RANKINGS]:
            return None

        return {
            "input": ["test"],
            "model": "test-model",
            "endpoint_type": str(endpoint_type),
            "multi_endpoint_plugin": True,
        }


@pytest.fixture
def test_chat_plugin():
    """Create a test chat plugin instance."""
    return TestChatPlugin()


@pytest.fixture
def test_multi_endpoint_plugin():
    """Create a test multi-endpoint plugin instance."""
    return TestMultiEndpointPlugin()
