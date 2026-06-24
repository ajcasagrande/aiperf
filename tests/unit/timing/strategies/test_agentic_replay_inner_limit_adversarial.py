# SPDX-FileCopyrightText: Copyright (c) 2025-2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Adversarial attacks on the AgenticReplayStrategy inner-session chokepoint.

Tries to BREAK ``_issue_gated`` and its release wiring (the inner-session
semaphore gate added behind ``--use-end-to-start-delays``). A real
``InnerSessionLimiter`` is used throughout (never mocked); only the
``CreditIssuer`` is a controllable fake that can hold a send "on the wire"
until the test releases it, refuse a send, or raise.

Sibling: ``test_agentic_replay_inner_limit.py`` covers the happy-path wiring
(cap holds at peak, default-off pass-through, single refusal release). This
file attacks the chokepoint's invariants directly:

- Cap holds at EXACTLY P: the (P+1)th send blocks; releasing one admits exactly
  one more; max in-flight never exceeds P even as the queue drains.
- A REFUSED issue (issuer returns False) releases the slot back to baseline,
  and for a CHILD the refusal->``on_child_stopped`` drain still fires.
- An issue that RAISES releases the slot in the ``finally`` (no leak); the
  exception still propagates.
- ``delay_ms`` path: a turn deferred via ``scheduler.schedule_later`` must NOT
  hold a semaphore slot during the think-time -- the acquire is inside the
  scheduled coro at send time, so in-flight is 0 while the coro is pending.
- Release on credit return is exactly once and idempotent: delivering the same
  ``(x_correlation_id, turn_index)`` twice releases the slot once, never
  inflating capacity above P.
- Token-stash key isolation across recycle: a recycled session reusing a
  trace_id but with a fresh x_correlation_id must not clobber a prior stash.
- DEFAULT-OFF byte-identity: with the gate off, N>P sends all fire, the limiter
  records zero acquires, and no token is stashed.

Out of scope: warmup spread/burst timing, cache-bust marker minting, rootless
lane recycle accounting -- those live in the sibling replay test modules.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from aiperf.common.enums import CacheBustTarget, ConversationBranchMode, CreditPhase
from aiperf.common.models import (
    ConversationMetadata,
    DatasetMetadata,
    TurnMetadata,
)
from aiperf.credit.structs import Credit, TurnToSend
from aiperf.plugin.enums import DatasetSamplingStrategy
from aiperf.timing.strategies.agentic_replay import AgenticReplayStrategy
from aiperf.timing.trajectory_source import (
    ConversationState,
    Trajectory,
    TrajectorySnapshot,
    TrajectorySource,
)

# ==========================================================================
# Helpers
# ==========================================================================

_ROOT_CORR = "tree-root"
_TRACE_ID = "trace_0"

# Four sibling subagent streams under one shared tree root. Their recorded busy
# spans all overlap on [100, 150], so session_achievable_peak == 4 -- giving us
# headroom to size the limiter DOWN to an arbitrary P via a peak override and
# attack "cap holds at exactly P" with P < number of streams.
_STREAMS = (
    ("trace_0::sa:a", "corr-a", 100.0, 100.0),
    ("trace_0::sa:b", "corr-b", 100.0, 100.0),
    ("trace_0::sa:c", "corr-c", 100.0, 100.0),
    ("trace_0::sa:d", "corr-d", 100.0, 100.0),
)


