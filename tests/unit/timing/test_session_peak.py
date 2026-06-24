# SPDX-FileCopyrightText: Copyright (c) 2025-2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
from aiperf.timing.session_peak import session_achievable_peak


def test_single_stream_is_one():
    # one stream, three serial requests -> a session is ≤1 in flight
    assert session_achievable_peak([[(0.0, 5.0), (5.0, 10.0), (10.0, 12.0)]]) == 1


def test_two_overlapping_streams_is_two():
    assert session_achievable_peak([[(0.0, 10.0)], [(3.0, 7.0)]]) == 2


def test_within_stream_overlap_collapses_to_one():
    # one stream whose own two requests overlap -> serial session counts it once
    assert session_achievable_peak([[(0.0, 6.0), (3.0, 9.0)]]) == 1


def test_touching_intervals_do_not_overlap():
    # stream A ends exactly when B starts -> not simultaneous
    assert session_achievable_peak([[(0.0, 5.0)], [(5.0, 10.0)]]) == 1


def test_empty_streams_floor_to_one():
    assert session_achievable_peak([[(0.0, 1.0)]]) == 1
    assert session_achievable_peak([]) == 1  # degenerate floor


def test_three_concurrent_streams():
    assert session_achievable_peak([[(0.0, 9.0)], [(1.0, 8.0)], [(2.0, 7.0)]]) == 3
