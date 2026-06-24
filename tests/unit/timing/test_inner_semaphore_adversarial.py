# SPDX-FileCopyrightText: Copyright (c) 2025-2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Adversarial async tests for the weka inner-session concurrency limiter.

Targets the two primitives that gate agentic-replay inner-session concurrency:

- ``InnerSessionLimiter`` (``src/aiperf/timing/inner_semaphore.py``): one
  ``asyncio.Semaphore(max(1, peak))`` per session tree, with ``in_flight`` /
  ``queued`` accounting and an idempotent ``release`` that must never inflate the
  semaphore's capacity.
- ``SessionTreeRegistry.note_queued`` and ``_TreeState.drained``
  (``src/aiperf/timing/session_tree.py``): queued-work accounting that holds a
  tree open while requests sit ready-but-queued on the inner semaphore.

The attacks here try to BREAK the limiter rather than document the happy path
(which ``test_inner_semaphore.py`` / ``test_session_tree.py`` already cover):

- Cancellation of a blocked waiter: ``queued`` must unwind via ``finally`` and
  ``in_flight`` must NOT increment; the freed slot must remain acquirable.
- Cancellation storms: cancelling half of N waiters leaves exactly the right
  number of survivors able to make progress, with non-negative counters.
- Over-release (double / triple) never raises and never inflates capacity.
- Release after ``close_tree`` is a no-op (no exception, no negative count).
- ``open_tree`` on an already-open tree -- characterizes the live-replace
  behavior (orphans in-flight tokens; this is the documented concern).
- P==1 strict serialization and FIFO-ish hand-off.
- Many independent trees: no cross-tree capacity bleed.
- ``acquire("unknown")`` -> ``None``; ``release(None)`` no-op.

