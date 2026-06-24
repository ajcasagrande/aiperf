# SPDX-FileCopyrightText: Copyright (c) 2025-2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Session-achievable peak concurrency for agentic-replay inner-session limits."""

from __future__ import annotations

_EPS_MS = 1e-6


def session_achievable_peak(streams: list[list[tuple[float, float]]]) -> int:
    """Max number of streams simultaneously busy, ≤1 in-flight per stream.

    A session replays serially, so within-stream overlap is collapsed (a stream
    is "busy" across the union of its request intervals). Returns the peak
    overlap across streams' busy-spans -- the cap a serial-session replay can
    actually reach. Floors at 1 (a tree always runs at least one request).

    ``streams``: per stream, a list of ``(start_ms, end_ms)`` request intervals.

    A zero-width busy-span (a turn whose recorded duration is 0 or unknown, so
    ``start == end``) still counts as momentarily busy at its instant: its end is
    nudged by ``_EPS_MS`` so it overlaps any span containing that instant.
    Without this a point's own end would cancel its own start before the sweep
    samples the count, undercounting the peak for zero/None-duration turns. The
    nudge is sub-ms, so it never turns an exact-touch hand-off between two real
    spans (A ends exactly when B starts) into a false overlap.
    """
    busy: list[tuple[float, float]] = []
    for s in streams:
        if not s:
            continue
        ivs = sorted(s)
        cur_s, cur_e = ivs[0]
        for st, en in ivs[1:]:
            if st <= cur_e + _EPS_MS:  # within-stream overlap -> merge (serial)
                cur_e = max(cur_e, en)
            else:
                busy.append((cur_s, cur_e))
                cur_s, cur_e = st, en
        busy.append((cur_s, cur_e))
    if not busy:
        return 1
    events: list[tuple[float, int]] = []
    for s, e in busy:
        events.append((s, 1))
        # A point (s == e) would self-cancel under the ends-before-starts tie
        # break; give it a sub-ms width so it registers as busy at its instant.
        events.append((max(e, s + _EPS_MS), -1))
    events.sort(key=lambda x: (x[0], x[1]))  # ends (-1) before starts (+1) at ties
    cur = peak = 0
    for _, d in events:
        cur += d
        peak = max(peak, cur)
    return max(1, peak)
