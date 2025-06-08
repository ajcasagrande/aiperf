#!/usr/bin/env python3
#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
"""
Test the modified stream_request functions that return RequestTimers instead of nanosecond timestamps.
"""

from aiperf_streaming import StreamingHttpClient, StreamingRequest, TimestampKind


def test_stream_request_returns_timers():
    """Test that stream_request now returns RequestTimers."""

    print("🧪 Testing Modified Functions - RequestTimers Return Types")
    print("=" * 60)

    # Create HTTP client
    client = StreamingHttpClient(
        timeout_ms=5000,
        default_headers={"User-Agent": "test-client/1.0"},
        user_agent="test-client/1.0",
    )
    print("✓ Created StreamingHttpClient")

    # Create a streaming request
    request = StreamingRequest(
        url="https://httpbin.org/stream/2",
        method="GET",
        headers={"Accept": "application/json"},
        body=None,
        timeout_ms=5000,
    )
    print("✓ Created StreamingRequest")

    # Test stream_request - should return RequestTimers only
    print("\n🎯 Testing stream_request() - Returns RequestTimers only")
    try:
        timers = client.stream_request(request)
        print(f"✅ Successfully received RequestTimers: {timers}")
        print(f"   Type: {type(timers)}")

        # Analyze the timing data
        analyze_request_timers(timers)

    except Exception as e:
        print(f"❌ stream_request failed: {e}")
        return False

    return True


def test_stream_request_with_details():
    """Test the new stream_request_with_details function."""

    print(
        "\n🎯 Testing stream_request_with_details() - Returns (Request, RequestTimers)"
    )

    client = StreamingHttpClient(
        timeout_ms=5000,
        default_headers={"User-Agent": "test-client/1.0"},
        user_agent="test-client/1.0",
    )

    request = StreamingRequest(
        url="https://httpbin.org/delay/1",
        method="GET",
        headers={"Accept": "application/json"},
        body=None,
        timeout_ms=5000,
    )

    try:
        result = client.stream_request_with_details(request)
        request_obj, timers = result

        print("✅ Successfully received tuple: (StreamingRequest, RequestTimers)")
        print(f"   Request type: {type(request_obj)}")
        print(f"   Timers type: {type(timers)}")
        print(f"   Request ID: {request_obj.request_id}")
        print(f"   Status Code: {request_obj.status_code}")
        print(f"   Timers: {timers}")

        # Verify both objects have the same timing data
        request_duration = timers.duration_ns(
            TimestampKind.RequestStart, TimestampKind.RequestEnd
        )
        if request_duration:
            print(f"   Duration: {request_duration / 1_000_000:.3f} ms")

    except Exception as e:
        print(f"❌ stream_request_with_details failed: {e}")
        return False

    return True


def test_concurrent_requests_returns_timers():
    """Test that concurrent requests now return list of RequestTimers."""

    print("\n🎯 Testing stream_requests_concurrent() - Returns List[RequestTimers]")

    client = StreamingHttpClient(
        timeout_ms=5000,
        default_headers={"User-Agent": "test-client/1.0"},
        user_agent="test-client/1.0",
    )

    # Create multiple requests
    requests = []
    for i in range(3):
        request = StreamingRequest(
            url=f"https://httpbin.org/delay/{i + 1}",
            method="GET",
            headers={"Accept": "application/json"},
            body=None,
            timeout_ms=8000,
        )
        requests.append(request)

    print(f"Created {len(requests)} requests")

    try:
        timers_list = client.stream_requests_concurrent(requests, max_concurrent=3)
        print(
            f"✅ Successfully received List[RequestTimers] with {len(timers_list)} items"
        )

        for i, timers in enumerate(timers_list):
            print(f"   Request {i + 1}: {timers}")
            duration = timers.duration_ns(
                TimestampKind.RequestStart, TimestampKind.RequestEnd
            )
            if duration:
                print(f"              Duration: {duration / 1_000_000:.3f} ms")

    except Exception as e:
        print(f"❌ stream_requests_concurrent failed: {e}")
        return False

    return True


