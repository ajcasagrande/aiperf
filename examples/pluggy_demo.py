#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Demonstration of the pluggy-based plugin system for request converters."""

import asyncio
from typing import Any

from aiperf.clients.model_endpoint_info import ModelEndpointInfo
from aiperf.common.config.endpoint_config import EndpointConfig
from aiperf.common.config.user_config import UserConfig
from aiperf.common.enums import EndpointType
from aiperf.common.models import Text, Turn
from aiperf.common.plugins import (
    get_hybrid_factory,
    get_plugin_manager,
    request_converter_plugin,
)


# Example 1: Creating a custom plugin using the decorator
@request_converter_plugin(
    endpoint_types=EndpointType.COMPLETIONS,
    name="Custom Completions Plugin",
    priority=200,  # Higher priority than built-in plugins
    auto_register=True,
)
class CustomCompletionsPlugin:
    """Custom plugin for completions with special formatting."""

    async def format_payload(
        self,
        endpoint_type: EndpointType,
        model_endpoint: ModelEndpointInfo,
        turn: Turn,
    ) -> dict[str, Any] | None:
        """Format payload with custom logic."""
        if endpoint_type != EndpointType.COMPLETIONS:
            return None

        # Custom formatting logic
        prompts = []
        for text in turn.texts:
            for content in text.contents:
                if content:
                    # Add custom prefix
                    prompts.append(f"[CUSTOM] {content}")

        payload = {
            "prompt": prompts,
            "model": turn.model or model_endpoint.primary_model_name,
            "stream": model_endpoint.endpoint.streaming,
            "custom_plugin": True,
            "temperature": 0.7,  # Custom default
        }

        if turn.max_tokens:
            payload["max_tokens"] = turn.max_tokens

        return payload


# Example 2: Creating a plugin that handles multiple endpoint types
@request_converter_plugin(
    endpoint_types=[EndpointType.CHAT, EndpointType.COMPLETIONS],
    name="Universal OpenAI Plugin",
    priority=50,  # Lower priority than built-ins
    auto_register=True,
)
class UniversalOpenAIPlugin:
    """Plugin that can handle multiple OpenAI endpoint types."""

    async def format_payload(
        self,
        endpoint_type: EndpointType,
        model_endpoint: ModelEndpointInfo,
        turn: Turn,
    ) -> dict[str, Any] | None:
        """Universal formatting for OpenAI-compatible endpoints."""
        if endpoint_type == EndpointType.CHAT:
            return await self._format_chat(model_endpoint, turn)
        elif endpoint_type == EndpointType.COMPLETIONS:
            return await self._format_completions(model_endpoint, turn)
        else:
            return None

    async def _format_chat(
        self, model_endpoint: ModelEndpointInfo, turn: Turn
    ) -> dict[str, Any]:
        """Format for chat endpoint."""
        messages = []
        for text in turn.texts:
            for content in text.contents:
                if content:
                    messages.append({"role": turn.role or "user", "content": content})

        return {
            "messages": messages,
            "model": turn.model or model_endpoint.primary_model_name,
            "stream": model_endpoint.endpoint.streaming,
            "universal_plugin": True,
        }

    async def _format_completions(
        self, model_endpoint: ModelEndpointInfo, turn: Turn
    ) -> dict[str, Any]:
        """Format for completions endpoint."""
        prompts = [
            content for text in turn.texts for content in text.contents if content
        ]

        return {
            "prompt": prompts,
            "model": turn.model or model_endpoint.primary_model_name,
            "stream": model_endpoint.endpoint.streaming,
            "universal_plugin": True,
        }