Out of scope: the higher-level wiring (CreditIssuer / BranchOrchestrator) and
the drain-callback recycle path -- those live in ``test_session_tree.py``.
"""

from __future__ import annotations

import asyncio

import pytest

from aiperf.common.enums import CreditPhase
from aiperf.timing.inner_semaphore import InnerSessionLimiter
from aiperf.timing.session_tree import SessionTreeRegistry

# ============================================================================
# Helpers
# ============================================================================


class _FakeConcurrencyManager:
    """Records ``release_session_slot`` calls per phase.

    Mirrors the fake in ``test_session_tree.py`` so the registry's release
    decision can be observed without a real concurrency manager / semaphore.
    """

    def __init__(self) -> None:
        self.released: list[CreditPhase] = []

    def release_session_slot(self, phase: CreditPhase) -> None:
        self.released.append(phase)


async def _spin(times: int = 3) -> None:
    """Yield the event loop ``times`` times so scheduled waiters can settle.

    A single ``await asyncio.sleep(0)`` only advances one scheduling step; a
    cancellation that re-releases a semaphore slot needs an extra turn for the
    next blocked waiter to wake. Spinning a few times drains those follow-ons
    deterministically (the ``no_sleep`` auto-fixture makes each instant).
    """
    for _ in range(times):
        await asyncio.sleep(0)


PROFILING = CreditPhase.PROFILING


# ============================================================================
# Cancellation of a blocked waiter
# ============================================================================


class TestInnerSessionLimiterCancellation:
    """A waiter cancelled while blocked in ``acquire`` must leave the limiter
    in a consistent state: queued unwound, in_flight untouched, slot reusable."""

    @pytest.mark.asyncio
    async def test_cancel_blocked_waiter_unwinds_queued_and_leaves_in_flight(
        self,
    ) -> None:
        lim = InnerSessionLimiter()
        lim.open_tree("tree-root-7f2a", 1)
        held = await lim.acquire("tree-root-7f2a")
        assert lim.in_flight("tree-root-7f2a") == 1

        waiter = asyncio.ensure_future(lim.acquire("tree-root-7f2a"))
        await _spin()
        assert lim.queued("tree-root-7f2a") == 1  # blocked behind the held slot

        waiter.cancel()
        with pytest.raises(asyncio.CancelledError):
            await waiter

        # finally: ran -> queued unwound; the cancelled waiter never reached
        # the post-acquire in_flight += 1, so in_flight stays at the holder's 1.
        assert lim.queued("tree-root-7f2a") == 0
        assert lim.in_flight("tree-root-7f2a") == 1
        assert held is not None

    @pytest.mark.asyncio
    async def test_freed_slot_after_cancel_is_acquirable_by_another_waiter(
        self,
    ) -> None:
        """Cancelling one waiter must not consume the capacity it never got: a
        second waiter must still be able to take the slot the holder releases."""
        lim = InnerSessionLimiter()
        lim.open_tree("tree-root-7f2a", 1)
        held = await lim.acquire("tree-root-7f2a")

        cancelled = asyncio.ensure_future(lim.acquire("tree-root-7f2a"))
        survivor = asyncio.ensure_future(lim.acquire("tree-root-7f2a"))
        await _spin()
        assert lim.queued("tree-root-7f2a") == 2

        cancelled.cancel()
        with pytest.raises(asyncio.CancelledError):
            await cancelled
        await _spin()
        assert lim.queued("tree-root-7f2a") == 1  # only the survivor remains

        lim.release(held)
        token = await asyncio.wait_for(survivor, timeout=1)
        assert token is not None
        assert lim.in_flight("tree-root-7f2a") == 1

    @pytest.mark.asyncio
    async def test_cancellation_storm_half_cancelled_rest_progress(self) -> None:
        """N waiters on a P=2 tree; cancel half. The remaining waiters must
        drain the freed capacity, counters never go negative, and every
        survivor eventually acquires exactly one real slot with no slot lost."""
        peak = 2
        lim = InnerSessionLimiter()
        lim.open_tree("tree-root-storm", peak)

        # Fill capacity, then pile up a crowd of blocked waiters. Each survivor
        # holds its slot only until the next event-loop turn, then releases --
        # so freed capacity cascades to the rest deterministically.
        holders = [await lim.acquire("tree-root-storm") for _ in range(peak)]
        assert lim.in_flight("tree-root-storm") == peak

        acquired: list[int] = []

        async def survivor_worker(idx: int) -> None:
            tok = await lim.acquire("tree-root-storm")
            acquired.append(idx)
            assert tok is not None
            # Holding never exceeds peak at the moment of acquire.
            assert 0 < lim.in_flight("tree-root-storm") <= peak
            await asyncio.sleep(0)
            lim.release(tok)

        n_waiters = 10
        cancelled = [
            asyncio.ensure_future(lim.acquire("tree-root-storm"))
            for _ in range(n_waiters // 2)
        ]
        survivors = [
            asyncio.ensure_future(survivor_worker(i)) for i in range(n_waiters // 2)
        ]
        await _spin()
        assert lim.queued("tree-root-storm") == n_waiters

        for w in cancelled:
            w.cancel()
        for w in cancelled:
            with pytest.raises(asyncio.CancelledError):
                await w
        await _spin()
        # Only the survivors remain queued; in_flight still pinned by holders.
        assert lim.queued("tree-root-storm") == len(survivors)
        assert lim.in_flight("tree-root-storm") == peak
        assert lim.queued("tree-root-storm") >= 0

        # Release the original holders; survivors cascade through the slots.
        for tok in holders:
            lim.release(tok)
        await asyncio.gather(*survivors)

        # No slot lost: every survivor acquired exactly once, all released.
        assert sorted(acquired) == list(range(len(survivors)))
        assert lim.in_flight("tree-root-storm") == 0
        assert lim.queued("tree-root-storm") == 0


# ============================================================================
# Over-release: double / triple release never inflates capacity
# ============================================================================


class TestInnerSessionLimiterOverRelease:
    """Releasing a token more than once -- or releasing every token then one
    more -- must never push the semaphore above its configured peak."""

    @pytest.mark.asyncio
    async def test_triple_release_single_token_does_not_inflate_capacity(
        self,
    ) -> None:
        lim = InnerSessionLimiter()
        lim.open_tree("tree-root-1", 1)
        tok = await lim.acquire("tree-root-1")
        lim.release(tok)
        lim.release(tok)
        lim.release(tok)
        assert lim.in_flight("tree-root-1") == 0

        # Capacity is still exactly 1: one acquire succeeds, the next blocks.
        first = await lim.acquire("tree-root-1")
        assert first is not None
        blocked = asyncio.ensure_future(lim.acquire("tree-root-1"))
        await _spin()
        assert not blocked.done()  # P+1 must still block, not inflate to 2
        blocked.cancel()
        with pytest.raises(asyncio.CancelledError):
            await blocked

    @pytest.mark.asyncio
    async def test_release_all_then_extra_release_keeps_peak_capacity(self) -> None:
        """Acquire P tokens, release all P, then release them AGAIN. Acquiring
        P succeeds but the (P+1)-th must still block -- capacity is exactly P."""
        peak = 3
        lim = InnerSessionLimiter()
        lim.open_tree("tree-root-cap", peak)
        tokens = [await lim.acquire("tree-root-cap") for _ in range(peak)]
        for tok in tokens:
            lim.release(tok)
        # Over-release storm: every token released a second time.
        for tok in tokens:
            lim.release(tok)
        assert lim.in_flight("tree-root-cap") == 0

        refilled = [await lim.acquire("tree-root-cap") for _ in range(peak)]
        assert lim.in_flight("tree-root-cap") == peak
        overflow = asyncio.ensure_future(lim.acquire("tree-root-cap"))
        await _spin()
        assert not overflow.done()  # capacity NOT inflated by the extra releases
        overflow.cancel()
        with pytest.raises(asyncio.CancelledError):
            await overflow
        for tok in refilled:
            lim.release(tok)
        assert lim.in_flight("tree-root-cap") == 0


# ============================================================================
# Release against a closed / recycled tree
# ============================================================================


class TestInnerSessionLimiterClosedTree:
    """``close_tree`` discards the limiter; a late ``release`` of a token whose
    tree is gone must be a silent no-op (no KeyError, no negative count)."""

    @pytest.mark.asyncio
    async def test_release_after_close_tree_is_noop(self) -> None:
        lim = InnerSessionLimiter()
        lim.open_tree("tree-root-recycle", 2)
        tok = await lim.acquire("tree-root-recycle")
        lim.close_tree("tree-root-recycle")

        # Tree gone: accessors report zero, and the late release drops cleanly.
        assert lim.in_flight("tree-root-recycle") == 0
        assert lim.queued("tree-root-recycle") == 0
        lim.release(tok)  # must not raise
        assert lim.in_flight("tree-root-recycle") == 0

    @pytest.mark.asyncio
    async def test_close_tree_then_reopen_starts_fresh_capacity(self) -> None:
        """Close then reopen the same root: the new tree has its own fresh
        semaphore and zeroed accounting, untouched by the old tree's tokens.

        Guaranteed by per-open generation stamping: the stale token carries the
        prior generation, so release ignores it instead of crediting the new
        tree's semaphore (no capacity inflation across recycle)."""
        lim = InnerSessionLimiter()
        lim.open_tree("tree-root-x", 1)
        stale = await lim.acquire("tree-root-x")
        lim.close_tree("tree-root-x")

        lim.open_tree("tree-root-x", 1)
        assert lim.in_flight("tree-root-x") == 0
        fresh = await lim.acquire("tree-root-x")
        assert fresh is not None
        assert lim.in_flight("tree-root-x") == 1

        # Releasing the stale token from the closed generation must not credit
        # the fresh tree's semaphore (no capacity inflation across recycle).
        lim.release(stale)
        assert lim.in_flight("tree-root-x") == 1
        overflow = asyncio.ensure_future(lim.acquire("tree-root-x"))
        await _spin()
        assert not overflow.done()
        overflow.cancel()
        with pytest.raises(asyncio.CancelledError):
            await overflow