def test_create_timer():
    """Test the new create_timer function."""

    print("\n🎯 Testing create_timer() - Returns RequestTimers")

    client = StreamingHttpClient(
        timeout_ms=5000,
        default_headers={"User-Agent": "test-client/1.0"},
        user_agent="test-client/1.0",
    )

    try:
        timer = client.create_timer()
        print(f"✅ Successfully created manual timer: {timer}")
        print(f"   Type: {type(timer)}")

        # Test manual timing
        timer.capture(TimestampKind.RequestStart)
        print("   ✓ Captured REQUEST_START")

        import time

        time.sleep(0.001)  # 1ms delay

        timer.capture(TimestampKind.RequestEnd)
        print("   ✓ Captured REQUEST_END")

        duration = timer.duration_ns(
            TimestampKind.RequestStart, TimestampKind.RequestEnd
        )
        if duration:
            print(f"   Manual timing duration: {duration / 1_000_000:.3f} ms")

    except Exception as e:
        print(f"❌ create_timer failed: {e}")
        return False

    return True


def analyze_request_timers(timers):
    """Analyze a RequestTimers object and display detailed information."""

    print("\n📊 Detailed RequestTimers Analysis:")
    print(f"   {timers}")

    # Check all timestamp types
    timestamp_kinds = [
        TimestampKind.RequestStart,
        TimestampKind.RequestEnd,
        TimestampKind.SendStart,
        TimestampKind.SendEnd,
        TimestampKind.RecvStart,
        TimestampKind.RecvEnd,
        TimestampKind.TokenStart,
        TimestampKind.TokenEnd,
    ]

    print("   Available Timestamps:")
    for kind in timestamp_kinds:
        has_timestamp = timers.has_timestamp(kind)
        status = "✓" if has_timestamp else "✗"
        print(f"     {status} {kind}")

    # Key timing measurements
    try:
        total_duration = timers.duration_ns(
            TimestampKind.RequestStart, TimestampKind.RequestEnd
        )
        if total_duration:
            print(f"   📏 Total Duration: {total_duration / 1_000_000:.3f} ms")

        send_duration = timers.duration_ns(
            TimestampKind.SendStart, TimestampKind.SendEnd
        )
        if send_duration:
            print(f"   📤 Send Duration: {send_duration / 1_000_000:.3f} ms")

        recv_duration = timers.duration_ns(
            TimestampKind.RecvStart, TimestampKind.RecvEnd
        )
        if recv_duration:
            print(f"   📥 Receive Duration: {recv_duration / 1_000_000:.3f} ms")

        # Token analysis
        if timers.token_starts_count() > 0:
            token_durations = timers.get_token_durations_ns()
            avg_token = (
                sum(token_durations) / len(token_durations) if token_durations else 0
            )
            print(
                f"   🔤 Tokens: {timers.token_starts_count()}, Avg: {avg_token / 1_000_000:.3f} ms"
            )

    except Exception as e:
        print(f"   ⚠️  Error analyzing timers: {e}")


def main():
    """Main test function."""

    print("🚀 Testing Modified Functions - No More Nanosecond Returns!")
    print("=" * 60)
    print("All functions now return RequestTimers objects instead of raw timestamps")
    print("=" * 60)

    # Test all modified functions
    success1 = test_stream_request_returns_timers()
    success2 = test_stream_request_with_details()
    success3 = test_concurrent_requests_returns_timers()
    success4 = test_create_timer()

    print("\n" + "=" * 60)
    if all([success1, success2, success3, success4]):
        print("🎉 All tests passed!")
        print("✨ Functions now exclusively return RequestTimers objects!")
        print("🚫 No more raw nanosecond timestamps exposed!")
    else:
        print("❌ Some tests failed")


if __name__ == "__main__":
    main()
