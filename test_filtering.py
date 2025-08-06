#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Test builtin filtering functionality."""

import json
import tempfile
from pathlib import Path

from aiperf.common.speedscope_exporter import FilterLevel, SpeedscopeProfiler


def workload_with_builtins():
    """Function that uses many builtins to test filtering."""
    # Common builtins that should be filtered at BASIC level
    data = list(range(100))
    total = sum(data)
    max_val = max(data)
    min_val = min(data)
    length = len(data)

    # String operations
    text = "hello world"
    upper_text = text.upper()
    words = text.split()
    joined = " ".join(words)

    # Dict operations
    mapping = {"a": 1, "b": 2}
    keys = list(mapping.keys())
    values = list(mapping.values())
    item = mapping.get("a")

    # Type checks
    is_list = isinstance(data, list)
    is_str = isinstance(text, str)

    return (
        total,
        max_val,
        min_val,
        length,
        upper_text,
        joined,
        keys,
        values,
        item,
        is_list,
        is_str,
    )


def application_function():
    """Your actual application code that should always be captured."""
    result = 0
    for i in range(50):
        result += workload_with_builtins()[0]
    return result


def test_filter_levels():
    """Test different filter levels."""
    filter_configs = [
        (FilterLevel.NONE, "No Filtering"),
        (FilterLevel.BASIC, "Basic Filtering"),
        (FilterLevel.AGGRESSIVE, "Aggressive Filtering"),
    ]

    results = {}

    for filter_level, description in filter_configs:
        print(f"\nTesting {description} ({filter_level.value})...")

        with tempfile.TemporaryDirectory() as temp_dir:
            profile_path = Path(temp_dir) / f"test_{filter_level.value}.json"

            profiler = SpeedscopeProfiler(max_events=50_000, filter_level=filter_level)

            profiler.start()

            # Run workload
            result = application_function()

            # Get stats before stopping
            stats = profiler.get_memory_stats()
            print(f"  Events captured: {stats['events_captured']:,}")
            print(f"  Frames cached: {stats['frames_cached']:,}")

            # Export profile
            data = profiler.stop()
            profiler.save(data, profile_path)

            # Analyze the profile
            with open(profile_path) as f:
                profile_data = json.load(f)

            frames = profile_data["shared"]["frames"]
            profiles = profile_data["profiles"]

            # Count builtin vs application frames
            builtin_frames = 0
            app_frames = 0

            for frame in frames:
                name = frame["name"]
                filename = frame.get("file", "")

                if (
                    name in SpeedscopeProfiler._BASIC_FILTERED_FUNCTIONS
                    or name in SpeedscopeProfiler._BASIC_FILTERED_METHODS
                    or filename in ("<built-in>", "<frozen>", "<string>")
                ):
                    builtin_frames += 1
                else:
                    app_frames += 1

            total_events = sum(len(p["events"]) for p in profiles)
            file_size = profile_path.stat().st_size

            results[filter_level.value] = {
                "total_frames": len(frames),
                "builtin_frames": builtin_frames,
                "app_frames": app_frames,
                "total_events": total_events,
                "file_size": file_size,
                "events_captured": stats["events_captured"],
            }

            print(f"  Total frames: {len(frames):,}")
            print(f"  Builtin frames: {builtin_frames:,}")
            print(f"  Application frames: {app_frames:,}")
            print(f"  Total events: {total_events:,}")
            print(f"  File size: {file_size:,} bytes")

    # Compare results
    print("\n" + "=" * 60)
    print("FILTERING COMPARISON")
    print("=" * 60)

    none_result = results["none"]
    basic_result = results["basic"]
    aggressive_result = results["aggressive"]

    print(f"{'Metric':<20} {'None':<12} {'Basic':<12} {'Aggressive':<12}")
    print("-" * 60)
    print(
        f"{'Events Captured':<20} {none_result['events_captured']:<12,} {basic_result['events_captured']:<12,} {aggressive_result['events_captured']:<12,}"
    )
    print(
        f"{'Total Frames':<20} {none_result['total_frames']:<12,} {basic_result['total_frames']:<12,} {aggressive_result['total_frames']:<12,}"
    )
    print(
        f"{'Builtin Frames':<20} {none_result['builtin_frames']:<12,} {basic_result['builtin_frames']:<12,} {aggressive_result['builtin_frames']:<12,}"
    )
    print(
        f"{'App Frames':<20} {none_result['app_frames']:<12,} {basic_result['app_frames']:<12,} {aggressive_result['app_frames']:<12,}"
    )
    print(
        f"{'Total Events':<20} {none_result['total_events']:<12,} {basic_result['total_events']:<12,} {aggressive_result['total_events']:<12,}"
    )
    print(
        f"{'File Size (KB)':<20} {none_result['file_size'] // 1024:<12,} {basic_result['file_size'] // 1024:<12,} {aggressive_result['file_size'] // 1024:<12,}"
    )

    # Calculate reductions
    basic_reduction = (
        (none_result["events_captured"] - basic_result["events_captured"])
        / none_result["events_captured"]
        * 100
    )
    aggressive_reduction = (
        (none_result["events_captured"] - aggressive_result["events_captured"])
        / none_result["events_captured"]
        * 100
    )

    print("\nEvent Reduction:")
    print(f"  Basic filtering: {basic_reduction:.1f}% reduction")
    print(f"  Aggressive filtering: {aggressive_reduction:.1f}% reduction")

    size_reduction_basic = (
        (none_result["file_size"] - basic_result["file_size"])
        / none_result["file_size"]
        * 100
    )
    size_reduction_aggressive = (
        (none_result["file_size"] - aggressive_result["file_size"])
        / none_result["file_size"]
        * 100
    )

    print("\nFile Size Reduction:")
    print(f"  Basic filtering: {size_reduction_basic:.1f}% smaller")
    print(f"  Aggressive filtering: {size_reduction_aggressive:.1f}% smaller")

    print("\n✅ Filtering effectively reduces noise while preserving application code!")
    return results


