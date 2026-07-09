# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Per-preset emission contracts: exact wire output for every registered preset."""

from __future__ import annotations

import pytest
from pydantic import ValidationError
from pytest import param

from aiperf.workers.session_routing import (
    BodyEmitter,
    ClaudeCodeHeaders,
    Custom,
    DispatchFacts,
    DynamoHeaders,
    DynamoNvext,
    MissingTurnHeaderError,
    PlanEntry,
    SessionIdHeader,
    SessionRoutingEmitterError,
    SessionRoutingPreset,
    SglangSession,
    SmgRoutingKey,
    UrlIndexHeader,
    resolve_plan,
)
from tests.unit.workers.session_routing.test_facts_and_sources import make_facts

_PRESETS = {
    "dynamo_headers": DynamoHeaders,
    "dynamo_nvext": DynamoNvext,
    "smg_routing_key": SmgRoutingKey,
    "session_id_header": SessionIdHeader,
    "sglang_session": SglangSession,
    "url_index_header": UrlIndexHeader,
    "claude_code_headers": ClaudeCodeHeaders,
    "custom": Custom,
}


def _plan(preset: str, opts: dict | None = None):
    return resolve_plan(
        [PlanEntry(preset=preset, opts=opts or {})], preset_lookup=_PRESETS.get
    )


def depth1_facts(**overrides) -> DispatchFacts:
    defaults = dict(
        x_correlation_id="child-1",
        parent_correlation_id="sess-1",
        root_correlation_id="sess-1",
    )
    defaults.update(overrides)
    return make_facts(**defaults)


def depth2_facts(**overrides) -> DispatchFacts:
    defaults = dict(
        x_correlation_id="grand-1",
        parent_correlation_id="child-1",
        root_correlation_id="sess-1",
    )
    defaults.update(overrides)
    return make_facts(**defaults)


@pytest.mark.parametrize(
    "preset, opts, facts, expected_headers",
    [
        param("dynamo_headers", None, make_facts(), {"X-Dynamo-Session-ID": "sess-1"}, id="dynamo_headers_root_session_only"),
        param("dynamo_headers", None, depth2_facts(), {"X-Dynamo-Session-ID": "grand-1", "X-Dynamo-Parent-Session-ID": "child-1"}, id="dynamo_headers_depth2_adds_parent"),
        param("smg_routing_key", None, make_facts(), {"X-SMG-Routing-Key": "sess-1"}, id="smg_default_source_root"),
        param("smg_routing_key", None, depth2_facts(), {"X-SMG-Routing-Key": "grand-1"}, id="smg_default_source_depth2"),
        param("smg_routing_key", {"source": "header:x-src", "missing": "skip"}, make_facts(), {}, id="smg_missing_skip_drops_header"),
        param("session_id_header", None, make_facts(), {"X-Session-ID": "sess-1"}, id="session_id_default_name"),
        param("session_id_header", {"header_name": "X-Affinity"}, depth2_facts(), {"X-Affinity": "grand-1"}, id="session_id_custom_name"),
        param("url_index_header", None, make_facts(), {"X-URL-Index": "0"}, id="url_index_default_zero"),
        param("url_index_header", None, make_facts(url_index=3), {"X-URL-Index": "3"}, id="url_index_stringified"),
        param("url_index_header", {"header_name": "X-Slot"}, depth2_facts(url_index=7), {"X-Slot": "7"}, id="url_index_custom_name"),
        param("claude_code_headers", None, make_facts(), {"x-claude-code-session-id": "sess-1"}, id="claude_code_root_session_only"),
        param("claude_code_headers", None, depth1_facts(), {"x-claude-code-session-id": "sess-1", "x-claude-code-agent-id": "child-1"}, id="claude_code_depth1_no_parent"),
        param("claude_code_headers", None, depth2_facts(), {"x-claude-code-session-id": "sess-1", "x-claude-code-agent-id": "grand-1", "x-claude-code-parent-agent-id": "child-1"}, id="claude_code_depth2_all_three"),
        param(
            "claude_code_headers",
            {"session_header_name": "X-Sess", "agent_header_name": "X-Agent", "parent_header_name": "X-Parent-Agent"},
            depth2_facts(),
            {"X-Sess": "sess-1", "X-Agent": "grand-1", "X-Parent-Agent": "child-1"},
            id="claude_code_custom_names",
        ),
        param("custom", {"headers": {"X-Affinity": "session", "X-Tree-ID": "root"}}, depth2_facts(), {"X-Affinity": "grand-1", "X-Tree-ID": "sess-1"}, id="custom_headers_map_each_assignment"),
        param("custom", {"headers": {"X-S": "session", "X-P": "parent"}}, make_facts(), {"X-S": "sess-1"}, id="custom_parent_source_skips_on_roots"),
        param("custom", {"headers": {"X-S": "session", "X-P": "parent"}}, depth1_facts(), {"X-S": "child-1", "X-P": "sess-1"}, id="custom_parent_source_emits_on_children"),
    ],
)  # fmt: skip
def test_header_emission_matrix(preset, opts, facts, expected_headers):
    assert _plan(preset, opts).headers(facts) == expected_headers


