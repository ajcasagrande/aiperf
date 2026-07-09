# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Behavioral expectations ported from the single-mode plugins to emitter plans.

Preset-by-preset emission matrices live in
``tests/unit/workers/session_routing/test_presets.py``; this file keeps the
wire-shape contracts the legacy suite proved (nvext merge semantics, input
immutability) and the ``custom`` equivalents of the removed
``identity_headers`` mode.
"""

import pytest
from pydantic import ValidationError
from pytest import param

from aiperf.workers.session_routing import (
    Custom,
    DynamoNvextOptions,
    PlanEntry,
    SessionRoutingConfigError,
    resolve_plan,
)
from tests.unit.workers.session_routing.test_facts_and_sources import make_facts


def _plan(preset: str, opts: dict | None = None):
    """Resolve a one-preset plan through the REAL plugin registry."""
    return resolve_plan([PlanEntry(preset=preset, opts=opts or {})])


class TestDynamoNvextWireShapes:
    @pytest.mark.parametrize(
        "opts, facts, expected_sc",
        [
            param({"timeout_seconds": 123}, make_facts(), {"session_id": "sess-1", "action": "bind", "timeout": 123}, id="non_final_binds_with_timeout"),
            param(None, make_facts(is_final_turn=True), {"session_id": "sess-1", "action": "close"}, id="conversation_final_closes_without_timeout"),
            # Under scope=lineage, every session in the tree binds the ROOT's
            # correlation ID so the whole lineage co-locates; a child's own
            # final turn must NOT close the shared key.
            param(
                {"scope": "lineage", "timeout_seconds": 77},
                make_facts(x_correlation_id="child-1", parent_correlation_id="root-1", root_correlation_id="root-1", is_final_turn=True),
                {"session_id": "root-1", "action": "bind", "timeout": 77},
                id="lineage_child_binds_root_id",
            ),
            # A shared key must never be torn down while siblings may still
            # run: even the root's own final turn only binds unless the issuer
            # stamped the request provably-last for the whole tree.
            param({"scope": "lineage"}, make_facts(is_final_turn=True), {"session_id": "sess-1", "action": "bind", "timeout": 300}, id="lineage_root_final_turn_binds_not_closes"),
            param({"scope": "lineage"}, make_facts(root_correlation_id="root-1", is_final_turn=True, is_tree_final=True), {"session_id": "root-1", "action": "close"}, id="lineage_closes_only_on_tree_final"),
        ],
    )  # fmt: skip
    def test_session_control_wire_shape(self, opts, facts, expected_sc):
        plan = _plan("dynamo_nvext", opts)
        merged = plan.transform_body({"messages": []}, facts)
        assert merged["nvext"]["session_control"] == expected_sc
        assert plan.mutates_body is True

    def test_never_mutates_input_payload(self):
        nested_sc = {"existing": "keep"}
        nvext = {"trace": "keep", "session_control": nested_sc}
        payload = {"nvext": nvext}
        merged = _plan("dynamo_nvext").transform_body(payload, make_facts())
        assert payload == {
            "nvext": {"trace": "keep", "session_control": {"existing": "keep"}}
        }
        assert nvext == {"trace": "keep", "session_control": {"existing": "keep"}}
        assert merged is not payload
        assert merged["nvext"]["session_control"]["existing"] == "keep"

    def test_options_defaults(self):
        assert DynamoNvextOptions().timeout_seconds == 300

    @pytest.mark.parametrize(
        "options_kwargs",
        [
            param({"timeout_seconds": 0}, id="timeout_lower_bound"),
            param({"timeout_secs": 5}, id="unknown_key"),
            param({"scope": "tree"}, id="invalid_scope"),
        ],
    )  # fmt: skip
    def test_invalid_options_rejected(self, options_kwargs):
        with pytest.raises(ValidationError):
            DynamoNvextOptions(**options_kwargs)

    def test_plan_session_control_wins_over_dataset_shipped_keys(self):
        """Merge precedence: the plan's live session identity must override
        any session_control keys the dataset shipped, or a recorded
        session_id would leak into live routing."""
        payload = {
            "nvext": {
                "session_control": {
                    "session_id": "recorded-stale",
                    "action": "open",
                    "keep": "me",
                }
            }
        }
        merged = _plan("dynamo_nvext", {"timeout_seconds": 42}).transform_body(
            payload, make_facts()
        )
        sc = merged["nvext"]["session_control"]
        assert sc["session_id"] == "sess-1"
        assert sc["action"] == "bind"
        assert sc["timeout"] == 42
        assert sc["keep"] == "me"

    def test_nvext_present_without_session_control_preserved(self):
        merged = _plan("dynamo_nvext").transform_body(
            {"nvext": {"trace": "keep"}}, make_facts()
        )
        assert merged["nvext"]["trace"] == "keep"
        assert merged["nvext"]["session_control"]["action"] == "bind"

    def test_non_dict_nvext_replaced(self):
        """A malformed (non-dict) nvext value is replaced rather than crashed on."""
        merged = _plan("dynamo_nvext").transform_body({"nvext": "bogus"}, make_facts())
        assert merged["nvext"]["session_control"]["session_id"] == "sess-1"


class TestCustomReplacesIdentityHeaders:
    """The custom preset covers everything identity_headers used to do."""

    @pytest.mark.parametrize(
        "opts, facts, expected_headers",
        [
            param({"headers": {"X-Affinity": "session"}}, make_facts(), {"X-Affinity": "sess-1"}, id="single_session_header"),
            # One plan, N additive headers, same correlation-ID value on each
            # -- the layered-router topology (e.g. ingress LB + SMG).
            param(
                {"headers": {"X-Session-ID": "session", "X-SMG-Routing-Key": "session"}},
                make_facts(),
                {"X-Session-ID": "sess-1", "X-SMG-Routing-Key": "sess-1"},
                id="multiple_headers_same_value_layered_routers",
            ),
            param({"headers": {"X-S": "session", "X-P": "parent"}}, make_facts(), {"X-S": "sess-1"}, id="parent_tier_omitted_for_roots"),
            param(
                {"headers": {"X-S": "session", "X-P": "parent"}},
                make_facts(x_correlation_id="child-1", parent_correlation_id="sess-1"),
                {"X-S": "child-1", "X-P": "sess-1"},
                id="parent_tier_emitted_for_children",
            ),
            param(
                {"headers": {"X-Tree": "root"}},
                make_facts(x_correlation_id="child-1", parent_correlation_id="parent-1", root_correlation_id="root-1"),
                {"X-Tree": "root-1"},
                id="root_tier_whole_tree_affinity",
            ),
            # effective_root == x_corr for root sessions, so root-tier
            # affinity degrades gracefully on flat (non-tree) workloads.
            param({"headers": {"X-S": "session", "X-Tree": "root"}}, make_facts(), {"X-S": "sess-1", "X-Tree": "sess-1"}, id="root_tier_equals_session_for_roots"),
        ],
    )  # fmt: skip
    def test_header_emission(self, opts, facts, expected_headers):
        plan = _plan("custom", opts)
        assert plan.headers(facts) == expected_headers
        assert plan.mutates_body is False

    def test_dynamo_headers_preset_expressible(self):
        """The dynamo_headers preset semantics, spelled via custom."""
        generic = _plan(
            "custom",
            {
                "headers": {
                    "X-Dynamo-Session-ID": "session",
                    "X-Dynamo-Parent-Session-ID": "parent",
                }
            },
        )
        preset = _plan("dynamo_headers")
        for facts in (
            make_facts(),
            make_facts(x_correlation_id="child-1", parent_correlation_id="sess-1"),
        ):
            assert generic.headers(facts) == preset.headers(facts)

    @pytest.mark.parametrize(
        "options_kwargs, match",
        [
            param({}, "at least one", id="no_assignments_anywhere"),
            param({"header_name": "X-Affinity"}, None, id="unknown_opt"),
        ],
    )  # fmt: skip
    def test_invalid_options_rejected(self, options_kwargs, match):
        with pytest.raises(ValidationError, match=match):
            Custom.Options(**options_kwargs)

    def test_duplicate_name_rejected_case_insensitive(self):
        """'X-Affinity' and 'x-affinity' are one header on the wire; the plan
        rejects the silent-overwrite hazard identity_headers used to catch."""
        with pytest.raises(SessionRoutingConfigError, match="conflict"):
            _plan(
                "custom",
                {"headers": {"X-Affinity": "session", "x-affinity": "root"}},
            )

    @pytest.mark.parametrize(
        "bad_name",
        [
            param("X Foo", id="interior-space"),
            param("X:Foo", id="colon"),
            param("X-Foo\r\nX-Evil: 1", id="crlf-injection"),
            param("X-Foé", id="non-ascii"),
        ],
    )  # fmt: skip
    def test_non_token_header_names_rejected(self, bad_name):
        """Names must be RFC 9110 tokens; anything else fails at plan
        resolution instead of corrupting (or injecting into) the wire request."""
        with pytest.raises(SessionRoutingConfigError, match="RFC 9110"):
            _plan("custom", {"headers": {bad_name: "session"}})