def _build_source(*, offset_ms: float = 1000.0) -> TrajectorySource:
    """Real TrajectorySource with one 4-stream snapshot trajectory (peak 4).

    Every stream is a background subagent (no dispatchable depth-0 root) so the
    lane dispatches them as children of the shared tree root. ``offset_ms`` sets
    each stream's ``next_dispatch_offset_ms``; a positive value routes the send
    through ``scheduler.schedule_later`` (the test owns what that scheduler does).
    """
    convs = [
        ConversationMetadata(
            conversation_id=cid,
            turns=[TurnMetadata(timestamp_ms=ts, api_time_ms=api)],
            is_root=False,
            agent_depth=1,
            parent_conversation_id=_TRACE_ID,
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
            next_dispatch_offset_ms=offset_ms,
            agent_depth=1,
            parent_correlation_id=_ROOT_CORR,
            root_correlation_id=_ROOT_CORR,
        )
        for cid, xc, _ts, _api in _STREAMS
    )
    trajectory = Trajectory(
        conversation_id=_TRACE_ID,
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
    *,
    enabled: bool,
    issuer: object,
    run_scheduled: bool = True,
    peak_override: int | None = None,
    source: TrajectorySource | None = None,
) -> tuple[AgenticReplayStrategy, list[asyncio.Task], list[Awaitable]]:
    """Build a PROFILING strategy.

    ``run_scheduled`` True: each ``schedule_later`` coro is launched as a
    concurrent task immediately (delay ignored) so deferred sends race at the
    chokepoint. False: the coro is captured into ``pending`` and NEVER started --
    used to assert no slot is held during a ``delay_ms`` think-time.

    ``peak_override`` forces ``source.peak_for`` to a fixed value so we can size
    the limiter below the stream count and attack the cap at an arbitrary P
    without crafting bespoke overlap intervals.
    """
    src = source if source is not None else _build_source()
    if peak_override is not None:
        src.peak_for = MagicMock(return_value=peak_override)  # type: ignore[method-assign]

    tasks: list[asyncio.Task] = []
    pending: list[Awaitable] = []

    def fake_schedule_later(_delay: float, coro: Awaitable) -> None:
        if run_scheduled:
            tasks.append(asyncio.ensure_future(coro))
        else:
            pending.append(coro)

    scheduler = MagicMock()
    scheduler.schedule_later.side_effect = fake_schedule_later

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
        benchmark_id="agentx-bench-7f2a",
    )
    cfg = MagicMock()
    cfg.phase = CreditPhase.PROFILING
    cfg.concurrency = 1
    # Recycle into a fresh root is out of scope here -- these tests probe the
    # gate, not the spawner -- so refuse new sessions: the rootless-lane drain
    # then releases its lane credit and stops instead of dispatching a turn-0
    # root through the chokepoint and reopening a tree mid-assertion.
    stop_checker = MagicMock()
    stop_checker.can_start_new_session.return_value = False
    strategy = AgenticReplayStrategy(
        config=cfg,
        conversation_source=src,
        scheduler=scheduler,
        stop_checker=stop_checker,
        credit_issuer=issuer,
        lifecycle=MagicMock(),
        user_config=user_config,
        branch_orchestrator=AsyncMock(),
    )
    return strategy, tasks, pending


async def _pump(n: int) -> None:
    """Yield ``n`` times so chained ``await asyncio.sleep(0)`` continuations run."""
    for _ in range(n):
        await asyncio.sleep(0)


def _final_child_credit(x_correlation_id: str, turn_index: int) -> Credit:
    """A final-turn child credit return for an on-wire send (frees its slot)."""
    return Credit(
        id=0,
        phase=CreditPhase.PROFILING,
        conversation_id=_TRACE_ID,
        x_correlation_id=x_correlation_id,
        turn_index=turn_index,
        num_turns=turn_index + 1,  # is_final_turn
        issued_at_ns=0,
        agent_depth=1,
        parent_correlation_id=_ROOT_CORR,
        root_correlation_id=_ROOT_CORR,
        branch_mode=ConversationBranchMode.SPAWN,
    )


class _HoldingIssuer:
    """Fake CreditIssuer that holds every send on the wire until released.

    Tracks max simultaneous in-flight sends so a test can assert the inner
    limiter capped concurrency. The ``behavior`` callback, when set, is
    consulted per send (by send ordinal, 1-based) and may return ``"refuse"``
    (off-wire False), ``"raise"`` (raise RuntimeError), or ``None`` (normal
    on-wire send that blocks on the gate).
    """

    def __init__(self, *, behavior: Callable[[int], str | None] | None = None) -> None:
        self._gate = asyncio.Event()
        self.in_flight = 0
        self.max_in_flight = 0
        self.total_started = 0
        self._behavior = behavior

    async def _send(self, turn: TurnToSend) -> bool:
        self.total_started += 1
        verdict = self._behavior(self.total_started) if self._behavior else None
        if verdict == "refuse":
            return False
        if verdict == "raise":
            raise RuntimeError(f"issuer blew up on send #{self.total_started}")
        self.in_flight += 1
        self.max_in_flight = max(self.max_in_flight, self.in_flight)
        await self._gate.wait()
        self.in_flight -= 1
        return True

    async def issue_credit(self, turn: TurnToSend) -> bool:
        return await self._send(turn)

    async def dispatch_child_turn(self, turn: TurnToSend) -> bool:
        return await self._send(turn)

    def acquire_lane_credit(self, *args: object, **kwargs: object) -> Awaitable[None]:
        async def _noop() -> None:
            return None

        return _noop()

    def release_lane_credit(self, *args: object, **kwargs: object) -> None:
        return None

    def release(self) -> None:
        self._gate.set()


# ==========================================================================
# Cap holds at exactly P
# ==========================================================================


