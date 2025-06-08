#!/usr/bin/env python3
#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
"""
Basic usage example for aiperf_streaming.

This example demonstrates how to use the high-performance streaming HTTP client
to measure AI inference response timing with nanosecond precision.
"""

from typing import Any

# Import the Rust-based streaming client
try:
    from aiperf_streaming import (
        PrecisionTimer,
        StreamingHttpClient,
        StreamingRequest,
        StreamingRequestModel,
        StreamingStats,
        TimingAnalysis,
    )
except ImportError:
    print("aiperf_streaming not installed. Run: pip install .")
    exit(1)


def create_openai_request(prompt: str, model: str = "gpt-3.5-turbo") -> dict[str, Any]:
    """Create an OpenAI-compatible streaming request payload."""
    return {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "stream": True,
        "max_tokens": 100,
        "temperature": 0.7,
    }


def create_headers(api_key: str) -> dict[str, str]:
    """Create headers for AI service requests."""
    return {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
        "Accept": "text/event-stream",
    }


def main():
    """Main example function."""
    print("🚀 aiperf_streaming Example - High-Performance AI Timing Analysis")
    print("=" * 70)

    # Initialize high-precision timer
    timer = PrecisionTimer()
    print(f"⏱️  High-precision timer initialized at: {timer.now_iso()}")

    # Create streaming HTTP client with optimal settings
    client = StreamingHttpClient(
        timeout_ms=30000,  # 30 second timeout
        default_headers={
            "User-Agent": "aiperf_streaming/0.1.0",
            "Accept-Encoding": "gzip, deflate",
        },
        user_agent="aiperf_streaming/0.1.0 (High-Performance AI Analysis)",
    )

    print(f"🔧 HTTP client created with stats: {client.get_stats()}")

    # Example 1: Single streaming request to a test endpoint
    print("\n📡 Example 1: Single Streaming Request")
    print("-" * 40)

    # Create a test request (using httpbin for demo)
    test_request = StreamingRequest(
        url="https://httpbin.org/stream/5",  # Returns 5 JSON objects
        method="GET",
        headers={"Accept": "application/json"},
        timeout_ms=10000,
    )

    print(f"📤 Created request: {test_request}")

    # Execute the streaming request
    start_time = timer.now_ns()
    completed_request = client.stream_request(test_request)
    end_time = timer.now_ns()

    print(f"✅ Request completed in {(end_time - start_time) / 1e6:.2f}ms")
    print("📊 Request stats:")
    print(f"   • Chunks received: {completed_request.chunk_count}")
    print(f"   • Total bytes: {completed_request.total_bytes}")
    print(f"   • Duration: {completed_request.duration_ns() / 1e6:.2f}ms")
    if completed_request.throughput_bps():
        print(
            f"   • Throughput: {completed_request.throughput_bps() / 1024 / 1024:.2f} MB/s"
        )

    # Analyze chunk timings
    chunk_timings = completed_request.chunk_timings()
    if chunk_timings:
        print("   • Chunk timing analysis:")
        print(f"     - First chunk: {chunk_timings[0] / 1e6:.2f}ms")
        print(
            f"     - Average interval: {sum(chunk_timings[1:]) / len(chunk_timings[1:]) / 1e6:.2f}ms"
        )
        print(f"     - Max interval: {max(chunk_timings[1:]) / 1e6:.2f}ms")

    # Example 2: Concurrent streaming requests
    print("\n🚀 Example 2: Concurrent Streaming Requests")
    print("-" * 45)

    # Create multiple requests
    concurrent_requests = []
    for i in range(3):
        req = StreamingRequest(
            url=f"https://httpbin.org/stream/{i + 2}",
            method="GET",
            headers={"Accept": "application/json"},
            timeout_ms=10000,
        )
        concurrent_requests.append(req)

    # Execute concurrent requests
    start_time = timer.now_ns()
    completed_requests = client.stream_requests_concurrent(
        concurrent_requests, max_concurrent=3
    )
    end_time = timer.now_ns()

    print(
        f"✅ {len(completed_requests)} concurrent requests completed in {(end_time - start_time) / 1e6:.2f}ms"
    )

    # Analyze results
    stats = StreamingStats()
    for req in completed_requests:
        stats.add_request(req)
        print(
            f"   • Request {req.request_id[:8]}: {req.chunk_count} chunks, {req.total_bytes} bytes"
        )

    print(f"📈 Aggregate statistics: {stats}")

    # Example 3: Advanced timing analysis with Pydantic models
    print("\n📊 Example 3: Advanced Timing Analysis")
    print("-" * 40)

    # Convert to Pydantic models for advanced analysis
    request_models = []
    for req in completed_requests:
        # Convert Rust objects to Python dictionaries for Pydantic
        model_data = {
            "request_id": req.request_id,
            "url": req.url,
            "method": req.method,
            "headers": dict(req.get_headers()),  # Convert to dict
            "start_time_ns": req.start_time_ns,
            "end_time_ns": req.end_time_ns,
            "total_bytes": req.total_bytes,
            "chunk_count": req.chunk_count,
            "timeout_ms": req.timeout_ms,
            "chunks": [],  # We'll populate this if needed
        }

        # Add chunks
        for chunk in req.get_chunks():
            chunk_data = {
                "timestamp_ns": chunk.timestamp_ns,
                "data": chunk.data,
                "size_bytes": chunk.size_bytes,
                "chunk_index": chunk.chunk_index,
            }
            model_data["chunks"].append(chunk_data)

        request_models.append(StreamingRequestModel(**model_data))

    # Perform advanced timing analysis
    analysis = TimingAnalysis(requests=request_models)

    print("🔍 Advanced Timing Analysis:")
    print(f"   • Request Duration Stats: {analysis.request_duration_stats}")
    print(f"   • Throughput Stats: {analysis.throughput_stats}")
    print(f"   • Chunk Timing Stats: {analysis.chunk_timing_stats}")

    # Example 4: Performance comparison
    print("\n⚡ Example 4: Performance Comparison")
    print("-" * 38)

    # Compare different request patterns
    patterns = [
        ("Sequential", 1),
        ("Concurrent-2", 2),
        ("Concurrent-5", 5),
    ]

    for pattern_name, concurrency in patterns:
        requests = [
            StreamingRequest(
                url="https://httpbin.org/stream/3",
                method="GET",
                timeout_ms=5000,
            )
            for _ in range(5)
        ]

        start_time = timer.now_ns()
        if concurrency == 1:
            # Sequential execution
            results = []
            for req in requests:
                result = client.stream_request(req)
                results.append(result)
        else:
            # Concurrent execution
            results = client.stream_requests_concurrent(
                requests, max_concurrent=concurrency
            )

        end_time = timer.now_ns()
        total_time = (end_time - start_time) / 1e6

        total_bytes = sum(req.total_bytes for req in results)
        total_chunks = sum(req.chunk_count for req in results)

        print(
            f"   • {pattern_name}: {total_time:.2f}ms, {total_bytes} bytes, {total_chunks} chunks"
        )

    print("\n🎯 Example completed successfully!")
    print("=" * 70)


if __name__ == "__main__":
    main()
