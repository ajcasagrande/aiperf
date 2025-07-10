#!/usr/bin/env python3
#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
"""
Quick demo of the new multimodal chat completions converter.

This script demonstrates the key features of the modernized converter
with a simple interactive example.
"""

import asyncio
import json
import sys
from pathlib import Path

# Add the aiperf directory to the path for imports
sys.path.insert(0, str(Path(__file__).parent / "aiperf"))

from aiperf.clients.model_endpoint_info import (
    EndpointInfo,
    ModelEndpointInfo,
    ModelInfo,
    ModelListInfo,
)
from aiperf.clients.openai.openai_multimodal_chat import (
    OpenAIMultimodalChatCompletionsRequestConverter,
)
from aiperf.common.dataset_models import Audio, Image, Text, Turn
from aiperf.common.enums import EndpointType, ModelSelectionStrategy


async def demo_multimodal_conversion():
    """Demo the new multimodal converter capabilities."""

    print("🚀 AIPerf Multimodal Chat Completions Converter Demo")
    print("=" * 60)

    # Create the converter
    converter = OpenAIMultimodalChatCompletionsRequestConverter()

    # Create model endpoint
    model_endpoint = ModelEndpointInfo(
        models=ModelListInfo(
            models=[ModelInfo(name="gpt-4o-mini")],
            model_selection_strategy=ModelSelectionStrategy.ROUND_ROBIN,
        ),
        endpoint=EndpointInfo(
            type=EndpointType.OPENAI_MULTIMODAL,
            streaming=True,
            extra={"temperature": 0.7, "max_tokens": 1000},
        ),
    )

    print("\n1. Text-only conversation:")
    print("-" * 30)

    # Example 1: Text only
    text_turn = Turn(
        text=[Text(content=["Hello! Can you help me with AI development?"])],
    )

    text_payload = await converter.format_payload(model_endpoint, text_turn)
    print(
        f"✅ Generated payload with {len(text_payload['messages'][0]['content'])} content items"
    )
    print(
        f"📝 Text content: {text_payload['messages'][0]['content'][0]['text'][:50]}..."
    )

    print("\n2. Image analysis:")
    print("-" * 30)

    # Example 2: Image + Text
    image_turn = Turn(
        text=[Text(content=["Please describe this image"])],
        image=[Image(content=["https://example.com/sample.jpg"])],
    )

    image_payload = await converter.format_payload(model_endpoint, image_turn)
    print(
        f"✅ Generated payload with {len(image_payload['messages'][0]['content'])} content items"
    )
    print(
        f"🖼️  Image URL: {image_payload['messages'][0]['content'][1]['image_url']['url']}"
    )

    print("\n3. Audio transcription:")
    print("-" * 30)

    # Example 3: Audio + Text (create sample base64 audio)
    import base64

    sample_audio = base64.b64encode(b"fake_audio_data").decode()

    audio_turn = Turn(
        text=[Text(content=["Please transcribe this audio"])],
        audio=[Audio(content=[f"wav,{sample_audio}"])],
    )

    audio_payload = await converter.format_payload(model_endpoint, audio_turn)
    print(
        f"✅ Generated payload with {len(audio_payload['messages'][0]['content'])} content items"
    )
    print(
        f"🎵 Audio format: {audio_payload['messages'][0]['content'][1]['input_audio']['format']}"
    )

    print("\n4. Complete multimodal example:")
    print("-" * 30)

    # Example 4: All together
    multimodal_turn = Turn(
        text=[Text(content=["Analyze this image and audio together"])],
        image=[Image(content=["https://example.com/chart.png"])],
        audio=[Audio(content=[f"mp3,{sample_audio}"])],
    )

    multimodal_payload = await converter.format_payload(model_endpoint, multimodal_turn)
    print(
        f"✅ Generated payload with {len(multimodal_payload['messages'][0]['content'])} content items"
    )
    print(
        f"🎯 Content types: {[c['type'] for c in multimodal_payload['messages'][0]['content']]}"
    )

    print("\n5. Error handling demo:")
    print("-" * 30)

    # Example 5: Error handling
    try:
        empty_turn = Turn()  # This should fail
        await converter.format_payload(model_endpoint, empty_turn)
    except Exception as e:
        print(f"✅ Caught expected error: {type(e).__name__}: {str(e)[:50]}...")

    print("\n6. Performance test:")
    print("-" * 30)

    # Performance test
    import time

    start_time = time.perf_counter()

    for i in range(1000):
        await converter.format_payload(model_endpoint, text_turn)

    end_time = time.perf_counter()
    print(f"✅ Processed 1000 conversions in {end_time - start_time:.4f} seconds")
    print(
        f"⚡ Average time per conversion: {(end_time - start_time) / 1000 * 1000:.2f} milliseconds"
    )

    print("\n" + "=" * 60)
    print("🎉 Demo completed successfully!")
    print("\nKey features demonstrated:")
    print("  ✅ Type-safe multimodal content handling")
    print("  ✅ Comprehensive validation")
    print("  ✅ Clean error handling")
    print("  ✅ High performance")
    print("  ✅ Modern async/await patterns")
    print("  ✅ Extensible architecture")

    print("\n📄 Sample payload structure:")
    print(json.dumps(text_payload, indent=2)[:300] + "...")


if __name__ == "__main__":
    asyncio.run(demo_multimodal_conversion())
