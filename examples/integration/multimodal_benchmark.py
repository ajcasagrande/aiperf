#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""
Multimodal Benchmark Example

Demonstrates benchmarking multimodal endpoints (text + images).

This example shows how to benchmark vision-language models that accept
both text and image inputs.

Usage:
    python multimodal_benchmark.py

Prerequisites:
    - Multimodal inference server (e.g., vLLM with vision model)
    - Vision-capable model (e.g., Qwen2-VL, LLaVA)
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from aiperf.cli_runner import run_system_controller
from aiperf.common.config import (
    EndpointConfig,
    ImageConfig,
    InputConfig,
    LoadGeneratorConfig,
    PromptConfig,
    UserConfig,
    load_service_config,
)
from aiperf.common.config.image_config import ImageHeightConfig, ImageWidthConfig
from aiperf.common.config.prompt_config import InputTokensConfig
from aiperf.common.enums import EndpointType, ImageFormat


def main():
    """Run multimodal benchmark."""

    print("Multimodal Benchmark Example")
    print("=" * 60)
    print("\nThis benchmark tests vision-language models with both")
    print("text prompts and images.")
    print("\nEach request will include:")
    print("  - Text prompt (describing the task)")
    print("  - One or more images")
    print("\nMetrics will reflect the processing of both modalities.")
    print("-" * 60)

    # Configure endpoint for multimodal model
    endpoint_config = EndpointConfig(
        model_names=["Qwen/Qwen2-VL-7B-Instruct"],  # Example vision model
        url="http://localhost:8000",
        type=EndpointType.CHAT,
        streaming=True,
        timeout_seconds=180.0,  # Longer timeout for image processing
    )

    # Configure text prompts
    # For vision models, prompts are typically shorter
    prompt_config = PromptConfig(
        input_tokens=InputTokensConfig(
            mean=128,  # Shorter text prompts
            stddev=32,
        ),
        batch_size=1,  # Number of images per request
    )

    # Configure image generation
    # Images will be synthetically generated
    image_config = ImageConfig(
        width=ImageWidthConfig(
            mean=512,  # Typical vision model input
            stddev=128,
        ),
        height=ImageHeightConfig(
            mean=512,
            stddev=128,
        ),
        format=ImageFormat.PNG,  # PNG for quality
        batch_size=1,  # 1 image per request (can increase for multi-image)
    )

    input_config = InputConfig(
        prompt=prompt_config,
        image=image_config,
        random_seed=42,
    )

    # Configure load - vision models typically slower
    loadgen_config = LoadGeneratorConfig(
        request_rate=5.0,  # Lower rate for complex processing
        concurrency=5,  # Lower concurrency due to memory
        request_count=50,
        warmup_request_count=5,
    )

    user_config = UserConfig(
        endpoint=endpoint_config,
        input=input_config,
        loadgen=loadgen_config,
    )

    service_config = load_service_config()

    print("\nBenchmark Configuration:")
    print(f"  Model: {endpoint_config.model_names[0]}")
    print("  Modalities: Text + Images")
    print(f"  Request Rate: {loadgen_config.request_rate} req/s")
    print(f"  Concurrency: {loadgen_config.concurrency}")
    print(f"  Image Size: {image_config.width.mean}x{image_config.height.mean}px")
    print(f"  Images per Request: {image_config.batch_size}")
    print("-" * 60)

    try:
        run_system_controller(user_config, service_config)

        print("\n" + "=" * 60)
        print("Multimodal Benchmark Complete")
        print("=" * 60)
        print("\nUnderstanding multimodal results:")
        print("  - TTFT: Includes image encoding + text prefill")
        print("  - Latency: Total time including visual processing")
        print("  - Throughput: May be lower than text-only models")
        print("\nVision model characteristics:")
        print("  - Higher TTFT due to image encoding")
        print("  - More GPU memory per request")
        print("  - Better performance with image caching")

    except KeyboardInterrupt:
        print("\n\nBenchmark cancelled")
        sys.exit(1)
    except Exception as e:
        print(f"\n\nBenchmark failed: {e}")
        print("\nCommon multimodal issues:")
        print("  - Image encoding errors: Check image format support")
        print("  - OOM: Reduce image size or concurrency")
        print("  - Slow responses: Normal for vision models")
        sys.exit(1)


if __name__ == "__main__":
    print("\nNote: This example uses synthetic images.")
    print("For real images, use a custom dataset with actual image URLs.")
    print("See examples/custom-datasets/ for custom dataset examples.")
    print()

    response = input("Continue with synthetic images? [y/N]: ")
    if response.lower() != "y":
        print("\nExiting. Modify this script to use your image dataset.")
        sys.exit(0)

    main()
