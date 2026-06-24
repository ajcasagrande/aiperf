# SPDX-FileCopyrightText: Copyright (c) 2025-2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Inner-session limiter wiring tests for AgenticReplayStrategy.

Exercises the centralized wire-send chokepoint (``_issue_gated``) end-to-end
through the snapshot PROFILING dispatch path with a real ``InnerSessionLimiter``
(never mocked) and a fake issuer that holds requests "on the wire" until
released:

- gating ON: a 3-stream trajectory whose post-t* session-achievable peak is 2
  never has more than 2 requests in flight (the 3rd queues on the semaphore).
- gating OFF (default): all 3 fire, proving the chokepoint is a zero-behavior
  pass-through when ``--use-end-to-start-delays`` is unset.
- a refused issue releases the slot (no leak): ``in_flight`` returns to baseline.
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from aiperf.common.enums import CacheBustTarget, ConversationBranchMode, CreditPhase
from aiperf.common.models import (
    ConversationMetadata,
    DatasetMetadata,
    TurnMetadata,
)
from aiperf.credit.structs import Credit
from aiperf.plugin.enums import DatasetSamplingStrategy
from aiperf.timing.strategies.agentic_replay import AgenticReplayStrategy
from aiperf.timing.trajectory_source import (
    ConversationState,
    Trajectory,
    TrajectorySnapshot,
    TrajectorySource,
)

# Three sibling streams under one shared tree root. Their recorded busy spans
# overlap pairwise but never all three at once, so session_achievable_peak == 2:
#   A: [0, 100], B: [50, 150]  -> overlap 50-100 (peak 2)
#   C: [200, 300]              -> disjoint from A/B (peak stays 2)
_ROOT_CORR = "tree-root"
_STREAMS = (
    ("trace_0::sa:a", "corr-a", 0.0, 100.0),
    ("trace_0::sa:b", "corr-b", 50.0, 100.0),
    ("trace_0::sa:c", "corr-c", 200.0, 100.0),
)


def _build_source() -> TrajectorySource:
    """Real TrajectorySource with one 3-stream snapshot trajectory (peak 2).

    All three streams are background subagents (agent_depth=1, no dispatchable
    depth-0 root) sharing one tree root. They are seeded in the snapshot, so the
    PROFILING resume dispatches each via issue_credit (the root wire path) -- the
    runtime dispatch_child_turn path is only for children a parent spawns on a
    turn completion. Both wire paths are gated by the limiter identically.
    """
    convs = [
        ConversationMetadata(
            conversation_id=cid,
            turns=[TurnMetadata(timestamp_ms=ts, api_time_ms=api)],
            is_root=False,
            agent_depth=1,
            parent_conversation_id="trace_0",
        )
        for cid, _xc, ts, api in _STREAMS
    ]
    ds = DatasetMetadata(
        conversations=convs,
        sampling_strategy=DatasetSamplingStrategy.SEQUENTIAL,
    )
    states = tuple(
        ConversationState(
            conversation_id=cid,
            x_correlation_id=xc,
            next_turn_index=0,
            # Spread mode anchors t0=0, so a positive offset routes the send
            # through scheduler.schedule_later -- which the test turns into a
            # concurrent task so all three race at the chokepoint at once.
            next_dispatch_offset_ms=1000.0,
            agent_depth=1,
            parent_correlation_id=_ROOT_CORR,
            root_correlation_id=_ROOT_CORR,
        )
        for cid, xc, _ts, _api in _STREAMS
    )
    trajectory = Trajectory(
        conversation_id="trace_0",
        start_turn_index=0,
        snapshot=TrajectorySnapshot(t_star_ms=0.0, states=states),
    )
    src = TrajectorySource.__new__(TrajectorySource)
    src._dataset_metadata = ds
    src._dataset_sampler = MagicMock()
    src._metadata_lookup = {c.conversation_id: c for c in ds.conversations}
    src.trajectories = [trajectory]
    return src


