# SPDX-FileCopyrightText: Copyright (c) 2025-2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Adversarial tests attacking the cache-bust "one prefix-cache domain per
trajectory tree" invariant in the weka agentic-replay path.

Invariant under attack: every spawned descendant of a trajectory tree must
carry the tree ROOT's cache-bust marker, so the whole tree is one server-side
prefix-cache domain. The root marker is deterministic:
``build_cache_bust_marker(benchmark_id, recycle_pass=0, trajectory_index=0,
base_trace_id(root), target)`` at the tree's primary instance (lane 0, pass 0).

Two production code paths enforce this:
- ``BranchOrchestrator._pre_session_tree_marker`` -- turn-0 pre-session
  (background) SPAWN children dispatched before the root session exists.
  Recently fixed: it previously keyed the digest on the CHILD conversation id,
  putting each background child in its own prefix-cache domain. These tests
  lock that the digest is on ``base_trace_id(root)``, not the child id.
- ``cache_bust.resolve_tree_marker`` -- per-tree mint keyed on
  ``root_correlation_id``, idempotent, collision-free across lanes/recycles.

Attack surfaces exercised here:
- Multiple pre-session branches/children under one root all share the root marker.
- Two distinct roots: children share their OWN root's marker; cross-root differ.
- ``cache_bust_target=NONE`` -> every marker is None (pre-session + per-turn).
- ``base_trace_id`` suffix stripping: ``::sa:``/``::fa:`` on the root id is
  stripped into the digest; a child whose own id carries a suffix never leaks
  into the root marker.
- ``resolve_tree_marker`` idempotency + cross-lane/recycle collision-freedom.
- Determinism: ``_pre_session_tree_marker(root)`` equals the lane-0/pass-0 mint.
- Documented limitation: a pre-session child binds to the root's lane-0 marker
  regardless of which lane the root's eventual primary instance lands on.

Out of scope (covered elsewhere): per-turn dispatch wiring and gate/join
bookkeeping -> ``tests/unit/timing/test_branch_orchestrator_pre_session.py``;
strategy-level minting -> agentic_replay strategy tests.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from pytest import param

from aiperf.common.enums import CacheBustTarget, ConversationBranchMode
from aiperf.common.models import (
    ConversationBranchInfo,
    ConversationMetadata,
    DatasetMetadata,
    TurnMetadata,
)
from aiperf.plugin.enums import DatasetSamplingStrategy
from aiperf.timing.branch_orchestrator import BranchOrchestrator
from aiperf.timing.strategies.cache_bust import (
    base_trace_id,
    build_cache_bust_marker,
    resolve_tree_marker,
)
from aiperf.timing.trajectory_source import CacheBustLedger

# ===========================================================================
# Helpers
# ===========================================================================

_BENCHMARK_ID = "aiperf-bench-7f2a"
_TARGETS_NON_NONE = [
    CacheBustTarget.SYSTEM_PREFIX,
    CacheBustTarget.SYSTEM_SUFFIX,
    CacheBustTarget.FIRST_TURN_PREFIX,
    CacheBustTarget.FIRST_TURN_SUFFIX,
]


def _root_marker(root_conversation_id: str, target: CacheBustTarget) -> str | None:
    """The canonical tree-root marker: lane-0, pass-0, digesting the stripped
    base trace id of the root. Every descendant must carry exactly this."""
    return build_cache_bust_marker(
        _BENCHMARK_ID,
        0,
        0,
        base_trace_id(root_conversation_id),
        target=target,
    )


def _mk_conv(
    cid: str,
    turns: list[TurnMetadata],
    branches: list[ConversationBranchInfo],
    agent_depth: int = 0,
) -> ConversationMetadata:
    return ConversationMetadata(
        conversation_id=cid,
        turns=turns,
        branches=branches,
        agent_depth=agent_depth,
    )


