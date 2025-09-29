# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Example usage of the OpenAI Chat endpoint plugin.

This demonstrates how to use the OpenAI Chat endpoint plugin in various scenarios
and how to register it with AIPerf's plugin system.
"""

import asyncio

from aiperf.clients.model_endpoint_info import ModelEndpointInfo
from aiperf.common.config import UserConfig
from aiperf.common.models import Audio, Image, Text, Turn
from aiperf.common.plugins import PluginManager

# Import the OpenAI chat endpoint plugins
from examples.openai_chat_endpoint_plugin import (
    OpenAIChatEndpoint,
    OpenAIChatReasoningEndpoint,
    OpenAIChatStreamingEndpoint,
)


async def demo_basic_chat():
    """Demonstrate basic chat functionality."""
    print("=== Basic Chat Demo ===")

    # Create endpoint instance
    config = UserConfig()
    model_endpoint = ModelEndpointInfo.from_user_config(config)
    endpoint = OpenAIChatEndpoint(model_endpoint)

    # Create a simple text turn
    turn = Turn(
        texts=[Text(contents=["Hello, how are you today?"])],
        role="user",
        model="gpt-4o",
    )

    # Format the payload
    payload = await endpoint.format_payload(turn)
    print(f"Generated payload: {payload}")

    # Show endpoint info
    info = endpoint.get_endpoint_info()
    print(f"Endpoint: {info.endpoint_tag}")
    print(f"Supports streaming: {info.supports_streaming}")
    print(f"Supports images: {info.supports_images}")
    print(
        f"Transport types: {[t.transport_type for t in info.transport_config.supported_transports]}"
    )


async def demo_multimodal_chat():
    """Demonstrate multi-modal chat with text, images, and audio."""
    print("\n=== Multi-modal Chat Demo ===")

    config = UserConfig()
    model_endpoint = ModelEndpointInfo.from_user_config(config)
    endpoint = OpenAIChatEndpoint(model_endpoint)

    # Create a multi-modal turn
    turn = Turn(
        texts=[
            Text(contents=["Please analyze this image and audio:"]),
            Text(contents=["What do you see and hear?"]),
        ],
        images=[
            Image(contents=["data:image/jpeg;base64,/9j/4AAQSkZJRgABAQEAAAAAAAD..."]),
        ],
        audios=[
            Audio(
                contents=[
                    "mp3,UklGRnoGAABXQVZFZm10IBAAAAABAAEAQB8AAEAfAAABAAgAZGF0YQoGAACBhY..."
                ]
            ),
        ],
        role="user",
        model="gpt-4o-audio-preview",
        max_tokens=1000,
    )

    # Format the payload
    payload = await endpoint.format_payload(turn)
    print(f"Multi-modal payload structure: {list(payload.keys())}")
    print(f"Messages count: {len(payload['messages'])}")

    # Show message content types
    for i, message in enumerate(payload["messages"]):
        if isinstance(message.get("content"), list):
            content_types = [item["type"] for item in message["content"]]
            print(f"Message {i} content types: {content_types}")
        else:
            print(f"Message {i} content: text")


async def demo_streaming_chat():
    """Demonstrate streaming-optimized chat."""
    print("\n=== Streaming Chat Demo ===")

    config = UserConfig()
    model_endpoint = ModelEndpointInfo.from_user_config(config)
    endpoint = OpenAIChatStreamingEndpoint(model_endpoint)

    turn = Turn(
        texts=[Text(contents=["Write a short story about AI"])],
        role="user",
        model="gpt-4o",
    )

    payload = await endpoint.format_payload(turn)
    print(f"Streaming enabled: {payload['stream']}")
    print(f"Stream options: {payload.get('stream_options', {})}")

    # Show streaming-specific headers
    headers = endpoint.get_custom_headers()
    streaming_headers = {
        k: v
        for k, v in headers.items()
        if "stream" in k.lower() or "cache" in k.lower()
    }
    print(f"Streaming headers: {streaming_headers}")


async def demo_reasoning_chat():
    """Demonstrate reasoning model support."""
    print("\n=== Reasoning Chat Demo ===")

    config = UserConfig()
    model_endpoint = ModelEndpointInfo.from_user_config(config)
    endpoint = OpenAIChatReasoningEndpoint(model_endpoint)

    turn = Turn(
        texts=[
            Text(
                contents=[
                    "Solve this complex math problem: What is the derivative of x^3 + 2x^2 - 5x + 7?"
                ]
            )
        ],
        role="user",
        model="o1-preview",
        max_tokens=2000,
    )

    payload = await endpoint.format_payload(turn)
    print(f"Reasoning model: {payload['model']}")
    print(f"Reasoning effort: {payload.get('reasoning_effort', 'default')}")

    # Show what parameters were removed for o1 models
    excluded_params = ["temperature", "top_p", "frequency_penalty", "presence_penalty"]
    removed_params = [param for param in excluded_params if param not in payload]
    if removed_params:
        print(f"Parameters excluded for o1 model: {removed_params}")


async def demo_plugin_manager_integration():
    """Demonstrate integration with AIPerf's plugin manager."""
    print("\n=== Plugin Manager Integration Demo ===")

    # Note: In a real plugin, these would be registered via entry points
    # For demo purposes, we'll show how they would be used

    plugin_manager = PluginManager()

    # In a real scenario, plugins would be auto-discovered
    # Here we simulate what would happen:

    print("Available endpoint plugins:")
    endpoint_configs = [
        ("openai-chat", OpenAIChatEndpoint),
        ("openai-chat-streaming", OpenAIChatStreamingEndpoint),
        ("openai-chat-reasoning", OpenAIChatReasoningEndpoint),
    ]

    for tag, endpoint_class in endpoint_configs:
        config = UserConfig()
        model_endpoint = ModelEndpointInfo.from_user_config(config)
        endpoint = endpoint_class(model_endpoint)
        info = endpoint.get_endpoint_info()

        print(f"  - {tag}: {info.description}")
        print(
            f"    Transports: {[t.transport_type.value for t in info.transport_config.supported_transports]}"
        )
        print(
            f"    Features: streaming={info.supports_streaming}, images={info.supports_images}, audio={info.supports_audio}"
        )