async def demonstrate_plugin_system():
    """Demonstrate the pluggy plugin system."""
    print("🔌 AIPerf Pluggy Plugin System Demonstration")
    print("=" * 50)

    # Get the plugin manager
    manager = get_plugin_manager()

    # Discover and load all plugins (including our custom ones above)
    print("\n📋 Loading plugins...")
    manager.discover_and_load_plugins()

    # List all registered plugins
    print("\n📦 Registered Plugins:")
    plugins_info = manager.list_plugins()
    for name, endpoint_types in plugins_info:
        types_str = ", ".join(str(et) for et in endpoint_types)
        print(f"  • {name} → [{types_str}]")

    # Create sample data for testing
    user_config = UserConfig(
        endpoint=EndpointConfig(
            type=EndpointType.COMPLETIONS,
            url="http://localhost:8000/v1/completions",
            streaming=False,
        )
    )

    model_endpoint = ModelEndpointInfo.from_user_config(user_config)

    sample_turn = Turn(
        texts=[Text(contents=["Write a short poem about AI"])],
        images=[],
        audios=[],
        max_tokens=100,
    )

    print(f"\n🧪 Testing with endpoint type: {EndpointType.COMPLETIONS}")

    # Test direct plugin manager usage
    print("\n1️⃣ Direct Plugin Manager Usage:")
    try:
        result = await manager.format_payload(
            EndpointType.COMPLETIONS, model_endpoint, sample_turn
        )
        print(f"   Result: {result}")

        # Check which plugin was used
        plugin = manager.get_plugin_for_endpoint_type(EndpointType.COMPLETIONS)
        print(f"   Plugin used: {plugin.get_plugin_name()}")

    except Exception as e:
        print(f"   Error: {e}")

    # Test hybrid factory usage
    print("\n2️⃣ Hybrid Factory Usage:")
    hybrid_factory = get_hybrid_factory(prefer_pluggy=True)

    try:
        converter = hybrid_factory.create_instance(EndpointType.COMPLETIONS)
        result = await converter.format_payload(model_endpoint, sample_turn)
        print(f"   Result: {result}")

    except Exception as e:
        print(f"   Error: {e}")

    # Test with different endpoint types
    print("\n3️⃣ Testing Different Endpoint Types:")

    test_types = [EndpointType.CHAT, EndpointType.EMBEDDINGS, EndpointType.RANKINGS]

    for endpoint_type in test_types:
        print(f"\n   Testing {endpoint_type}:")
        try:
            plugin = manager.get_plugin_for_endpoint_type(endpoint_type)
            print(f"     ✅ Plugin available: {plugin.get_plugin_name()}")
        except Exception as e:
            print(f"     ❌ No plugin available: {e}")

    # Show system information
    print("\n4️⃣ System Information:")
    detailed_info = hybrid_factory.get_detailed_info()

    print("   Pluggy Plugins:")
    for name, endpoint_types in detailed_info.get("pluggy_plugins", []):
        types_str = ", ".join(str(et) for et in endpoint_types)
        print(f"     • {name} → [{types_str}]")

    print("   Original Factory Classes:")
    for cls, endpoint_type in detailed_info.get("original_classes", []):
        print(f"     • {cls.__name__} → {endpoint_type}")

    supported_types = detailed_info.get("supported_types", {})
    print("   Supported Types Summary:")
    for system, types in supported_types.items():
        print(f"     • {system.title()}: {len(types)} types")

    print("\n✨ Plugin system demonstration complete!")


def demonstrate_plugin_creation():
    """Demonstrate how to create plugins programmatically."""
    print("\n🛠️  Plugin Creation Examples")
    print("=" * 30)

    # Example 1: Manual plugin registration
    print("1️⃣ Manual Plugin Registration:")

    class ManualPlugin:
        def get_plugin_name(self):
            return "Manual Test Plugin"

        def get_plugin_priority(self):
            return 10

        def get_supported_endpoint_types(self):
            return [EndpointType.EMBEDDINGS]

        def can_handle_endpoint_type(self, endpoint_type):
            return endpoint_type == EndpointType.EMBEDDINGS

        async def format_payload(self, endpoint_type, model_endpoint, turn):
            return {"manual_plugin": True, "input": ["test"]}

    from aiperf.common.plugins import register_plugin_instance

    manual_plugin = ManualPlugin()
    register_plugin_instance(manual_plugin)
    print("   ✅ Manual plugin registered")

    # Example 2: Using base class
    print("\n2️⃣ Using Base Class:")

    from aiperf.common.plugins import BaseRequestConverterPlugin

    class BaseClassPlugin(BaseRequestConverterPlugin):
        def get_supported_endpoint_types(self):
            return [EndpointType.RANKINGS]

        async def format_payload(self, endpoint_type, model_endpoint, turn):
            if endpoint_type != EndpointType.RANKINGS:
                return None
            return {"base_class_plugin": True, "query": {"text": "test"}}

    from aiperf.common.plugins import register_plugin_class

    register_plugin_class(BaseClassPlugin)
    print("   ✅ Base class plugin registered")

    print("\n📊 Plugin registration complete!")


if __name__ == "__main__":
    print("Starting pluggy demonstration...\n")

    # Run the demonstrations
    demonstrate_plugin_creation()
    asyncio.run(demonstrate_plugin_system())

    print("\n🎉 All demonstrations complete!")
    print("\nTo run this demo:")
    print("1. Make sure you have the AIPerf environment set up")
    print("2. Run: python examples/pluggy_demo.py")
    print("\nTo use the plugin system in your code:")
    print("1. Import: from aiperf.common.plugins import get_hybrid_factory")
    print("2. Create factory: factory = get_hybrid_factory()")
    print("3. Use factory: converter = factory.create_instance(endpoint_type)")
