#!/usr/bin/env python3
#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
"""
Time To First Byte (TTFB) Comparison Example

This example demonstrates the difference between normal and low-latency mode
for measuring time to first byte in streaming responses.
"""

import time

from aiperf_streaming import StreamingHttpClient, StreamingRequest


def test_ttfb_comparison():
    """Compare TTFB between normal and low-latency clients."""

    # Test URLs - use a streaming endpoint that sends data gradually
    test_urls = [
        "https://httpbin.org/stream/10",  # Returns 10 JSON objects
        "https://httpbin.org/drip?duration=5&numbytes=1024&code=200",  # Slow drip
    ]

    for url in test_urls:
        print(f"\n🔍 Testing TTFB for: {url}")
        print("-" * 60)

        # Test with normal client
        print("📡 Normal Client:")
        normal_client = StreamingHttpClient(
            timeout_ms=30000,
            default_headers={"Accept": "application/json"},
            user_agent="aiperf_streaming/ttfb-test",
        )

        try:
            request = StreamingRequest(
                url=url,
                method="GET",
                headers={},
                body=None,
                timeout_ms=30000,
            )
        except Exception as e:
            print(f"❌ Error creating request: {e}")
            continue

        timers1 = normal_client.stream_request(request)

        # Calculate TTFB (time from send start to first token)
        send_start = timers1.get_timestamp("SendStart")
        first_token = timers1.get_timestamp("TokenStart")

        if send_start and first_token:
            ttfb_normal = (
                first_token - send_start
            ) / 1_000_000  # Convert to milliseconds
            print(f"   TTFB: {ttfb_normal:.2f}ms")
        else:
            print("   TTFB: Could not calculate")

        # Test with low-latency client
        print("⚡ Low-Latency Client:")
        low_latency_client = StreamingHttpClient.new_low_latency(
            timeout_ms=30000,
            default_headers={"Accept": "application/json"},
            user_agent="aiperf_streaming/ttfb-test",
        )

        try:
            request2 = StreamingRequest(
                url=url,
                method="GET",
                headers={},
                body=None,
                timeout_ms=30000,
            )
        except Exception as e:
            print(f"❌ Error creating request: {e}")
            continue

        timers2 = low_latency_client.stream_request(request2)

        # Calculate TTFB (time from send start to first token)
        send_start = timers2.get_timestamp("SendStart")
        first_token = timers2.get_timestamp("TokenStart")

        if send_start and first_token:
            ttfb_low_latency = (
                first_token - send_start
            ) / 1_000_000  # Convert to milliseconds
            print(f"   TTFB: {ttfb_low_latency:.2f}ms")

            if "ttfb_normal" in locals():
                improvement = ((ttfb_normal - ttfb_low_latency) / ttfb_normal) * 100
                print(f"   Improvement: {improvement:.1f}% faster")
        else:
            print("   TTFB: Could not calculate")

        # Small delay between tests
        time.sleep(1)


def test_detailed_timing_breakdown():
    """Show detailed timing breakdown for streaming responses."""

    print("\n📊 Detailed Timing Breakdown")
    print("=" * 50)

    url = "https://httpbin.org/stream/5"

    # Use low-latency client for best performance
    client = StreamingHttpClient.new_low_latency(
        timeout_ms=30000,
        default_headers={"User-Agent": "aiperf_streaming/ttfb-test"},
        user_agent="aiperf_streaming/ttfb-test",
    )

    try:
        request = StreamingRequest(
            url=url,
            method="GET",
            headers={},
            body=None,
            timeout_ms=30000,
        )
    except Exception as e:
        print(f"❌ Error creating request: {e}")
        return

    request_with_details, timers = client.stream_request_with_details(request)

    print(f"URL: {url}")
    print(f"Total tokens received: {request_with_details.token_count}")
    print(f"Total bytes: {request_with_details.total_bytes}")

    # Show timing breakdown
    request_start = timers.get_timestamp("RequestStart")
    send_start = timers.get_timestamp("SendStart")
    send_end = timers.get_timestamp("SendEnd")
    recv_start = timers.get_timestamp("RecvStart")
    first_token = timers.get_timestamp("TokenStart")
    recv_end = timers.get_timestamp("RecvEnd")
    request_end = timers.get_timestamp("RequestEnd")

    if all([request_start, send_start, send_end, recv_start, first_token]):
        print("\n⏱️  Timing Breakdown:")

        dns_time = (send_start - request_start) / 1_000_000
        send_time = (send_end - send_start) / 1_000_000
        wait_time = (recv_start - send_end) / 1_000_000
        ttfb = (first_token - recv_start) / 1_000_000

        print(f"   DNS + Connect: {dns_time:.2f}ms")
        print(f"   Send Request:  {send_time:.2f}ms")
        print(f"   Wait for Response: {wait_time:.2f}ms")
        print(f"   Time to First Byte: {ttfb:.2f}ms")

        if recv_end:
            total_time = (recv_end - request_start) / 1_000_000
            print(f"   Total Request Time: {total_time:.2f}ms")

    # Show first few tokens
    if hasattr(request_with_details, "get_tokens"):
        tokens = request_with_details.get_tokens()
        print("\n📦 First 3 tokens:")
        for i, token in enumerate(tokens[:3]):
            preview = token.data[:50] + "..." if len(token.data) > 50 else token.data
            print(f"   Token {i}: {len(token.data)} bytes - {preview}")


if __name__ == "__main__":
    print("🚀 TTFB Comparison Example")
    print(
        "This example compares time to first byte between normal and low-latency clients"
    )

    try:
        test_ttfb_comparison()
        test_detailed_timing_breakdown()

        print("\n✅ TTFB comparison completed!")
        print("\n💡 Tips for better TTFB performance:")
        print("   • Use StreamingHttpClient.new_low_latency() for minimal latency")
        print("   • Prefer HTTP/1.1 over HTTP/2 for streaming responses")
        print("   • Use smaller buffer sizes (4KB) for faster first byte")
        print("   • Enable TCP_NODELAY to reduce network latency")

    except Exception as e:
        print(f"❌ Error during TTFB test: {e}")
        print(
            "   Make sure you have internet connectivity and the test endpoints are accessible"
        )