@pytest.mark.parametrize(
    "preset, opts, expected",
    [
        param("dynamo_headers", None, False, id="dynamo_headers"),
        param("dynamo_nvext", None, True, id="dynamo_nvext"),
        param("smg_routing_key", None, False, id="smg_routing_key"),
        param("sglang_session", None, True, id="sglang_session"),
        param("url_index_header", None, False, id="url_index_header"),
        param("custom", {"headers": {"X-Affinity": "session"}}, False, id="custom_headers_only"),
        param("custom", {"body": {"nvext": {"session_id": "session"}}}, True, id="custom_body"),
    ],
)  # fmt: skip
def test_mutates_body(preset, opts, expected):
    assert _plan(preset, opts).mutates_body is expected


@pytest.mark.parametrize(
    "options_call, match",
    [
        param(lambda: DynamoHeaders.Options(anything="x"), None, id="dynamo_headers_rejects_any_opt"),
        param(lambda: DynamoNvext.Options(timeout_seconds=0), None, id="dynamo_nvext_timeout_lower_bound"),
        param(lambda: DynamoNvext.Options(scope="tree"), None, id="dynamo_nvext_invalid_scope"),
        param(lambda: SmgRoutingKey.Options(source="session", missing="skip"), "header:", id="smg_missing_requires_header_source"),
        param(lambda: SmgRoutingKey.Options(source="bogus"), "valid sources", id="smg_unknown_source"),
        param(lambda: SmgRoutingKey.Options(source="header:x-src", missing="ignore"), None, id="smg_invalid_missing_value"),
        param(lambda: SglangSession.Options(missing="skip"), "header:", id="sglang_missing_requires_header_source"),
        param(lambda: Custom.Options(), "at least one", id="custom_zero_assignments"),
        param(lambda: Custom.Options(body={"nvext": {}}), "at least one", id="custom_empty_nested_mapping"),
        param(lambda: Custom.Options(body={"nvext": {"timeout": 300}}), "nvext.timeout", id="custom_non_string_body_leaf"),
        param(lambda: Custom.Options(headers={"X-A": "bogus"}), "valid sources", id="custom_unknown_source_in_headers"),
        param(lambda: Custom.Options(body={"a": "bogus"}), "valid sources", id="custom_unknown_source_in_body"),
    ],
)  # fmt: skip
def test_invalid_options_rejected(options_call, match):
    with pytest.raises(ValidationError, match=match):
        options_call()


class TestDynamoNvext:
    @pytest.mark.parametrize(
        "opts, facts, expected_sc",
        [
            param(None, make_facts(), {"session_id": "sess-1", "action": "bind", "timeout": 300}, id="non_final_binds_default_timeout"),
            param({"timeout_seconds": 123}, make_facts(is_final_turn=True), {"session_id": "sess-1", "action": "close"}, id="final_closes_without_timeout"),
            param({"scope": "lineage", "timeout_seconds": 77}, depth2_facts(is_final_turn=True), {"session_id": "sess-1", "action": "bind", "timeout": 77}, id="lineage_depth2_binds_root_id"),
            param({"scope": "lineage"}, depth2_facts(is_final_turn=True, is_tree_final=True), {"session_id": "sess-1", "action": "close"}, id="lineage_closes_only_on_tree_final"),
        ],
    )  # fmt: skip
    def test_session_control_emission(self, opts, facts, expected_sc):
        plan = _plan("dynamo_nvext", opts)
        merged = plan.transform_body({"messages": []}, facts)
        assert merged["nvext"]["session_control"] == expected_sc
        assert plan.headers(facts) == {}

    def test_options_defaults(self):
        options = DynamoNvext.Options()
        assert options.timeout_seconds == 300
        assert options.scope == "conversation"


