# SPDX-FileCopyrightText: Copyright (c) 2025-2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Adversarial REAL-subprocess integration test for the agentic-replay
inner-session semaphore + cache-bust marker TREE invariant.

The ``inferencex-agentx-mvp`` scenario forces ``--use-end-to-start-delays``,
which engages ``InnerSessionLimiter`` (``src/aiperf/timing/inner_semaphore.py``):
one ``asyncio.Semaphore(P)`` per session TREE, keyed by ``root_correlation_id``
and sized to that trajectory's session-achievable peak ``P`` (the maximum number
of the tree's streams that can be simultaneously busy under a serial replay --
see ``session_achievable_peak`` / ``TrajectorySource.peak_for``). This drives a
real subprocess (real ZMQ + real workers + real HTTP against the in-repo mock
server) over a SPAWN fan-out fixture and asserts, from ``result.raw_records``:

1. SAFETY (always-checked -- no-deadlock + a sound, slice-independent in-flight
   sanity bound; the TIGHT cap==P proof lives in the flat-split + component
   tests, see the test docstring): the run exits 0, produces PROFILING records,
   drains without deadlock under an injected slowdown, and per session TREE the
   peak number of CONCURRENTLY in-flight requests -- measured
   by wall-clock ``[request_start_ns, request_end_ns]`` interval overlap grouped
   by ``root_correlation_id`` -- never exceeds a SOUND, record-derivable upper
   bound on ``P``: the number of DISTINCT streams in that tree (distinct
   ``x_correlation_id`` under the same ``root_correlation_id``). This is a valid
   bound because ``session_achievable_peak`` counts busy-span overlap across
   streams, with each stream contributing at most 1 -- so ``P`` can never exceed
   the tree's distinct-stream count. An UNbounded replay of a fan-out tree would
   put the parent root AND its spawned subagent on the wire simultaneously while
   STILL counting as <= distinct-stream-count, so the binding-strength is gated
   separately as a non-vacuity floor (3) rather than baked into the safety bound.

2. MARKER (always-checked): every spawn-descendant record (``agent_depth > 0``)
   carries its tree-ROOT's cache-bust marker (the rid minted for the root of its
   base conversation), i.e. descendants SHARE the root marker -- they are not
   independently busted -- so the whole tree is one prefix-cache domain. Mirrors
   ``test_spawn_subagent_children_share_root_marker_real_subprocess`` in the
   sibling ``test_agentic_replay_cache_bust.py``.

3. NON-VACUITY FLOOR (xfail-guarded for load starvation): the fan-out must have
   actually surfaced (>= 1 spawn-descendant record AND at least one tree whose
   distinct-stream count > 1) for the safety bound to be non-vacuous. On a
   heavily loaded box the fixed-wall-clock benchmark can under-produce sessions
   or not surface the spawn split before the deadline (CPU starvation, not a
   correctness issue); xfail in that case so the SAFETY + MARKER checks above
   still run as the regression bar rather than hard-failing on load.

