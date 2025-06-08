#!/usr/bin/env python3
#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
"""
Test the new StreamingTokenChunk functionality that represents SSE data payloads.
"""

from aiperf_streaming import (
    StreamingHttpClient,
    StreamingRequest,
    StreamingTokenChunk,
    TimestampKind,
)


def test_streaming_tokens():
    """Test the new StreamingTokenChunk functionality."""

    print("🔄 Testing StreamingTokenChunks - SSE Data Payloads")
    print("=" * 60)

    # Create HTTP client
    client = StreamingHttpClient(
        timeout_ms=5000,
        default_headers={"User-Agent": "test-token-client/1.0"},
        user_agent="test-token-client/1.0",
    )
    print("✓ Created StreamingHttpClient")

    # Create a streaming request
    request = StreamingRequest(
        url="https://httpbin.org/stream/3",  # Stream 3 JSON objects
        method="GET",
        headers={"Accept": "application/json"},
        body=None,
        timeout_ms=5000,
    )
    print("✓ Created StreamingRequest")

    # Execute the streaming request
    print("\n🌐 Executing streaming request with tokens...")
    try:
        timers = client.stream_request(request)
        print("✅ Request completed successfully!")

        # Get the full request details for analysis
        request, timers = client.stream_request_with_details(
            StreamingRequest(
                url="https://httpbin.org/stream/2",
                method="GET",
                headers={"Accept": "application/json"},
                body=None,
                timeout_ms=5000,
            )
        )

        analyze_streaming_tokens(request, timers)

    except Exception as e:
        print(f"❌ Request failed: {e}")
        return False

    return True


def test_manual_token_creation():
    """Test manual StreamingTokenChunk creation."""

    print("\n🔧 Testing Manual StreamingTokenChunk Creation")
    print("-" * 40)

    # Create manual tokens
    token1 = StreamingTokenChunk('data: {"message": "hello"}', 0)
    token2 = StreamingTokenChunk('data: {"message": "world"}', 1)
    token3 = StreamingTokenChunk('data: {"status": "complete"}', 2)

    tokens = [token1, token2, token3]

    print(f"Created {len(tokens)} manual tokens:")
    for token in tokens:
        print(f"  {token}")

    # Test token properties
    print("\n📊 Token Analysis:")
    total_bytes = sum(token.size_bytes for token in tokens)
    print(f"  Total tokens: {len(tokens)}")
    print(f"  Total bytes: {total_bytes}")
    print(f"  Average size: {total_bytes / len(tokens):.1f} bytes")

    # Test token data access
    print("\n📝 Token Data:")
    for _, token in enumerate(tokens):
        print(f"  Token {token.token_index}: {token.size_bytes} bytes")
        print(f"    Data preview: {token.data[:30]}...")

    return True


def analyze_streaming_tokens(request, timers):
    """Analyze StreamingTokenChunks and their relationship to RequestTimers."""

    print("\n📊 StreamingTokenChunk Analysis")
    print("=" * 50)

    # Request summary
    print("Request Summary:")
    print(f"  Request ID: {request.request_id}")
    print(f"  URL: {request.url}")
    print(f"  Status Code: {request.status_code}")
    print(f"  Total Tokens: {request.token_count}")
    print(f"  Total Bytes: {request.total_bytes}")

    # Token details
    print("\n🔤 Token Details:")
    try:
        # Note: get_tokens() requires Python context, so we'll use individual token access instead
        print(f"  Total tokens available: {request.token_count}")
        print("  Accessing tokens individually...")
    except Exception as e:
        print(f"  Could not retrieve tokens directly: {e}")

    # Individual token access
    print("\n📝 Individual Token Access:")
    for i in range(min(request.token_count, 3)):  # Show first 3 tokens
        token = request.get_token(i)
        if token:
            print(f"  Token {i}: {token}")

            # Get timing for this token
            try:
                token_timing = request.get_token_timing(i)
                if token_timing:
                    print(f"           Timing: {token_timing / 1_000_000:.3f} ms")
            except Exception as e:
                print(f"           Timing error: {e}")

    if request.token_count > 3:
        print(f"  ... and {request.token_count - 3} more tokens")

    # Timing analysis from RequestTimers
    print("\n⏱️  Timing Analysis:")
    print(f"  Timer State: {timers}")

    try:
        # Overall request timing
        total_duration = timers.duration_ns(
            TimestampKind.RequestStart, TimestampKind.RequestEnd
        )
        if total_duration:
            print(f"  📏 Total Duration: {total_duration / 1_000_000:.3f} ms")

        # Token timing statistics
        token_durations = timers.get_token_durations_ns()
        if token_durations:
            print("  🔤 Token Statistics:")
            print(f"     Token count: {len(token_durations)}")
            print(
                f"     Average duration: {sum(token_durations) / len(token_durations) / 1_000_000:.3f} ms"
            )
            print(f"     Min duration: {min(token_durations) / 1_000_000:.3f} ms")
            print(f"     Max duration: {max(token_durations) / 1_000_000:.3f} ms")

            # Show individual token timings
            print("     Individual timings:")
            for i, duration in enumerate(token_durations[:5]):  # Show first 5
                print(f"       Token {i}: {duration / 1_000_000:.3f} ms")
            if len(token_durations) > 5:
                print(f"       ... and {len(token_durations) - 5} more")

        # Token timing relationship
        print("\n🔗 Token-Timer Relationship:")
        print(f"  Tokens in request: {request.token_count}")
        print(f"  Token starts in timer: {timers.token_starts_count()}")
        print(f"  Token ends in timer: {timers.token_ends_count()}")

        if (
            request.token_count
            == timers.token_starts_count()
            == timers.token_ends_count()
        ):
            print("  ✅ Perfect 1:1 relationship between tokens and timers!")
        else:
            print("  ⚠️  Mismatch in token/timer counts")

    except Exception as e:
        print(f"  ⚠️  Error analyzing timing: {e}")

    # Response text analysis
    print("\n📄 Response Content:")
    response_text = request.get_response_text()
    print(f"  Full response length: {len(response_text)} characters")
    print(f"  Response preview: {response_text[:100]}...")

    # Token timing from request
    try:
        token_timings = request.token_timings()
        print(f"  Token timing stats from request: {len(token_timings)} measurements")
    except Exception as e:
        print(f"  Token timing error: {e}")


def main():
    """Main test function."""

    print("🚀 Testing StreamingTokenChunks - SSE Data Payload Concept")
    print("=" * 60)
    print("StreamingTokenChunks now represent SSE data payloads")
    print("Timing is handled through RequestTimers with token indices")
    print("No more timestamp_ns stored in tokens directly")
    print("=" * 60)

    # Test streaming tokens with HTTP requests
    success1 = test_streaming_tokens()

    # Test manual token creation
    success2 = test_manual_token_creation()

    print("\n" + "=" * 60)
    if all([success1, success2]):
        print("🎉 All StreamingTokenChunk tests passed!")
        print("✨ Tokens now represent SSE data payloads!")
        print("🔗 Timing handled through RequestTimers indices!")
        print("🚫 No more embedded timestamps in tokens!")
    else:
        print("❌ Some tests failed")


if __name__ == "__main__":
    main()