def _pre_branch(branch_id: str, child_ids: list[str]) -> ConversationBranchInfo:
    return ConversationBranchInfo(
        branch_id=branch_id,
        child_conversation_ids=child_ids,
        mode=ConversationBranchMode.SPAWN,
        is_background=True,
        dispatch_timing="pre",
    )


def _mk_source(conversations: list[ConversationMetadata]) -> MagicMock:
    """A conversation source whose ``start_pre_session_child`` captures the
    cache_bust_marker each pre-session child is dispatched with."""
    cs = MagicMock()
    cs.dataset_metadata = DatasetMetadata(
        conversations=conversations,
        sampling_strategy=DatasetSamplingStrategy.SEQUENTIAL,
    )
    cs.get_metadata.side_effect = lambda cid: next(
        c for c in conversations if c.conversation_id == cid
    )

    def _start_pre(child_cid, **kwargs):
        s = MagicMock()
        s.x_correlation_id = f"corr-{child_cid}"
        s.conversation_id = child_cid
        s.agent_depth = 1
        s.parent_correlation_id = None
        return s

    cs.start_pre_session_child = MagicMock(side_effect=_start_pre)
    return cs


def _markers_by_child(cs: MagicMock) -> dict[str, str | None]:
    """Map child_conversation_id -> the cache_bust_marker it was dispatched with."""
    out: dict[str, str | None] = {}
    for call in cs.start_pre_session_child.call_args_list:
        child_cid = call.args[0]
        out[child_cid] = call.kwargs["cache_bust_marker"]
    return out


def _orch(cs: MagicMock, target: CacheBustTarget) -> BranchOrchestrator:
    issuer = MagicMock()
    issuer.dispatch_first_turn = AsyncMock(return_value=True)
    return BranchOrchestrator(
        conversation_source=cs,
        credit_issuer=issuer,
        benchmark_id=_BENCHMARK_ID,
        cache_bust_target=target,
    )


# ===========================================================================
# Pre-session children all share the ROOT marker (multi-branch, multi-child)
# ===========================================================================


class TestPreSessionChildrenShareRootMarker:
    """Every pre-session background child of one root carries the SAME root
    tree marker, regardless of its own conversation id or which branch it's on.
    """

    @pytest.mark.asyncio
    @pytest.mark.parametrize("target", _TARGETS_NON_NONE)
    async def test_multi_branch_multi_child_all_carry_root_marker(
        self, target: CacheBustTarget
    ) -> None:
        # Two pre-session branches on turn 0, four children with deliberately
        # divergent conversation ids -- none of which may leak into the marker.
        branch_a = _pre_branch("root:pre:a", ["bg-alpha", "bg-beta"])
        branch_b = _pre_branch("root:pre:b", ["bg-gamma", "bg-delta"])
        root = _mk_conv(
            "trace-root-001",
            [TurnMetadata(branch_ids=["root:pre:a", "root:pre:b"]), TurnMetadata()],
            [branch_a, branch_b],
        )
        children = [_mk_conv(c, [TurnMetadata()], []) for c in branch_a.child_conversation_ids + branch_b.child_conversation_ids]  # fmt: skip
        cs = _mk_source([root, *children])
        orch = _orch(cs, target)

        await orch.dispatch_pre_session_branches()

        expected = _root_marker("trace-root-001", target)
        markers = _markers_by_child(cs)
        assert set(markers) == {"bg-alpha", "bg-beta", "bg-gamma", "bg-delta"}
        # Single shared domain: every child carries the identical root marker.
        assert set(markers.values()) == {expected}
        # And it is NOT any child-keyed marker.
        for child_cid in markers:
            child_keyed = build_cache_bust_marker(
                _BENCHMARK_ID, 0, 0, child_cid, target=target
            )
            assert markers[child_cid] != child_keyed

    @pytest.mark.asyncio
    async def test_child_marker_independent_of_child_conversation_id(self) -> None:
        """Two roots with byte-identical base trace ids but differently-named
        children produce the SAME marker for every child -- proving the digest
        ignores the child id entirely."""
        target = CacheBustTarget.FIRST_TURN_PREFIX
        branch = _pre_branch("r:pre", ["wildly-different-child-name-xyz"])
        root = _mk_conv(
            "shared-base-trace",
            [TurnMetadata(branch_ids=["r:pre"]), TurnMetadata()],
            [branch],
        )
        child = _mk_conv("wildly-different-child-name-xyz", [TurnMetadata()], [])
        cs = _mk_source([root, child])
        orch = _orch(cs, target)

        await orch.dispatch_pre_session_branches()

        markers = _markers_by_child(cs)
        assert markers["wildly-different-child-name-xyz"] == _root_marker(
            "shared-base-trace", target
        )