# ============================================================================
# open_tree on an already-open tree (characterization)
# ============================================================================


class TestInnerSessionLimiterReopenLive:
    """``open_tree`` installs a fresh ``_TreeLimiter`` with a NEW generation.
    Calling it on a STILL-LIVE tree replaces the semaphore and zeroes
    in_flight/queued, but the prior generation's tokens are stamped with the old
    generation, so releasing them is ignored -- in_flight can never go negative."""

    @pytest.mark.asyncio
    async def test_reopen_live_tree_resets_in_flight_to_zero(self) -> None:
        lim = InnerSessionLimiter()
        lim.open_tree("tree-root-dup", 2)
        tok_a = await lim.acquire("tree-root-dup")
        tok_b = await lim.acquire("tree-root-dup")
        assert lim.in_flight("tree-root-dup") == 2

        # Re-open the live tree: a fresh semaphore + new generation; accounting
        # zeroes and the prior generation's tokens are now stale.
        lim.open_tree("tree-root-dup", 2)
        assert lim.in_flight("tree-root-dup") == 0
        assert lim.queued("tree-root-dup") == 0

        # Releasing an orphaned (prior-generation) token is a no-op: generation
        # mismatch is ignored, so in_flight never goes negative.
        lim.release(tok_a)
        assert lim.in_flight("tree-root-dup") == 0
        lim.release(tok_b)
        assert lim.in_flight("tree-root-dup") == 0