class TestSmgRoutingKey:
    def test_header_source_reads_recorded_turn_header(self):
        plan = _plan("smg_routing_key", {"source": "header:x-src"})
        facts = make_facts(turn_extra_headers={"X-Src": "recorded-key"})
        assert plan.headers(facts) == {"X-SMG-Routing-Key": "recorded-key"}
        assert plan.reads_turn_headers is True


@pytest.mark.parametrize(
    "preset, opts",
    [
        # The plan boundary wraps the emitter fault with entry attribution;
        # the missing=error semantic is preserved as the cause.
        param("smg_routing_key", {"source": "header:x-src"}, id="smg_routing_key"),
        param("custom", {"headers": {"X-A": "header:x-src"}}, id="custom_header_source_always_missing_error"),
    ],
)  # fmt: skip
def test_header_source_missing_error_raises(preset, opts):
    plan = _plan(preset, opts)
    with pytest.raises(SessionRoutingEmitterError, match="missing=error") as exc:
        plan.headers(make_facts())
    assert isinstance(exc.value.__cause__, MissingTurnHeaderError)


class TestSglangSession:
    @pytest.mark.parametrize(
        "opts, payload, facts, expected_body",
        [
            param(None, {"messages": []}, make_facts(), {"messages": [], "session_id": "sess-1"}, id="default_writes_session_id_field"),
            # No dot-descent: field="a.b" writes the top-level key "a.b".
            param({"field": "a.b"}, {}, make_facts(), {"a.b": "sess-1"}, id="dotted_field_is_a_literal_key"),
            param({"source": "header:x-sid", "missing": "skip"}, {}, make_facts(), {}, id="header_source_missing_skip"),
            param({"source": "header:x-sid", "missing": "skip"}, {}, make_facts(turn_extra_headers={"x-sid": "rec-1"}), {"session_id": "rec-1"}, id="header_source_present"),
            param(None, {}, depth2_facts(), {"session_id": "grand-1"}, id="depth2_uses_own_session_id"),
        ],
    )  # fmt: skip
    def test_transform_body(self, opts, payload, facts, expected_body):
        assert (
            _plan("sglang_session", opts).transform_body(payload, facts)
            == expected_body
        )


class TestClaudeCodeHeaders:
    def test_default_header_names(self):
        options = ClaudeCodeHeaders.Options()
        assert options.session_header_name == "x-claude-code-session-id"
        assert options.agent_header_name == "x-claude-code-agent-id"
        assert options.parent_header_name == "x-claude-code-parent-agent-id"


class TestCustom:
    def test_nested_body_map_flattens_to_paths(self):
        preset = Custom(Custom.Options(body={"nvext": {"session_id": "session"}}))
        emitters = preset.emitters()
        assert emitters == [BodyEmitter(("nvext", "session_id"), "session")]

    @pytest.mark.parametrize(
        "opts, payload, expected_body",
        [
            param({"body": {"nvext": {"session_id": "session"}}}, {"nvext": {"keep": 1}}, {"nvext": {"keep": 1, "session_id": "sess-1"}}, id="nested_body_applies_at_path"),
            param({"body": {"session_id": "session"}}, {}, {"session_id": "sess-1"}, id="string_leaf_at_top_level"),
        ],
    )  # fmt: skip
    def test_body_transform(self, opts, payload, expected_body):
        assert (
            _plan("custom", opts).transform_body(payload, make_facts()) == expected_body
        )

    def test_json_string_opts_parsed(self):
        """CLI --session-routing-opt values are strings; JSON is accepted."""
        options = Custom.Options(headers='{"X-A": "session"}')
        assert options.headers == {"X-A": "session"}


class TestPresetBase:
    def test_default_options_and_hooks(self):
        preset = SessionRoutingPreset(SessionRoutingPreset.Options())
        assert preset.emitters() == []
        assert preset.on_session_end("sess-1") is None

    @pytest.mark.parametrize(
        "name, cls",
        [param(name, cls, id=name) for name, cls in _PRESETS.items()],
    )  # fmt: skip
    def test_every_preset_subclasses_base(self, name, cls):
        assert issubclass(cls, SessionRoutingPreset)
