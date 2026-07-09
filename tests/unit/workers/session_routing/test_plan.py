# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Plan resolution + validation: prefix-freedom, header hygiene, composition."""

from __future__ import annotations

import asyncio
import re

import pytest
from pydantic import ConfigDict, Field
from pytest import param

from aiperf.common.models import AIPerfBaseModel
from aiperf.workers.session_routing import (
    BodyEmitter,
    BodyTransformDiagnostics,
    HeaderEmitter,
    NvextSessionControlEmitter,
    PlanEntry,
    SessionRoutingConfigError,
    SessionRoutingEmitterError,
    resolve_plan,
)
from tests.unit.workers.session_routing.test_facts_and_sources import make_facts


class _NoOpts(AIPerfBaseModel):
    model_config = ConfigDict(extra="forbid")


class _OneOpt(AIPerfBaseModel):
    model_config = ConfigDict(extra="forbid")
    enabled: bool = Field(default=True, description="toggle")


def _fake_preset(emitters_list, *, options_cls=_NoOpts, on_session_end=None):
    """Build a fake preset class exposing the Task-4 duck-type contract."""

    class _Fake:
        Options = options_cls

        def __init__(self, options) -> None:
            self.options = options

        def emitters(self) -> list:
            return list(emitters_list)

    if on_session_end is not None:
        _Fake.on_session_end = on_session_end
    return _Fake


def _hdr(name: str, source: str, **kwargs):
    """Fake preset with a single HeaderEmitter."""
    return _fake_preset([HeaderEmitter(name, source, **kwargs)])


def _body(path: tuple[str, ...], source: str):
    """Fake preset with a single BodyEmitter."""
    return _fake_preset([BodyEmitter(path, source)])


@pytest.mark.parametrize(
    "fakes, entries, expected_substrings",
    [
        param(
            {"a": _hdr("X-Foo", "session")},
            [PlanEntry(preset="a"), PlanEntry(preset="a")],
            ["entry[0] (a)", "entry[1] (a)"],
            id="duplicate_preset",
        ),
        param(
            {"rid": _hdr("X-Request-ID", "session")},
            [PlanEntry(preset="rid")],
            ["x-request-id"],
            id="reserved_header",
        ),
        param(
            {"up": _hdr("X-Foo", "session"), "lo": _hdr("x-foo", "root")},
            [PlanEntry(preset="up"), PlanEntry(preset="lo")],
            ["entry[0] (up)", "entry[1] (lo)", "'x-foo'"],
            id="header_collision_case_insensitive",
        ),
        param(
            {"root": _body(("nvext",), "session"), "child": _body(("nvext", "session_id"), "root")},
            [PlanEntry(preset="root"), PlanEntry(preset="child")],
            ["entry[0] (root)", "entry[1] (child)", "'nvext'", "'nvext.session_id'"],
            id="body_prefix_conflict",
        ),
        param(
            {"p": _fake_preset([HeaderEmitter("X-Foo", "session"), HeaderEmitter("x-foo", "root")])},
            [PlanEntry(preset="p")],
            ["header conflict", "entry[0] (p)", "'x-foo'"],
            id="intra_entry_header_case_conflict",
        ),
        param(
            {"p": _fake_preset([BodyEmitter(("nvext",), "session"), BodyEmitter(("nvext", "session_id"), "root")])},
            [PlanEntry(preset="p")],
            ["body path conflict", "entry[0] (p)", "'nvext'", "'nvext.session_id'"],
            id="intra_entry_body_prefix_conflict",
        ),
        param(
            {"a": _body(("nvext", "sid"), "session"), "b": _body(("nvext", "sid"), "root")},
            [PlanEntry(preset="a"), PlanEntry(preset="b")],
            ["both write", "'nvext.sid'"],
            id="exact_body_path_conflict_names_the_path",
        ),
        param(
            {"p": _fake_preset([HeaderEmitter("X-Foo", "session")], options_cls=_OneOpt)},
            [PlanEntry(preset="p", opts={"bogus": 1})],
            ["entry[0] (p)"],
            id="unknown_opt",
        ),
        param(
            {"p": _hdr("X-Foo", "session", missing="bogus")},
            [PlanEntry(preset="p")],
            ["missing"],
            id="invalid_missing_value",
        ),
    ],
)  # fmt: skip
def test_resolve_plan_config_errors(fakes, entries, expected_substrings):
    with pytest.raises(SessionRoutingConfigError) as exc:
        resolve_plan(entries, preset_lookup=fakes.get)
    for substring in expected_substrings:
        assert substring in str(exc.value)


