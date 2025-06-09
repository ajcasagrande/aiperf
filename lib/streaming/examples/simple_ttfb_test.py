#!/usr/bin/env python3
#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
"""
Simple TTFB Test Example

This example demonstrates the difference between normal and low-latency HTTP clients
for measuring time to first byte in streaming responses.
"""

import time

from aiperf_streaming import StreamingHttpClient, StreamingRequest


def test_simple_request():
    """Test a simple streaming request with both client types."""

    test_url = "https://httpbin.org/stream/5"  # Simple streaming endpoint

    print("🚀 Simple TTFB Test")
    print("=" * 50)

    # Test with normal client
    print("\n📡 Testing Normal Client:")
    try:
        normal_client = StreamingHttpClient(
            timeout_ms=30000,
            default_headers={},
            user_agent="aiperf_streaming/test",
        )

        request = StreamingRequest(
            url=test_url,
            method="GET",
            headers={},
            body=None,
            timeout_ms=30000,
        )

        start_time = time.time()
        timers = normal_client.stream_request(request)
        end_time = time.time()

        print(f"   ✅ Request completed in {(end_time - start_time) * 1000:.1f}ms")
        print("   📊 Request successful")

    except Exception as e:
        print(f"   ❌ Error: {e}")

    # Test with low-latency client
    print("\n⚡ Testing Low-Latency Client:")
    try:
        low_latency_client = StreamingHttpClient.new_low_latency(
            timeout_ms=30000,
            default_headers={},
            user_agent="aiperf_streaming/test",
        )

        request2 = StreamingRequest(
            url=test_url,
            method="GET",
            headers={},
            body=None,
            timeout_ms=30000,
        )

        start_time = time.time()
        timers2 = low_latency_client.stream_request(request2)
        end_time = time.time()

        print(f"   ✅ Request completed in {(end_time - start_time) * 1000:.1f}ms")
        print("   📊 Request successful")

    except Exception as e:
        print(f"   ❌ Error: {e}")


if __name__ == "__main__":
    test_simple_request()