# ===========================================================================
# Cross-root isolation: each child shares its OWN root, trees don't collide
# ===========================================================================


class TestCrossRootIsolation:
    """Distinct roots are distinct prefix-cache domains. A child of root A must
    never carry root B's marker, and the two root markers must differ."""

    @pytest.mark.asyncio
    async def test_two_roots_children_carry_own_root_marker_collision_free(
        self,
    ) -> None:
        target = CacheBustTarget.SYSTEM_PREFIX
        branch_a = _pre_branch("ra:pre", ["child-of-a"])
        branch_b = _pre_branch("rb:pre", ["child-of-b"])
        root_a = _mk_conv(
            "trace-root-A", [TurnMetadata(branch_ids=["ra:pre"]), TurnMetadata()], [branch_a]
        )  # fmt: skip
        root_b = _mk_conv(
            "trace-root-B", [TurnMetadata(branch_ids=["rb:pre"]), TurnMetadata()], [branch_b]
        )  # fmt: skip
        child_a = _mk_conv("child-of-a", [TurnMetadata()], [])
        child_b = _mk_conv("child-of-b", [TurnMetadata()], [])
        cs = _mk_source([root_a, root_b, child_a, child_b])
        orch = _orch(cs, target)

        await orch.dispatch_pre_session_branches()

        markers = _markers_by_child(cs)
        marker_a = _root_marker("trace-root-A", target)
        marker_b = _root_marker("trace-root-B", target)
        assert markers["child-of-a"] == marker_a
        assert markers["child-of-b"] == marker_b
        # Collision-free across trees: the two domains are distinct.
        assert marker_a != marker_b


# ===========================================================================
# cache_bust_target == NONE: all markers None on every path
# ===========================================================================


class TestTargetNoneDisablesAllMarkers:
    """When cache-bust is disabled the invariant degenerates: every path
    yields None, never an empty string and never a stray digest."""

    @pytest.mark.asyncio
    async def test_pre_session_children_all_none(self) -> None:
        branch = _pre_branch("r:pre", ["bg-one", "bg-two"])
        root = _mk_conv(
            "trace-root", [TurnMetadata(branch_ids=["r:pre"]), TurnMetadata()], [branch]
        )  # fmt: skip
        children = [_mk_conv(c, [TurnMetadata()], []) for c in ["bg-one", "bg-two"]]
        cs = _mk_source([root, *children])
        orch = _orch(cs, CacheBustTarget.NONE)

        await orch.dispatch_pre_session_branches()

        markers = _markers_by_child(cs)
        assert markers == {"bg-one": None, "bg-two": None}

    def test_pre_session_tree_marker_none_target_returns_none(self) -> None:
        cs = _mk_source([_mk_conv("trace-root", [TurnMetadata()], [])])
        orch = _orch(cs, CacheBustTarget.NONE)
        assert orch._pre_session_tree_marker("trace-root") is None

    def test_marker_for_root_none_target_returns_none(self) -> None:
        ledger = CacheBustLedger()
        ledger.session_marker["corr-root"] = "[rid:deadbeefcafe]\n\n"
        cs = _mk_source([_mk_conv("trace-root", [TurnMetadata()], [])])
        issuer = MagicMock()
        orch = BranchOrchestrator(
            conversation_source=cs,
            credit_issuer=issuer,
            benchmark_id=_BENCHMARK_ID,
            cache_bust_target=CacheBustTarget.NONE,
            cache_bust_ledger=ledger,
        )
        # Even with a marker sitting in the ledger, NONE target short-circuits.
        assert orch._marker_for_root("corr-root") is None

    def test_resolve_tree_marker_none_records_none(self) -> None:
        ledger = CacheBustLedger()
        result = resolve_tree_marker(
            ledger,
            "corr-root",
            benchmark_id=_BENCHMARK_ID,
            trajectory_index=0,
            conversation_id="trace-root",
            target=CacheBustTarget.NONE,
        )
        assert result is None
        # The None is recorded so callers can look it up unconditionally.
        assert ledger.session_marker["corr-root"] is None
        # No pass was burned for a disabled tree.
        assert "trace-root" not in ledger.recycle_pass


