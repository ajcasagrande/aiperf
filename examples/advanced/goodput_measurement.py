#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""
Goodput Measurement Example

Demonstrates goodput metrics with SLO (Service Level Objective) thresholds.

Goodput measures the rate of "good" requests that meet performance SLOs.
For example, with TTFT < 100ms SLO, a request with TTFT=50ms is "good",
but a request with TTFT=150ms is not.

Usage:
    python goodput_measurement.py

Prerequisites:
    - Streaming inference server at localhost:8000
    - Model capable of streaming responses
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from aiperf.cli_runner import run_system_controller
from aiperf.common.config import (
    EndpointConfig,
    InputConfig,
    LoadGeneratorConfig,
    UserConfig,
    load_service_config,
)
from aiperf.common.enums import EndpointType


def main():
    """Run a goodput measurement benchmark."""

    print("Goodput Measurement Example")
    print("=" * 60)
    print("\nGoodput measures the rate of requests meeting SLO thresholds.")
    print("\nSLOs for this benchmark:")
    print("  - Time to First Token (TTFT) < 100 ms")
    print("  - Request Latency < 1000 ms")
    print("  - Inter-Token Latency (ITL) < 50 ms")
    print()

    # Configure endpoint
    endpoint_config = EndpointConfig(
        model_names=["Qwen/Qwen3-0.6B"],
        url="http://localhost:8000",
        type=EndpointType.CHAT,
        streaming=True,
    )

    # Configure input with goodput SLOs
    # SLOs are specified as metric_tag: threshold_value
    input_config = InputConfig(
        goodput={
            "ttft": 100.0,  # TTFT < 100 ms
            "request_latency": 1000.0,  # Latency < 1000 ms
            "inter_token_latency": 50.0,  # ITL < 50 ms
        }
    )

    # Configure load generation
    # Use request rate to create realistic load
    loadgen_config = LoadGeneratorConfig(
        request_rate=20.0,  # 20 req/s
        concurrency=10,
        request_count=200,
        warmup_request_count=20,
    )

    # Create user configuration
    user_config = UserConfig(
        endpoint=endpoint_config,
        input=input_config,
        loadgen=loadgen_config,
    )

    service_config = load_service_config()

    print("Benchmark Configuration:")
    print(f"  Request Rate: {loadgen_config.request_rate} req/s")
    print(f"  Concurrency: {loadgen_config.concurrency}")
    print(f"  Total Requests: {loadgen_config.request_count}")
    print("-" * 60)

    try:
        run_system_controller(user_config, service_config)

        print("\n" + "=" * 60)
        print("Understanding Goodput Results")
        print("=" * 60)
        print("\nLook for these metrics in the output above:")
        print("  - Good Request Count: Number of requests meeting ALL SLOs")
        print("  - Request Count: Total valid requests")
        print("  - Goodput: Good requests per second")
        print("  - Request Throughput: Total requests per second")
        print("\nGoodput Ratio = Good Request Count / Request Count")
        print("\nA high goodput ratio (close to 1.0) indicates the system")
        print("consistently meets performance targets.")
        print("\nA low goodput ratio suggests:")
        print("  - System is overloaded (reduce rate or increase capacity)")
        print("  - SLOs are too aggressive (relax thresholds)")
        print("  - Intermittent performance issues (investigate spikes)")

    except KeyboardInterrupt:
        print("\n\nBenchmark cancelled")
        sys.exit(1)
    except Exception as e:
        print(f"\n\nBenchmark failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
