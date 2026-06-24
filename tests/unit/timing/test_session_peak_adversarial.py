# SPDX-FileCopyrightText: Copyright (c) 2025-2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Adversarial tests for the weka inner-session achievable-peak math.

Attacks ``aiperf.timing.session_peak.session_achievable_peak`` and the
``TrajectorySource.peak_for`` wrapper that feeds it. The goal is to break the
sweep-line / within-stream-merge logic with pathological inputs:

- zero-duration intervals, exact-touch cross-stream ties, near-touch within a
  stream at the ``_EPS_MS = 1e-6`` merge boundary (just above / just below).
- unsorted within-stream intervals, deeply nested / staircase overlaps,
  identical intervals across many streams, large N for the sweep line.
- empty / all-empty / single-empty stream lists, the degenerate ``[]`` floor.
- ``peak_for`` edges: ``snapshot is None``, a state whose conversation_id is
  missing from ``_metadata_lookup`` (the ``meta is None`` continue branch),
  ``next_turn_index`` past the end of turns, ``timestamp_ms=None`` (skipped),
  ``api_time_ms=None`` / ``0.0`` (point interval), an all-timestamp-less
  trajectory falling back to 1.

Out of scope (covered by siblings): the happy-path peaks in
``test_session_peak.py`` and the ``full_trace_peak`` recycle cap and basic
``peak_for`` flows in ``test_trajectory_source_peak.py``. This file does NOT
re-test those; it only pushes the boundaries.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from pytest import param