def show_pyproject_toml_example():
    """Show how to register these plugins in pyproject.toml."""
    print("\n=== pyproject.toml Registration Example ===")

    example_config = """
# In your plugin package's pyproject.toml:
[project.entry-points."aiperf.plugins"]
openai-chat = "your_package.openai_plugins:OpenAIChatEndpoint"
openai-chat-streaming = "your_package.openai_plugins:OpenAIChatStreamingEndpoint"
openai-chat-reasoning = "your_package.openai_plugins:OpenAIChatReasoningEndpoint"

# Then users can install your plugin:
# pip install your-aiperf-openai-plugin

# And use it with AIPerf:
# aiperf --endpoint-type openai-chat --url https://api.openai.com --api-key $OPENAI_API_KEY
# aiperf --endpoint-type openai-chat-streaming --model gpt-4o --streaming
# aiperf --endpoint-type openai-chat-reasoning --model o1-preview
"""

    print(example_config)


def show_usage_examples():
    """Show command-line usage examples."""
    print("\n=== Command Line Usage Examples ===")

    examples = [
        "# Basic chat completion",
        "aiperf --endpoint-type openai-chat --url https://api.openai.com --api-key $OPENAI_API_KEY --model gpt-4o",
        "",
        "# Streaming chat",
        "aiperf --endpoint-type openai-chat-streaming --url https://api.openai.com --api-key $OPENAI_API_KEY --model gpt-4o --streaming",
        "",
        "# Reasoning model",
        "aiperf --endpoint-type openai-chat-reasoning --url https://api.openai.com --api-key $OPENAI_API_KEY --model o1-preview",
        "",
        "# With custom parameters",
        "aiperf --endpoint-type openai-chat --url https://api.openai.com --api-key $OPENAI_API_KEY --model gpt-4o --extra temperature:0.8 --extra max_tokens:2000",
        "",
        "# Multi-modal with images",
        "aiperf --endpoint-type openai-chat --url https://api.openai.com --api-key $OPENAI_API_KEY --model gpt-4o --input-type image --input-path ./images/",
        "",
        "# List available transports",
        "aiperf --endpoint-type openai-chat --list-transports",
        "",
        "# Use specific transport (when multiple available)",
        "aiperf --endpoint-type openai-chat --transport-type http --url https://api.openai.com",
    ]

    for example in examples:
        print(example)


async def main():
    """Run all demonstrations."""
    print("OpenAI Chat Endpoint Plugin Demonstration")
    print("=" * 50)

    await demo_basic_chat()
    await demo_multimodal_chat()
    await demo_streaming_chat()
    await demo_reasoning_chat()
    await demo_plugin_manager_integration()

    show_pyproject_toml_example()
    show_usage_examples()

    print("\n" + "=" * 50)
    print("Demo completed! The OpenAI Chat endpoint plugin provides:")
    print("✅ Full OpenAI Chat Completions API compatibility")
    print("✅ Multi-modal support (text, images, audio)")
    print("✅ Streaming and non-streaming responses")
    print("✅ Reasoning model optimizations")
    print("✅ Comprehensive response parsing")
    print("✅ Transport abstraction")
    print("✅ Easy plugin registration")


if __name__ == "__main__":
    asyncio.run(main())
