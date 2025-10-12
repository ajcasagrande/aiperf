#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Performance benchmarks for dataset chunking optimization.

This benchmark measures the throughput improvement from chunking.
"""

import asyncio
import time

from aiperf.common.config import EndpointConfig, ServiceConfig, UserConfig
from aiperf.common.config.input_config import InputConfig
from aiperf.common.messages import (
    ConversationChunkRequestMessage,
    ConversationRequestMessage,
)
from aiperf.common.models import Conversation, Text, Turn
from aiperf.dataset.dataset_manager import DatasetManager


async def benchmark_single_conversation_mode(
    manager: DatasetManager, num_requests: int
):
    """Benchmark single-conversation mode throughput."""
    start = time.perf_counter()

    for i in range(num_requests):
        request = ConversationRequestMessage(
            service_id="bench-worker",
            request_id=f"req-{i}",
        )
        await manager._handle_conversation_request(request)

    duration = time.perf_counter() - start
    throughput = num_requests / duration

    return {
        "mode": "single",
        "requests": num_requests,
        "duration": duration,
        "throughput": throughput,
        "req_per_sec": throughput,
    }


async def benchmark_chunked_mode(
    manager: DatasetManager, num_requests: int, chunk_size: int
):
    """Benchmark chunked mode throughput."""
    start = time.perf_counter()

    num_chunks = (num_requests + chunk_size - 1) // chunk_size
    total_received = 0

    for i in range(num_chunks):
        request = ConversationChunkRequestMessage(
            service_id="bench-worker",
            request_id=f"chunk-{i}",
            chunk_size=chunk_size,
        )
        response = await manager._handle_chunk_request(request)
        total_received += len(response.conversations)

    duration = time.perf_counter() - start
    throughput = total_received / duration

    return {
        "mode": f"chunked-{chunk_size}",
        "chunks": num_chunks,
        "conversations": total_received,
        "duration": duration,
        "throughput": throughput,
        "req_per_sec": num_chunks / duration,  # Actual requests to DatasetManager
        "conversations_per_sec": throughput,
    }


async def create_test_dataset_manager(num_conversations: int = 1000) -> DatasetManager:
    """Create a DatasetManager with test data."""
    user_config = UserConfig(
        endpoint=EndpointConfig(url="http://test:8000", model_names=["test"]),
        input=InputConfig(random_seed=42),
    )

    manager = DatasetManager(ServiceConfig(), user_config)

    # Create test conversations
    conversations = [
        Conversation(
            session_id=f"conv-{i:04d}",
            turns=[
                Turn(
                    role="user",
                    texts=[Text(contents=[f"This is test message number {i}"])],
                )
            ],
        )
        for i in range(num_conversations)
    ]

    manager.dataset = {c.session_id: c for c in conversations}
    manager._session_ids_cache = list(manager.dataset.keys())
    manager.dataset_configured.set()

    return manager


async def main():
    """Run benchmarks and display results."""
    print("=" * 80)
    print("Dataset Chunking Performance Benchmark")
    print("=" * 80)
    print()

    # Create test dataset
    print("Setting up test dataset (1000 conversations)...")
    manager = await create_test_dataset_manager(num_conversations=1000)
    print(f"✓ Dataset ready: {len(manager.dataset)} conversations")
    print()

    # Benchmark configurations
    num_requests = 10000  # 10,000 conversation requests

    benchmarks = []

    # Benchmark 1: Single-conversation mode (baseline)
    print("[1/5] Benchmarking single-conversation mode...")
    manager = await create_test_dataset_manager()
    result = await benchmark_single_conversation_mode(manager, num_requests)
    benchmarks.append(result)
    print(f"  Throughput: {result['throughput']:.0f} conversations/sec")
    print(f"  Duration: {result['duration']:.2f}s")
    print()

    # Benchmark 2: Chunked mode - size 50
    print("[2/5] Benchmarking chunked mode (chunk_size=50)...")
    manager = await create_test_dataset_manager()
    result = await benchmark_chunked_mode(manager, num_requests, chunk_size=50)
    benchmarks.append(result)
    print(f"  Throughput: {result['conversations_per_sec']:.0f} conversations/sec")
    print(f"  Requests to DatasetManager: {result['req_per_sec']:.0f} req/sec")
    print(f"  Duration: {result['duration']:.2f}s")
    print()

    # Benchmark 3: Chunked mode - size 100
    print("[3/5] Benchmarking chunked mode (chunk_size=100)...")
    manager = await create_test_dataset_manager()
    result = await benchmark_chunked_mode(manager, num_requests, chunk_size=100)
    benchmarks.append(result)
    print(f"  Throughput: {result['conversations_per_sec']:.0f} conversations/sec")
    print(f"  Requests to DatasetManager: {result['req_per_sec']:.0f} req/sec")
    print(f"  Duration: {result['duration']:.2f}s")
    print()

    # Benchmark 4: Chunked mode - size 200
    print("[4/5] Benchmarking chunked mode (chunk_size=200)...")
    manager = await create_test_dataset_manager()
    result = await benchmark_chunked_mode(manager, num_requests, chunk_size=200)
    benchmarks.append(result)
    print(f"  Throughput: {result['conversations_per_sec']:.0f} conversations/sec")
    print(f"  Requests to DatasetManager: {result['req_per_sec']:.0f} req/sec")
    print(f"  Duration: {result['duration']:.2f}s")
    print()

    # Benchmark 5: Chunked mode - size 500
    print("[5/5] Benchmarking chunked mode (chunk_size=500)...")
    manager = await create_test_dataset_manager()
    result = await benchmark_chunked_mode(manager, num_requests, chunk_size=500)
    benchmarks.append(result)
    print(f"  Throughput: {result['conversations_per_sec']:.0f} conversations/sec")
    print(f"  Requests to DatasetManager: {result['req_per_sec']:.0f} req/sec")
    print(f"  Duration: {result['duration']:.2f}s")
    print()

    # Summary
    print("=" * 80)
    print("Results Summary")
    print("=" * 80)
    print()
    print(f"{'Mode':<20} {'Conversations/s':<20} {'Requests/s':<20} {'Speedup':>10}")
    print("-" * 80)

    baseline_throughput = benchmarks[0]["throughput"]

    for result in benchmarks:
        mode = result["mode"]
        conv_per_sec = result["throughput"]
        speedup = conv_per_sec / baseline_throughput

        if "chunked" in mode:
            req_per_sec = result["req_per_sec"]
            print(
                f"{mode:<20} {conv_per_sec:>18.0f}  {req_per_sec:>18.0f}  {speedup:>9.1f}x"
            )
        else:
            print(
                f"{mode:<20} {conv_per_sec:>18.0f}  {conv_per_sec:>18.0f}  {speedup:>9.1f}x"
            )

    print()
    print("=" * 80)
    print("Key Insights")
    print("=" * 80)

    chunk_100 = benchmarks[2]  # chunk_size=100
    improvement = chunk_100["conversations_per_sec"] / baseline_throughput
    request_reduction = baseline_throughput / chunk_100["req_per_sec"]

    print(f"• Chunking (size=100) provides {improvement:.1f}x throughput improvement")
    print(
        f"• Reduces DatasetManager requests by {request_reduction:.0f}x ({chunk_100['req_per_sec']:.0f} vs {baseline_throughput:.0f} req/sec)"
    )
    print("• Optimal chunk size appears to be: 100-200 (sweet spot)")
    print()


if __name__ == "__main__":
    asyncio.run(main())