# ===========================================================================
# base_trace_id stripping: suffixes on root vs leakage from child
# ===========================================================================


class TestBaseTraceIdStripping:
    """The digest keys on the STRIPPED base trace id. A descendant suffix on
    the root id collapses to the base; a child's own suffix never leaks in."""

    @pytest.mark.parametrize(
        "conversation_id,expected_base",
        [
            param("trace-root", "trace-root", id="no-suffix-unchanged"),
            param("trace-root::sa:0", "trace-root", id="subagent-suffix-stripped"),
            param("trace-root::fa:3", "trace-root", id="flat-agent-suffix-stripped"),
            param("trace-root::sa:0::fa:1", "trace-root", id="nested-suffix-stripped"),
        ],
    )  # fmt: skip
    def test_base_trace_id_strips_descendant_suffixes(
        self, conversation_id: str, expected_base: str
    ) -> None:
        assert base_trace_id(conversation_id) == expected_base

    def test_pre_session_marker_digests_stripped_root_base(self) -> None:
        """A root whose conversation id carries a ``::sa:`` suffix must digest
        on the stripped base, so the suffixed and bare forms share a domain."""
        target = CacheBustTarget.FIRST_TURN_PREFIX
        branch = _pre_branch("r:pre", ["child"])
        root = _mk_conv(
            "trace-root::sa:0",
            [TurnMetadata(branch_ids=["r:pre"]), TurnMetadata()],
            [branch],
        )
        child = _mk_conv("child", [TurnMetadata()], [])
        cs = _mk_source([root, child])
        orch = _orch(cs, target)

        marker = orch._pre_session_tree_marker("trace-root::sa:0")
        # Equals the marker for the BARE base -- one domain across the suffix.
        assert marker == _root_marker("trace-root", target)
        # Suffixed and bare roots are NOT in different domains.
        assert marker == orch._pre_session_tree_marker("trace-root")

    @pytest.mark.asyncio
    async def test_child_suffix_does_not_leak_into_root_marker(self) -> None:
        """A pre-session child whose own conversation id carries a ``::sa:``
        suffix must still receive the ROOT's base marker -- the child id (and
        its suffix) is irrelevant to the digest."""
        target = CacheBustTarget.SYSTEM_PREFIX
        # Child id deliberately carries a suffix and shares the root's prefix;
        # if the marker were child-keyed, base_trace_id(child) would still
        # strip to "trace-root" and accidentally pass. Use a DISTINCT child
        # base so a leak is detectable.
        branch = _pre_branch("r:pre", ["other-base::sa:2"])
        root = _mk_conv(
            "trace-root", [TurnMetadata(branch_ids=["r:pre"]), TurnMetadata()], [branch]
        )  # fmt: skip
        child = _mk_conv("other-base::sa:2", [TurnMetadata()], [])
        cs = _mk_source([root, child])
        orch = _orch(cs, target)

        await orch.dispatch_pre_session_branches()

        markers = _markers_by_child(cs)
        assert markers["other-base::sa:2"] == _root_marker("trace-root", target)
        # Guard the premise: a child-base-keyed marker would differ.
        child_base_keyed = build_cache_bust_marker(
            _BENCHMARK_ID, 0, 0, base_trace_id("other-base::sa:2"), target=target
        )
        assert markers["other-base::sa:2"] != child_base_keyed


