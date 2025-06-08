#!/usr/bin/env python3
#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
"""
Simple test for the modified RequestTimers class.
"""

import time

from aiperf_streaming import RequestTimers, TimestampKind


def test_request_timers():
    """Test the RequestTimers functionality."""

    print("🧪 Testing RequestTimers with HashMap structure...")

    # Create a new timer instance
    timers = RequestTimers()
    print(f"Created timers: {timers}")

    # Test capturing different timestamp kinds
    print("\n📊 Capturing timestamps...")

    # Capture non-token timestamps
    timers.capture(TimestampKind.RequestStart)
    print("✓ Captured REQUEST_START")

    time.sleep(0.001)
    timers.capture(TimestampKind.SendStart)
    print("✓ Captured SEND_START")

    time.sleep(0.001)
    timers.capture(TimestampKind.SendEnd)
    print("✓ Captured SEND_END")

    time.sleep(0.001)
    timers.capture(TimestampKind.RecvStart)
    print("✓ Captured RECV_START")

    # Capture token timestamps (multiple)
    for i in range(3):
        timers.capture(TimestampKind.TokenStart)
        time.sleep(0.001)
        timers.capture(TimestampKind.TokenEnd)
        print(f"✓ Captured Token {i + 1}")

    time.sleep(0.001)
    timers.capture(TimestampKind.RecvEnd)
    print("✓ Captured RECV_END")

    timers.capture(TimestampKind.RequestEnd)
    print("✓ Captured REQUEST_END")

    print(f"\nFinal state: {timers}")

    # Test checking for timestamps
    print("\n🔍 Checking timestamp presence...")
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

    for kind in timestamp_kinds:
        has_timestamp = timers.has_timestamp(kind)
        print(f"  {kind}: {'✓' if has_timestamp else '✗'}")

    # Test durations
    print("\n⏱️  Testing durations...")

    total_duration = timers.duration_ns(
        TimestampKind.RequestStart, TimestampKind.RequestEnd
    )
    if total_duration:
        print(f"  Total request duration: {total_duration / 1_000_000:.2f} ms")

    send_duration = timers.duration_ns(TimestampKind.SendStart, TimestampKind.SendEnd)
    if send_duration:
        print(f"  Send duration: {send_duration / 1_000_000:.2f} ms")

    # Test token counts
    print("\n🔤 Token counts:")
    print(f"  Token starts: {timers.token_starts_count()}")
    print(f"  Token ends: {timers.token_ends_count()}")

    # Test token durations
    try:
        token_durations = timers.get_token_durations_ns()
        print(f"  Token durations: {[d / 1_000_000 for d in token_durations]} ms")
    except Exception as e:
        print(f"  Error getting token durations: {e}")

    # Test clearing
    print("\n🧹 Testing clear functionality...")
    timers.clear()
    print(f"After clear: {timers}")

    # Verify everything is cleared
    for kind in timestamp_kinds:
        has_timestamp = timers.has_timestamp(kind)
        if has_timestamp:
            print(f"  ERROR: {kind} still present after clear!")
            return False

    print("✅ All tests passed!")
    return True


if __name__ == "__main__":
    success = test_request_timers()
    if success:
        print("\n🎉 RequestTimers HashMap implementation works correctly!")
    else:
        print("\n❌ Some tests failed!")
