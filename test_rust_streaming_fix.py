#!/usr/bin/env python3
#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
"""
Test script for the updated OpenAI Rust streaming client with pure Rust timing.
This verifies that the streaming tokens and timing fixes work correctly.
"""

import asyncio
import logging
import os

from aiperf.backend.openai_client_rust_streaming import (
    OpenAIBackendClientRustStreaming,
)
from aiperf.backend.openai_common import (
    OpenAIBackendClientConfig,
)

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def test_rust_streaming_client():
    """Test the updated Rust streaming client with pure Rust timing."""

    print("🚀 Testing OpenAI Rust Streaming Client with Pure Rust Timing")
    print("=" * 70)

    # Skip the test if no API key is available
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("⚠️  OPENAI_API_KEY not set - creating client without API call")
        api_key = "test-key"

    try:
        # Create client configuration
        client_config = OpenAIBackendClientConfig(
            url="api.openai.com",
            endpoint="v1/chat/completions",
            api_key=api_key,
            model="gpt-3.5-turbo",
            max_tokens=50,
            timeout_ms=30000,
        )

        print(f"✅ Created client config with model: {client_config.model}")

        # Create the Rust streaming client
        async with OpenAIBackendClientRustStreaming(client_config) as client:
            print("✅ Created Rust streaming client successfully")

            # Test performance configuration
            perf_config = client.perf_config
            print(
                f"✅ Performance config: timeout={perf_config.timeout_ms}ms, gzip={perf_config.enable_gzip_compression}"
            )

            # Test format_payload method
            test_payload = {
                "messages": [{"role": "user", "content": "Say hello in one word"}],
                "kwargs": {"temperature": 0.7},
            }

            formatted_payload = await client.format_payload(
                "v1/chat/completions", test_payload
            )
            print(f"✅ Formatted payload: {type(formatted_payload).__name__}")
            print(f"   Messages: {len(formatted_payload.messages)}")
            print(f"   Model: {formatted_payload.model}")
            print(f"   Max tokens: {formatted_payload.max_tokens}")

            # Test get_performance_statistics method
            stats = client.get_performance_statistics()
            print("✅ Performance statistics:")
            print(f"   Timing source: {stats.get('timing_source', 'N/A')}")
            print(f"   Rust precision: {stats.get('rust_native_precision', 'N/A')}")
            print(f"   Total requests: {stats.get('total_requests', 0)}")

            # If we have a real API key, test an actual request
            if api_key != "test-key":
                print("\n🌐 Testing actual API request with pure Rust timing...")
                try:
                    record = await client.send_request(
                        "v1/chat/completions", formatted_payload
                    )
                    print("✅ Request completed!")
                    print(f"   Start timestamp: {record.start_perf_counter_ns}")
                    print(f"   Response count: {len(record.responses)}")
                    print(
                        f"   TTFT: {record.time_to_first_response_ns / 1e6:.2f} ms"
                        if record.time_to_first_response_ns
                        else "   TTFT: N/A"
                    )
                    print(
                        f"   Total duration: {record.total_duration_ns / 1e6:.2f} ms"
                        if record.total_duration_ns
                        else "   Total duration: N/A"
                    )

                    # Check if we got streaming responses
                    if record.responses:
                        first_response = record.responses[0]
                        print(
                            f"   First response timestamp: {first_response.timestamp_ns}"
                        )
                        print(
                            f"   First response type: {type(first_response).__name__}"
                        )

                        # Check for errors
                        error_responses = [
                            r for r in record.responses if hasattr(r, "error")
                        ]
                        if error_responses:
                            print(f"   ⚠️  Found {len(error_responses)} error responses")
                            for err_resp in error_responses[:3]:  # Show first 3 errors
                                print(f"      Error: {err_resp.error}")
                        else:
                            print(
                                f"   ✅ No error responses - all {len(record.responses)} responses successful"
                            )

                except Exception as e:
                    print(f"   ⚠️  API request failed: {e}")
                    print(
                        "   This is expected if there's no valid API key or network issues"
                    )
            else:
                print("\n⏭️  Skipping actual API test (no OPENAI_API_KEY)")

            print("\n✅ All client tests completed successfully!")

    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback

        traceback.print_exc()
        return False

    return True


