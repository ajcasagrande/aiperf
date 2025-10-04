#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""
Trace Replay Benchmark Example

This example demonstrates trace replay benchmarking using the
fixed schedule feature.

Trace replay allows you to:
- Reproduce real production traffic patterns
- Compare different model deployments with identical workloads
- Test system behavior under specific load patterns

Usage:
    python trace_replay.py

This will:
    1. Generate a sample trace file with timestamps
    2. Run a benchmark replaying that trace
"""

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))


def generate_sample_trace(output_file: Path, duration_seconds: int = 60):
    """
    Generate a sample trace file.

    Trace format (Mooncake-compatible):
    - timestamp: Unix timestamp in milliseconds
    - text_input: Prompt text (or input_length for synthetic)
    - hash_ids: (optional) For KV cache simulation

    Args:
        output_file: Path to write the trace
        duration_seconds: Duration of trace in seconds
    """
    start_time_ms = int(time.time() * 1000)

    prompts = [
        "What is artificial intelligence?",
        "Explain machine learning.",
        "What is deep learning?",
        "How do neural networks work?",
        "What is natural language processing?",
    ]

    with open(output_file, "w") as f:
        current_time_ms = start_time_ms

        # Generate requests with varying inter-arrival times
        request_id = 0
        while (current_time_ms - start_time_ms) < (duration_seconds * 1000):
            # Poisson-like arrival pattern
            # High activity periods and low activity periods
            second_offset = (current_time_ms - start_time_ms) // 1000

            if second_offset % 20 < 10:
                # High activity: 10 req/s
                interval_ms = 100
            else:
                # Low activity: 2 req/s
                interval_ms = 500

            current_time_ms += interval_ms

            entry = {
                "timestamp": current_time_ms,
                "text_input": prompts[request_id % len(prompts)],
                # Optional: For synthetic prompts, use input_length instead
                # "input_length": 100,
                # Optional: For KV cache simulation
                # "hash_ids": [1, 2, 3, 4, 5],
            }

            f.write(json.dumps(entry) + "\n")
            request_id += 1

    print(f"Generated trace with {request_id} requests over {duration_seconds}s")
    print(f"Trace file: {output_file}")
    print(f"Average rate: {request_id / duration_seconds:.1f} req/s")


def run_trace_replay(trace_file: Path):
    """
    Run a trace replay benchmark.

    Args:
        trace_file: Path to the trace file
    """
    from aiperf.cli_runner import run_system_controller
    from aiperf.common.config import (
        EndpointConfig,
        InputConfig,
        LoadGeneratorConfig,
        UserConfig,
        load_service_config,
    )
    from aiperf.common.enums import CustomDatasetType, EndpointType

    print("\nRunning trace replay benchmark...")
    print("=" * 60)

    # Configure endpoint
    endpoint_config = EndpointConfig(
        model_names=["Qwen/Qwen3-0.6B"],
        url="http://localhost:8000",
        type=EndpointType.CHAT,
        streaming=True,
    )

    # Configure input with trace replay
    input_config = InputConfig(
        file=trace_file,
        custom_dataset_type=CustomDatasetType.MOONCAKE_TRACE,
        # Enable fixed schedule mode
        fixed_schedule=True,
        # Auto-offset: start trace at time 0
        fixed_schedule_auto_offset=True,
        # Optional: filter trace by time range
        # fixed_schedule_start_offset=0,
        # fixed_schedule_end_offset=30000,  # First 30 seconds only
        random_seed=42,
    )

    # Configure load generation
    # Note: request_count and concurrency are ignored in fixed schedule mode
    loadgen_config = LoadGeneratorConfig(
        # Grace period for in-flight requests after trace ends
        benchmark_grace_period=30.0,
    )

    # Create user configuration
    user_config = UserConfig(
        endpoint=endpoint_config,
        input=input_config,
        loadgen=loadgen_config,
    )

    # Load service configuration
    service_config = load_service_config()

    print(f"Trace file: {trace_file}")
    print("Mode: Fixed Schedule (Trace Replay)")
    print(f"Auto-offset: {input_config.fixed_schedule_auto_offset}")
    print(f"Grace period: {loadgen_config.benchmark_grace_period}s")
    print("-" * 60)

    try:
        run_system_controller(user_config, service_config)
    except KeyboardInterrupt:
        print("\nBenchmark cancelled")
        sys.exit(1)
    except Exception as e:
        print(f"\nBenchmark failed: {e}")
        sys.exit(1)


def main():
    """Main function."""
    # Create output directory
    output_dir = Path(__file__).parent / "data"
    output_dir.mkdir(exist_ok=True)

    # Generate sample trace
    trace_file = output_dir / "sample_trace.jsonl"
    generate_sample_trace(trace_file, duration_seconds=60)

    print("\nTrace Format Example:")
    print("-" * 60)
    with open(trace_file) as f:
        # Show first 3 lines
        for i, line in enumerate(f):
            if i >= 3:
                break
            entry = json.loads(line)
            print(json.dumps(entry, indent=2))
            print()

    # Analyze trace
    with open(trace_file) as f:
        lines = f.readlines()
        timestamps = [json.loads(line)["timestamp"] for line in lines]

    print("Trace Statistics:")
    print(f"  Total requests: {len(timestamps)}")
    print(f"  Start time: {timestamps[0]} ms")
    print(f"  End time: {timestamps[-1]} ms")
    print(f"  Duration: {(timestamps[-1] - timestamps[0]) / 1000:.1f} s")
    print()

    # Run benchmark
    response = input("Run trace replay benchmark? [y/N]: ")
    if response.lower() == "y":
        run_trace_replay(trace_file)
    else:
        print(f"\nTrace saved to: {trace_file}")
        print("You can run trace replay later with:")
        print(f"  aiperf profile --file {trace_file} \\")
        print("    --custom-dataset-type mooncake_trace \\")
        print("    --fixed-schedule \\")
        print("    --fixed-schedule-auto-offset \\")
        print("    --model Qwen/Qwen3-0.6B \\")
        print("    --url http://localhost:8000 \\")
        print("    --endpoint-type chat")


if __name__ == "__main__":
    main()
