# SPDX-FileCopyrightText: Copyright (c) 2025-2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""End-to-end raw-export proof that every ``--session-routing`` mode reaches the wire.

Runs a real ``aiperf profile`` subprocess against the in-repo mock server with
``--export-level raw`` for each session-routing mode, then reads the exported
wire payloads / request headers and asserts the per-mode contract:

- ``dynamo_headers``: ``X-Dynamo-Session-ID`` on every request equals the
  session's ``x_correlation_id``; no parent header on root sessions; body is
  untouched (``"nvext" not in payload``).
- ``dynamo_nvext``: ``nvext.session_control`` carries ``bind`` (+ timeout) on
  every non-final turn and ``close`` (no timeout) on the final turn, with one
  stable ``session_id == x_correlation_id`` across the session.
- ``smg_routing_key``: ``X-SMG-Routing-Key`` equals ``x_correlation_id``.
- ``session_id_header``: the preset's ``X-Session-ID`` equals ``x_correlation_id``.
- ``custom`` (``headers={"X-Affinity":"session","X-SMG-Routing-Key":"session",
  "X-Tree-ID":"root"}``): every configured header equals ``x_correlation_id``
  (flat sessions are their own tree roots).
"""

from __future__ import annotations

import json
import re
from collections import defaultdict
from collections.abc import Callable, Sequence
from functools import partial
from pathlib import Path

import pytest
from pytest import param

from aiperf.common.models import RawRecordInfo
from tests.harness.utils import AIPerfCLI, AIPerfMockServer

_TOKENIZER = "openai/gpt-oss-120b"  # pre-cached + offline in integration conftest

_NUM_SESSIONS = 2
_TURNS_PER_SESSION = 3
# Non-default (plugin default is 300) so the assertions prove the CLI ->
# config -> worker numeric plumb actually carries this value to the wire,
# rather than coinciding with the default.
_TIMEOUT_SECONDS = 123


def _payload_dict(record: RawRecordInfo) -> dict:
    """Decode the exported wire payload regardless of which field carries it."""
    if record.payload is not None:
        return record.payload
    if record.payload_bytes is not None:
        return json.loads(record.payload_bytes)
    return {}


def _build_cmd(
    urls: Sequence[str], *, modes: Sequence[str], opts: Sequence[str] = ()
) -> str:
    """Emit one ``--url`` per entry (the rule-6 dp-rank recipe) and one
    ``--session-routing`` per mode (for stacked plans)."""
    url_flags = " ".join(f"--url {u}" for u in urls)
    mode_flags = " ".join(f"--session-routing {m}" for m in modes)
    opt_flags = " ".join(f"--session-routing-opt {kv}" for kv in opts)
    return f"""
        aiperf profile \
            --model {_TOKENIZER} \
            {url_flags} \
            --endpoint-type chat \
            --num-sessions {_NUM_SESSIONS} \
            --session-turns-mean {_TURNS_PER_SESSION} \
            --session-turns-stddev 0 \
            --random-seed 42 \
            --workers-max 1 \
            {mode_flags} \
            {opt_flags} \
            --export-level raw \
            --ui simple
    """


async def _records_by_session(
    cli: AIPerfCLI, url: str, *, mode: str, opts: Sequence[str]
) -> dict[str, list[RawRecordInfo]]:
    """Run a benchmark and return each session's raw records ordered by
    turn_index, keyed by X-Correlation-ID."""
    result = await cli.run(_build_cmd([url], modes=[mode], opts=opts), timeout=300.0)

    records = list(result.raw_records or [])
    assert records, f"no raw records\n{(result.log or '')[-1500:]}"

    grouped: dict[str, list[RawRecordInfo]] = defaultdict(list)
    for rec in records:
        grouped[rec.metadata.x_correlation_id].append(rec)

    assert len(grouped) == _NUM_SESSIONS, (
        f"expected {_NUM_SESSIONS} sessions, got {len(grouped)}"
    )
    out: dict[str, list[RawRecordInfo]] = {}
    for xcorr, recs in grouped.items():
        assert len(recs) == _TURNS_PER_SESSION, (
            f"session {xcorr}: expected {_TURNS_PER_SESSION} turns, got {len(recs)}"
        )
        recs.sort(key=lambda r: r.metadata.turn_index)
        out[xcorr] = recs
    return out


def _verify_headers_equal_xcorr(
    by_session: dict[str, list[RawRecordInfo]],
    *,
    present: tuple[str, ...],
    absent: tuple[str, ...] = (),
) -> None:
    """Header-only modes: every ``present`` header equals the session's
    X-Correlation-ID on every request, every ``absent`` header stays off the
    wire, and the body is untouched."""
    for xcorr, recs in by_session.items():
        for rec in recs:
            headers = rec.request_headers or {}
            for name in present:
                assert headers.get(name) == xcorr, (
                    f"session {xcorr} turn {rec.metadata.turn_index}: "
                    f"missing/mismatched {name}; headers={headers}"
                )
            for name in absent:
                assert name not in headers, (
                    f"session {xcorr}: {name} must be absent; headers={headers}"
                )
            assert "nvext" not in _payload_dict(rec), (
                f"session {xcorr}: header-mode must not mutate the body"
            )


def _verify_dynamo_nvext(by_session: dict[str, list[RawRecordInfo]]) -> None:
    for xcorr, recs in by_session.items():
        scs = []
        for rec in recs:
            sc = _payload_dict(rec).get("nvext", {}).get("session_control")
            assert sc is not None, (
                f"session {xcorr} turn {rec.metadata.turn_index}: "
                "every request must carry nvext.session_control"
            )
            scs.append(sc)

        actions = [sc.get("action") for sc in scs]
        assert all(a == "bind" for a in actions[:-1]), (
            f"session {xcorr}: non-final turns must bind; {actions}"
        )
        assert actions[-1] == "close", f"session {xcorr}: actions={actions}"
        assert "open" not in actions, f"session {xcorr}: emitted open; {actions}"

        # Every non-final 'bind' carries the timeout; 'close' does not.
        for sc in scs[:-1]:
            assert sc["timeout"] == _TIMEOUT_SECONDS, f"session {xcorr}: {sc}"
        assert "timeout" not in scs[-1], (
            f"session {xcorr}: close carried timeout; {scs[-1]}"
        )

        # One stable session_id == the X-Correlation-ID, on every turn.
        assert {sc["session_id"] for sc in scs} == {xcorr}, (
            f"session {xcorr}: session_id drift; {[sc.get('session_id') for sc in scs]}"
        )


def _verify_sglang_session(by_session: dict[str, list[RawRecordInfo]]) -> None:
    """SGLang body-field session key: a flat ``session_id`` top-level field on
    every request equals the session's X-Correlation-ID, stable across turns,
    with no routing headers and no ``nvext`` structure."""
    for xcorr, recs in by_session.items():
        for rec in recs:
            payload = _payload_dict(rec)
            assert payload.get("session_id") == xcorr, (
                f"session {xcorr} turn {rec.metadata.turn_index}: "
                f"session_id={payload.get('session_id')!r}"
            )
            assert "nvext" not in payload, (
                f"session {xcorr}: body-field mode must not add nvext structure"
            )
            headers = rec.request_headers or {}
            for name in ("X-SMG-Routing-Key", "X-Session-ID", "X-Dynamo-Session-ID"):
                assert name not in headers, (
                    f"session {xcorr}: body-field mode must not stamp {name}; "
                    f"headers={headers}"
                )


@pytest.mark.integration
@pytest.mark.asyncio
@pytest.mark.parametrize(
    "mode, opts, verifier",
    [
        # Root sessions have no parent, so the parent header must be absent.
        param("dynamo_headers", (),
              partial(_verify_headers_equal_xcorr, present=("X-Dynamo-Session-ID",),
                      absent=("X-Dynamo-Parent-Session-ID",)),
              id="dynamo_headers"),
        param("dynamo_nvext", (f"timeout_seconds={_TIMEOUT_SECONDS}",), _verify_dynamo_nvext, id="dynamo_nvext"),
        param("smg_routing_key", (),
              partial(_verify_headers_equal_xcorr, present=("X-SMG-Routing-Key",)), id="smg_routing_key"),
        param("session_id_header", (),
              partial(_verify_headers_equal_xcorr, present=("X-Session-ID",)), id="session_id_header"),
        # Two session-sourced names plus a root-sourced name; flat sessions are
        # their own tree roots, so every header carries the session's
        # X-Correlation-ID. Single-quoted so shlex keeps the JSON (with its
        # double quotes and no spaces) as one --session-routing-opt token.
        param(
            "custom",
            (
                """'headers={"X-Affinity":"session","X-SMG-Routing-Key":"session","X-Tree-ID":"root"}'""",
            ),
            partial(_verify_headers_equal_xcorr,
                    present=("X-Affinity", "X-SMG-Routing-Key", "X-Tree-ID")),
            id="custom_headers",
        ),
        param("sglang_session", (), _verify_sglang_session, id="sglang_session"),
    ],
)  # fmt: skip
async def test_session_routing_mode_reaches_wire(
    cli: AIPerfCLI,
    aiperf_mock_server: AIPerfMockServer,
    mode: str,
    opts: tuple[str, ...],
    verifier: Callable[[dict[str, list[RawRecordInfo]]], None],
):
    """Each session-routing mode stamps its per-session identity on the wire and
    it survives to the raw export exactly as the plugin specifies."""
    by_session = await _records_by_session(
        cli, aiperf_mock_server.url, mode=mode, opts=opts
    )
    verifier(by_session)


# --- Cases 2 + 5: url_index_header over two repeated URLs (alone + stacked) --
#
# ``url_index`` is post-fallback (the slot that also selects the actual URL).
# The documented dp-rank recipe repeats the SAME frontend URL once per rank,
# so both entries resolve to the one mock server and every request is captured.
# NOTE: ``MetricRecordMetadata`` carries no ``url_index`` field, so the emitted
# header value is the SOLE observable -- we assert its shape (a stringified
# int) and full coverage ({"0","1"}), not a header==metadata cross-check.
#
# The stacked variant adds ``session_id_header`` -- two composing header
# emitters with disjoint write-sets: ``X-Session-ID`` carries the session id on
# every request while ``X-URL-Index`` carries the round-robin slot.


@pytest.mark.integration
@pytest.mark.asyncio
@pytest.mark.parametrize(
    "modes",
    [
        param(["url_index_header"], id="url_index_header_two_urls"),
        param(["url_index_header", "session_id_header"], id="url_index_plus_session_id_header_stack"),
    ],
)  # fmt: skip
async def test_session_routing_url_index_header_two_urls(
    cli: AIPerfCLI,
    aiperf_mock_server: AIPerfMockServer,
    modes: list[str],
):
    """``url_index_header`` stamps each request's assigned round-robin URL slot;
    with two repeated URLs both slots (0 and 1) are reached and observable.
    Stacked with ``session_id_header``, the session header composes on top."""
    url = aiperf_mock_server.url
    result = await cli.run(_build_cmd([url, url], modes=modes), timeout=300.0)
    records = list(result.raw_records or [])
    assert records, f"no raw records\n{(result.log or '')[-1500:]}"

    observed: set[str] = set()
    for rec in records:
        headers = rec.request_headers or {}
        if "session_id_header" in modes:
            assert headers.get("X-Session-ID") == rec.metadata.x_correlation_id, (
                f"turn {rec.metadata.turn_index}: X-Session-ID mismatch; "
                f"headers={headers}"
            )
        value = headers.get("X-URL-Index")
        assert value in {"0", "1"}, (
            f"X-URL-Index must be a configured slot index; got {value!r}; "
            f"headers={headers}"
        )
        observed.add(value)
        payload = _payload_dict(rec)
        assert "nvext" not in payload, "header-only mode must not mutate the body"
        assert "session_id" not in payload, "header-only mode must not mutate the body"

    assert observed == {"0", "1"}, (
        f"round-robin must reach both URL slots across the run; observed={observed}"
    )


# --- Case 3: claude_code_headers on a DAG agent tree (depth 0 / 1) ----------
#
# DEPTH SCOPE (design-vs-reality deviation): the design asked for depth 0/1/2 to
# exercise the agent_parent header (emitted only at depth >= 2). Depth >= 2 is
# NOT reachable through a subprocess run on this branch: BranchOrchestrator only
# dispatches spawns on agent_depth=0 credits -- a spawned child (depth 1) does
# NOT auto-recurse to spawn its own children. This is an intentional v1
# property, asserted by
# tests/component_integration/timing/test_dag_combined_pathology.py::
# test_deep_dag_depth_4_chain ("depth>0 does NOT auto-recurse via
# orchestrator.intercept"), which reaches depth 4 only by manually driving each
# level's intercept in-process. So this wire test covers the reachable root
# (depth 0, `root` source) and child (depth 1, `agent` source) headers; the
# depth-2 `agent_parent` emission is unit-covered instead
# (tests/unit/workers/session_routing/test_facts_and_sources.py `n_depth2` /
# `ln_depth2`, and test_presets.py's claude_code parent-header case).

_AGENT_TREE_FIXTURE = (
    Path(__file__).resolve().parents[1] / "fixtures" / "dag" / "spawn_minimal.dag.jsonl"
)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_session_routing_claude_code_headers_agent_tree(
    cli: AIPerfCLI,
    aiperf_mock_server: AIPerfMockServer,
):
    """``claude_code_headers`` on a root->child spawn tree stamps the
    session/agent headers per the depth-conditional source rules: root emits only
    the session header (its own id, `root` source); depth-1 adds the agent header
    (its own id) while the session header still carries the tree root."""
    assert _AGENT_TREE_FIXTURE.exists(), f"fixture missing: {_AGENT_TREE_FIXTURE}"
    result = await cli.run(
        f"""
        aiperf profile \
            --model {_TOKENIZER} \
            --url {aiperf_mock_server.url} \
            --endpoint-type chat \
            --input-file {_AGENT_TREE_FIXTURE} \
            --custom-dataset-type dag_jsonl \
            --num-conversations 1 \
            --concurrency 1 \
            --workers-max 1 \
            --session-routing claude_code_headers \
            --export-level raw \
            --ui simple
        """,
        timeout=300.0,
    )
    records = list(result.raw_records or [])
    assert len(records) == 2, (
        f"expected root+child = 2 requests, got {len(records)}\n"
        f"{(result.log or '')[-1500:]}"
    )

    by_depth: dict[int, RawRecordInfo] = {}
    for rec in records:
        depth = rec.metadata.agent_depth
        assert depth not in by_depth, f"two records at depth {depth}"
        by_depth[depth] = rec
    assert set(by_depth) == {0, 1}, f"depths present: {sorted(by_depth)}"

    root, d1 = by_depth[0], by_depth[1]
    root_id = root.metadata.x_correlation_id
    d1_id = d1.metadata.x_correlation_id

    # The tree root is stable across the descendant and distinct from the child's
    # own id -- proves the session header tracks the tree root, not the session.
    assert d1.metadata.root_correlation_id == root_id
    assert d1.metadata.parent_correlation_id == root_id
    assert d1_id != root_id

    root_h = root.request_headers or {}
    d1_h = d1.request_headers or {}

    # root (depth 0): session header is its own id (root source); no agent/parent.
    assert root_h.get("x-claude-code-session-id") == root_id, root_h
    assert "x-claude-code-agent-id" not in root_h, root_h
    assert "x-claude-code-parent-agent-id" not in root_h, root_h

    # depth 1 (child): session header is the tree root; agent header is its own
    # id; no parent-agent (its parent IS the tree root).
    assert d1_h.get("x-claude-code-session-id") == root_id, d1_h
    assert d1_h.get("x-claude-code-agent-id") == d1_id, d1_h
    assert "x-claude-code-parent-agent-id" not in d1_h, d1_h

    for rec in records:
        assert "nvext" not in _payload_dict(rec), (
            "header-only mode must not mutate body"
        )


# --- Case 4: smg_routing_key + sglang_session, both source=header:... -------
#
# INTENTIONAL GAP -- NOT RUNNABLE AS A WIRE TEST ON THIS BRANCH.
#
# The spec contract (spec sec. 4.1 / sec. 6 replay row) has a dataset author a
# per-turn ``x-dynamo-session-id`` header; both the SMG routing key and the
# SGLang body ``session_id`` source it via ``header:x-dynamo-session-id`` so
# gateway affinity and body grouping share one recorded identity. That case is
# impossible to drive as a subprocess integration test here: NO loader on this
# branch authors ``Turn.extra_headers``. The ``dag_jsonl`` ``DagTurn`` model is
# ``extra="forbid"`` with no such field (a fixture that adds it is hard-rejected),
# every other loader ignores it, and the Exgentic per-turn stamping loader is out
# of scope on this base (spec sec. 8). A subprocess test can only supply data via
# ``--input-file``, so there is no path to put a dispatch-turn header on the wire
# for the ``header:`` source to read.
#
# The mechanics ARE covered by unit tests instead:
#   - Task 5 transport layering: ``build_headers`` dataset-wins layering over a
#     programmatically constructed ``Turn(extra_headers=...)``.
#   - Task 7 runtime gate: ``header:`` source drop/resolution semantics.
#   - Task 8 dataset fail-fast: ``missing="error"`` fails at dataset load when the
#     authored header is absent.
# This wire case is deferred until the Exgentic loader lands (spec sec. 8).


# --- Case 6: custom with a nested body path --------------------------------


@pytest.mark.integration
@pytest.mark.asyncio
async def test_session_routing_custom_nested_body(
    cli: AIPerfCLI,
    aiperf_mock_server: AIPerfMockServer,
):
    """``custom`` with a nested body assignment writes two levels deep via
    ``merge_at_path`` -- a plain nested write, distinct from the structured
    ``dynamo_nvext`` session_control emitter."""
    by_session = await _records_by_session(
        cli,
        aiperf_mock_server.url,
        mode="custom",
        # Single-quoted so shlex keeps the JSON (double quotes, no spaces) as
        # one --session-routing-opt token.
        opts=("""'body={"nvext":{"session_id":"session"}}'""",),
    )
    for xcorr, recs in by_session.items():
        for rec in recs:
            payload = _payload_dict(rec)
            nvext = payload.get("nvext")
            assert isinstance(nvext, dict), (
                f"session {xcorr} turn {rec.metadata.turn_index}: "
                f"nvext not a dict; payload keys={list(payload)}"
            )
            assert nvext.get("session_id") == xcorr, (
                f"session {xcorr} turn {rec.metadata.turn_index}: "
                f"nvext.session_id={nvext.get('session_id')!r}"
            )
            assert nvext.get("session_control") is None, (
                f"session {xcorr}: plain nested write must not add session_control"
            )


# --- Case 7: config-error cases (rule 1 / 2 / 6), fail BEFORE any request ---


@pytest.mark.integration
@pytest.mark.asyncio
@pytest.mark.parametrize(
    "modes, opts, expected_substrs",
    [
        param(
            ["custom"],
            ("""'headers={"X-Request-ID":"session"}'""",),
            ("x-request-id", "reserved"),
            id="rule1_reserved_header",
        ),
        param(
            # Stacked presets require namespaced opts; `custom` writes body path
            # ("nvext",) while dynamo_nvext writes ("nvext","session_control") --
            # ("nvext",) is a prefix of the latter, tripping prefix-freedom.
            ["dynamo_nvext", "custom"],
            ("""'custom.body={"nvext":"session"}'""",),
            # The conflict message names both dotted write targets.
            ("entry[", "nvext", "overlaps", "nvext.session_control"),
            id="rule2_prefix_freedom",
        ),
        param(
            ["url_index_header"],
            (),
            ("url_index", "only one --url"),
            id="rule6_url_index_single_url",
        ),
    ],
)  # fmt: skip
async def test_session_routing_config_error_fails_before_request(
    cli: AIPerfCLI,
    aiperf_mock_server: AIPerfMockServer,
    modes: list[str],
    opts: tuple[str, ...],
    expected_substrs: tuple[str, ...],
):
    """Each misconfiguration is rejected at config load, before any request
    reaches the mock server (so no raw-export file materializes)."""
    # Single --url satisfies the required arg; rules 1/2 never consult it and
    # rule 6 fires precisely because only one URL is configured.
    result = await cli.run(
        _build_cmd([aiperf_mock_server.url], modes=modes, opts=opts),
        timeout=120.0,
        assert_success=False,
    )
    combined = f"{result.stdout or ''}\n{result.stderr or ''}\n{result.log or ''}"
    assert result.exit_code != 0, f"expected non-zero exit; {combined[-2000:]}"
    # The error surfaces inside a Rich panel that word-wraps and inserts box
    # borders, so a message like "only one --url is configured" is split across
    # lines. Strip box-drawing glyphs (U+2500-U+257F) and collapse whitespace
    # so the expected substrings match regardless of terminal wrapping.
    normalized = re.sub(r"[─-╿]", " ", combined)
    lowered = re.sub(r"\s+", " ", normalized).lower()
    for substr in expected_substrs:
        assert substr.lower() in lowered, (
            f"missing {substr!r} in output; {combined[-2000:]}"
        )
    assert not result.raw_records, "config error must not reach the wire"