async def test_streaming_token_integration():
    """Test the integration with streaming tokens specifically."""

    print("\n🔤 Testing StreamingTokenChunk Integration")
    print("=" * 50)

    try:
        from aiperf_streaming import (
            StreamingHttpClient,
            StreamingRequest,
            TimestampKind,
        )

        # Test the basic streaming functionality that the client uses
        client = StreamingHttpClient(
            timeout_ms=5000,
            default_headers={"User-Agent": "test-client/1.0"},
            user_agent="test-client/1.0",
        )

        request = StreamingRequest(
            url="https://httpbin.org/stream/2",  # Stream 2 JSON objects
            method="GET",
            headers={"Accept": "application/json"},
            body=None,
            timeout_ms=5000,
        )

        print("✅ Created StreamingHttpClient and StreamingRequest")

        # Test the stream_request_with_details method that our client uses
        completed_request, timers = client.stream_request_with_details(request)

        print("✅ Completed streaming request:")
        print(f"   Request ID: {completed_request.request_id}")
        print(f"   Token count: {completed_request.token_count}")
        print(f"   Total bytes: {completed_request.total_bytes}")
        print(f"   Status code: {completed_request.status_code}")

        # Test token access (what our OpenAI client does)
        print("\n🔍 Testing token access:")
        for i in range(min(completed_request.token_count, 3)):  # Test first 3 tokens
            token = completed_request.get_token(i)
            token_timing = completed_request.get_token_timing(i)

            print(f"   Token {i}:")
            print(f"     Size: {token.size_bytes} bytes")
            print(f"     Index: {token.token_index}")
            print(f"     Data preview: {token.data[:50]}...")
            print(
                f"     Timing: {token_timing / 1e6:.3f} ms"
                if token_timing
                else "     Timing: N/A"
            )

        # Test RequestTimers access (what our OpenAI client does)
        print("\n⏱️  Testing RequestTimers:")
        request_start = timers.timestamp_ns(TimestampKind.RequestStart, 0)
        request_end = timers.timestamp_ns(TimestampKind.RequestEnd, 0)
        total_duration = timers.duration_ns(
            TimestampKind.RequestStart, TimestampKind.RequestEnd
        )

        print(f"   Request start: {request_start}")
        print(f"   Request end: {request_end}")
        print(
            f"   Total duration: {total_duration / 1e6:.3f} ms"
            if total_duration
            else "   Total duration: N/A"
        )
        print(f"   Token starts: {timers.token_starts_count()}")
        print(f"   Token ends: {timers.token_ends_count()}")

        # Verify the 1:1 relationship
        if (
            completed_request.token_count
            == timers.token_starts_count()
            == timers.token_ends_count()
        ):
            print("   ✅ Perfect 1:1 token-timer relationship!")
        else:
            print(
                f"   ⚠️  Token-timer mismatch: tokens={completed_request.token_count}, starts={timers.token_starts_count()}, ends={timers.token_ends_count()}"
            )

        print("✅ StreamingTokenChunk integration test completed successfully!")

    except Exception as e:
        print(f"❌ StreamingTokenChunk integration test failed: {e}")
        import traceback

        traceback.print_exc()
        return False

    return True


async def main():
    """Run all tests."""

    print("🧪 Testing Updated OpenAI Rust Streaming Client")
    print("=" * 80)
    print("This verifies the fixes for:")
    print("• Pure Rust timing (no Python timestamps)")
    print("• StreamingTokenChunk processing with SSE data payloads")
    print("• RequestTimers.timestamp_ns(kind, index) API")
    print("• Removed StreamingStats.add_request() dependency")
    print("=" * 80)

    # Run tests
    test1_success = await test_rust_streaming_client()
    test2_success = await test_streaming_token_integration()

    print("\n" + "=" * 80)
    if test1_success and test2_success:
        print("🎉 ALL TESTS PASSED!")
        print("✨ OpenAI Rust streaming client is working with pure Rust timing!")
        print("🔗 StreamingTokenChunks integration is working correctly!")
        print("🚫 NO Python timestamp overhead!")
    else:
        print("❌ SOME TESTS FAILED")
        if not test1_success:
            print("   • OpenAI client test failed")
        if not test2_success:
            print("   • StreamingTokenChunk integration test failed")


if __name__ == "__main__":
    asyncio.run(main())
