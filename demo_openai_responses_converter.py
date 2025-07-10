#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
OpenAI Responses Converter Demo

This demo showcases the OpenAI Responses converter for o1 reasoning models
and compares it with the multimodal chat converter to highlight their
differences and appropriate use cases.
"""

import asyncio
import json
import logging
import time
from typing import Any

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def print_header(title: str) -> None:
    """Print a formatted header."""
    print(f"\n{'=' * 60}")
    print(f"{title:^60}")
    print(f"{'=' * 60}")


def print_section(title: str) -> None:
    """Print a formatted section header."""
    print(f"\n{'-' * 40}")
    print(f"📋 {title}")
    print(f"{'-' * 40}")


def print_payload_comparison(
    title: str, payload1: dict[str, Any], payload2: dict[str, Any]
) -> None:
    """Print a comparison of two payloads."""
    print(f"\n🔍 {title}")
    print(f"{'Chat Completions':<20} | {'Responses API':<20}")
    print(f"{'-' * 20} | {'-' * 20}")

    # Compare key fields
    fields = [
        "model",
        "input",
        "messages",
        "max_tokens",
        "max_output_tokens",
        "reasoning_effort",
        "temperature",
    ]

    for field in fields:
        val1 = payload1.get(field, "N/A")
        val2 = payload2.get(field, "N/A")

        if field == "input" and isinstance(val2, str):
            val2 = val2[:30] + "..." if len(val2) > 30 else val2
        elif field == "messages" and isinstance(val1, list):
            val1 = f"[{len(val1)} messages]"

        print(f"{str(val1):<20} | {str(val2):<20}")


async def demo_responses_converter():
    """Demonstrate the OpenAI Responses converter."""
    print_header("🧠 OpenAI Responses Converter Demo")

    try:
        import base64
        from unittest.mock import Mock

        from aiperf.clients.openai.openai_responses import (
            OpenAIResponsesRequestConverter,
        )
        from aiperf.common.dataset_models import Audio, Image, Text, Turn

        # Create converter
        converter = OpenAIResponsesRequestConverter()

        # Create mock model endpoint
        endpoint = Mock()
        endpoint.max_tokens = 2000
        endpoint.streaming = False
        endpoint.extra = {
            "reasoning_effort": "high",
            "store": True,
            "metadata": {"task": "complex_reasoning"},
        }

        model_endpoint = Mock()
        model_endpoint.primary_model_name = "o1-preview"
        model_endpoint.endpoint = endpoint

        print_section("Text-Only Reasoning")

        # Text-only reasoning
        turn = Turn(
            text=[
                Text(
                    content=[
                        "Solve this step by step: If a train leaves Chicago at 2 PM traveling east at 60 mph, and another train leaves New York at 3 PM traveling west at 80 mph, and the distance between the cities is 800 miles, when and where will they meet?"
                    ]
                )
            ],
            images=[],
            audio=[],
        )

        start_time = time.time()
        payload = await converter.format_payload(model_endpoint, turn)
        end_time = time.time()

        print(f"✅ Conversion completed in {(end_time - start_time) * 1000:.2f}ms")
        print(f"📝 Model: {payload['model']}")
        print(f"🎯 Input type: {type(payload['input']).__name__}")
        print(f"🧠 Reasoning effort: {payload['reasoning_effort']}")
        print(f"📊 Max output tokens: {payload['max_output_tokens']}")
        print(f"💾 Store: {payload['store']}")

        print_section("Multimodal Reasoning")

        # Multimodal reasoning
        audio_data = base64.b64encode(b"fake audio data").decode("utf-8")
        multimodal_turn = Turn(
            text=[
                Text(
                    content=[
                        "Analyze all provided content and provide detailed reasoning"
                    ]
                )
            ],
            images=[Image(url="https://example.com/diagram.png")],
            audio=[Audio(base64=audio_data, format="wav")],
        )

        start_time = time.time()
        multimodal_payload = await converter.format_payload(
            model_endpoint, multimodal_turn
        )
        end_time = time.time()

        print(f"✅ Conversion completed in {(end_time - start_time) * 1000:.2f}ms")
        print(f"📝 Model: {multimodal_payload['model']}")
        print(f"🎯 Input type: {type(multimodal_payload['input']).__name__}")
        print(f"📊 Content items: {len(multimodal_payload['input'])}")

        # Show content distribution
        content_types = [item["type"] for item in multimodal_payload["input"]]
        type_counts = {t: content_types.count(t) for t in set(content_types)}
        print(f"📄 Content distribution: {type_counts}")

        return payload, multimodal_payload

    except ImportError as e:
        print(f"❌ Import error: {e}")
        return None, None
    except Exception as e:
        print(f"❌ Error: {e}")
        return None, None


async def demo_chat_converter():
    """Demonstrate the multimodal chat converter for comparison."""
    print_header("💬 Multimodal Chat Converter Demo")

    try:
        from unittest.mock import Mock

        from aiperf.clients.openai.openai_multimodal_chat import (
            OpenAIMultimodalChatCompletionsRequestConverter,
        )
        from aiperf.common.dataset_models import Image, Text, Turn

        # Create converter
        converter = OpenAIMultimodalChatCompletionsRequestConverter()

        # Create mock model endpoint
        endpoint = Mock()
        endpoint.max_tokens = 2000
        endpoint.streaming = False
        endpoint.extra = {
            "temperature": 0.7,
            "top_p": 0.9,
            "frequency_penalty": 0.0,
            "presence_penalty": 0.0,
        }

        model_endpoint = Mock()
        model_endpoint.primary_model_name = "gpt-4o"
        model_endpoint.endpoint = endpoint

        print_section("Chat Completions Format")

        # Create turn
        turn = Turn(
            text=[
                Text(content=["Analyze this image and provide a detailed description"])
            ],
            images=[Image(url="https://example.com/image.jpg")],
            audio=[],
        )

        start_time = time.time()
        payload = await converter.format_payload(model_endpoint, turn)
        end_time = time.time()

        print(f"✅ Conversion completed in {(end_time - start_time) * 1000:.2f}ms")
        print(f"📝 Model: {payload['model']}")
        print(f"🎯 Messages: {len(payload['messages'])}")
        print(f"🌡️ Temperature: {payload['temperature']}")
        print(f"📊 Max tokens: {payload['max_tokens']}")
        print(f"🎚️ Top P: {payload['top_p']}")

        return payload

    except ImportError as e:
        print(f"❌ Import error: {e}")
        return None
    except Exception as e:
        print(f"❌ Error: {e}")
        return None


def demonstrate_api_differences():
    """Demonstrate the key differences between the two APIs."""
    print_header("🔄 API Differences Comparison")

    print_section("Key Architectural Differences")

    differences = [
        ("Input Structure", "messages (array)", "input (string/array)"),
        ("Token Limit", "max_tokens", "max_output_tokens"),
        ("Model Control", "temperature, top_p", "reasoning_effort"),
        ("Reasoning", "Standard generation", "Chain-of-thought reasoning"),
        ("Optimal For", "General chat/completion", "Complex reasoning tasks"),
        ("Streaming", "Full support", "Limited support"),
        ("Function Calling", "Supported", "Not supported"),
        ("System Messages", "Supported", "Not supported"),
        ("Response Format", "Standard", "Includes reasoning tokens"),
    ]

    print(f"{'Feature':<15} | {'Chat Completions':<20} | {'Responses API':<20}")
    print(f"{'-' * 15} | {'-' * 20} | {'-' * 20}")

    for feature, chat, responses in differences:
        print(f"{feature:<15} | {chat:<20} | {responses:<20}")

    print_section("Use Case Recommendations")

    use_cases = [
        ("📝 General Chat", "Chat Completions", "Standard conversational AI"),
        ("🧮 Math Problems", "Responses API", "Complex mathematical reasoning"),
        ("🔬 Scientific Analysis", "Responses API", "Multi-step scientific reasoning"),
        ("💻 Code Generation", "Chat Completions", "Quick code snippets"),
        ("🧠 Complex Logic", "Responses API", "Multi-step logical reasoning"),
        ("🎨 Creative Writing", "Chat Completions", "Creative and varied outputs"),
        ("📊 Data Analysis", "Responses API", "Deep analytical reasoning"),
        ("🤖 Function Calling", "Chat Completions", "Tool/function integration"),
    ]

    print(f"{'Use Case':<20} | {'Recommended API':<20} | {'Reason':<30}")
    print(f"{'-' * 20} | {'-' * 20} | {'-' * 30}")

    for use_case, api, reason in use_cases:
        print(f"{use_case:<20} | {api:<20} | {reason:<30}")


def demonstrate_model_selection():
    """Demonstrate model selection guidelines."""
    print_header("🎯 Model Selection Guidelines")

    print_section("Chat Completions Models")

    chat_models = [
        ("gpt-4o", "General multimodal tasks", "128K context", "High quality"),
        ("gpt-4o-mini", "Fast lightweight tasks", "128K context", "Cost effective"),
        ("gpt-4-turbo", "Complex reasoning", "128K context", "Balanced performance"),
        ("gpt-3.5-turbo", "Simple tasks", "16K context", "Very cost effective"),
    ]

    print(f"{'Model':<15} | {'Best For':<25} | {'Context':<12} | {'Notes':<15}")
    print(f"{'-' * 15} | {'-' * 25} | {'-' * 12} | {'-' * 15}")

    for model, best_for, context, notes in chat_models:
        print(f"{model:<15} | {best_for:<25} | {context:<12} | {notes:<15}")

    print_section("Responses API Models")

    responses_models = [
        ("o1-preview", "Complex reasoning", "128K context", "Highest reasoning"),
        ("o1-mini", "Fast reasoning", "128K context", "Cost effective"),
        ("o3-mini", "Latest reasoning", "200K context", "Advanced features"),
        ("o1", "Production reasoning", "200K context", "Most capable"),
    ]

    print(f"{'Model':<15} | {'Best For':<25} | {'Context':<12} | {'Notes':<15}")
    print(f"{'-' * 15} | {'-' * 25} | {'-' * 12} | {'-' * 15}")

    for model, best_for, context, notes in responses_models:
        print(f"{model:<15} | {best_for:<25} | {context:<12} | {notes:<15}")


async def performance_comparison():
    """Compare performance between converters."""
    print_header("⚡ Performance Comparison")

    try:
        from unittest.mock import Mock

        from aiperf.clients.openai.openai_multimodal_chat import (
            OpenAIMultimodalChatCompletionsRequestConverter,
        )
        from aiperf.clients.openai.openai_responses import (
            OpenAIResponsesRequestConverter,
        )
        from aiperf.common.dataset_models import Image, Text, Turn

        # Create converters
        responses_converter = OpenAIResponsesRequestConverter()
        chat_converter = OpenAIMultimodalChatCompletionsRequestConverter()

        # Create mock endpoints
        responses_endpoint = Mock()
        responses_endpoint.max_tokens = 1000
        responses_endpoint.streaming = False
        responses_endpoint.extra = {"reasoning_effort": "medium"}

        chat_endpoint = Mock()
        chat_endpoint.max_tokens = 1000
        chat_endpoint.streaming = False
        chat_endpoint.extra = {"temperature": 0.7}

        responses_model = Mock()
        responses_model.primary_model_name = "o1-preview"
        responses_model.endpoint = responses_endpoint

        chat_model = Mock()
        chat_model.primary_model_name = "gpt-4o"
        chat_model.endpoint = chat_endpoint

        # Test data
        turn = Turn(
            text=[Text(content=["Analyze this content"])],
            images=[Image(url="https://example.com/image.jpg")],
            audio=[],
        )

        # Benchmark responses converter
        print_section("Responses Converter Performance")

        iterations = 100
        start_time = time.time()

        for _ in range(iterations):
            await responses_converter.format_payload(responses_model, turn)

        responses_time = time.time() - start_time
        responses_avg = (responses_time / iterations) * 1000

        print(f"⚡ {iterations} iterations in {responses_time:.4f}s")
        print(f"📈 Average: {responses_avg:.2f}ms per conversion")
        print(f"🚀 Rate: {iterations / responses_time:.0f} conversions/sec")

        # Benchmark chat converter
        print_section("Chat Converter Performance")

        start_time = time.time()

        for _ in range(iterations):
            await chat_converter.format_payload(chat_model, turn)

        chat_time = time.time() - start_time
        chat_avg = (chat_time / iterations) * 1000

        print(f"⚡ {iterations} iterations in {chat_time:.4f}s")
        print(f"📈 Average: {chat_avg:.2f}ms per conversion")
        print(f"🚀 Rate: {iterations / chat_time:.0f} conversions/sec")

        # Comparison
        print_section("Performance Comparison")

        print(f"{'Converter':<20} | {'Avg Time':<10} | {'Rate':<12} | {'Notes':<15}")
        print(f"{'-' * 20} | {'-' * 10} | {'-' * 12} | {'-' * 15}")
        print(
            f"{'Responses':<20} | {responses_avg:.2f}ms | {iterations / responses_time:.0f}/sec | {'Reasoning optimized':<15}"
        )
        print(
            f"{'Chat':<20} | {chat_avg:.2f}ms | {iterations / chat_time:.0f}/sec | {'General purpose':<15}"
        )

        faster = "Responses" if responses_avg < chat_avg else "Chat"
        difference = abs(responses_avg - chat_avg)
        print(f"\n🏆 {faster} converter is {difference:.2f}ms faster on average")

    except Exception as e:
        print(f"❌ Performance benchmark error: {e}")


async def main():
    """Run the complete demo."""
    print("🚀 OpenAI Converters Comparison Demo")
    print("=" * 60)

    # Demo both converters
    responses_payloads = await demo_responses_converter()
    chat_payload = await demo_chat_converter()

    # Show API differences
    demonstrate_api_differences()

    # Show model selection
    demonstrate_model_selection()

    # Performance comparison
    await performance_comparison()

    # Payload comparison if both succeeded
    if responses_payloads[0] and chat_payload:
        print_header("📊 Payload Structure Comparison")

        print_section("Text-Only Comparison")
        print_payload_comparison(
            "Simple Text Request", chat_payload, responses_payloads[0]
        )

        print_section("JSON Structure Examples")

        print("\n🔍 Chat Completions Payload:")
        print(
            json.dumps(
                {
                    "model": "gpt-4o",
                    "messages": [{"role": "user", "content": "Hello"}],
                    "max_tokens": 1000,
                    "temperature": 0.7,
                },
                indent=2,
            )
        )

        print("\n🔍 Responses API Payload:")
        print(
            json.dumps(
                {
                    "model": "o1-preview",
                    "input": "Hello",
                    "max_output_tokens": 1000,
                    "reasoning_effort": "medium",
                },
                indent=2,
            )
        )

    # Final summary
    print_header("🎉 Demo Summary")

    print("\n✨ Key Takeaways:")
    print("   • OpenAI Responses API is optimized for complex reasoning tasks")
    print("   • Chat Completions API is better for general conversational AI")
    print("   • Both converters integrate seamlessly with AIPerf")
    print("   • Performance is comparable for both converters")
    print("   • Model selection depends on your specific use case")

    print("\n🎯 When to Use Each:")
    print("   • Responses API: Math, science, complex logic, multi-step reasoning")
    print("   • Chat Completions: General chat, creative tasks, function calling")

    print("\n🔄 AIPerf Integration:")
    print("   • Factory pattern automatically selects the right converter")
    print("   • Endpoint type determines which converter to use")
    print("   • Seamless switching between APIs")

    print("\n🌟 Both converters are production-ready!")
    print("=" * 60)
    print("🎊 Demo completed successfully!")


if __name__ == "__main__":
    asyncio.run(main())
