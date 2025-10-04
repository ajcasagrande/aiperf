#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""
Simple Benchmark Example

This example demonstrates the most basic AIPerf usage:
- Single model benchmarking
- Default configuration
- Console output only

Usage:
    python simple_benchmark.py

Prerequisites:
    - AIPerf installed: pip install aiperf
    - Inference server running at localhost:8000
    - Model loaded (e.g., Qwen/Qwen3-0.6B)
"""

import sys
from pathlib import Path

# Add aiperf to path if running from source
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from aiperf.cli_runner import run_system_controller
from aiperf.common.config import UserConfig, load_service_config
from aiperf.common.config.endpoint_config import EndpointConfig
from aiperf.common.config.loadgen_config import LoadGeneratorConfig
from aiperf.common.enums import EndpointType


def main():
    """Run a simple benchmark."""

    # Configure the endpoint
    endpoint_config = EndpointConfig(
        model_names=["Qwen/Qwen3-0.6B"],
        url="http://localhost:8000",
        type=EndpointType.CHAT,
        streaming=True,
        timeout_seconds=600.0,
    )

    # Configure load generation
    loadgen_config = LoadGeneratorConfig(
        request_count=100,  # Send 100 requests total
        concurrency=10,  # 10 concurrent requests
        warmup_request_count=10,  # 10 warmup requests
    )

    # Create user configuration
    user_config = UserConfig(
        endpoint=endpoint_config,
        loadgen=loadgen_config,
    )

    # Load service configuration (or use defaults)
    service_config = load_service_config()

    print("Starting simple benchmark...")
    print(f"Endpoint: {endpoint_config.url}")
    print(f"Model: {endpoint_config.model_names[0]}")
    print(f"Requests: {loadgen_config.request_count}")
    print(f"Concurrency: {loadgen_config.concurrency}")
    print("-" * 60)

    # Run the benchmark
    try:
        run_system_controller(user_config, service_config)
    except KeyboardInterrupt:
        print("\nBenchmark cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\nBenchmark failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