class TestInnerLimitCapHoldsExactlyAtP:
    """The semaphore must admit exactly P, queue the rest, and release 1-for-1."""

    @pytest.mark.asyncio
    async def test_p_plus_one_blocks_and_releasing_one_admits_exactly_one_more(
        self,
    ) -> None:
        # Force peak P=2 over 4 streams: 2 on the wire, 2 queued on the semaphore.
        issuer = _HoldingIssuer()
        strategy, tasks, _ = _make_strategy(
            enabled=True, issuer=issuer, peak_override=2
        )
        await strategy.setup_phase()
        await strategy.execute_phase()
        await _pump(16)

        assert issuer.max_in_flight == 2, "more than P sends reached the wire"
        assert issuer.in_flight == 2
        assert strategy._limiter.in_flight(_ROOT_CORR) == 2
        assert strategy._limiter.queued(_ROOT_CORR) == 2

        # Return exactly ONE on-wire credit. That frees one slot; exactly one of
        # the two queued sends must acquire and reach the wire -- never two.
        issuer.release()
        await _pump(2)
        first_key = next(iter(strategy._release_tokens))
        await strategy.handle_credit_return(_final_child_credit(*first_key))
        await _pump(8)

        assert issuer.max_in_flight == 2, "releasing one slot admitted more than one"
        assert strategy._limiter.queued(_ROOT_CORR) == 1, (
            "exactly one queued send should remain"
        )

        # Drain the rest by returning every parked token; the gate is open so
        # each freshly admitted send completes and parks its own token.
        for _ in range(8):
            keys = list(strategy._release_tokens.keys())
            if not keys:
                break
            for key in keys:
                await strategy.handle_credit_return(_final_child_credit(*key))
            await _pump(4)
        await asyncio.wait_for(asyncio.gather(*tasks), timeout=5.0)

        assert issuer.total_started == 4
        assert issuer.max_in_flight == 2, "limiter exceeded P at some point"
        assert strategy._limiter.in_flight(_ROOT_CORR) == 0
        assert strategy._limiter.queued(_ROOT_CORR) == 0


# ==========================================================================
# Refusal releases the slot (and preserves child drain)
# ==========================================================================


class TestInnerLimitRefusalReleasesSlot:
    """A refused send frees its slot and, for a child, still drains the parent."""

    @pytest.mark.asyncio
    async def test_all_refused_returns_in_flight_to_baseline_zero(self) -> None:
        # Every send refused: none goes on the wire, every acquired slot must be
        # released in the finally. in_flight must settle at 0, nothing queued,
        # nothing stashed.
        issuer = _HoldingIssuer(behavior=lambda _n: "refuse")
        strategy, tasks, _ = _make_strategy(
            enabled=True, issuer=issuer, peak_override=2
        )
        await strategy.setup_phase()
        await strategy.execute_phase()
        await asyncio.wait_for(asyncio.gather(*tasks), timeout=5.0)

        assert issuer.total_started == 4
        assert strategy._limiter.in_flight(_ROOT_CORR) == 0, "refused slot leaked"
        assert strategy._limiter.queued(_ROOT_CORR) == 0
        assert strategy._release_tokens == {}

    @pytest.mark.asyncio
    async def test_child_refusal_releases_slot_and_fires_on_child_stopped(
        self,
    ) -> None:
        # A child continuation refused at the wire must (a) release its slot and
        # (b) still notify the orchestrator so the parent's join drains. Drive
        # the single child chokepoint directly so the refusal->drain edge is
        # isolated from the snapshot fan-out.
        issuer = _HoldingIssuer(behavior=lambda _n: "refuse")
        strategy, _tasks, _ = _make_strategy(
            enabled=True, issuer=issuer, peak_override=2
        )
        strategy._limiter.open_tree(_ROOT_CORR, 2)

        turn = TurnToSend(
            conversation_id="trace_0::sa:a",
            x_correlation_id="corr-a",
            turn_index=1,
            num_turns=3,
            agent_depth=1,
            parent_correlation_id=_ROOT_CORR,
            root_correlation_id=_ROOT_CORR,
            branch_mode=ConversationBranchMode.SPAWN,
        )
        await strategy._issue_child_continuation_or_drain(turn)

        strategy.branch_orchestrator.on_child_stopped.assert_awaited_once_with("corr-a")
        assert strategy._limiter.in_flight(_ROOT_CORR) == 0, "refused child leaked slot"
        assert strategy._release_tokens == {}


# ==========================================================================
# Raising send releases the slot in finally
# ==========================================================================


