#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""
vLLM Integration Example

Demonstrates benchmarking a vLLM server with optimal settings.

vLLM is a high-performance inference server with OpenAI-compatible API.

Usage:
    # Start vLLM server first:
    python -m vllm.entrypoints.openai.api_server \
        --model Qwen/Qwen3-0.6B \
        --port 8000

    # Then run this benchmark:
    python vllm_integration.py

Prerequisites:
    - vLLM installed: pip install vllm
    - GPU available (recommended)
    - Model cached locally or accessible
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
from aiperf.common.enums import EndpointType, RequestRateMode


def main():
    """Run vLLM benchmark with optimal settings."""

    print("vLLM Integration Benchmark")
    print("=" * 60)
    print("\nThis benchmark is optimized for vLLM servers with:")
    print("  - Streaming enabled for TTFT/ITL metrics")
    print("  - Poisson request rate for realistic traffic")
    print("  - Appropriate concurrency for GPU utilization")
    print("  - Token length distribution matching typical usage")
    print("-" * 60)

    # Configure vLLM endpoint
    endpoint_config = EndpointConfig(
        model_names=["Qwen/Qwen3-0.6B"],
        url="http://localhost:8000",
        type=EndpointType.CHAT,
        streaming=True,  # vLLM supports streaming
        timeout_seconds=120.0,  # Reasonable timeout for generation
    )

    # Configure synthetic prompts with realistic token distributions
    prompt_config = PromptConfig(
        input_tokens=InputTokensConfig(
            mean=512,  # Average prompt length
            stddev=128,  # Some variation
        ),
        output_tokens=OutputTokensConfig(
            mean=256,  # Average completion length
            stddev=64,  # Some variation
        ),
    )

    input_config = InputConfig(
        prompt=prompt_config,
        random_seed=42,  # Reproducible results
    )

    # Configure load generation
    # Poisson mode simulates realistic bursty traffic
    loadgen_config = LoadGeneratorConfig(
        request_rate=20.0,  # 20 req/s
        request_rate_mode=RequestRateMode.POISSON,  # Realistic traffic
        concurrency=10,  # Limit concurrent for GPU memory
        request_count=200,
        warmup_request_count=20,  # Warm up vLLM's KV cache
    )

    user_config = UserConfig(
        endpoint=endpoint_config,
        input=input_config,
        loadgen=loadgen_config,
    )

    service_config = load_service_config()

    print("\nBenchmark Configuration:")
    print(f"  Model: {endpoint_config.model_names[0]}")
    print(f"  Endpoint: {endpoint_config.url}")
    print(f"  Request Rate: {loadgen_config.request_rate} req/s")
    print(f"  Mode: {loadgen_config.request_rate_mode.value}")
    print(f"  Concurrency: {loadgen_config.concurrency}")
    print(f"  Total Requests: {loadgen_config.request_count}")
    print(
        f"  Input Tokens: {prompt_config.input_tokens.mean} ± {prompt_config.input_tokens.stddev}"
    )
    print(
        f"  Output Tokens: {prompt_config.output_tokens.mean} ± {prompt_config.output_tokens.stddev}"
    )
    print("-" * 60)

    try:
        run_system_controller(user_config, service_config)

        print("\n" + "=" * 60)
        print("vLLM Benchmark Complete")
        print("=" * 60)
        print("\nKey metrics for vLLM performance:")
        print("  - TTFT: Measures vLLM's prefill performance")
        print("  - ITL: Measures decode performance")
        print("  - Throughput: Overall token generation rate")
        print("\nvLLM optimization tips:")
        print("  - Lower TTFT: Increase --max-model-len or optimize prefill")
        print("  - Lower ITL: Tune batch size and speculative decoding")
        print("  - Higher throughput: Increase concurrency up to GPU capacity")

    except KeyboardInterrupt:
        print("\n\nBenchmark cancelled")
        sys.exit(1)
    except Exception as e:
        print(f"\n\nBenchmark failed: {e}")
        print("\nCommon vLLM issues:")
        print("  - Server not running: Check vLLM process")
        print("  - Model not loaded: Check vLLM logs")
        print("  - OOM: Reduce concurrency or input/output token lengths")
        sys.exit(1)


if __name__ == "__main__":
    main()
