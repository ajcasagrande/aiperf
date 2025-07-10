#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
Example usage of the modern multimodal chat completions converter.

This example demonstrates how to use the new AIPerf multimodal chat completions
converter with various types of content including text, images, and audio.
"""

import asyncio
import base64
import json
import logging

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

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def create_sample_audio_base64() -> str:
    """Create a sample base64-encoded audio file for demonstration."""
    # Create a minimal WAV file with PCM data
    wav_header = b"RIFF\x24\x08\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x01\x00\x44\xac\x00\x00\x44\xac\x00\x00\x01\x00\x08\x00data\x00\x08\x00\x00"
    sample_data = b"\x00\x01\x02\x03\x04\x05\x06\x07" * 100  # Some sample audio data
    wav_data = wav_header + sample_data
    return base64.b64encode(wav_data).decode()


async def example_text_only_conversation():
    """Example of a text-only conversation."""
    logger.info("=== Text-Only Conversation Example ===")

    # Create the converter
    converter = OpenAIMultimodalChatCompletionsRequestConverter()

    # Create model endpoint configuration
    model_endpoint = ModelEndpointInfo(
        models=ModelListInfo(
            models=[ModelInfo(name="gpt-4o-mini")],
            model_selection_strategy=ModelSelectionStrategy.ROUND_ROBIN,
        ),
        endpoint=EndpointInfo(
            type=EndpointType.OPENAI_MULTIMODAL,
            streaming=True,
            extra={
                "temperature": 0.7,
                "max_tokens": 1000,
                "top_p": 0.9,
            },
        ),
    )

    # Create a text-only turn
    turn = Turn(
        text=[
            Text(
                content=[
                    "Hello! Can you help me understand the benefits of multimodal AI?"
                ]
            )
        ],
    )

    # Convert to payload
    payload = await converter.format_payload(model_endpoint, turn)

    # Display the result
    logger.info("Generated payload:")
    print(json.dumps(payload, indent=2))

    return payload


async def example_image_analysis():
    """Example of image analysis with text prompt."""
    logger.info("=== Image Analysis Example ===")

    converter = OpenAIMultimodalChatCompletionsRequestConverter()

    model_endpoint = ModelEndpointInfo(
        models=ModelListInfo(
            models=[ModelInfo(name="gpt-4o")],
            model_selection_strategy=ModelSelectionStrategy.ROUND_ROBIN,
        ),
        endpoint=EndpointInfo(
            type=EndpointType.OPENAI_MULTIMODAL,
            streaming=False,
            extra={
                "temperature": 0.3,
                "max_tokens": 500,
            },
        ),
    )

    # Create a turn with text and image
    turn = Turn(
        text=[
            Text(
                content=[
                    "Please analyze this image and describe what you see in detail. "
                    "Focus on colors, objects, composition, and any notable features."
                ]
            )
        ],
        image=[
            Image(
                content=[
                    "https://example.com/sample_image.jpg",
                    "https://example.com/another_image.png",
                ]
            )
        ],
    )

    payload = await converter.format_payload(model_endpoint, turn)

    logger.info("Generated payload for image analysis:")
    print(json.dumps(payload, indent=2))

    return payload


async def example_audio_transcription():
    """Example of audio transcription with additional context."""
    logger.info("=== Audio Transcription Example ===")

    converter = OpenAIMultimodalChatCompletionsRequestConverter()

    model_endpoint = ModelEndpointInfo(
        models=ModelListInfo(
            models=[ModelInfo(name="gpt-4o-audio-preview")],
            model_selection_strategy=ModelSelectionStrategy.ROUND_ROBIN,
        ),
        endpoint=EndpointInfo(
            type=EndpointType.OPENAI_MULTIMODAL,
            streaming=True,
            extra={
                "temperature": 0.1,
                "max_tokens": 1000,
            },
        ),
    )

    # Create sample audio data
    sample_audio = create_sample_audio_base64()

    # Create a turn with text and audio
    turn = Turn(
        text=[
            Text(
                content=[
                    "Please transcribe this audio file and provide a summary of the content. "
                    "If there are multiple speakers, identify them as Speaker A, Speaker B, etc."
                ]
            )
        ],
        audio=[
            Audio(
                content=[
                    f"wav,{sample_audio}",
                    f"mp3,{sample_audio}",  # Multiple audio files
                ]
            )
        ],
    )

    payload = await converter.format_payload(model_endpoint, turn)

    logger.info("Generated payload for audio transcription:")
    print(json.dumps(payload, indent=2))

    return payload


async def example_comprehensive_multimodal():
    """Example of a comprehensive multimodal conversation with text, images, and audio."""
    logger.info("=== Comprehensive Multimodal Example ===")

    converter = OpenAIMultimodalChatCompletionsRequestConverter()

    model_endpoint = ModelEndpointInfo(
        models=ModelListInfo(
            models=[ModelInfo(name="gpt-4o-multimodal")],
            model_selection_strategy=ModelSelectionStrategy.ROUND_ROBIN,
        ),
        endpoint=EndpointInfo(
            type=EndpointType.OPENAI_MULTIMODAL,
            streaming=True,
            extra={
                "temperature": 0.8,
                "max_tokens": 2000,
                "top_p": 0.95,
                "frequency_penalty": 0.1,
                "presence_penalty": 0.1,
            },
        ),
    )

    # Create sample audio data
    sample_audio = create_sample_audio_base64()

    # Create a comprehensive multimodal turn
    turn = Turn(
        text=[
            Text(
                content=[
                    "I need help analyzing this multimedia content. Here's what I have:",
                    "1. A few images that need description",
                    "2. Audio files that need transcription",
                    "3. Please provide insights on how these different media types relate to each other",
                ]
            )
        ],
        image=[
            Image(
                content=[
                    "https://example.com/chart_analysis.png",
                    "https://example.com/product_photo.jpg",
                    "data:image/jpeg;base64,/9j/4AAQSkZJRgABAQAAAQABAAD...",  # Base64 encoded image
                ]
            )
        ],
        audio=[
            Audio(
                content=[
                    f"wav,{sample_audio}",
                    f"mp3,{sample_audio}",
                    f"flac,{sample_audio}",
                ]
            )
        ],
    )

    payload = await converter.format_payload(model_endpoint, turn)

    logger.info("Generated payload for comprehensive multimodal analysis:")
    print(json.dumps(payload, indent=2))

    return payload


async def example_conversation_with_system_role():
    """Example showing how to handle different message roles."""
    logger.info("=== Conversation with System Role Example ===")

    converter = OpenAIMultimodalChatCompletionsRequestConverter()

    model_endpoint = ModelEndpointInfo(
        models=ModelListInfo(
            models=[ModelInfo(name="gpt-4o-mini")],
            model_selection_strategy=ModelSelectionStrategy.ROUND_ROBIN,
        ),
        endpoint=EndpointInfo(
            type=EndpointType.OPENAI_MULTIMODAL,
            streaming=False,
            extra={
                "temperature": 0.5,
                "max_tokens": 800,
            },
        ),
    )

    # Create a turn with system role
    turn = Turn(
        text=[
            Text(
                content=[
                    "You are a helpful AI assistant specialized in multimodal content analysis. "
                    "You should provide detailed, accurate, and helpful responses when analyzing "
                    "images, audio, or other multimedia content."
                ]
            )
        ],
        role="system",
    )

    payload = await converter.format_payload(model_endpoint, turn)

    logger.info("Generated payload with system role:")
    print(json.dumps(payload, indent=2))

    return payload


async def example_error_handling():
    """Example demonstrating error handling."""
    logger.info("=== Error Handling Example ===")

    converter = OpenAIMultimodalChatCompletionsRequestConverter()

    model_endpoint = ModelEndpointInfo(
        models=ModelListInfo(
            models=[ModelInfo(name="gpt-4o-mini")],
            model_selection_strategy=ModelSelectionStrategy.ROUND_ROBIN,
        ),
        endpoint=EndpointInfo(
            type=EndpointType.OPENAI_MULTIMODAL,
            streaming=True,
        ),
    )

    # Example 1: Empty turn (should raise error)
    try:
        empty_turn = Turn()
        await converter.format_payload(model_endpoint, empty_turn)
    except Exception as e:
        logger.info(f"Expected error for empty turn: {e}")

    # Example 2: Invalid audio format (should raise error)
    try:
        invalid_audio_turn = Turn(
            audio=[Audio(content=["invalid_format,some_data"])],
        )
        await converter.format_payload(model_endpoint, invalid_audio_turn)
    except Exception as e:
        logger.info(f"Expected error for invalid audio format: {e}")

    # Example 3: Malformed audio content (should raise error)
    try:
        malformed_audio_turn = Turn(
            audio=[Audio(content=["no_comma_separator"])],
        )
        await converter.format_payload(model_endpoint, malformed_audio_turn)
    except Exception as e:
        logger.info(f"Expected error for malformed audio content: {e}")


async def performance_benchmark():
    """Example showing performance characteristics."""
    logger.info("=== Performance Benchmark Example ===")

    converter = OpenAIMultimodalChatCompletionsRequestConverter()

    model_endpoint = ModelEndpointInfo(
        models=ModelListInfo(
            models=[ModelInfo(name="gpt-4o-mini")],
            model_selection_strategy=ModelSelectionStrategy.ROUND_ROBIN,
        ),
        endpoint=EndpointInfo(
            type=EndpointType.OPENAI_MULTIMODAL,
            streaming=True,
        ),
    )

    # Create a complex turn with multiple content types
    sample_audio = create_sample_audio_base64()

    turn = Turn(
        text=[Text(content=[f"Text content {i}" for i in range(10)])],
        image=[Image(content=[f"https://example.com/image_{i}.jpg" for i in range(5)])],
        audio=[Audio(content=[f"wav,{sample_audio}" for i in range(3)])],
    )

    import time

    start_time = time.perf_counter()

    # Convert multiple times to measure performance
    for i in range(100):
        payload = await converter.format_payload(model_endpoint, turn)

    end_time = time.perf_counter()

    logger.info(
        f"Converted 100 complex multimodal turns in {end_time - start_time:.4f} seconds"
    )
    logger.info(
        f"Average time per conversion: {(end_time - start_time) / 100:.6f} seconds"
    )


async def main():
    """Run all examples."""
    logger.info("Starting multimodal chat completions converter examples...")

    # Run all examples
    await example_text_only_conversation()
    print("\n" + "=" * 60 + "\n")

    await example_image_analysis()
    print("\n" + "=" * 60 + "\n")

    await example_audio_transcription()
    print("\n" + "=" * 60 + "\n")

    await example_comprehensive_multimodal()
    print("\n" + "=" * 60 + "\n")

    await example_conversation_with_system_role()
    print("\n" + "=" * 60 + "\n")

    await example_error_handling()
    print("\n" + "=" * 60 + "\n")

    await performance_benchmark()

    logger.info("All examples completed successfully!")


if __name__ == "__main__":
    asyncio.run(main())