class TestInnerLimitRaisingSendReleasesSlot:
    """An exception from the issuer must not strand a held slot."""

    @pytest.mark.asyncio
    async def test_raise_releases_slot_and_propagates(self) -> None:
        issuer = _HoldingIssuer(behavior=lambda _n: "raise")
        strategy, _tasks, _ = _make_strategy(
            enabled=True, issuer=issuer, peak_override=2
        )
        strategy._limiter.open_tree(_ROOT_CORR, 2)

        turn = TurnToSend(
            conversation_id=_TRACE_ID,
            x_correlation_id="corr-root",
            turn_index=0,
            num_turns=2,
            root_correlation_id=_ROOT_CORR,
        )
        with pytest.raises(RuntimeError, match=r"issuer blew up on send #1"):
            await strategy._issue_gated(turn, _ROOT_CORR, is_child=False)

        assert strategy._limiter.in_flight(_ROOT_CORR) == 0, (
            "raising send did not release its slot in the finally"
        )
        assert strategy._release_tokens == {}, "a raised send must not stash a token"


# ==========================================================================
# delay_ms path holds no slot during think-time
# ==========================================================================


class TestInnerLimitDelayHoldsNoSlot:
    """A deferred (think-time) send must acquire only at send time, not before."""

    @pytest.mark.asyncio
    async def test_pending_scheduled_send_holds_zero_slots(self) -> None:
        # All streams have a positive next_dispatch_offset_ms, so every send is
        # handed to schedule_later. With run_scheduled=False the coros are
        # captured but never started. If the acquire happened at scheduling time
        # (a bug), in_flight would be > 0 while the coros sit idle.
        issuer = _HoldingIssuer()
        strategy, _tasks, pending = _make_strategy(
            enabled=True,
            issuer=issuer,
            run_scheduled=False,
            peak_override=2,
        )
        await strategy.setup_phase()
        await strategy.execute_phase()
        await _pump(8)

        assert len(pending) == 4, "every stream should have been deferred"
        assert issuer.total_started == 0, "no send fired during think-time"
        assert strategy._limiter.in_flight(_ROOT_CORR) == 0, (
            "a semaphore slot is held while the deferred send is still pending"
        )
        assert strategy._limiter.queued(_ROOT_CORR) == 0

        # Now run the deferred coros: the acquire happens here, at send time.
        run = [asyncio.ensure_future(c) for c in pending]
        await _pump(12)
        assert issuer.in_flight == 2, "send-time acquire should now hold P slots"

        # Drain: open the gate, return parked tokens to free slots so the two
        # still-queued sends acquire and complete. Cancel any stragglers so the
        # test never hangs on the (intentionally) capped queue.
        issuer.release()
        for _ in range(8):
            keys = list(strategy._release_tokens.keys())
            if not keys:
                break
            for key in keys:
                await strategy.handle_credit_return(_final_child_credit(*key))
            await _pump(4)
        for task in run:
            task.cancel()
        await asyncio.gather(*run, return_exceptions=True)


# ==========================================================================
# Release on credit return is exactly once / idempotent
# ==========================================================================


class TestInnerLimitReleaseIdempotent:
    """A duplicate credit return must release the slot once -- never inflate P."""

    @pytest.mark.asyncio
    async def test_duplicate_credit_return_releases_slot_once(self) -> None:
        issuer = _HoldingIssuer()
        strategy, tasks, _ = _make_strategy(
            enabled=True, issuer=issuer, peak_override=2
        )
        await strategy.setup_phase()
        await strategy.execute_phase()
        await _pump(16)

        issuer.release()
        await _pump(2)
        key = next(iter(strategy._release_tokens))

        # First return frees the slot and admits a queued send.
        await strategy.handle_credit_return(_final_child_credit(*key))
        await _pump(4)
        in_flight_after_first = strategy._limiter.in_flight(_ROOT_CORR)

        # Duplicate return for the SAME (x_correlation_id, turn_index): the token
        # is already popped + released, so this must be a no-op. If it
        # over-released, in_flight would drop below the post-admit count and a
        # spurious extra slot would open (max_in_flight could exceed P).
        await strategy.handle_credit_return(_final_child_credit(*key))
        await _pump(8)

        assert strategy._limiter.in_flight(_ROOT_CORR) <= 2
        assert in_flight_after_first <= 2
        # Drain remaining and confirm the cap was never breached.
        for _ in range(8):
            keys = list(strategy._release_tokens.keys())
            if not keys:
                break
            for k in keys:
                await strategy.handle_credit_return(_final_child_credit(*k))
            await _pump(4)
        await asyncio.wait_for(asyncio.gather(*tasks), timeout=5.0)
        assert issuer.max_in_flight == 2, "duplicate return inflated capacity above P"
        assert strategy._limiter.in_flight(_ROOT_CORR) == 0