# ===========================================================================
# resolve_tree_marker idempotency and cross-lane/recycle collision-freedom
# ===========================================================================


class TestResolveTreeMarkerIdempotencyAndCollisions:
    """``resolve_tree_marker`` mints once per ``root_correlation_id`` and is
    collision-free across lanes and recycle passes of the same base."""

    def test_resolving_same_root_twice_is_idempotent_and_bumps_pass_once(
        self,
    ) -> None:
        ledger = CacheBustLedger()
        first = resolve_tree_marker(
            ledger,
            "corr-root-1",
            benchmark_id=_BENCHMARK_ID,
            trajectory_index=0,
            conversation_id="trace-root",
            target=CacheBustTarget.SYSTEM_PREFIX,
        )
        pass_after_first = ledger.recycle_pass["trace-root"]
        second = resolve_tree_marker(
            ledger,
            "corr-root-1",
            benchmark_id=_BENCHMARK_ID,
            trajectory_index=99,  # ignored: cached by root_correlation_id
            conversation_id="trace-root",
            target=CacheBustTarget.SYSTEM_PREFIX,
        )
        assert first == second
        # The second resolve reused the stored value; no extra pass burned.
        assert ledger.recycle_pass["trace-root"] == pass_after_first == 0

    def test_two_distinct_roots_same_base_get_distinct_passes(self) -> None:
        """Two lanes/recycles of the SAME base trace land on different
        ``root_correlation_id`` keys and must mint DISTINCT markers (pass 0
        then pass 1) -- collision-free across recycles."""
        ledger = CacheBustLedger()
        target = CacheBustTarget.FIRST_TURN_SUFFIX
        marker_lane0 = resolve_tree_marker(
            ledger,
            "corr-root-lane0",
            benchmark_id=_BENCHMARK_ID,
            trajectory_index=0,
            conversation_id="trace-root",
            target=target,
        )
        marker_lane1 = resolve_tree_marker(
            ledger,
            "corr-root-lane1",
            benchmark_id=_BENCHMARK_ID,
            trajectory_index=1,
            conversation_id="trace-root",
            target=target,
        )
        assert marker_lane0 != marker_lane1
        assert ledger.recycle_pass["trace-root"] == 1
        # Each equals its own explicit pass digest.
        assert marker_lane0 == build_cache_bust_marker(
            _BENCHMARK_ID, 0, 0, "trace-root", target=target
        )
        assert marker_lane1 == build_cache_bust_marker(
            _BENCHMARK_ID, 1, 1, "trace-root", target=target
        )

    def test_descendant_resolving_with_suffixed_id_reuses_root_marker(self) -> None:
        """A descendant calling ``resolve_tree_marker`` with its OWN suffixed
        conversation id but the SAME ``root_correlation_id`` reuses the root's
        already-minted marker -- it does not re-digest the suffixed id."""
        ledger = CacheBustLedger()
        target = CacheBustTarget.SYSTEM_PREFIX
        root_marker = resolve_tree_marker(
            ledger,
            "corr-root",
            benchmark_id=_BENCHMARK_ID,
            trajectory_index=0,
            conversation_id="trace-root",
            target=target,
        )
        descendant_marker = resolve_tree_marker(
            ledger,
            "corr-root",  # same tree
            benchmark_id=_BENCHMARK_ID,
            trajectory_index=0,
            conversation_id="trace-root::sa:0",  # descendant id, ignored
            target=target,
        )
        assert descendant_marker == root_marker
        # Only one pass ever burned for the base.
        assert ledger.recycle_pass["trace-root"] == 0