Sibling: ``test_agentic_replay_cache_bust.py`` (marker position/uniqueness on
the wire) and ``test_weka_flat_split_e2e.py`` (cap binding under injected
slowdown with a hand-computed peak of 2). This file's distinguishing claim is a
PURELY record-derived per-tree upper bound -- no hardcoded peak -- so it stays
valid regardless of which post-t* slice each lane sampled.
"""

from __future__ import annotations

import json
import re
from collections import defaultdict
from collections.abc import AsyncIterator, Callable
from pathlib import Path

import pytest

from tests.harness.utils import AIPerfCLI, AIPerfMockServer

pytestmark = pytest.mark.integration

# Slow-server factory fixture (tests/integration/conftest.py): a context manager
# yielding an AIPerfMockServer with custom latency (ttft/itl) so requests queue
# at the inner-session limiter instead of racing through uncontended.
MockServerFactory = Callable[..., AsyncIterator[AIPerfMockServer]]

_OPUS = "claude-opus-4-5-20251101"
_HAIKU = "claude-haiku-4-5-20251001"
_TOKENIZER = "openai/gpt-oss-120b"  # pre-cached + offline in integration conftest
_RID_RE = re.compile(r"\[rid:[0-9a-f]{12}\]")


# --- fixtures ---------------------------------------------------------------


def _req(t: float, hash_ids: list[int], in_tokens: int, *, model: str = _OPUS) -> dict:
    return {
        "t": t,
        "type": "n",
        "model": model,
        "in": in_tokens,
        "out": 8,
        "hash_ids": hash_ids,
        "input_types": ["text"],
        "output_types": ["text"],
        "stop": "end_turn",
        "api_time": 0.05,
        "think_time": 0.0,
    }


def _write_subagent_fixture(target_dir: Path, *, num_traces: int = 6) -> Path:
    """Weka traces each carrying a ``type:subagent`` entry -> a SPAWN child.

    The subagent's request timestamp overlaps the parent's bracketing turns so
    the recorded session-achievable peak of the tree is 2 (root stream + one
    subagent stream busy at once). Copied in shape from the cache-bust sibling's
    ``_write_subagent_fixture`` so the spawn fan-out path is exercised identically.
    """
    target_dir.mkdir(parents=True, exist_ok=True)
    for i in range(1, num_traces + 1):
        base = i * 10
        trace = {
            "id": f"sa_trace_{i:02d}",
            "models": [_OPUS],
            "block_size": 64,
            "hash_id_scope": "local",
            "requests": [
                _req(0.0, [base + 1, base + 2, base + 3], 200),
                {
                    "t": 2.0,
                    "type": "subagent",
                    "agent_id": f"agent_{i:03d}",
                    "subagent_type": "Explore",
                    "duration_ms": 3000,
                    "total_tokens": 500,
                    "tool_use_count": 2,
                    "status": "completed",
                    "requests": [
                        _req(0.0, [base + 100, base + 101], 100, model=_HAIKU),
                    ],
                    "models": [_HAIKU],
                    "tool_tokens": 20,
                    "system_tokens": 10,
                },
                _req(6.0, [base + 1, base + 2, base + 3, base + 4, base + 5], 400),
            ],
        }
        # subagent inner request stop must be a tool-using stop on parent turn 0
        trace["requests"][0]["stop"] = "tool_use"
        trace["requests"][2]["input_types"] = ["tool_result"]
        (target_dir / f"sa_trace_{i:02d}.json").write_text(json.dumps(trace))
    return target_dir


# --- helpers ----------------------------------------------------------------


def _payload_dict(record) -> dict:
    if record.payload is not None:
        return record.payload
    if record.payload_bytes is not None:
        return json.loads(record.payload_bytes)
    return {}


def _user_content(payload: dict) -> str | None:
    for msg in payload.get("messages", []):
        if isinstance(msg, dict) and msg.get("role") == "user":
            c = msg.get("content")
            return c if isinstance(c, str) else None
    return None


def _profiling_records(result) -> list:
    return [
        r
        for r in (result.raw_records or [])
        if r.metadata.benchmark_phase == "profiling"
    ]


def _max_inflight(intervals: list[tuple[int, int]]) -> int:
    """Peak count of intervals ``(start_ns, end_ns)`` simultaneously in flight.

    A sweep-line: a request occupies the wire across ``[request_start_ns,
    request_end_ns]``. Ties resolve ends (-1) before starts (+1) so a request
    that ends exactly when another starts is not double-counted -- a sound
    (conservative-low) treatment for an UPPER-bound safety check.
    """
    events: list[tuple[int, int]] = []
    for s, e in intervals:
        events.append((s, 1))
        events.append((e, -1))
    events.sort(key=lambda x: (x[0], x[1]))
    cur = peak = 0
    for _, d in events:
        cur += d
        peak = max(peak, cur)
    return peak


def _build_cmd(weka_dir: Path, url: str) -> str:
    """Drive a duration-bounded agentic-replay run of the MVP scenario.

    ``--benchmark-duration 8`` (a wall-clock window, mirroring the sibling
    ``test_agentic_replay_cache_bust.py::_build_cmd``) bounds runtime
    deterministically so the run does not race the pytest-global ``--timeout``
    on a loaded box -- a ``--request-count`` cap can run arbitrarily long when
    the host is CPU-starved. The drain is still load-bearing: a deadlock in the
    inner-session limiter would hang past the window and fail to exit 0, so a
    clean exit 0 remains part of the safety claim. ``--scenario
    inferencex-agentx-mvp`` auto-sets ``use_end_to_start_delays``, engaging the
    per-tree semaphore.
    """
    return f"""
        aiperf profile \
            --model {_HAIKU} \
            --model {_OPUS} \
            --url {url} \
            --endpoint-type chat \
            --streaming \
            --custom-dataset-type weka_trace \
            --input-file {weka_dir} \
            --no-fixed-schedule \
            --benchmark-duration 8 \
            --concurrency 3 \
            --random-seed 42 \
            --tokenizer {_TOKENIZER} \
            --extra-inputs ignore_eos:true \
            --workers-max 2 \
            --scenario inferencex-agentx-mvp \
            --unsafe-override \
            --cache-bust first_turn_prefix \
            --export-level raw \
            --ui simple
    """


# --- tests ------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.timeout(420)  # headroom over the subprocess timeout below on a loaded box
async def test_inner_semaphore_real_run_under_slowdown_drains_and_shares_root_marker(
    cli: AIPerfCLI,
    mock_server_factory: MockServerFactory,
    tmp_path: Path,
) -> None:
    """REAL run of ``inferencex-agentx-mvp`` over a SPAWN fan-out under an
    injected per-request slowdown, asserting the properties this real-subprocess
    path can prove SOUNDLY:

      1. NO DEADLOCK under contention: with the inner-session semaphore engaged
         and the server slowed so requests actually queue at the limiter, the
         phase still drains and exits 0. Adding a blocking gate to the wire path
         risks deadlock; this exercises that under genuine back-pressure.
      2. MARKER INVARIANT: every spawn descendant shares its tree-root's
         cache-bust marker (one prefix-cache domain per tree).
      3. SOUND in-flight bound: per tree, peak concurrent in-flight never exceeds
         the tree's distinct-stream count -- a slice-independent upper bound on
         the semaphore size P (P <= stream count), which catches a limiter that
         admitted MORE than the tree could ever put on the wire (a duplicated
         stream or a lost semaphore).

    Deliberately NOT asserted here: the TIGHT cap == recorded peak. A
    trajectory's P is the achievable peak over its randomized post-t* slice,
    which is absent from the output records and cannot be re-derived from the raw
    fixture (the loader warps timestamps and samples the slice), so a tight
    per-tree P bound here would be UNSOUND. The cap-binds-at-exactly-P proof
    lives where P is known and fixed: ``test_weka_flat_split_e2e.py::
    test_inner_session_limiter_caps_tree_inflight_under_slowdown`` (3 streams,
    invariant peak 2, asserts the cap holds AND binds under slowdown) and the
    component test ``test_agentic_replay_inner_limit.py`` (cap pinned at exactly
    P with a controllable issuer).

    Synonym note: "session"/"tree" means a trajectory's whole agentic session
    (root conversation + spawned subagent descendants), grouped by
    ``root_correlation_id`` -- NOT a single Turn or a single Credit.
    """
    weka_dir = _write_subagent_fixture(tmp_path / "sa", num_traces=6)
    # Slow server (ttft=400ms, well above the fixture's small recorded api_times)
    # so requests genuinely queue at the inner-session limiter -- this is what
    # makes the no-deadlock-under-contention claim load-bearing rather than a
    # race through an uncontended fast server.
    async with mock_server_factory(ttft=400.0, itl=2.0, workers=4) as server:
        result = await cli.run(_build_cmd(weka_dir, server.url), timeout=360.0)

    # --- run-level safety: exit 0 + drained (no deadlock) + has records ---
    assert result.exit_code == 0, (
        f"run failed (possible inner-semaphore deadlock): exit={result.exit_code}\n"
        f"log tail=\n{(result.log or '')[-2000:]}"
    )
    records = _profiling_records(result)
    assert records, f"no profiling records\n{(result.log or '')[-1500:]}"

    # --- group every executed request by its session TREE root --------------
    # root_correlation_id is stable across the whole tree (root + every
    # descendant subagent); it equals x_correlation_id for the root session.
    tree_intervals: dict[str, list[tuple[int, int]]] = defaultdict(list)
    tree_streams: dict[str, set[str]] = defaultdict(set)
    for rec in records:
        md = rec.metadata
        if md.was_cancelled:
            continue
        root = md.root_correlation_id or md.x_correlation_id
        if root is None:
            continue
        # request_end_ns >= request_start_ns always (both wall-clock time_ns on
        # the same record); guard against a degenerate/zero end defensively.
        start = md.request_start_ns
        end = md.request_end_ns if md.request_end_ns >= start else start
        tree_intervals[root].append((start, end))
        if md.x_correlation_id is not None:
            tree_streams[root].add(md.x_correlation_id)

    assert tree_intervals, "no non-cancelled PROFILING records to measure in-flight"

    # --- SAFETY (always-checked): per-tree peak in-flight <= distinct streams.
    # distinct-stream-count is a SOUND upper bound on the semaphore size P:
    # session_achievable_peak overlaps per-stream busy spans, each stream adds
    # at most 1, so P <= number of streams in the tree. An unbounded replay
    # would not violate this bound by itself, which is exactly why the binding
    # strength is gated as a separate non-vacuity floor below -- the bound here
    # only catches a limiter that admitted MORE than the tree's stream count
    # (i.e. duplicated a stream onto the wire or lost its semaphore entirely).
    violations: dict[str, tuple[int, int]] = {}
    for root, ivs in tree_intervals.items():
        peak = _max_inflight(ivs)
        bound = max(1, len(tree_streams.get(root, set())))
        if peak > bound:
            violations[root] = (peak, bound)
    assert not violations, (
        "a session tree exceeded its record-derived in-flight upper bound "
        "(distinct stream count); the inner-session semaphore failed to bound "
        f"per-tree concurrency. root_corr -> (observed_peak, bound): {violations}"
    )

    # --- MARKER (always-checked): descendants share the tree-root marker. ----
    # Collect root (depth==0) markers per base conversation id, then verify each
    # spawn descendant (depth>0, '::sa:' in conv id) carries one of them.
    root_rids_by_base: dict[str, set[str]] = defaultdict(set)
    child_records: list[tuple[object, str | None]] = []
    for rec in records:
        payload = _payload_dict(rec)
        m = _RID_RE.search(_user_content(payload) or "")
        conv = rec.metadata.conversation_id or ""
        if rec.metadata.agent_depth and "::sa:" in conv:
            child_records.append((rec, m.group(0) if m else None))
        elif m:
            root_rids_by_base[conv].add(m.group(0))

    for rec, child_rid in child_records:
        conv = rec.metadata.conversation_id or ""
        base = conv.split("::sa:")[0]
        assert child_rid is not None, (
            f"SPAWN descendant {conv} carries no cache-bust marker (not busted)"
        )
        root_rids = root_rids_by_base.get(base, set())
        assert child_rid in root_rids, (
            f"SPAWN descendant {conv} carries marker {child_rid}, which is not "
            f"its tree-root's minted marker (descendants must share the tree-root "
            f"marker so the whole tree is one prefix-cache domain): "
            f"root rids for base {base!r}={root_rids}"
        )

    # --- NON-VACUITY FLOOR (xfail on load starvation) -----------------------
    # The safety bound is only meaningful if the fan-out actually surfaced: at
    # least one spawn descendant executed AND at least one tree held >1 distinct
    # stream (so the cap had something to bound). A loaded box can under-produce
    # sessions or not surface the spawn split before the request-count is met.
    multi_stream_trees = {
        root for root, streams in tree_streams.items() if len(streams) > 1
    }
    if not child_records or not multi_stream_trees:
        pytest.xfail(
            "load-starved / spawn fan-out did not surface: "
            f"{len(child_records)} spawn-descendant records, "
            f"{len(multi_stream_trees)} multi-stream trees "
            "(need >=1 of each for a non-vacuous per-tree cap claim). The SAFETY "
            "in-flight upper-bound and the descendants-share-root-marker checks "
            "above both passed unconditionally."
        )