def _make_strategy(
    *, enabled: bool, issuer: AsyncMock
) -> tuple[AgenticReplayStrategy, list]:
    """Build a PROFILING strategy whose scheduler runs each deferred dispatch as
    a concurrent task (delay ignored), so the three sends race at the chokepoint.
    """
    src = _build_source()
    tasks: list[asyncio.Task] = []

    def fake_schedule_later(_delay, coro):
        tasks.append(asyncio.ensure_future(coro))

    scheduler = MagicMock()
    scheduler.schedule_later.side_effect = fake_schedule_later

    # Real-shaped config stub: only ``input.use_end_to_start_delays`` toggles the
    # gate; the cache-bust target is forced to NONE so the marker path stays out
    # of the way (this test is about the limiter, not cache busting).
    user_config = SimpleNamespace(
        input=SimpleNamespace(
            use_end_to_start_delays=enabled,
            prompt=SimpleNamespace(
                cache_bust=SimpleNamespace(target=CacheBustTarget.NONE)
            ),
        ),
        loadgen=SimpleNamespace(
            burst_phase_starts=False, trace_idle_gap_cap_seconds=None
        ),
        benchmark_id="test-bench",
    )
    cfg = MagicMock()
    cfg.phase = CreditPhase.PROFILING
    cfg.concurrency = 1
    strategy = AgenticReplayStrategy(
        config=cfg,
        conversation_source=src,
        scheduler=scheduler,
        stop_checker=MagicMock(),
        credit_issuer=issuer,
        lifecycle=MagicMock(),
        user_config=user_config,
        branch_orchestrator=AsyncMock(),
    )
    return strategy, tasks


class _HoldingIssuer:
    """Fake CreditIssuer that holds every send on the wire until released.

    Tracks the max simultaneous in-flight sends so the test can assert the inner
    limiter capped concurrency. ``refuse_first`` forces one send off the wire
    (returns False) to exercise the refusal-release path.
    """

    def __init__(self, *, refuse_first: bool = False) -> None:
        self._gate = asyncio.Event()
        self.in_flight = 0
        self.max_in_flight = 0
        self.total_started = 0
        # Per-wire-path counts so a test can assert subagent streams went through
        # the CHILD path (dispatch_child_turn), not the root path (issue_credit).
        self.root_sends = 0
        self.child_sends = 0
        self._refuse_first = refuse_first

    async def _send(self, turn) -> bool:
        self.total_started += 1
        if self._refuse_first:
            self._refuse_first = False
            return False  # refused: never goes on the wire
        self.in_flight += 1
        self.max_in_flight = max(self.max_in_flight, self.in_flight)
        await self._gate.wait()
        self.in_flight -= 1
        return True

    async def issue_credit(self, turn) -> bool:
        self.root_sends += 1
        return await self._send(turn)

    async def dispatch_child_turn(self, turn) -> bool:
        self.child_sends += 1
        return await self._send(turn)

    def acquire_lane_credit(self, *args, **kwargs):
        async def _noop() -> None:
            return None

        return _noop()

    def release(self) -> None:
        self._gate.set()


async def _pump(n: int) -> None:
    for _ in range(n):
        await asyncio.sleep(0)


def _final_child_credit(x_correlation_id: str, turn_index: int) -> Credit:
    """A final-turn child credit return for an on-wire send (frees its slot)."""
    return Credit(
        id=0,
        phase=CreditPhase.PROFILING,
        conversation_id="trace_0",
        x_correlation_id=x_correlation_id,
        turn_index=turn_index,
        num_turns=turn_index + 1,  # is_final_turn
        issued_at_ns=0,
        agent_depth=1,
        parent_correlation_id=_ROOT_CORR,
        root_correlation_id=_ROOT_CORR,
        branch_mode=ConversationBranchMode.SPAWN,
    )


