#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""
Request Cancellation Example

Demonstrates request cancellation for testing timeout behavior.

Request cancellation allows you to:
- Test how your system handles client timeouts
- Measure goodput under timeout conditions
- Validate timeout error handling

Usage:
    python request_cancellation.py

This will run a benchmark where 20% of requests are cancelled after 5 seconds.
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
    """Run a benchmark with request cancellation."""

    print("Request Cancellation Example")
    print("=" * 60)
    print("\nThis benchmark demonstrates request cancellation, where a")
    print("percentage of requests are cancelled after a specified delay.")
    print("\nConfiguration:")
    print("  - Cancellation Rate: 20% of requests")
    print("  - Cancellation Delay: 5 seconds")
    print("\nCancelled requests will:")
    print("  - Have HTTP code 499 (Client Closed Request)")
    print("  - Be marked as cancelled in the results")
    print("  - Count toward error statistics")
    print("-" * 60)

    # Configure endpoint
    endpoint_config = EndpointConfig(
        model_names=["Qwen/Qwen3-0.6B"],
        url="http://localhost:8000",
        type=EndpointType.CHAT,
        streaming=True,
        timeout_seconds=600.0,
    )

    # Configure load generation with cancellation
    loadgen_config = LoadGeneratorConfig(
        request_rate=5.0,  # 5 req/s
        concurrency=5,
        request_count=50,
        warmup_request_count=5,
        # Cancellation settings
        request_cancellation_rate=20.0,  # Cancel 20% of requests
        request_cancellation_delay=5.0,  # After 5 seconds
    )

    # Create user configuration
    user_config = UserConfig(
        endpoint=endpoint_config,
        loadgen=loadgen_config,
    )

    service_config = load_service_config()

    print("\nBenchmark Configuration:")
    print(f"  Request Rate: {loadgen_config.request_rate} req/s")
    print(f"  Total Requests: {loadgen_config.request_count}")
    print(f"  Cancellation Rate: {loadgen_config.request_cancellation_rate}%")
    print(f"  Cancellation Delay: {loadgen_config.request_cancellation_delay}s")
    print(
        f"  Expected Cancellations: ~{int(loadgen_config.request_count * loadgen_config.request_cancellation_rate / 100)}"
    )
    print("-" * 60)

    try:
        run_system_controller(user_config, service_config)

        print("\n" + "=" * 60)
        print("Understanding Cancellation Results")
        print("=" * 60)
        print("\nIn the results above, check:")
        print("  - Error Request Count: Should show cancelled requests")
        print("  - Request Count: Total successful (non-cancelled) requests")
        print("\nCancelled requests are treated as errors with code 499.")
        print("They are excluded from latency metrics but counted separately.")

    except KeyboardInterrupt:
        print("\n\nBenchmark cancelled")
        sys.exit(1)
    except Exception as e:
        print(f"\n\nBenchmark failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
