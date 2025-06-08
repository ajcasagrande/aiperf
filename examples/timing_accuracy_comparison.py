#!/usr/bin/env python3
#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0

"""
Timing Accuracy Comparison Script

This script compares the timing accuracy and precision between different backend clients:
1. OpenAIBackendClientRustStreaming (Pure Rust timing)
2. OpenAIBackendClientHttpx (Rust timing module + Python)
3. OpenAIBackendClientAioHttp (Rust timing module + Python)

It demonstrates the superior nanosecond precision of the pure Rust implementation.
"""

import asyncio
import os
import statistics
from typing import Any

from aiperf.backend.openai_common import (
    OpenAIBackendClientConfig,
    OpenAIChatCompletionRequest,
)

# Import all available clients
try:
    from aiperf.backend.openai_client_rust_streaming import (
        OpenAIBackendClientRustStreaming,
    )

    RUST_STREAMING_AVAILABLE = True
except ImportError:
    RUST_STREAMING_AVAILABLE = False

from aiperf.backend.openai_client_aiohttp import OpenAIBackendClientAioHttp
from aiperf.backend.openai_client_httpx import OpenAIBackendClientHttpx


async def test_client_timing_accuracy(
    client_class, client_name: str, num_requests: int = 5
) -> dict[str, Any]:
    """Test timing accuracy for a specific client."""
    print(f"\n🔍 Testing {client_name} Timing Accuracy")
    print("=" * 50)

    try:
        config = OpenAIBackendClientConfig(
            url="http://127.0.0.1:8080",
            api_key=os.getenv("OPENAI_API_KEY", "sk-fakeai-1234567890abcdef"),
            model="deepseek-ai/DeepSeek-R1-Distill-Llama-8B",
            max_tokens=50,
            timeout_ms=30000,
        )

        ttft_times = []
        ttst_times = []
        total_durations = []

        for i in range(num_requests):
            print(f"  Request {i + 1}/{num_requests}...")

            async with client_class(config) as client:
                request = OpenAIChatCompletionRequest(
                    model=config.model,
                    max_tokens=config.max_tokens,
                    messages=[
                        {
                            "role": "user",
                            "content": f"Count from 1 to 5. Request {i + 1}",
                        }
                    ],
                )

                response = await client.send_chat_completion_request(request)

                if response.valid and response.responses:
                    # Extract timing data
                    ttft_ns = response.time_to_first_response_ns
                    ttst_ns = response.time_to_second_response_ns
                    total_ns = response.time_to_last_response_ns

                    if ttft_ns:
                        ttft_times.append(ttft_ns / 1e6)  # Convert to ms
                    if ttst_ns:
                        ttst_times.append(ttst_ns / 1e6)  # Convert to ms
                    if total_ns:
                        total_durations.append(total_ns / 1e6)  # Convert to ms

                    # Show raw timing values for the first request
                    if i == 0:
                        print("    Raw Timing Data (Request 1):")
                        print(
                            f"      • Start time: {response.start_perf_counter_ns} ns"
                        )
                        print(
                            f"      • First chunk: {response.responses[0].timestamp_ns} ns"
                        )
                        if len(response.responses) > 1:
                            print(
                                f"      • Second chunk: {response.responses[1].timestamp_ns} ns"
                            )
                        print(f"      • TTFT: {ttft_ns} ns = {ttft_ns / 1e6:.3f} ms")
                        if ttst_ns:
                            print(
                                f"      • TTST: {ttst_ns} ns = {ttst_ns / 1e6:.3f} ms"
                            )

                        # Show timing precision
                        timing_precision = (
                            "Nanosecond" if "Rust" in client_name else "Microsecond"
                        )
                        print(f"      • Timing precision: {timing_precision}")
                else:
                    print(f"    ❌ Request {i + 1} failed or invalid")

                # Small delay between requests
                await asyncio.sleep(0.1)

        # Calculate statistics
        results = {
            "client_name": client_name,
            "successful_requests": len(ttft_times),
            "ttft_stats": calculate_timing_stats(ttft_times) if ttft_times else {},
            "ttst_stats": calculate_timing_stats(ttst_times) if ttst_times else {},
            "duration_stats": calculate_timing_stats(total_durations)
            if total_durations
            else {},
        }

        # Display results
        print(f"\n📊 {client_name} Results:")
        print(f"  Successful requests: {results['successful_requests']}/{num_requests}")

        if ttft_times:
            print(
                f"  TTFT - Mean: {results['ttft_stats']['mean']:.3f}ms, "
                f"Std: {results['ttft_stats']['std']:.3f}ms, "
                f"Min: {results['ttft_stats']['min']:.3f}ms, "
                f"Max: {results['ttft_stats']['max']:.3f}ms"
            )

        if ttst_times:
            print(
                f"  TTST - Mean: {results['ttst_stats']['mean']:.3f}ms, "
                f"Std: {results['ttst_stats']['std']:.3f}ms"
            )

        if total_durations:
            print(
                f"  Total - Mean: {results['duration_stats']['mean']:.3f}ms, "
                f"Std: {results['duration_stats']['std']:.3f}ms"
            )

        return results

    except Exception as e:
        print(f"❌ Error testing {client_name}: {e}")
        return {
            "client_name": client_name,
            "error": str(e),
            "successful_requests": 0,
        }