@pytest.mark.asyncio
async def test_inner_limit_caps_concurrency_at_peak_when_enabled():
    """Gating ON: 3 streams, post-t* peak 2 -> at most 2 in flight; 3rd queues."""
    issuer = _HoldingIssuer()
    strategy, tasks = _make_strategy(enabled=True, issuer=issuer)

    assert strategy._inner_limit_enabled is True
    await strategy.setup_phase()
    await strategy.execute_phase()  # schedules 3 concurrent dispatch tasks

    # Let the three dispatch tasks reach the chokepoint and the gate.
    await _pump(12)

    # peak_for == 2, so the limiter opened the tree at 2: exactly 2 sends got on
    # the wire, the 3rd is queued on the semaphore.
    assert (
        strategy.conversation_source.peak_for(
            strategy.conversation_source.trajectories[0]
        )
        == 2
    )
    assert issuer.max_in_flight == 2
    assert issuer.in_flight == 2
    assert strategy._limiter.in_flight(_ROOT_CORR) == 2
    assert strategy._limiter.queued(_ROOT_CORR) == 1
    # The snapshot RESUME dispatches each post-t* stream via issue_credit (the
    # root wire path, is_child=False) -- even background subagents (agent_depth=1)
    # -- because at t* these are pre-existing streams being resumed, not children
    # freshly spawned by a parent's turn completion. (The runtime child-spawn path
    # via dispatch_child_turn is gated too and is covered by the child-refusal
    # test.) Lock that dispatch shape so a routing refactor is caught: the 2
    # on-wire sends went root-path; the 3rd is still queued at the limiter acquire
    # and has not reached either wire method yet.
    assert (issuer.child_sends, issuer.root_sends) == (0, 2)

    # Free the gate so the two on-wire sends complete, then return their credits
    # (the on-wire release path) so each frees its semaphore slot -- the queued
    # 3rd send then acquires and reaches the wire. The two slots cap the whole
    # drain: max_in_flight must stay 2 even as the 3rd proceeds.
    issuer.release()
    await _pump(8)
    on_wire_keys = list(strategy._release_tokens.keys())
    assert len(on_wire_keys) == 2
    for xc, idx in on_wire_keys:
        await strategy.handle_credit_return(_final_child_credit(xc, idx))
    await asyncio.wait_for(asyncio.gather(*tasks), timeout=5.0)
    assert issuer.total_started == 3
    assert issuer.max_in_flight == 2, "limiter must never have exceeded the peak"
    # The formerly-queued 3rd subagent also resumed via the root wire path.
    assert (issuer.child_sends, issuer.root_sends) == (0, 3)


@pytest.mark.asyncio
async def test_inner_limit_disabled_lets_all_streams_fire():
    """Gating OFF (default): no cap -- all 3 streams reach the wire at once."""
    issuer = _HoldingIssuer()
    strategy, tasks = _make_strategy(enabled=False, issuer=issuer)

    assert strategy._inner_limit_enabled is False
    await strategy.setup_phase()
    await strategy.execute_phase()
    await _pump(12)

    # No limiter engaged -> all three sends are on the wire simultaneously.
    assert issuer.max_in_flight == 3
    assert issuer.in_flight == 3
    # No tree was opened (pass-through), so the limiter knows nothing.
    assert strategy._limiter.in_flight(_ROOT_CORR) == 0
    assert not strategy._release_tokens

    issuer.release()
    await asyncio.wait_for(asyncio.gather(*tasks), timeout=5.0)


@pytest.mark.asyncio
async def test_inner_limit_refused_issue_releases_slot_no_leak():
    """A refused send (issuer returns False once) releases its slot immediately.

    The refusal happens before the wire, so no credit return ever fires for it.
    in_flight must return to the on-wire count (1 here: 2 acquired, 1 refused),
    proving the finally-guarded release ran and nothing leaked.
    """
    issuer = _HoldingIssuer(refuse_first=True)
    strategy, tasks = _make_strategy(enabled=True, issuer=issuer)

    await strategy.setup_phase()
    await strategy.execute_phase()
    await _pump(12)

    # 3 sends started: 1 refused (released its slot back in the finally) + 2 on
    # the wire (still holding their acquired slots). The refused slot did not
    # leak, so in_flight == 2 (not 3) and nothing is queued. The two on-wire
    # sends are still blocked inside the try, so no release token is parked yet
    # (the stash happens in the finally, after the send returns).
    assert issuer.total_started == 3
    assert strategy._limiter.in_flight(_ROOT_CORR) == 2
    assert strategy._limiter.queued(_ROOT_CORR) == 0
    assert strategy._release_tokens == {}

    issuer.release()
    await asyncio.wait_for(asyncio.gather(*tasks), timeout=5.0)
    # Now both on-wire sends returned True and parked their tokens; nothing
    # over-released. Returning their credits frees both slots: the semaphore is
    # back to full capacity, confirming the refused send leaked nothing.
    assert len(strategy._release_tokens) == 2
    for xc, idx in list(strategy._release_tokens.keys()):
        await strategy.handle_credit_return(_final_child_credit(xc, idx))
    assert strategy._limiter.in_flight(_ROOT_CORR) == 0