@pytest.mark.parametrize(
    "fakes, entries",
    [
        param(
            {"p": _fake_preset([BodyEmitter(("nvext", "a"), "session"), BodyEmitter(("nvext", "b"), "root")])},
            [PlanEntry(preset="p")],
            id="intra_entry",
        ),
        param(
            {"a": _body(("nvext", "a"), "session"), "b": _body(("nvext", "b"), "root")},
            [PlanEntry(preset="a"), PlanEntry(preset="b")],
            id="cross_entry",
        ),
    ],
)  # fmt: skip
def test_disjoint_body_paths_compose(fakes, entries):
    plan = resolve_plan(entries, preset_lookup=fakes.get)
    body = plan.transform_body({}, make_facts())
    assert body == {"nvext": {"a": "sess-1", "b": "sess-1"}}


def test_mutates_body_and_reads_turn_headers_computed():
    fakes = {
        "hdr": _hdr("X-Src", "header:x-src-id"),
        "body": _body(("nvext", "sid"), "session"),
    }
    plan = resolve_plan(
        [PlanEntry(preset="hdr"), PlanEntry(preset="body")], preset_lookup=fakes.get
    )
    assert plan.mutates_body is True
    assert plan.reads_turn_headers is True

    header_only = resolve_plan(
        [PlanEntry(preset="hdr")],
        preset_lookup={"hdr": _hdr("X-Src", "session")}.get,
    )
    assert header_only.mutates_body is False
    assert header_only.reads_turn_headers is False


@pytest.mark.parametrize(
    "source, payload, expected_leaf, overwrites, non_dict_replacements",
    [
        param("session", {"nvext": {"sid": "dataset-value"}}, "sess-1", [("entry[0] (p)", "nvext.sid")], [], id="dataset_value_overwrite_flagged"),
        param("session", {"nvext": "opaque-string"}, "sess-1", [], [("entry[0] (p)", "nvext.sid")], id="non_dict_intermediate_flagged"),
        param("session", {"model": "m"}, "sess-1", [], [], id="fresh_write_no_flags"),
        # An explicit None leaf is not a dataset value: replacing it is silent.
        param("session", {"nvext": {"sid": None}}, "sess-1", [], [], id="none_leaf_not_flagged"),
        # A None-source skip writes nothing, so nothing is flagged even when
        # the leaf already carries a value.
        param("parent", {"nvext": {"sid": "dataset-value"}}, "dataset-value", [], [], id="skipped_emitter_no_flags"),
    ],
)  # fmt: skip
def test_transform_body_diagnostics(
    source, payload, expected_leaf, overwrites, non_dict_replacements
):
    fakes = {"p": _body(("nvext", "sid"), source)}
    plan = resolve_plan([PlanEntry(preset="p")], preset_lookup=fakes.get)
    diagnostics = BodyTransformDiagnostics()
    body = plan.transform_body(payload, make_facts(), diagnostics)
    assert body["nvext"]["sid"] == expected_leaf
    assert diagnostics.overwrites == overwrites
    assert diagnostics.non_dict_replacements == non_dict_replacements


def test_transform_body_without_diagnostics_unchanged():
    """The diagnostics argument is optional; omitting it keeps the old shape."""
    fakes = {"p": _body(("nvext", "sid"), "session")}
    plan = resolve_plan([PlanEntry(preset="p")], preset_lookup=fakes.get)
    body = plan.transform_body({"nvext": {"sid": "dataset-value"}}, make_facts())
    assert body["nvext"]["sid"] == "sess-1"


