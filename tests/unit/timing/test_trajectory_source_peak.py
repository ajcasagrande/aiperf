# SPDX-FileCopyrightText: Copyright (c) 2025-2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Tests for ``TrajectorySource.peak_for`` (post-t* session-achievable P)."""

from types import SimpleNamespace

from aiperf.timing.trajectory_source import (
    ConversationState,
    Trajectory,
    TrajectorySnapshot,
    TrajectorySource,
)


def _turn(timestamp_ms: float | None, api_time_ms: float | None) -> SimpleNamespace:
    return SimpleNamespace(timestamp_ms=timestamp_ms, api_time_ms=api_time_ms)


def _make_source(metadata_lookup: dict[str, SimpleNamespace]) -> TrajectorySource:
    src = object.__new__(TrajectorySource)
    src._metadata_lookup = metadata_lookup
    return src


def _state(conversation_id: str, next_turn_index: int) -> ConversationState:
    return ConversationState(
        conversation_id=conversation_id,
        x_correlation_id="x",
        next_turn_index=next_turn_index,
    )


def _trajectory_with_states(*states: ConversationState) -> Trajectory:
    snapshot = TrajectorySnapshot(t_star_ms=0.0, states=tuple(states))
    return Trajectory(
        conversation_id=states[0].conversation_id if states else "root",
        start_turn_index=0,
        snapshot=snapshot,
    )


def test_peak_for_two_overlapping_streams():
    # Two streams whose post-t* turns overlap in wall-clock time -> peak 2.
    meta = {
        "a": SimpleNamespace(turns=[_turn(0.0, 100.0), _turn(100.0, 100.0)]),
        "b": SimpleNamespace(turns=[_turn(50.0, 100.0)]),
    }
    src = _make_source(meta)
    traj = _trajectory_with_states(_state("a", 0), _state("b", 0))
    assert src.peak_for(traj) == 2


def test_peak_for_single_serial_stream():
    # One stream replays serially -> peak 1 even with many turns.
    meta = {
        "a": SimpleNamespace(
            turns=[_turn(0.0, 10.0), _turn(20.0, 10.0), _turn(40.0, 10.0)]
        ),
    }
    src = _make_source(meta)
    traj = _trajectory_with_states(_state("a", 0))
    assert src.peak_for(traj) == 1


def test_peak_for_two_non_overlapping_streams():
    # Two streams that never overlap in time -> peak 1.
    meta = {
        "a": SimpleNamespace(turns=[_turn(0.0, 10.0)]),
        "b": SimpleNamespace(turns=[_turn(100.0, 10.0)]),
    }
    src = _make_source(meta)
    traj = _trajectory_with_states(_state("a", 0), _state("b", 0))
    assert src.peak_for(traj) == 1


def test_peak_for_respects_next_turn_index_slice():
    # Stream "a" only replays from next_turn_index=1 onward; its turn 0 (which
    # would overlap "b") is before t* and must not count.
    meta = {
        "a": SimpleNamespace(turns=[_turn(0.0, 100.0), _turn(200.0, 10.0)]),
        "b": SimpleNamespace(turns=[_turn(50.0, 10.0)]),
    }
    src = _make_source(meta)
    traj = _trajectory_with_states(_state("a", 1), _state("b", 0))
    assert src.peak_for(traj) == 1


def test_peak_for_no_snapshot_falls_back_to_one():
    src = _make_source({})
    traj = Trajectory(conversation_id="root", start_turn_index=0, snapshot=None)
    assert src.peak_for(traj) == 1


def test_peak_for_timestampless_turns_skipped_falls_back_to_one():
    # Turns with no timestamp are skipped; no usable streams -> fallback 1.
    meta = {
        "a": SimpleNamespace(turns=[_turn(None, 100.0), _turn(None, 100.0)]),
    }
    src = _make_source(meta)
    traj = _trajectory_with_states(_state("a", 0))
    assert src.peak_for(traj) == 1


def test_full_trace_peak_includes_root_and_branch_children():
    # Recycled-tree cap: root + 2 branch children over ALL turns.
    # root [0,100), child a [50,150), child b [120,200): no instant has all 3,
    # but root&a and a&b each overlap -> full-trace peak 2 (not 1).
    meta = {
        "root": SimpleNamespace(turns=[_turn(0.0, 100.0)]),
        "a": SimpleNamespace(turns=[_turn(50.0, 100.0)]),
        "b": SimpleNamespace(turns=[_turn(120.0, 80.0)]),
    }
    src = _make_source(meta)
    src._branch_runtimes = lambda root_meta: [
        SimpleNamespace(child_conversation_ids=["a", "b"])
    ]
    assert src.full_trace_peak("root") == 2


def test_full_trace_peak_counts_all_turns_not_a_slice():
    # Unlike peak_for, the recycle cap replays from turn 0 -> every stream's
    # first turn counts. All three busy at t=20..50 -> peak 3.
    meta = {
        "root": SimpleNamespace(turns=[_turn(0.0, 50.0)]),
        "a": SimpleNamespace(turns=[_turn(10.0, 50.0)]),
        "b": SimpleNamespace(turns=[_turn(20.0, 50.0)]),
    }
    src = _make_source(meta)
    src._branch_runtimes = lambda root_meta: [
        SimpleNamespace(child_conversation_ids=["a", "b"])
    ]
    assert src.full_trace_peak("root") == 3


def test_full_trace_peak_missing_root_falls_back_to_one():
    src = _make_source({})
    assert src.full_trace_peak("missing") == 1


def test_full_trace_peak_timestampless_falls_back_to_one():
    meta = {"root": SimpleNamespace(turns=[_turn(None, 100.0)])}
    src = _make_source(meta)
    src._branch_runtimes = lambda root_meta: []
    assert src.full_trace_peak("root") == 1
