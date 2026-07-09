# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
import pytest
from pytest import param

from aiperf.workers.session_routing.emitters import (
    BodyEmitter,
    HeaderEmitter,
    MissingTurnHeaderError,
    NvextSessionControlEmitter,
    merge_at_path,
)
from tests.unit.workers.session_routing.test_facts_and_sources import make_facts


def test_merge_at_path_copy_on_write_preserves_siblings():
    payload = {"nvext": {"keep": 1}, "model": "m"}
    merged = merge_at_path(payload, ("nvext", "session_id"), "s-1")
    assert merged["nvext"] == {"keep": 1, "session_id": "s-1"}
    assert payload == {"nvext": {"keep": 1}, "model": "m"}  # input unmutated
    assert merged is not payload and merged["nvext"] is not payload["nvext"]


def test_merge_at_path_replaces_non_dict_intermediate():
    merged = merge_at_path({"nvext": "oops"}, ("nvext", "session_id"), "s-1")
    assert merged["nvext"] == {"session_id": "s-1"}


def test_header_emitter_skips_none_source():
    assert HeaderEmitter("X-Parent", "parent").emit(make_facts()) is None


def test_header_emitter_missing_error_for_header_source():
    with pytest.raises(MissingTurnHeaderError, match="x-src-id"):
        HeaderEmitter("X-Out", "header:x-src-id", missing="error").emit(make_facts())
    assert (
        HeaderEmitter("X-Out", "header:x-src-id", missing="skip").emit(make_facts())
        is None
    )


def test_body_emitter_writes_value():
    facts = make_facts()
    out = BodyEmitter(("session_id",), "session").apply({"model": "m"}, facts)
    assert out == {"model": "m", "session_id": "sess-1"}


@pytest.mark.parametrize(
    "emitter_kwargs, facts_kwargs, expected",
    [
        param(
            {},
            {"is_final_turn": False},
            {"session_id": "sess-1", "action": "bind", "timeout": 600},
            id="conversation_bind_on_non_final",
        ),
        param(
            {},
            {"is_final_turn": True},
            {"session_id": "sess-1", "action": "close"},
            id="conversation_close_on_final",
        ),
        param(
            {"scope": "lineage"},
            {
                "x_correlation_id": "child-1",
                "root_correlation_id": "root-1",
                "is_final_turn": True,
                "is_tree_final": False,
            },
            {"session_id": "root-1", "action": "bind", "timeout": 600},
            id="lineage_binds_root_id_ignores_final_turn",
        ),
        param(
            {"scope": "lineage"},
            {
                "x_correlation_id": "child-1",
                "root_correlation_id": "root-1",
                "is_tree_final": True,
            },
            {"session_id": "root-1", "action": "close"},
            id="lineage_closes_only_on_tree_final",
        ),
    ],
)  # fmt: skip
def test_nvext_session_control(emitter_kwargs, facts_kwargs, expected):
    e = NvextSessionControlEmitter(timeout_seconds=600, **emitter_kwargs)
    out = e.apply({}, make_facts(**facts_kwargs))
    assert out["nvext"]["session_control"] == expected


def test_nvext_merges_preexisting_nvext_without_mutating_input():
    e = NvextSessionControlEmitter(timeout_seconds=600)
    payload = {
        "nvext": {
            "trace": "keep",
            "session_control": {"session_id": "recorded-stale", "keep": "me"},
        }
    }
    out = e.apply(payload, make_facts())
    assert out["nvext"]["trace"] == "keep"  # unrelated sibling preserved
    sc = out["nvext"]["session_control"]
    assert sc["session_id"] == "sess-1"  # plugin identity wins
    assert sc["action"] == "bind"
    assert sc["timeout"] == 600
    assert sc["keep"] == "me"  # dataset-shipped extra key merged under
    assert payload == {
        "nvext": {
            "trace": "keep",
            "session_control": {"session_id": "recorded-stale", "keep": "me"},
        }
    }  # input unmutated


def test_nvext_invalid_scope_raises():
    with pytest.raises(ValueError, match="scope"):
        NvextSessionControlEmitter(timeout_seconds=600, scope="bogus")
