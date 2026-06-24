# SPDX-FileCopyrightText: Copyright (c) 2025-2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Prototype: per-tree INNER semaphore for inner-session concurrency limits.

Instead of modeling dependencies (which fabricates edges), cap each session
tree's in-flight requests at its recorded peak P via a semaphore. Each request
fires at its recorded offset (within-stream end-to-start preserved), acquires a
slot (waits if the tree is at P), releases on completion. By construction peak
in-flight <= P = recorded peak. No edges, no fabrication.

Validates two-sided (peak vs recorded; semaphore caps at P so over=0 by
construction -- the real question is whether it HOLDS at P under slowdown vs
spuriously under-shoots) AND the concurrency TIME-SERIES shape (normalized L1),
the metric that exposed packing/happens-before distortion. Event-driven sim.
"""

from __future__ import annotations

import heapq
import json

import tools._overlap_gating_ab as ab
import tools._thinktime_ab as tt


def _inflight_curve(intervals):
    """Step function of in-flight count over time as (time, count) change points."""
    ev = []
    for s, e in intervals:
        ev.append((s, 1))
        ev.append((e, -1))
    ev.sort(key=lambda x: (x[0], x[1]))
    cur = 0
    pts = []  # (time, count_after)
    for t, d in ev:
        cur += d
        pts.append((t, cur))
    return pts


def _norm_l1(rec_intervals, rep_intervals):
    """Shape-normalized L1 between two in-flight curves: rescale each to unit
    total duration and unit area, integrate |diff|. ~0 means same shape (pure
    time-dilation scores 0); large means the concurrency profile was reshaped."""

    def normalize(intervals):
        if not intervals:
            return []
        lo = min(s for s, _ in intervals)
        hi = max(e for _, e in intervals)
        span = hi - lo or 1.0
        # sample the step function at a fixed grid in normalized time
        pts = _inflight_curve(intervals)
        return lo, span, pts

    rlo, rspan, rpts = normalize(rec_intervals)
    plo, pspan, ppts = normalize(rep_intervals)
    N = 200

    def sample(lo, span, pts, u):
        t = lo + u * span
        c = 0
        for pt_t, pt_c in pts:
            if pt_t <= t + 1e-12:
                c = pt_c
            else:
                break
        return c

    # normalize amplitude by mean so a pure stretch (same shape) -> 0
    def mean_amp(lo, span, pts):
        return sum(sample(lo, span, pts, i / N) for i in range(N)) / N or 1.0

    ra = mean_amp(rlo, rspan, rpts)
    pa = mean_amp(plo, pspan, ppts)
    diff = 0.0
    for i in range(N):
        u = i / N
        rv = sample(rlo, rspan, rpts, u) / ra
        pv = sample(plo, pspan, ppts, u) / pa
        diff += abs(rv - pv)
    return diff / N


def session_achievable_peak(streams):
    """Peak SIMULTANEOUS BUSY STREAMS (<=1 in-flight per stream) -- the peak a
    serial-session replay can actually produce. Per stream, merge its request
    intervals (a serial session is busy across them as one), then peak overlap
    across streams. This is the correct semaphore size, not the raw per-request
    interval peak (which double-counts within-stream overlap a session can't hit)."""
    busy = []
    for s in streams:
        ivs = sorted((t, t + a) for t, a, _ in s)
        # merge overlapping within-stream intervals into busy spans
        cur_s, cur_e = ivs[0]
        for st, en in ivs[1:]:
            if st <= cur_e + 1e-9:
                cur_e = max(cur_e, en)
            else:
                busy.append((cur_s, cur_e))
                cur_s, cur_e = st, en
        busy.append((cur_s, cur_e))
    return ab._peak_inflight(busy)


def _post_tstar(streams, frac=0.5):
    """Keep only requests in flight at/after a per-trace t* (deterministic)."""
    import hashlib

    all_starts = [t for s in streams for t, _a, _ in s]
    all_ends = [t + a for s in streams for t, a, _ in s]
    lo, hi = min(all_starts), max(all_ends)
    # deterministic t* in [0.25, 0.75]
    h = (
        int.from_bytes(hashlib.sha256(f"{lo}:{hi}".encode()).digest()[:8], "big")
        / 2**64
    )
    ts = lo + (0.25 + 0.5 * h) * (hi - lo)
    out = []
    for s in streams:
        kept = [(t, a, tt) for t, a, tt in s if t + a >= ts]
        if kept:
            out.append(kept)
    return out


def simulate(streams, P, slowdown_fn):
    """Event-driven per-tree semaphore sim. Returns replay intervals."""
    t0 = min(s[0][0] for s in streams)
    heap = []
    seq = 0

    def push(time, kind, si, k):
        nonlocal seq
        heapq.heappush(heap, (time, seq, kind, si, k))
        seq += 1

    for si, s in enumerate(streams):
        push(s[0][0] - t0, "ready", si, 0)

    in_flight = 0
    waiting = []
    intervals = []

    def dispatch(now, si, k):
        nonlocal in_flight
        api = streams[si][k][1]
        comp = now + api * slowdown_fn(api)
        intervals.append((now, comp))
        in_flight += 1
        push(comp, "complete", si, k)

    while heap:
        time, _, kind, si, k = heapq.heappop(heap)
        if kind == "ready":
            if in_flight < P:
                dispatch(time, si, k)
            else:
                heapq.heappush(waiting, (time, seq, si, k))
                seq += 1
        else:  # complete
            in_flight -= 1
            s = streams[si]
            if k + 1 < len(s):
                t_k, api_k = s[k][0], s[k][1]
                t_n = s[k + 1][0]
                gap = max(0.0, t_n - (t_k + api_k))  # end-to-start within stream
                push(time + gap, "ready", si, k + 1)
            if waiting and in_flight < P:
                _, _, wsi, wk = heapq.heappop(waiting)
                dispatch(time, wsi, wk)
    return intervals


def main():
    import random

    rows = []
    recycle_rows = []
    l1_1 = []
    l1_2 = []
    n = 0
    with open(tt.CORPUS) as f:
        for line in f:
            if not line.strip():
                continue
            try:
                streams = [s for s in tt.streams_with_thinktime(json.loads(line)) if s]
            except Exception:
                continue
            if not streams:
                continue
            streams_full = streams  # pre-t* full trace (for recycle re-sampling)
            streams = _post_tstar(streams)  # runtime replays the post-t* slice
            if not streams:
                continue
            rec_intervals = [(t, t + a) for s in streams for t, a, _ in s]
            rec_raw_peak = ab._peak_inflight(rec_intervals)
            P = session_achievable_peak(streams)  # KEY FIX: achievable, not raw
            if P <= 0 or rec_raw_peak <= 0:
                continue
            n += 1
            d = json.loads(line)
            rng = random.Random(hash(d.get("id", n)) & 0xFFFFFFFF)
            rep1 = simulate(streams, P, lambda a: 1.0)
            rep2 = simulate(streams, P, lambda a: 2.0)
            rep5 = simulate(streams, P, lambda a: 5.0)
            repn = simulate(streams, P, lambda a, _rng=rng: _rng.uniform(1.0, 8.0))
            rows.append(
                (
                    P,
                    rec_raw_peak,
                    ab._peak_inflight(rep1),
                    ab._peak_inflight(rep2),
                    ab._peak_inflight(rep5),
                    ab._peak_inflight(repn),
                )
            )
            # Recycle regime: a recycled trajectory is re-sampled post-t* (spec §6
            # decision), NOT replayed full-trace. Verify over=0 holds there too.
            streams_r = _post_tstar(streams_full, frac=0.5)  # independent re-sample
            if streams_r:
                rec_raw_r = ab._peak_inflight(
                    [(t, t + a) for s in streams_r for t, a, _ in s]
                )
                P_r = session_achievable_peak(streams_r)
                if P_r > 0 and rec_raw_r > 0:
                    rep_r = simulate(streams_r, P_r, lambda a: 2.0)
                    recycle_rows.append((rec_raw_r, ab._peak_inflight(rep_r)))
            # time-series shape (rebased to recorded start)
            l1_1.append(_norm_l1(rec_intervals, rep1))
            l1_2.append(_norm_l1(rec_intervals, rep2))

    def pct(xs, q):
        xs = sorted(xs)
        return xs[min(len(xs) - 1, int(len(xs) * q))]

    print(
        f"\nPER-TREE SEMAPHORE prototype (post-t*; P = session-ACHIEVABLE peak) — {n} traces"
    )
    slack = sum(1 for k in range(len(rows)) if rows[k][0] < rows[k][1])
    print(
        f"  P (achievable) < recorded raw peak on {slack}/{len(rows)} (was the slack/no-protection set)"
    )
    print(
        "  PROTECTION — replay peak vs recorded RAW peak (over = fabrication, must be 0):"
    )
    for idx, lbl in [
        (2, "uniform 1.0x"),
        (3, "uniform 2.0x"),
        (4, "uniform 5.0x"),
        (5, "NON-uniform [1,8]x"),
    ]:
        r = sorted(rows[k][idx] / rows[k][1] for k in range(len(rows)))
        over = sum(1 for x in r if x > 1.0001)
        print(
            f"    {lbl:>18}: median={r[len(r) // 2]:.2f}x  over={over}/{len(r)}  max={max(r):.2f}"
        )
    print(
        "  CAP-BINDS — replay peak vs achievable P (under = cap is slack / doesn't bind):"
    )
    for idx, lbl in [
        (2, "uniform 1.0x"),
        (3, "uniform 2.0x"),
        (5, "NON-uniform [1,8]x"),
    ]:
        r = sorted(rows[k][idx] / rows[k][0] for k in range(len(rows)))
        under = sum(1 for x in r if x < 0.9999)
        print(
            f"    {lbl:>18}: median={r[len(r) // 2]:.2f}x  under={under}/{len(r)}  min={min(r):.2f}"
        )
    print(
        "\n  concurrency TIME-SERIES shape divergence (normalized L1; ~0 = faithful shape):"
    )
    print(
        f"    @1.0x: median={pct(l1_1, 0.5):.3f}  p90={pct(l1_1, 0.9):.3f}  max={max(l1_1):.3f}  >0.05={sum(1 for x in l1_1 if x > 0.05)}/{len(l1_1)}"
    )
    print(
        f"    @2.0x: median={pct(l1_2, 0.5):.3f}  p90={pct(l1_2, 0.9):.3f}  max={max(l1_2):.3f}  >0.05={sum(1 for x in l1_2 if x > 0.05)}/{len(l1_2)}"
    )
    print("\n  RECYCLE regime (re-sampled post-t*, @2.0x) — over must be 0:")
    rr = sorted(rc[1] / rc[0] for rc in recycle_rows)
    over = sum(1 for x in rr if x > 1.0001)
    print(
        f"    over={over}/{len(rr)}  median={rr[len(rr) // 2]:.2f}x  max={max(rr):.2f}"
    )


if __name__ == "__main__":
    main()