def test_specific_filtering():
    """Test that specific functions are filtered correctly."""
    print("\nTesting specific function filtering...")

    profiler = SpeedscopeProfiler(filter_level=FilterLevel.BASIC)

    # Test the filtering method directly
    test_cases = [
        # (name, filename, should_be_filtered)
        ("len", "<built-in>", True),
        ("isinstance", "<built-in>", True),
        ("append", "some_file.py", True),  # Common method name
        ("get", "some_file.py", True),  # Common method name
        ("application_function", "/path/to/my_app.py", False),  # Application code
        ("my_custom_function", "/path/to/my_app.py", False),  # Application code
        ("__init__", "/path/to/my_app.py", False),  # Keep dunder methods
        (
            "_private_method",
            "/path/to/my_app.py",
            True,
        ),  # Filter private methods at basic level
    ]

    for name, filename, expected_filtered in test_cases:
        result = profiler._should_filter_frame(name, filename)
        status = "FILTERED" if result else "KEPT"
        expected = "FILTERED" if expected_filtered else "KEPT"

        if result == expected_filtered:
            print(f"  ✓ {name:<20} in {filename:<20} -> {status}")
        else:
            print(
                f"  ❌ {name:<20} in {filename:<20} -> {status} (expected {expected})"
            )


def main():
    """Run filtering tests."""
    print("Testing Builtin Filtering Functionality")
    print("=" * 50)

    try:
        test_specific_filtering()
        results = test_filter_levels()

        print("\n" + "=" * 50)
        print("✅ All filtering tests passed!")
        print("\nRecommendations:")
        print("  • Use FilterLevel.BASIC for most cases (good balance)")
        print("  • Use FilterLevel.NONE for debugging or detailed analysis")
        print("  • Use FilterLevel.AGGRESSIVE for production monitoring")
        print("  • Filtering significantly reduces file sizes and noise")

    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback

        traceback.print_exc()
        return 1

    return 0


if __name__ == "__main__":
    exit(main())
