#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""
Streaming Benchmark Example

Demonstrates benchmarking streaming endpoints with token-by-token metrics.

Streaming endpoints return tokens incrementally, allowing measurement of:
- Time to First Token (TTFT)
- Inter-Token Latency (ITL)
- Output Token Throughput Per User

Usage:
    python streaming_benchmark.py

Prerequisites:
    - Inference server supporting streaming at localhost:8000
    - Model with streaming capability
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from aiperf.cli_runner import run_system_controller
from aiperf.common.config import (
    EndpointConfig,
    LoadGeneratorConfig,
    UserConfig,
    load_service_config,
)
from aiperf.common.enums import EndpointType


def main():
    """Run a streaming benchmark."""

    # Configure streaming endpoint
    endpoint_config = EndpointConfig(
        model_names=["Qwen/Qwen3-0.6B"],
        url="http://localhost:8000",
        type=EndpointType.CHAT,
        streaming=True,  # Enable streaming
        timeout_seconds=600.0,
    )

    # Configure load generation
    loadgen_config = LoadGeneratorConfig(
        request_count=50,
        concurrency=5,
        warmup_request_count=5,
    )

    # Create user configuration
    user_config = UserConfig(
        endpoint=endpoint_config,
        loadgen=loadgen_config,
    )

    service_config = load_service_config()

    print("Streaming Benchmark")
    print("=" * 60)
    print(f"Endpoint: {endpoint_config.url}")
    print(f"Model: {endpoint_config.model_names[0]}")
    print(f"Streaming: {endpoint_config.streaming}")
    print(f"Requests: {loadgen_config.request_count}")
    print(f"Concurrency: {loadgen_config.concurrency}")
    print()
    print("Streaming-specific metrics that will be reported:")
    print("  - Time to First Token (TTFT)")
    print("  - Inter-Token Latency (ITL)")
    print("  - Output Token Throughput Per User")
    print("-" * 60)

    try:
        run_system_controller(user_config, service_config)
    except KeyboardInterrupt:
        print("\nBenchmark cancelled")
        sys.exit(1)
    except Exception as e:
        print(f"\nBenchmark failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