# ==========================================================================
# Token stash key isolation across recycle
# ==========================================================================


class TestInnerLimitStashKeyIsolation:
    """Stash keyed by (x_correlation_id, turn_index) must not collide on reuse."""

    @pytest.mark.asyncio
    async def test_recycled_session_same_trace_fresh_corr_does_not_clobber(
        self,
    ) -> None:
        # A recycled session reuses trace_id but draws a fresh x_correlation_id.
        # The stash key includes the correlation id, so an on-wire send from the
        # recycled session at the same turn_index as a live one must occupy a
        # DISTINCT slot in _release_tokens -- never overwrite the live entry.
        issuer = _HoldingIssuer()
        strategy, _tasks, _ = _make_strategy(
            enabled=True, issuer=issuer, peak_override=4
        )
        strategy._limiter.open_tree(_ROOT_CORR, 4)

        live_turn = TurnToSend(
            conversation_id=_TRACE_ID,
            x_correlation_id="corr-live",
            turn_index=2,
            num_turns=5,
            root_correlation_id=_ROOT_CORR,
        )
        recycled_turn = TurnToSend(
            conversation_id=_TRACE_ID,  # SAME trace
            x_correlation_id="corr-recycled-fresh",  # FRESH correlation id
            turn_index=2,  # SAME turn index as the live one
            num_turns=5,
            root_correlation_id=_ROOT_CORR,
        )
        live = asyncio.ensure_future(
            strategy._issue_gated(live_turn, _ROOT_CORR, is_child=False)
        )
        recycled = asyncio.ensure_future(
            strategy._issue_gated(recycled_turn, _ROOT_CORR, is_child=False)
        )
        await _pump(6)
        assert issuer.in_flight == 2

        issuer.release()
        await asyncio.wait_for(asyncio.gather(live, recycled), timeout=5.0)

        # Two distinct stash entries -- the fresh correlation id did not clobber.
        assert ("corr-live", 2) in strategy._release_tokens
        assert ("corr-recycled-fresh", 2) in strategy._release_tokens
        assert len(strategy._release_tokens) == 2

        # Returning the recycled credit must release ONLY its own slot, leaving
        # the live one parked and its slot still held.
        await strategy.handle_credit_return(
            _final_child_credit("corr-recycled-fresh", 2)
        )
        assert ("corr-live", 2) in strategy._release_tokens
        assert strategy._limiter.in_flight(_ROOT_CORR) == 1
        issuer.release()
        await strategy.handle_credit_return(_final_child_credit("corr-live", 2))
        assert strategy._limiter.in_flight(_ROOT_CORR) == 0


# ==========================================================================
# Default-off byte-identity
# ==========================================================================


class TestInnerLimitDefaultOffByteIdentity:
    """Gate off: N>P sends all fire, zero limiter acquires, zero stash."""

    @pytest.mark.asyncio
    async def test_disabled_fires_all_streams_with_no_limiter_touch(self) -> None:
        # peak_override=2 would cap to 2 IF the gate engaged. Disabled, all 4
        # must reach the wire and the limiter must record nothing.
        issuer = _HoldingIssuer()
        strategy, tasks, _ = _make_strategy(
            enabled=False, issuer=issuer, peak_override=2
        )
        assert strategy._inner_limit_enabled is False

        await strategy.setup_phase()
        await strategy.execute_phase()
        await _pump(16)

        assert issuer.max_in_flight == 4, "gate-off must not cap concurrency"
        assert issuer.in_flight == 4
        assert strategy._limiter.in_flight(_ROOT_CORR) == 0, "limiter was touched"
        assert strategy._limiter.queued(_ROOT_CORR) == 0
        assert not strategy._release_tokens, "no token may be stashed when gate is off"

        issuer.release()
        await asyncio.wait_for(asyncio.gather(*tasks), timeout=5.0)

    @pytest.mark.asyncio
    async def test_disabled_credit_return_does_not_touch_limiter(self) -> None:
        # A credit return while gating is off must not call into the limiter at
        # all (the release block is guarded by _inner_limit_enabled). We assert
        # the observable: no token is ever popped/parked and in_flight stays 0.
        issuer = _HoldingIssuer()
        strategy, tasks, _ = _make_strategy(
            enabled=False, issuer=issuer, peak_override=2
        )
        await strategy.setup_phase()
        await strategy.execute_phase()
        await _pump(8)
        issuer.release()
        await asyncio.wait_for(asyncio.gather(*tasks), timeout=5.0)

        await strategy.handle_credit_return(_final_child_credit("corr-a", 0))
        assert strategy._limiter.in_flight(_ROOT_CORR) == 0
        assert strategy._release_tokens == {}