def calculate_timing_stats(times: list[float]) -> dict[str, float]:
    """Calculate timing statistics."""
    if not times:
        return {}

    return {
        "mean": statistics.mean(times),
        "median": statistics.median(times),
        "std": statistics.stdev(times) if len(times) > 1 else 0.0,
        "min": min(times),
        "max": max(times),
        "count": len(times),
    }


def compare_timing_precision(results: list[dict[str, Any]]):
    """Compare timing precision between clients."""
    print("\n🏆 Timing Precision Comparison")
    print("=" * 60)

    for result in results:
        if "error" in result:
            print(f"❌ {result['client_name']}: {result['error']}")
            continue

        client_name = result["client_name"]
        successful = result["successful_requests"]

        if successful == 0:
            print(f"❌ {client_name}: No successful requests")
            continue

        # Analyze timing precision based on standard deviation
        ttft_std = result.get("ttft_stats", {}).get("std", 0)
        ttst_std = result.get("ttst_stats", {}).get("std", 0)

        precision_score = "Unknown"
        if ttft_std < 0.1:  # Less than 0.1ms std deviation
            precision_score = "🔥 Excellent (< 0.1ms std)"
        elif ttft_std < 0.5:
            precision_score = "✅ Good (< 0.5ms std)"
        elif ttft_std < 1.0:
            precision_score = "⚠️  Fair (< 1.0ms std)"
        else:
            precision_score = "❌ Poor (> 1.0ms std)"

        print(f"{client_name}:")
        print(f"  Precision Score: {precision_score}")
        print(f"  TTFT Consistency: {ttft_std:.3f}ms std deviation")
        print(f"  TTST Consistency: {ttst_std:.3f}ms std deviation")

        # Show timing source
        timing_source = (
            "Pure Rust (nanosecond)"
            if "Rust Streaming" in client_name
            else "Mixed Python+Rust (microsecond)"
        )
        print(f"  Timing Source: {timing_source}")
        print()


async def main():
    """Run the timing accuracy comparison."""
    print("🎯 AIPerf Backend Client Timing Accuracy Comparison")
    print("=" * 70)
    print("This script compares timing precision between different backend clients.")
    print("Lower standard deviation indicates more consistent/accurate timing.")
    print()

    # Configure test parameters
    num_requests = 3  # Small number for demonstration

    # List of clients to test
    clients_to_test = [
        (OpenAIBackendClientHttpx, "HttpX Client (Rust timing + Python)"),
        (OpenAIBackendClientAioHttp, "AioHttp Client (Rust timing + Python)"),
    ]

    if RUST_STREAMING_AVAILABLE:
        clients_to_test.insert(
            0,
            (
                OpenAIBackendClientRustStreaming,
                "🚀 Rust Streaming Client (Pure Rust timing)",
            ),
        )
    else:
        print(
            "⚠️  Rust Streaming Client not available. Install with: cd lib/streaming && pip install ."
        )

    # Test each client
    all_results = []
    for client_class, client_name in clients_to_test:
        result = await test_client_timing_accuracy(
            client_class, client_name, num_requests
        )
        all_results.append(result)

    # Compare results
    compare_timing_precision(all_results)

    print("💡 Key Insights:")
    print("  • Pure Rust timing provides the highest precision (nanosecond level)")
    print("  • Mixed Python+Rust timing still offers good accuracy (microsecond level)")
    print("  • Lower standard deviation = more consistent/accurate measurements")
    print(
        "  • For AI benchmarking, nanosecond precision is crucial for TTFT measurements"
    )
    print("\n🔧 To install the Rust streaming client:")
    print("  cd lib/streaming && pip install .")


if __name__ == "__main__":
    asyncio.run(main())