def test_headers_merges_all_emitters():
    fakes = {"a": _hdr("X-Session", "session"), "b": _hdr("X-Root", "root")}
    plan = resolve_plan(
        [PlanEntry(preset="a"), PlanEntry(preset="b")], preset_lookup=fakes.get
    )
    assert plan.headers(make_facts()) == {"X-Session": "sess-1", "X-Root": "sess-1"}


def test_transform_body_applies_in_entry_order():
    fakes = {
        "sc": _fake_preset([NvextSessionControlEmitter(timeout_seconds=30)]),
        "sid": _body(("nvext", "sid"), "session"),
    }
    plan = resolve_plan(
        [PlanEntry(preset="sc"), PlanEntry(preset="sid")], preset_lookup=fakes.get
    )
    body = plan.transform_body({}, make_facts(is_final_turn=True))
    assert body["nvext"]["sid"] == "sess-1"
    assert body["nvext"]["session_control"]["action"] == "close"


def test_notify_session_end_runs_sync_and_collects_labeled_coroutines():
    calls: list[str] = []

    def sync_hook(self, x_correlation_id: str) -> None:
        calls.append(f"sync:{x_correlation_id}")

    async def async_hook(self, x_correlation_id: str) -> None:
        calls.append(f"async:{x_correlation_id}")

    fakes = {
        "s": _fake_preset([HeaderEmitter("X-A", "session")], on_session_end=sync_hook),
        "a": _fake_preset([HeaderEmitter("X-B", "root")], on_session_end=async_hook),
    }
    plan = resolve_plan(
        [PlanEntry(preset="s"), PlanEntry(preset="a")], preset_lookup=fakes.get
    )
    labeled = plan.notify_session_end("sess-9")
    assert calls == ["sync:sess-9"]
    assert [label for label, _ in labeled] == ["entry[1] (a)"]
    asyncio.run(labeled[0][1])
    assert calls == ["sync:sess-9", "async:sess-9"]


@pytest.mark.parametrize(
    "fakes, entries, phase, entry_label",
    [
        # Empty turn headers + missing=error (the emitter default) raises; the
        # fault surfaces as a RuntimeError naming the owning entry and phase.
        param(
            {"a": _hdr("X-A", "session"), "b": _hdr("X-Src", "header:x-src-id")},
            [PlanEntry(preset="a"), PlanEntry(preset="b")],
            "headers()",
            "entry[1] (b)",
            id="headers_phase",
        ),
        param(
            {"p": _body(("nvext", "sid"), "header:x-src-id")},
            [PlanEntry(preset="p")],
            "transform_body()",
            "entry[0] (p)",
            id="transform_body_phase",
        ),
    ],
)  # fmt: skip
def test_emitter_error_attributed_to_entry(fakes, entries, phase, entry_label):
    plan = resolve_plan(entries, preset_lookup=fakes.get)
    with pytest.raises(SessionRoutingEmitterError, match=re.escape(entry_label)) as exc:
        if phase == "headers()":
            plan.headers(make_facts())
        else:
            plan.transform_body({}, make_facts())
    assert phase in str(exc.value)
    assert isinstance(exc.value, RuntimeError)


def test_header_names_and_owner_lowercased():
    """header_names exposes the plan's header write-set (lowercased) without
    reaching into emitter internals; header_owner attributes any casing."""
    fakes = {
        "hdr": _hdr("X-Session", "session"),
        "body": _body(("nvext", "sid"), "session"),
    }
    plan = resolve_plan(
        [PlanEntry(preset="hdr"), PlanEntry(preset="body")], preset_lookup=fakes.get
    )
    assert plan.header_names == frozenset({"x-session"})
    assert plan.header_owner("X-SESSION") == "entry[0] (hdr)"
    assert plan.header_owner("x-other") is None
