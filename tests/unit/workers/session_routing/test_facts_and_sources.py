# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
import dataclasses

import pytest
from pytest import param

from aiperf.workers.session_routing import (
    DispatchFacts,
    is_header_source,
    resolve_source,
)


def make_facts(**overrides) -> DispatchFacts:
    defaults = dict(
        x_correlation_id="sess-1",
        parent_correlation_id=None,
        root_correlation_id="sess-1",
        is_final_turn=False,
        is_parent_final=None,
        is_tree_final=False,
        url_index=0,
        turn_extra_headers={},
    )
    defaults.update(overrides)
    return DispatchFacts(**defaults)


def test_dispatch_facts_is_frozen():
    facts = make_facts()
    with pytest.raises(dataclasses.FrozenInstanceError):
        facts.x_correlation_id = "other"


@pytest.mark.parametrize(
    "spec, facts_kwargs, expected",
    [
        param("session", {}, "sess-1", id="session"),
        param("root", {}, "sess-1", id="root_of_root_is_self"),
        param("parent", {}, None, id="parent_none_for_root"),
        param("parent", {"x_correlation_id": "c", "parent_correlation_id": "sess-1"}, "sess-1", id="parent_of_child"),
        param("url_index", {"url_index": 3}, "3", id="url_index_stringified"),
        param("agent", {}, None, id="agent_none_on_root"),
        param("agent", {"x_correlation_id": "c", "parent_correlation_id": "sess-1"}, "c", id="agent_on_child"),
        param("agent_parent", {"x_correlation_id": "c", "parent_correlation_id": "sess-1"}, None, id="agent_parent_none_depth1"),
        param(
            "agent_parent",
            {"x_correlation_id": "g", "parent_correlation_id": "c", "root_correlation_id": "sess-1"},
            "c",
            id="agent_parent_depth2",
        ),
        param("header:x-src-id", {"turn_extra_headers": {"X-Src-Id": "rec-9"}}, "rec-9", id="header_case_insensitive"),
        param("header:x-src-id", {}, None, id="header_absent_returns_none"),
    ],
)  # fmt: skip
def test_source_resolution(spec, facts_kwargs, expected):
    assert resolve_source(spec)(make_facts(**facts_kwargs)) == expected


@pytest.mark.parametrize(
    "spec, match",
    [
        param("bogus", r"session.*header:<name>", id="unknown_lists_registry_and_header_form"),
        param("header:", "header name", id="empty_header_spec_rejected"),
    ],
)  # fmt: skip
def test_invalid_source_spec_raises(spec, match):
    with pytest.raises(ValueError, match=match):
        resolve_source(spec)


@pytest.mark.parametrize(
    "spec, expected",
    [
        param("header:x", True, id="header_prefixed"),
        param("session", False, id="builtin_source"),
    ],
)  # fmt: skip
def test_is_header_source(spec, expected):
    assert is_header_source(spec) is expected
