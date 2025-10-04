#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""
Request Rate Benchmark Example

Demonstrates request rate benchmarking with different modes:
- CONSTANT: Fixed inter-arrival time
- POISSON: Exponentially distributed (realistic traffic)
- CONCURRENCY_BURST: Maximum throughput up to concurrency limit

Usage:
    python request_rate_test.py

This example runs three benchmarks to compare different request rate modes.
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
from aiperf.common.enums import EndpointType, RequestRateMode


def run_benchmark(
    mode: RequestRateMode, request_rate: float = 10.0, concurrency: int = None
):
    """
    Run a benchmark with specified request rate mode.

    Args:
        mode: Request rate mode (CONSTANT, POISSON, CONCURRENCY_BURST)
        request_rate: Target request rate (requests/sec)
        concurrency: Maximum concurrent requests
    """
    print(f"\n{'=' * 60}")
    print(f"Request Rate Mode: {mode.value.upper()}")
    print(f"{'=' * 60}")

    endpoint_config = EndpointConfig(
        model_names=["Qwen/Qwen3-0.6B"],
        url="http://localhost:8000",
        type=EndpointType.CHAT,
        streaming=True,
    )

    loadgen_config = LoadGeneratorConfig(
        request_rate=request_rate
        if mode != RequestRateMode.CONCURRENCY_BURST
        else None,
        request_rate_mode=mode,
        concurrency=concurrency,
        request_count=100,
        warmup_request_count=10,
    )

    user_config = UserConfig(
        endpoint=endpoint_config,
        loadgen=loadgen_config,
    )

    service_config = load_service_config()

    print(f"Request Rate: {request_rate if request_rate else 'N/A'} req/s")
    print(f"Concurrency: {concurrency if concurrency else 'unlimited'}")
    print(f"Mode: {mode.value}")
    print("-" * 60)

    try:
        run_system_controller(user_config, service_config)
    except KeyboardInterrupt:
        print("\nBenchmark cancelled")
        raise
    except Exception as e:
        print(f"\nBenchmark failed: {e}")
        raise


def main():
    """Run benchmarks with different request rate modes."""

    print("Request Rate Benchmark Comparison")
    print("\nThis example runs three benchmarks to demonstrate different")
    print("request rate modes and their characteristics.\n")

    try:
        # 1. Constant mode: Evenly spaced requests
        print("\n[1/3] CONSTANT Mode")
        print("Sends requests at fixed intervals (1/rate)")
        print("Produces predictable, evenly-spaced load")
        run_benchmark(
            mode=RequestRateMode.CONSTANT,
            request_rate=10.0,
            concurrency=5,
        )

        # 2. Poisson mode: Realistic traffic pattern
        print("\n[2/3] POISSON Mode")
        print("Uses exponentially distributed inter-arrival times")
        print("Simulates realistic, bursty traffic patterns")
        run_benchmark(
            mode=RequestRateMode.POISSON,
            request_rate=10.0,
            concurrency=5,
        )

        # 3. Concurrency burst: Maximum throughput
        print("\n[3/3] CONCURRENCY_BURST Mode")
        print("Sends requests as fast as possible up to concurrency limit")
        print("Tests maximum system throughput")
        run_benchmark(
            mode=RequestRateMode.CONCURRENCY_BURST,
            request_rate=None,
            concurrency=10,
        )

        print("\n" + "=" * 60)
        print("All benchmarks completed!")
        print("=" * 60)
        print("\nComparison Notes:")
        print("- CONSTANT: Most predictable, good for capacity planning")
        print("- POISSON: Most realistic, good for production simulation")
        print("- CONCURRENCY_BURST: Maximum throughput testing")

    except KeyboardInterrupt:
        print("\n\nBenchmarks cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\nBenchmarks failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