# ============================================================================
# P==1 strict serialization and FIFO-ish hand-off
# ============================================================================


class TestInnerSessionLimiterSerialization:
    """A P==1 tree must let exactly one acquirer hold at a time; releases hand
    off to waiters in roughly FIFO order (asyncio.Semaphore is FIFO)."""

    @pytest.mark.asyncio
    async def test_p1_serializes_three_acquirers_one_holder_at_a_time(self) -> None:
        lim = InnerSessionLimiter()
        lim.open_tree("tree-root-serial", 1)

        order: list[int] = []

        async def worker(idx: int) -> None:
            tok = await lim.acquire("tree-root-serial")
            order.append(idx)
            # Exactly one holder at any instant under P==1.
            assert lim.in_flight("tree-root-serial") == 1
            await asyncio.sleep(0)
            lim.release(tok)

        tasks = [asyncio.ensure_future(worker(i)) for i in range(3)]
        await asyncio.gather(*tasks)

        assert order == [0, 1, 2]  # FIFO hand-off
        assert lim.in_flight("tree-root-serial") == 0
        assert lim.queued("tree-root-serial") == 0


# ============================================================================
# Many independent trees: no cross-tree capacity bleed
# ============================================================================


class TestInnerSessionLimiterMultiTree:
    """Each tree owns an independent semaphore; saturating one must not block or
    credit another, and the unknown-tree path stays unbounded."""

    @pytest.mark.asyncio
    async def test_independent_caps_do_not_interfere(self) -> None:
        lim = InnerSessionLimiter()
        lim.open_tree("tree-a", 1)
        lim.open_tree("tree-b", 3)

        a_held = await lim.acquire("tree-a")
        assert lim.in_flight("tree-a") == 1

        # tree-a is saturated; tree-b must still grant all 3 of its slots.
        b_tokens = [await lim.acquire("tree-b") for _ in range(3)]
        assert lim.in_flight("tree-b") == 3
        assert lim.in_flight("tree-a") == 1  # untouched by tree-b activity

        # A second tree-a acquire blocks; tree-b is unaffected.
        a_blocked = asyncio.ensure_future(lim.acquire("tree-a"))
        await _spin()
        assert not a_blocked.done()
        assert lim.queued("tree-a") == 1
        assert lim.queued("tree-b") == 0

        lim.release(a_held)
        a_second = await asyncio.wait_for(a_blocked, timeout=1)
        assert a_second is not None
        for tok in b_tokens:
            lim.release(tok)
        lim.release(a_second)
        assert lim.in_flight("tree-a") == 0
        assert lim.in_flight("tree-b") == 0

    @pytest.mark.asyncio
    async def test_unknown_tree_acquire_returns_none_and_release_none_is_noop(
        self,
    ) -> None:
        lim = InnerSessionLimiter()
        lim.open_tree("known", 1)
        tok = await lim.acquire("never-opened")
        assert tok is None
        lim.release(None)  # no-op, must not raise
        lim.release(tok)  # token is None -> no-op
        # The real tree is unaffected by the unknown-tree traffic.
        real = await lim.acquire("known")
        assert real is not None
        assert lim.in_flight("known") == 1


# ============================================================================
# Counter non-negativity invariants under release/cancel orderings
# ============================================================================


class TestInnerSessionLimiterCounterInvariants:
    """Under the SUPPORTED usage (one release per acquired token, plus
    idempotent re-releases), in_flight and queued must never go negative."""

    @pytest.mark.asyncio
    async def test_interleaved_acquire_release_keeps_counts_non_negative(
        self,
    ) -> None:
        lim = InnerSessionLimiter()
        lim.open_tree("tree-root-mix", 2)

        tok1 = await lim.acquire("tree-root-mix")
        tok2 = await lim.acquire("tree-root-mix")
        lim.release(tok1)
        tok3 = await lim.acquire("tree-root-mix")
        lim.release(tok2)
        lim.release(tok2)  # idempotent
        lim.release(tok3)
        lim.release(tok1)  # idempotent

        assert lim.in_flight("tree-root-mix") == 0
        assert lim.in_flight("tree-root-mix") >= 0
        assert lim.queued("tree-root-mix") == 0
        assert lim.queued("tree-root-mix") >= 0


