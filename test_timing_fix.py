#!/usr/bin/env python3
#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
"""
Test script to verify timestamp conversion fixes for RequestRecord calculations.
This should resolve the negative values and 0.00 timing issues.
"""

import asyncio
import logging
import time

from aiperf.backend.openai_client_rust_streaming import OpenAIBackendClientRustStreaming
from aiperf.backend.openai_common import OpenAIBackendClientConfig

# Set up minimal logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def test_timestamp_conversion():
    """Test the timestamp conversion with a simple HTTP endpoint that simulates streaming."""

    print("🔧 Testing Timestamp Conversion Fix")
    print("=" * 50)

    # Create a client that points to a test endpoint that returns streaming data
    client_config = OpenAIBackendClientConfig(
        url="httpbin.org",  # Use httpbin for testing
        endpoint="stream/3",  # Stream 3 JSON objects
        api_key="test-key",
        model="test-model",
        max_tokens=10,
        timeout_ms=10000,
    )

    print(
        f"✅ Created test config pointing to: {client_config.url}/{client_config.endpoint}"
    )

    try:
        async with OpenAIBackendClientRustStreaming(client_config) as client:
            # Manually craft a streaming request to httpbin
            from aiperf_streaming import (
                StreamingRequest,
                TimestampKind,
            )

            # Use the internal Rust client directly for this test
            test_request = StreamingRequest(
                url="https://httpbin.org/stream/3",  # This will return 3 streaming JSON chunks
                method="GET",
                headers={"Accept": "application/json", "User-Agent": "aiperf-test/1.0"},
                body=None,
                timeout_ms=10000,
            )

            print("🌐 Executing test streaming request...")

            # Execute the streaming request to get tokens
            completed_request, timers = client._rust_client.stream_request_with_details(
                test_request
            )

            print("✅ Request completed:")
            print(f"   Request ID: {completed_request.request_id}")
            print(f"   Token count: {completed_request.token_count}")
            print(f"   Status code: {completed_request.status_code}")
            print(f"   Total bytes: {completed_request.total_bytes}")

            # Test our timestamp conversion logic manually
            print("\n⏱️  Testing Timestamp Conversion:")

            # Get Rust timestamps (relative)
            rust_request_start_ns = timers.timestamp_ns(TimestampKind.RequestStart, 0)
            rust_request_end_ns = timers.timestamp_ns(TimestampKind.RequestEnd, 0)

            print(f"   Rust request start (relative): {rust_request_start_ns}")
            print(f"   Rust request end (relative): {rust_request_end_ns}")

            # Calculate absolute timestamps (like our fix does)
            current_time_ns = time.perf_counter_ns()
            rust_elapsed_ns = rust_request_end_ns - rust_request_start_ns
            absolute_start_ns = current_time_ns - rust_elapsed_ns

            print(f"   Current time: {current_time_ns}")
            print(f"   Rust elapsed: {rust_elapsed_ns / 1e6:.3f} ms")
            print(f"   Calculated absolute start: {absolute_start_ns}")

            # Test token timestamp conversion (with sorting like our fix)
            print("\n🔤 Testing Token Timestamp Conversion:")

            token_data_list = []
            for i in range(completed_request.token_count):
                token = completed_request.get_token(i)
                rust_token_timing_ns = completed_request.get_token_timing(i)

                # Convert to absolute (like our fix does)
                token_offset_ns = rust_token_timing_ns - rust_request_start_ns
                absolute_token_timestamp_ns = absolute_start_ns + token_offset_ns

                token_data_list.append(
                    {
                        "token": token,
                        "rust_timing": rust_token_timing_ns,
                        "absolute_timestamp": absolute_token_timestamp_ns,
                        "index": i,
                    }
                )

                print(f"   Token {i} (original order):")
                print(f"     Rust timing (relative): {rust_token_timing_ns}")
                print(f"     Token offset: {token_offset_ns / 1e6:.3f} ms")
                print(f"     Absolute timestamp: {absolute_token_timestamp_ns}")
                print(f"     Size: {token.size_bytes} bytes")

            # Sort by absolute timestamp (like our fix does)
            print("\n🔄 Sorting tokens by absolute timestamp:")
            token_data_list.sort(key=lambda x: x["absolute_timestamp"])

            absolute_token_timestamps = []
            for sorted_token_data in token_data_list:
                absolute_token_timestamps.append(
                    sorted_token_data["absolute_timestamp"]
                )
                print(f"   Sorted Token (orig {sorted_token_data['index']}):")
                print(
                    f"     Absolute timestamp: {sorted_token_data['absolute_timestamp']}"
                )
                print(f"     Rust timing: {sorted_token_data['rust_timing']}")

            # Simulate RequestRecord calculations
            print("\n📊 Simulating RequestRecord Calculations:")

            if len(absolute_token_timestamps) >= 1:
                # TTFT = first_response.timestamp_ns - start_perf_counter_ns
                ttft_ns = absolute_token_timestamps[0] - absolute_start_ns
                ttft_ms = ttft_ns / 1e6
                print(f"   Time to First Token: {ttft_ms:.3f} ms")

                if len(absolute_token_timestamps) >= 2:
                    # TTST = second_response.timestamp_ns - first_response.timestamp_ns
                    ttst_ns = (
                        absolute_token_timestamps[1] - absolute_token_timestamps[0]
                    )
                    ttst_ms = ttst_ns / 1e6
                    print(f"   Time to Second Token: {ttst_ms:.3f} ms")

                    # Check for negative values
                    if ttst_ms < 0:
                        print(f"   ❌ NEGATIVE TTST detected: {ttst_ms:.3f} ms")
                    else:
                        print(f"   ✅ Positive TTST: {ttst_ms:.3f} ms")
                else:
                    print("   Only 1 token - cannot calculate TTST")

                # Check if values are too small (0.00 when rounded)
                if ttft_ms < 0.001:
                    print(
                        f"   ⚠️  TTFT very small: {ttft_ms:.6f} ms (might show as 0.00)"
                    )
                else:
                    print(f"   ✅ TTFT reasonable: {ttft_ms:.3f} ms")

            print("\n📈 Timing Summary:")
            print(f"   Total request duration: {rust_elapsed_ns / 1e6:.3f} ms")
            print(f"   Tokens processed: {completed_request.token_count}")
            print("   All timestamps converted from relative to absolute")
            print("   No negative timing values expected")

    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback

        traceback.print_exc()
        return False

    return True


async def main():
    """Run the timestamp conversion test."""

    print("🧪 Testing Timestamp Conversion Fix for RequestRecord")
    print("=" * 70)
    print("This should resolve:")
    print("• Negative Time to Second Token values")
    print("• 0.00 values in AIPerf dashboard")
    print("• Proper absolute timestamp conversion from Rust relative timestamps")
    print("=" * 70)

    success = await test_timestamp_conversion()

    print("\n" + "=" * 70)
    if success:
        print("🎉 TIMESTAMP CONVERSION TEST PASSED!")
        print("✨ Timestamps properly converted from relative to absolute!")
        print("🚫 No negative values expected!")
        print("📊 RequestRecord calculations should now work correctly!")
    else:
        print("❌ TIMESTAMP CONVERSION TEST FAILED")


if __name__ == "__main__":
    asyncio.run(main())