# ===========================================================================
# Determinism: pre-session marker == lane-0/pass-0 mint
# ===========================================================================


class TestPreSessionMarkerDeterminism:
    """``_pre_session_tree_marker(root)`` must equal what ``resolve_tree_marker``
    mints for that root's primary (lane-0, pass-0) instance, and must NOT be
    keyed on the child id (the bug that was just fixed)."""

    @pytest.mark.parametrize("target", _TARGETS_NON_NONE)
    def test_pre_session_marker_equals_lane0_pass0_mint(
        self, target: CacheBustTarget
    ) -> None:
        cs = _mk_source([_mk_conv("trace-root", [TurnMetadata()], [])])
        orch = _orch(cs, target)

        ledger = CacheBustLedger()
        minted = resolve_tree_marker(
            ledger,
            "corr-root",
            benchmark_id=_BENCHMARK_ID,
            trajectory_index=0,
            conversation_id="trace-root",
            target=target,
        )
        assert orch._pre_session_tree_marker("trace-root") == minted

    def test_pre_session_marker_root_keyed_not_child_keyed(self) -> None:
        """Locks the fixed bug: marker keyed on root base, not the child id."""
        target = CacheBustTarget.FIRST_TURN_PREFIX
        cs = _mk_source([_mk_conv("trace-root", [TurnMetadata()], [])])
        orch = _orch(cs, target)

        root_keyed = orch._pre_session_tree_marker("trace-root")
        child_keyed = build_cache_bust_marker(
            _BENCHMARK_ID, 0, 0, "background-child", target=target
        )
        assert root_keyed == _root_marker("trace-root", target)
        assert root_keyed != child_keyed


# ===========================================================================
# Documented limitation: pre-session child binds to lane-0
# ===========================================================================


class TestPreSessionLane0Limitation:
    """A pre-session child binds to the root's lane-0/pass-0 marker because the
    root session does not exist yet at pre-dispatch. If the root's eventual
    primary instance lands on a NON-zero lane (a recycle, where pass>0), the
    pre-session child's marker will NOT match. Characterize the actual behavior;
    don't assume it matches a non-zero lane."""

    @pytest.mark.asyncio
    async def test_pre_session_child_binds_lane0_even_when_root_recycles_to_pass1(
        self,
    ) -> None:
        target = CacheBustTarget.SYSTEM_PREFIX
        branch = _pre_branch("r:pre", ["bg-child"])
        root = _mk_conv(
            "trace-root", [TurnMetadata(branch_ids=["r:pre"]), TurnMetadata()], [branch]
        )  # fmt: skip
        child = _mk_conv("bg-child", [TurnMetadata()], [])
        cs = _mk_source([root, child])
        orch = _orch(cs, target)

        await orch.dispatch_pre_session_branches()
        markers = _markers_by_child(cs)

        # The child is bound to lane-0/pass-0 unconditionally.
        assert markers["bg-child"] == _root_marker("trace-root", target)

        # Simulate the root's eventual primary instance landing on pass 1
        # (e.g. this base was already minted once -> recycle). The lane-0
        # pre-session marker does NOT match the pass-1 mint -- documented
        # limitation, not a bug, since pre-dispatch cannot know the lane.
        ledger = CacheBustLedger()
        ledger.recycle_pass["trace-root"] = 0  # base already used once
        pass1_marker = resolve_tree_marker(
            ledger,
            "corr-root-recycled",
            benchmark_id=_BENCHMARK_ID,
            trajectory_index=1,
            conversation_id="trace-root",
            target=target,
        )
        assert pass1_marker == build_cache_bust_marker(
            _BENCHMARK_ID, 1, 1, "trace-root", target=target
        )
        assert markers["bg-child"] != pass1_marker