from aiperf.timing.session_peak import session_achievable_peak
from aiperf.timing.trajectory_source import (
    ConversationState,
    Trajectory,
    TrajectorySnapshot,
    TrajectorySource,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_EPS_MS = 1e-6


def _turn(timestamp_ms: float | None, api_time_ms: float | None) -> SimpleNamespace:
    """One trace turn carrying the two fields ``peak_for`` reads off metadata."""
    return SimpleNamespace(timestamp_ms=timestamp_ms, api_time_ms=api_time_ms)


def _make_source(metadata_lookup: dict[str, SimpleNamespace]) -> TrajectorySource:
    """A TrajectorySource with only ``_metadata_lookup`` wired (no __init__).

    Matches the construction pattern in ``test_trajectory_source_peak.py``:
    ``peak_for`` reads nothing else off ``self``.
    """
    src = object.__new__(TrajectorySource)
    src._metadata_lookup = metadata_lookup
    return src


def _state(conversation_id: str, next_turn_index: int) -> ConversationState:
    return ConversationState(
        conversation_id=conversation_id,
        x_correlation_id="x-conv-2026-06-24-9c3a",
        next_turn_index=next_turn_index,
    )


def _trajectory_with_states(*states: ConversationState) -> Trajectory:
    snapshot = TrajectorySnapshot(t_star_ms=0.0, states=tuple(states))
    return Trajectory(
        conversation_id=states[0].conversation_id if states else "root",
        start_turn_index=0,
        snapshot=snapshot,
    )


# ==========================================================================
# session_achievable_peak: cross-stream tie / touch boundaries
# ==========================================================================


class TestSessionPeakTouchTies:
    """At cross-stream ties, an end must be processed before a start."""

    def test_exact_touch_across_streams_is_one_not_two(self) -> None:
        # A ends at 5.0, B starts at 5.0. The two are NOT simultaneous: ends
        # (-1) sort before starts (+1) at the tie, so the count returns to 0
        # before B opens. Peak 1.
        assert session_achievable_peak([[(0.0, 5.0)], [(5.0, 10.0)]]) == 1

    def test_three_way_baton_pass_at_same_instant_is_one(self) -> None:
        # A:[0,5] hands to B:[5,10] hands to C:[10,15]; every handoff is an
        # exact touch. No instant has two streams busy. Peak 1.
        streams = [[(0.0, 5.0)], [(5.0, 10.0)], [(10.0, 15.0)]]
        assert session_achievable_peak(streams) == 1

    def test_start_one_epsilon_before_a_peer_end_overlaps(self) -> None:
        # B starts 1 ns before A ends -> genuine (if tiny) overlap -> peak 2.
        assert session_achievable_peak([[(0.0, 5.0)], [(5.0 - _EPS_MS, 10.0)]]) == 2

    def test_all_streams_share_one_instant_point_is_three(self) -> None:
        # Three zero-duration intervals all exactly at t=5.0. Each point's end
        # is nudged to 5+_EPS_MS, so all three are momentarily busy together at
        # t=5 -> peak 3. Under the "count a zero/None-duration turn as
        # momentarily busy" semantics, three streams each firing at the same
        # instant are genuinely 3-way concurrent at that instant.
        streams = [[(5.0, 5.0)], [(5.0, 5.0)], [(5.0, 5.0)]]
        assert session_achievable_peak(streams) == 3


# ==========================================================================
# session_achievable_peak: zero-duration / point intervals
# ==========================================================================


class TestSessionPeakZeroDuration:
    """Point intervals (start == end) must not crash or over-count."""

    def test_single_point_interval_is_one(self) -> None:
        assert session_achievable_peak([[(3.0, 3.0)]]) == 1

    def test_point_inside_another_streams_span_overlaps(self) -> None:
        # A:[0,10] is busy across t=5; B is a point exactly at 5.0 inside it.
        # Two streams ARE simultaneously busy at t=5 -> peak is 2. The point's
        # end is nudged by _EPS_MS so it registers instead of self-cancelling.
        assert session_achievable_peak([[(0.0, 10.0)], [(5.0, 5.0)]]) == 2

    def test_point_at_peer_boundary_does_not_overlap(self) -> None:
        # B is a point exactly at A's end (10.0). B expands to [10, 10+eps);
        # A-end(-1) and B-start(+1) tie at 10 with ends-before-starts, so they
        # do not stack (hand-off, not overlap) -> peak stays 1.
        assert session_achievable_peak([[(0.0, 10.0)], [(10.0, 10.0)]]) == 1


# ==========================================================================
# session_achievable_peak: within-stream merge at the _EPS_MS boundary
# ==========================================================================


class TestSessionPeakWithinStreamMerge:
    """A serial session collapses its own overlapping/near-touching intervals."""

    def test_gap_just_under_eps_merges_one_busy_span(self) -> None:
        # Two within-stream intervals separated by a gap < _EPS_MS: the second
        # start <= cur_e + _EPS_MS, so they merge into one busy span. Paired
        # with a peer that overlaps the merged span only -> peak 2 once.
        stream = [[(0.0, 5.0), (5.0 + _EPS_MS / 2, 10.0)]]
        # The merged busy span is [0, 10]; a peer fully inside is concurrent.
        peer = [[(2.0, 3.0)]]
        assert session_achievable_peak(stream + peer) == 2

    def test_gap_exactly_eps_merges(self) -> None:
        # st == cur_e + _EPS_MS exactly: condition is `<=`, so it MERGES.
        # Merged span [0,10]; without a merge there would be two separate
        # spans but it is still one stream so peak stays 1 either way -- the
        # observable is that no crash and result is the serial floor 1.
        assert session_achievable_peak([[(0.0, 5.0), (5.0 + _EPS_MS, 10.0)]]) == 1

    def test_gap_above_eps_within_one_stream_still_one(self) -> None:
        # Even when the two within-stream intervals do NOT merge (gap > eps),
        # they belong to the SAME serial session, so peak is still 1. This is
        # the invariant the merge protects: a session is never >1 in flight.
        assert session_achievable_peak([[(0.0, 5.0), (5.0 + 1.0, 10.0)]]) == 1

    def test_non_merged_within_stream_spans_each_overlap_distinct_peers(self) -> None:
        # Stream A has two non-merging busy spans [0,5] and [100,105]. Peer B
        # overlaps the first, peer C overlaps the second. A is serial so it is
        # never simultaneous with itself; peak is A+B (=2) at t~2, never 3.
        a = [(0.0, 5.0), (100.0, 105.0)]
        b = [(1.0, 4.0)]
        c = [(101.0, 104.0)]
        assert session_achievable_peak([a, b, c]) == 2


# ==========================================================================
# session_achievable_peak: unsorted input / nested / staircase
# ==========================================================================


class TestSessionPeakOrderingAndShape:
    """The function sorts internally; ordering of inputs must not matter."""

    def test_within_stream_intervals_given_out_of_order_still_collapse(self) -> None:
        # Reversed within-stream order; sorted() inside fixes it -> peak 1.
        assert session_achievable_peak([[(10.0, 12.0), (0.0, 5.0), (5.0, 10.0)]]) == 1

    def test_stream_order_does_not_change_peak(self) -> None:
        forward = session_achievable_peak([[(0.0, 9.0)], [(1.0, 8.0)], [(2.0, 7.0)]])
        reversed_streams = session_achievable_peak(
            [[(2.0, 7.0)], [(1.0, 8.0)], [(0.0, 9.0)]]
        )
        assert forward == reversed_streams == 3

    def test_nested_intervals_across_streams_peak_equals_depth(self) -> None:
        # Fully nested: [0,100] contains [10,90] contains [20,80]. At t=50 all
        # three are busy -> peak 3.
        streams = [[(0.0, 100.0)], [(10.0, 90.0)], [(20.0, 80.0)]]
        assert session_achievable_peak(streams) == 3

    def test_staircase_overlaps_peak_is_two(self) -> None:
        # Each step overlaps only its neighbour: [0,3],[2,5],[4,7],[6,9]. No
        # instant has 3 busy at once -> peak 2.
        streams = [[(0.0, 3.0)], [(2.0, 5.0)], [(4.0, 7.0)], [(6.0, 9.0)]]
        assert session_achievable_peak(streams) == 2


# ==========================================================================
# session_achievable_peak: scale / identical intervals
# ==========================================================================


class TestSessionPeakScale:
    """Many streams stress the O(n log n) sweep line."""

    @pytest.mark.parametrize(
        "n",
        [
            param(1, id="n-1"),
            param(2, id="n-2"),
            param(50, id="n-50"),
            param(100, id="n-100"),
        ],
    )  # fmt: skip
    def test_n_fully_overlapping_streams_peak_equals_n(self, n: int) -> None:
        # All N streams busy across the identical span -> peak == N.
        streams = [[(0.0, 1000.0)] for _ in range(n)]
        assert session_achievable_peak(streams) == n

    def test_identical_intervals_across_many_streams_peak_equals_count(self) -> None:
        # 100 byte-identical intervals; all simultaneously busy -> peak 100.
        streams = [[(42.0, 99.0)] for _ in range(100)]
        assert session_achievable_peak(streams) == 100

    def test_disjoint_staggered_singletons_peak_one(self) -> None:
        # 100 streams, each a 1-wide interval starting 10 apart and ending
        # exactly when the next begins (touch) -> never two busy -> peak 1.
        streams = [[(float(i * 10), float(i * 10 + 10))] for i in range(100)]
        assert session_achievable_peak(streams) == 1


# ==========================================================================
# session_achievable_peak: empty / degenerate floor
# ==========================================================================


class TestSessionPeakEmpties:
    """Empty streams are skipped; an all-empty input floors to 1."""

    def test_empty_list_floors_to_one(self) -> None:
        assert session_achievable_peak([]) == 1

    def test_single_empty_stream_floors_to_one(self) -> None:
        assert session_achievable_peak([[]]) == 1

    def test_all_empty_streams_floor_to_one(self) -> None:
        assert session_achievable_peak([[], [], []]) == 1

    def test_empty_streams_mixed_with_two_overlapping_is_two(self) -> None:
        # Empty streams are `continue`-skipped; the two real overlapping
        # streams still produce peak 2.
        streams = [[], [(0.0, 10.0)], [], [(3.0, 7.0)], []]
        assert session_achievable_peak(streams) == 2

    def test_single_real_stream_among_empties_is_one(self) -> None:
        assert session_achievable_peak([[], [(0.0, 5.0)], []]) == 1


# ==========================================================================
# session_achievable_peak: float-precision around the merge epsilon
# ==========================================================================


class TestSessionPeakFloatPrecision:
    """Probe the merge boundary just above / below / at 1e-6."""

    @pytest.mark.parametrize(
        "gap",
        [
            param(0.0, id="touching-merges"),
            param(_EPS_MS / 10.0, id="tenth-eps-merges"),
            param(_EPS_MS, id="exact-eps-merges"),
            param(_EPS_MS * 2.0, id="two-eps-no-merge-still-serial"),
            param(1.0, id="big-gap-no-merge-still-serial"),
        ],
    )  # fmt: skip
    def test_within_stream_two_intervals_always_one_regardless_of_gap(
        self, gap: float
    ) -> None:
        # Whether the two within-stream intervals merge or not, a single serial
        # session can never be >1 in flight. The eps only affects how many busy
        # spans are emitted (an internal detail), never the single-stream peak.
        assert session_achievable_peak([[(0.0, 5.0), (5.0 + gap, 10.0)]]) == 1


# ==========================================================================
# TrajectorySource.peak_for: snapshot / lookup / slice edges
# ==========================================================================


class TestPeakForEdges:
    """Boundary behaviour of the metadata-walking wrapper."""

    def test_missing_conversation_in_lookup_is_skipped(self) -> None:
        # State "ghost" has no metadata entry -> `meta is None` continue branch.
        # Only "a" contributes; one serial stream -> peak 1 (not a KeyError).
        meta = {"a": SimpleNamespace(turns=[_turn(0.0, 100.0)])}
        src = _make_source(meta)
        traj = _trajectory_with_states(_state("a", 0), _state("ghost", 0))
        assert src.peak_for(traj) == 1

    def test_missing_lookup_for_only_stream_falls_back_to_one(self) -> None:
        # The single live stream has no metadata -> no usable streams -> 1.
        src = _make_source({})
        traj = _trajectory_with_states(_state("ghost", 0))
        assert src.peak_for(traj) == 1

    def test_overlap_survives_a_missing_peer(self) -> None:
        # Two real overlapping streams plus a ghost: ghost is skipped, the two
        # real ones still overlap -> peak 2.
        meta = {
            "a": SimpleNamespace(turns=[_turn(0.0, 100.0)]),
            "b": SimpleNamespace(turns=[_turn(50.0, 100.0)]),
        }
        src = _make_source(meta)
        traj = _trajectory_with_states(
            _state("a", 0), _state("ghost", 0), _state("b", 0)
        )
        assert src.peak_for(traj) == 2

    def test_next_turn_index_past_end_yields_empty_slice(self) -> None:
        # next_turn_index=5 but the stream only has 2 turns -> empty slice ->
        # no intervals -> stream skipped. With its only peer also sliced away,
        # no usable streams -> fallback 1.
        meta = {"a": SimpleNamespace(turns=[_turn(0.0, 100.0), _turn(100.0, 100.0)])}
        src = _make_source(meta)
        traj = _trajectory_with_states(_state("a", 5))
        assert src.peak_for(traj) == 1

    def test_one_stream_sliced_to_empty_other_still_counts_one(self) -> None:
        # "a" sliced past end (empty), "b" has one usable turn. Only b counts;
        # a single stream -> peak 1.
        meta = {
            "a": SimpleNamespace(turns=[_turn(0.0, 10.0)]),
            "b": SimpleNamespace(turns=[_turn(0.0, 10.0)]),
        }
        src = _make_source(meta)
        traj = _trajectory_with_states(_state("a", 9), _state("b", 0))
        assert src.peak_for(traj) == 1


# ==========================================================================
# TrajectorySource.peak_for: timestamp / api_time field edges
# ==========================================================================


class TestPeakForFieldEdges:
    """``timestamp_ms`` / ``api_time_ms`` None and zero handling."""

    def test_timestampless_turns_in_one_stream_are_skipped(self) -> None:
        # Stream "a": turn 0 has no timestamp (skipped), turn 1 overlaps b.
        meta = {
            "a": SimpleNamespace(turns=[_turn(None, 100.0), _turn(50.0, 100.0)]),
            "b": SimpleNamespace(turns=[_turn(60.0, 100.0)]),
        }
        src = _make_source(meta)
        traj = _trajectory_with_states(_state("a", 0), _state("b", 0))
        assert src.peak_for(traj) == 2

    def test_api_time_none_makes_a_point_interval(self) -> None:
        # api_time_ms=None -> interval is [t, t]; a bare point. Two such points
        # at different instants never overlap -> peak 1.
        meta = {
            "a": SimpleNamespace(turns=[_turn(0.0, None)]),
            "b": SimpleNamespace(turns=[_turn(100.0, None)]),
        }
        src = _make_source(meta)
        traj = _trajectory_with_states(_state("a", 0), _state("b", 0))
        assert src.peak_for(traj) == 1

    def test_api_time_zero_makes_a_point_interval_inside_a_peer(self) -> None:
        # b is a zero-api point at t=5 inside a's [0,100] span; both streams are
        # simultaneously busy at t=5 -> peak is 2. session_achievable_peak nudges
        # the point's end by _EPS_MS so an instantaneous (0ms/None api) turn
        # mid-fan-out still counts instead of self-cancelling.
        meta = {
            "a": SimpleNamespace(turns=[_turn(0.0, 100.0)]),
            "b": SimpleNamespace(turns=[_turn(5.0, 0.0)]),
        }
        src = _make_source(meta)
        traj = _trajectory_with_states(_state("a", 0), _state("b", 0))
        assert src.peak_for(traj) == 2

    def test_every_turn_timestampless_falls_back_to_one(self) -> None:
        # No turn in any stream has a timestamp -> no usable streams -> 1.
        meta = {
            "a": SimpleNamespace(turns=[_turn(None, 100.0), _turn(None, 50.0)]),
            "b": SimpleNamespace(turns=[_turn(None, 100.0)]),
        }
        src = _make_source(meta)
        traj = _trajectory_with_states(_state("a", 0), _state("b", 0))
        assert src.peak_for(traj) == 1

    def test_non_finite_timestamp_is_treated_as_absent(self) -> None:
        # _as_timestamp_ms rejects NaN/inf -> that turn is skipped like a
        # timestamp-less one. Here a's only usable turn (finite) overlaps b.
        meta = {
            "a": SimpleNamespace(
                turns=[_turn(float("nan"), 100.0), _turn(50.0, 100.0)]
            ),
            "b": SimpleNamespace(turns=[_turn(60.0, 100.0)]),
        }
        src = _make_source(meta)
        traj = _trajectory_with_states(_state("a", 0), _state("b", 0))
        assert src.peak_for(traj) == 2

    def test_no_snapshot_returns_one_without_touching_lookup(self) -> None:
        # snapshot is None -> immediate fallback; _metadata_lookup untouched.
        src = _make_source({})
        traj = Trajectory(conversation_id="root", start_turn_index=0, snapshot=None)
        assert src.peak_for(traj) == 1