# ============================================================================
# SessionTreeRegistry.note_queued and drained predicate
# ============================================================================


class TestSessionTreeNoteQueued:
    """``note_queued`` is the bridge that lets the inner semaphore's queued work
    hold a tree open. Attack the accounting: negative totals, imbalance, unknown
    trees, and the precise queued -> 0 drain transition."""

    def test_note_queued_unknown_tree_returns_false(self) -> None:
        cm = _FakeConcurrencyManager()
        registry = SessionTreeRegistry(cm)
        assert registry.note_queued("ghost-root", +1) is False
        assert cm.released == []

    def test_note_queued_can_drive_running_total_negative(self) -> None:
        """``note_queued`` adds the delta unconditionally (no clamp). A lone -1
        drives queued to -1. This is a characterization: the contract relies on
        callers being balanced (+1 on acquire, -1 on settle), so an unbalanced
        -1 is a caller bug, but the registry does not defend against it.

        The hazard: queued == -1 makes ``drained`` (which checks ``queued == 0``)
        FALSE, so a stray -1 can WEDGE a tree open forever."""
        cm = _FakeConcurrencyManager()
        registry = SessionTreeRegistry(cm)
        registry.open_tree("root-neg", PROFILING, root_pending=False)

        # Unbalanced -1: queued goes to -1, tree does NOT drain (queued != 0).
        released = registry.note_queued("root-neg", -1)
        assert released is False
        assert cm.released == []

        # Even the root going terminal cannot drain it now: queued == -1 != 0.
        # (Wedged-open hazard documented.)
        assert registry.on_root_terminal("root-neg") is False
        assert cm.released == []

    def test_balanced_plus_n_minus_n_drains_only_on_return_to_zero(self) -> None:
        """+N then -N nets to zero; the tree drains exactly on the queued -> 0
        transition (with root already terminal and no outstanding)."""
        cm = _FakeConcurrencyManager()
        registry = SessionTreeRegistry(cm)
        registry.open_tree("root-bal", PROFILING, root_pending=False)

        registry.note_queued("root-bal", +3)
        assert registry.note_queued("root-bal", -1) is False  # queued 2
        assert registry.note_queued("root-bal", -1) is False  # queued 1
        assert cm.released == []
        # The final -1 brings queued to 0 -> drains and releases exactly once.
        assert registry.note_queued("root-bal", -1) is True
        assert cm.released == [PROFILING]
        assert registry.open_count() == 0

    def test_queued_holds_tree_open_with_root_done_and_outstanding_zero(
        self,
    ) -> None:
        """The interplay the queued field exists for: root_pending cleared AND
        outstanding == 0, but queued > 0 -> NOT drained. Only queued -> 0 drains."""
        cm = _FakeConcurrencyManager()
        registry = SessionTreeRegistry(cm)
        registry.open_tree("root-hold", PROFILING, root_pending=True)
        registry.register_descendants("root-hold", 1)
        registry.note_queued("root-hold", +1)

        # Root terminal: root_pending False, but outstanding=1, queued=1 -> held.
        assert registry.on_root_terminal("root-hold") is False
        # Descendant done: outstanding -> 0, but queued=1 still holds it.
        assert registry.on_descendant_done("root-hold") is False
        assert cm.released == []
        # Only the queued -> 0 transition finally drains.
        assert registry.note_queued("root-hold", -1) is True
        assert cm.released == [PROFILING]

    def test_drained_false_when_queued_positive_even_if_root_done(self) -> None:
        """Direct ``drained`` predicate probe: root done + outstanding 0 + queued
        positive must read NOT drained (the queued == 0 conjunct)."""
        cm = _FakeConcurrencyManager()
        registry = SessionTreeRegistry(cm)
        registry.open_tree("root-pred", PROFILING, root_pending=True)
        registry.note_queued("root-pred", +2)
        registry.on_root_terminal("root-pred")  # held by queued

        # Still tracked (not released) because queued > 0.
        assert registry.has_tree("root-pred") is True
        assert registry.open_count() == 1
        # Drain it explicitly to confirm the queued conjunct was the only hold.
        assert registry.note_queued("root-pred", -2) is True
        assert registry.has_tree("root-pred") is False
