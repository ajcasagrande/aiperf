#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""
Text Generation Inference (TGI) Integration Example

Demonstrates benchmarking a TGI server from HuggingFace.

TGI provides optimized inference with OpenAI-compatible endpoints.

Usage:
    # Start TGI server first:
    docker run --gpus all --shm-size 1g -p 8080:80 \
        ghcr.io/huggingface/text-generation-inference:latest \
        --model-id Qwen/Qwen3-0.6B

    # Then run this benchmark:
    python tgi_integration.py

Prerequisites:
    - TGI server running on port 8080
    - GPU available
    - Docker installed
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from aiperf.cli_runner import run_system_controller
from aiperf.common.config import (
    EndpointConfig,
    InputConfig,
    LoadGeneratorConfig,
    PromptConfig,
    UserConfig,
    load_service_config,
)
from aiperf.common.config.prompt_config import InputTokensConfig, OutputTokensConfig
from aiperf.common.enums import EndpointType


def main():
    """Run TGI benchmark."""

    print("Text Generation Inference (TGI) Benchmark")
    print("=" * 60)
    print("\nHuggingFace TGI provides optimized inference with features:")
    print("  - Flash Attention for faster computation")
    print("  - Continuous batching for improved throughput")
    print("  - Token streaming with low latency")
    print("-" * 60)

    # Configure TGI endpoint
    # TGI typically runs on port 80 in container (mapped to 8080)
    endpoint_config = EndpointConfig(
        model_names=["Qwen/Qwen3-0.6B"],
        url="http://localhost:8080",  # TGI default Docker mapping
        type=EndpointType.CHAT,
        streaming=True,
        timeout_seconds=120.0,
    )

    # Configure prompts
    # TGI performs well with moderate-length prompts
    prompt_config = PromptConfig(
        input_tokens=InputTokensConfig(
            mean=256,
            stddev=64,
        ),
        output_tokens=OutputTokensConfig(
            mean=128,
            stddev=32,
        ),
    )

    input_config = InputConfig(
        prompt=prompt_config,
        random_seed=42,
    )

    # Configure load - TGI handles concurrency well
    loadgen_config = LoadGeneratorConfig(
        request_rate=30.0,  # 30 req/s
        concurrency=15,  # TGI's continuous batching handles this well
        request_count=300,
        warmup_request_count=30,
    )

    user_config = UserConfig(
        endpoint=endpoint_config,
        input=input_config,
        loadgen=loadgen_config,
    )

    service_config = load_service_config()

    print("\nBenchmark Configuration:")
    print(f"  TGI Endpoint: {endpoint_config.url}")
    print(f"  Model: {endpoint_config.model_names[0]}")
    print(f"  Request Rate: {loadgen_config.request_rate} req/s")
    print(f"  Concurrency: {loadgen_config.concurrency}")
    print(f"  Total Requests: {loadgen_config.request_count}")
    print("-" * 60)

    try:
        run_system_controller(user_config, service_config)

        print("\n" + "=" * 60)
        print("TGI Benchmark Complete")
        print("=" * 60)
        print("\nTGI-specific insights:")
        print("  - TTFT: Benefits from Flash Attention and optimized kernels")
        print("  - Throughput: Continuous batching maximizes GPU utilization")
        print("  - ITL: Should be consistent due to batching")
        print("\nOptimization tips:")
        print("  - Increase concurrency to saturate GPU")
        print("  - Use --max-concurrent-requests in TGI for backpressure")
        print("  - Monitor GPU memory with nvidia-smi")

    except KeyboardInterrupt:
        print("\n\nBenchmark cancelled")
        sys.exit(1)
    except Exception as e:
        print(f"\n\nBenchmark failed: {e}")
        print("\nCommon TGI issues:")
        print("  - Port mismatch: Check Docker port mapping")
        print("  - Model loading: Check TGI logs with 'docker logs'")
        print("  - OOM: Reduce --max-batch-total-tokens in TGI")
        sys.exit(1)


if __name__ == "__main__":
    main()
