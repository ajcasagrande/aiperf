#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
OpenAI Responses Converter Example

This example demonstrates the usage of the OpenAI Responses converter for o1 reasoning models.
The converter handles the responses API format with 'input' instead of 'messages' and
'max_output_tokens' instead of 'max_tokens'.
"""

import asyncio
import base64
import logging
import time
from typing import Any

from aiperf.clients.model_endpoint_info import ModelEndpointInfo
from aiperf.clients.openai.openai_responses import (
    OpenAIResponsesRequestConverter,
)
from aiperf.common.dataset_models import Audio, Image, Text, Turn
from aiperf.common.exceptions import AIPerfError

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def create_mock_model_endpoint(
    model_name: str = "o1-preview",
    max_tokens: int = 1000,
    streaming: bool = False,
    extra: dict[str, Any] | None = None,
) -> ModelEndpointInfo:
    """Create a mock model endpoint for testing."""
    from unittest.mock import Mock

    endpoint = Mock()
    endpoint.max_tokens = max_tokens
    endpoint.streaming = streaming
    endpoint.extra = extra or {}

    model_endpoint = Mock()
    model_endpoint.primary_model_name = model_name
    model_endpoint.endpoint = endpoint

    return model_endpoint


def create_sample_audio_base64() -> str:
    """Create sample base64 audio data."""
    # Create a simple WAV header for demonstration
    sample_data = b"RIFF\x24\x08\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x01\x00\x22\x56\x00\x00\x44\xac\x00\x00\x02\x00\x10\x00data\x00\x08\x00\x00"
    return base64.b64encode(sample_data).decode("utf-8")


async def demonstrate_text_only_reasoning():
    """Demonstrate text-only reasoning with o1 model."""
    print("=" * 60)
    print("1. TEXT-ONLY REASONING EXAMPLE")
    print("=" * 60)

    converter = OpenAIResponsesRequestConverter()

    # Create model endpoint with reasoning effort
    model_endpoint = create_mock_model_endpoint(
        model_name="o1-preview",
        max_tokens=2000,
        streaming=False,
        extra={"reasoning_effort": "high"},
    )

    # Create turn with complex reasoning task
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

    try:
        start_time = time.time()
        payload = await converter.format_payload(model_endpoint, turn)
        end_time = time.time()

        print(f"✅ Conversion completed in {(end_time - start_time) * 1000:.2f}ms")
        print(f"📝 Model: {payload['model']}")
        print(f"🎯 Input type: {type(payload['input']).__name__}")
        print(f"📊 Max output tokens: {payload['max_output_tokens']}")
        print(f"🧠 Reasoning effort: {payload['reasoning_effort']}")
        print(f"📄 Input preview: {payload['input'][:100]}...")

        return payload

    except Exception as e:
        print(f"❌ Error: {str(e)}")
        return None


async def demonstrate_multimodal_reasoning():
    """Demonstrate multimodal reasoning with o1 model."""
    print("\n" + "=" * 60)
    print("2. MULTIMODAL REASONING EXAMPLE")
    print("=" * 60)

    converter = OpenAIResponsesRequestConverter()

    # Create model endpoint with medium reasoning effort
    model_endpoint = create_mock_model_endpoint(
        model_name="o1-preview",
        max_tokens=1500,
        streaming=False,
        extra={
            "reasoning_effort": "medium",
            "store": True,
            "metadata": {"task": "image_analysis"},
        },
    )

    # Create turn with text and image
    turn = Turn(
        text=[
            Text(
                content=[
                    "Analyze this diagram and explain the mathematical relationship shown"
                ]
            )
        ],
        images=[Image(url="https://example.com/math_diagram.png")],
        audio=[],
    )

    try:
        start_time = time.time()
        payload = await converter.format_payload(model_endpoint, turn)
        end_time = time.time()

        print(f"✅ Conversion completed in {(end_time - start_time) * 1000:.2f}ms")
        print(f"📝 Model: {payload['model']}")
        print(f"🎯 Input type: {type(payload['input']).__name__}")
        print(f"📊 Content items: {len(payload['input'])}")
        print(f"🧠 Reasoning effort: {payload['reasoning_effort']}")
        print(f"💾 Store completion: {payload['store']}")
        print(f"📋 Metadata: {payload['metadata']}")

        # Show content types
        content_types = [item["type"] for item in payload["input"]]
        print(f"📄 Content types: {', '.join(content_types)}")

        return payload

    except Exception as e:
        print(f"❌ Error: {str(e)}")
        return None


async def demonstrate_audio_transcription():
    """Demonstrate audio transcription with o1 model."""
    print("\n" + "=" * 60)
    print("3. AUDIO TRANSCRIPTION EXAMPLE")
    print("=" * 60)

    converter = OpenAIResponsesRequestConverter()

    # Create model endpoint for audio processing
    model_endpoint = create_mock_model_endpoint(
        model_name="o1-mini",
        max_tokens=500,
        streaming=False,
        extra={"reasoning_effort": "low"},
    )

    # Create turn with audio
    audio_data = create_sample_audio_base64()
    turn = Turn(
        text=[
            Text(content=["Transcribe and summarize the key points from this audio"])
        ],
        images=[],
        audio=[Audio(base64=audio_data, format="wav")],
    )

    try:
        start_time = time.time()
        payload = await converter.format_payload(model_endpoint, turn)
        end_time = time.time()

        print(f"✅ Conversion completed in {(end_time - start_time) * 1000:.2f}ms")
        print(f"📝 Model: {payload['model']}")
        print(f"🎯 Input type: {type(payload['input']).__name__}")
        print(f"📊 Content items: {len(payload['input'])}")
        print(f"🧠 Reasoning effort: {payload['reasoning_effort']}")

        # Show audio content details
        audio_content = next(
            item for item in payload["input"] if item["type"] == "input_audio"
        )
        print(f"🔊 Audio format: {audio_content['input_audio']['format']}")
        print(
            f"📏 Audio data length: {len(audio_content['input_audio']['data'])} chars"
        )

        return payload

    except Exception as e:
        print(f"❌ Error: {str(e)}")
        return None


async def demonstrate_comprehensive_multimodal():
    """Demonstrate comprehensive multimodal reasoning with all content types."""
    print("\n" + "=" * 60)
    print("4. COMPREHENSIVE MULTIMODAL EXAMPLE")
    print("=" * 60)

    converter = OpenAIResponsesRequestConverter()

    # Create model endpoint with all features
    model_endpoint = create_mock_model_endpoint(
        model_name="o1-preview",
        max_tokens=3000,
        streaming=True,
        extra={
            "reasoning_effort": "high",
            "store": True,
            "metadata": {
                "task": "comprehensive_analysis",
                "user": "researcher",
                "session": "multimodal_test",
            },
        },
    )

    # Create turn with all content types
    audio_data = create_sample_audio_base64()
    turn = Turn(
        text=[
            Text(content=["Analyze all the provided content:"]),
            Text(content=["1. Examine the image for visual patterns"]),
            Text(content=["2. Transcribe and analyze the audio"]),
            Text(content=["3. Provide a comprehensive summary with reasoning"]),
        ],
        images=[
            Image(url="https://example.com/chart.png"),
            Image(
                base64="iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="
            ),
        ],
        audio=[Audio(base64=audio_data, format="wav")],
    )

    try:
        start_time = time.time()
        payload = await converter.format_payload(model_endpoint, turn)
        end_time = time.time()

        print(f"✅ Conversion completed in {(end_time - start_time) * 1000:.2f}ms")
        print(f"📝 Model: {payload['model']}")
        print(f"🎯 Input type: {type(payload['input']).__name__}")
        print(f"📊 Total content items: {len(payload['input'])}")
        print(f"🧠 Reasoning effort: {payload['reasoning_effort']}")
        print(f"🌊 Streaming: {payload['stream']}")
        print(f"💾 Store completion: {payload['store']}")
        print(f"📋 Metadata keys: {list(payload['metadata'].keys())}")

        # Analyze content distribution
        content_types = [item["type"] for item in payload["input"]]
        type_counts = {t: content_types.count(t) for t in set(content_types)}
        print(f"📄 Content distribution: {type_counts}")

        return payload

    except Exception as e:
        print(f"❌ Error: {str(e)}")
        return None


async def demonstrate_error_handling():
    """Demonstrate error handling scenarios."""
    print("\n" + "=" * 60)
    print("5. ERROR HANDLING EXAMPLES")
    print("=" * 60)

    converter = OpenAIResponsesRequestConverter()
    model_endpoint = create_mock_model_endpoint()

    # Test empty turn
    print("🔍 Testing empty turn...")
    try:
        empty_turn = Turn(text=[], images=[], audio=[])
        await converter.format_payload(model_endpoint, empty_turn)
        print("❌ Should have failed with empty turn")
    except AIPerfError as e:
        print(f"✅ Expected error caught: {str(e)}")

    # Test invalid reasoning effort
    print("\n🔍 Testing invalid reasoning effort...")
    try:
        invalid_model_endpoint = create_mock_model_endpoint(
            extra={"reasoning_effort": "invalid_effort"}
        )
        turn = Turn(text=[Text(content=["Test"])], images=[], audio=[])
        payload = await converter.format_payload(invalid_model_endpoint, turn)

        if "reasoning_effort" not in payload:
            print("✅ Invalid reasoning effort properly ignored")
        else:
            print(
                f"❌ Invalid reasoning effort not filtered: {payload['reasoning_effort']}"
            )
    except Exception as e:
        print(f"❌ Unexpected error: {str(e)}")


async def performance_benchmark():
    """Benchmark the converter performance."""
    print("\n" + "=" * 60)
    print("6. PERFORMANCE BENCHMARK")
    print("=" * 60)

    converter = OpenAIResponsesRequestConverter()
    model_endpoint = create_mock_model_endpoint()

    # Create test data
    turn = Turn(
        text=[Text(content=["Performance test with sample content"])],
        images=[],
        audio=[],
    )

    # Benchmark different scenarios
    scenarios = [
        ("Text only", turn),
        (
            "With image",
            Turn(
                text=[Text(content=["Test with image"])],
                images=[Image(url="https://example.com/test.jpg")],
                audio=[],
            ),
        ),
        (
            "Multimodal",
            Turn(
                text=[Text(content=["Multimodal test"])],
                images=[Image(url="https://example.com/test.jpg")],
                audio=[Audio(base64=create_sample_audio_base64(), format="wav")],
            ),
        ),
    ]

    for scenario_name, test_turn in scenarios:
        print(f"\n📊 Benchmarking: {scenario_name}")

        # Warm up
        await converter.format_payload(model_endpoint, test_turn)

        # Actual benchmark
        iterations = 100
        start_time = time.time()

        for _ in range(iterations):
            await converter.format_payload(model_endpoint, test_turn)

        end_time = time.time()

        total_time = end_time - start_time
        avg_time = (total_time / iterations) * 1000

        print(f"   ⚡ {iterations} iterations in {total_time:.4f}s")
        print(f"   📈 Average: {avg_time:.2f}ms per conversion")
        print(f"   🚀 Rate: {iterations / total_time:.0f} conversions/sec")


async def main():
    """Run all examples."""
    print("🚀 OpenAI Responses Converter Examples")
    print("=" * 60)

    results = []

    # Run all demonstrations
    results.append(await demonstrate_text_only_reasoning())
    results.append(await demonstrate_multimodal_reasoning())
    results.append(await demonstrate_audio_transcription())
    results.append(await demonstrate_comprehensive_multimodal())

    # Error handling
    await demonstrate_error_handling()

    # Performance benchmark
    await performance_benchmark()

    # Summary
    print("\n" + "=" * 60)
    print("📊 EXAMPLE SUMMARY")
    print("=" * 60)

    successful_conversions = sum(1 for r in results if r is not None)
    print(f"✅ Successful conversions: {successful_conversions}/{len(results)}")

    if successful_conversions > 0:
        print("\n🎯 Key Features Demonstrated:")
        print("   • Text-only reasoning with o1 models")
        print("   • Multimodal input handling (text + images)")
        print("   • Audio transcription and analysis")
        print("   • Comprehensive content type support")
        print("   • Reasoning effort configuration")
        print("   • Store and metadata parameters")
        print("   • Error handling and validation")
        print("   • Performance optimization")

        print("\n📋 Converter Benefits:")
        print("   • 🧠 Optimized for o1 reasoning models")
        print("   • 🔄 Seamless AIPerf integration")
        print("   • 📊 Comprehensive input validation")
        print("   • ⚡ High-performance conversion")
        print("   • 🛡️ Robust error handling")
        print("   • 🎯 Type-safe operations")

        print("\n🌟 Ready for production use with o1 models!")

    print("\n" + "=" * 60)
    print("🎉 Examples completed successfully!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
