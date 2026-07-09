# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Stacked --session-routing config forms and the --session-routing-opt key grammar.

Locks the binding grammar for the plan-list config surface:

- accepted ``session_routing`` YAML/CLI forms (bare string, list of names,
  single-key mappings, trailing-colon ``None`` opts, forgotten-dash error);
- opt-key resolution (reserved ``headers.``/``body.`` custom assignments,
  ``<preset>.<key>`` namespacing, bare keys binding to the sole preset);
- cross-channel duplicate detection (bare + namespaced, flat + inline);
- endpoint-context validations (single-URL ``url_index``, multipart body);
- plan-vs-``--header`` case-insensitive collisions (config-load error);
- canonical-plan round-trips through ``model_dump``.
"""

import re

import pytest
from pytest import param

from aiperf.common.config import EndpointConfig, InputConfig, PlanEntry, UserConfig

_URL_INDEX_RECIPE = re.escape("repeat the URL once per rank: --url U --url U ...")


def _config(**kwargs) -> EndpointConfig:
    return EndpointConfig(model_names=["test-model"], **kwargs)


def _user_config(*, headers=None, **endpoint_kwargs) -> UserConfig:
    return UserConfig(
        endpoint=_config(**endpoint_kwargs),
        input=InputConfig(headers=headers),
    )


def _entry(preset: str, **opts) -> PlanEntry:
    return PlanEntry(preset=preset, opts=opts)


class TestSessionRoutingAcceptedForms:
    """Spec A: accepted --session-routing / session_routing shapes."""

    def test_default_off_empty_plan(self):
        config = _config()
        assert config.session_routing is None
        assert config.session_routing_plan == []

    @pytest.mark.parametrize(
        "session_routing, expected_plan",
        [
            param("dynamo_headers", [_entry("dynamo_headers")], id="bare_string_is_one_entry_list"),
            param(["dynamo_headers", "smg_routing_key"],
                  [_entry("dynamo_headers"), _entry("smg_routing_key")], id="list_of_names_preserves_order"),
            param([{"dynamo_nvext": {"timeout_seconds": 600}}],
                  [_entry("dynamo_nvext", timeout_seconds=600)], id="single_key_mapping_carries_opts"),
            # YAML `- smg_routing_key:` parses as {name: None}; treated as {}.
            param([{"smg_routing_key": None}], [_entry("smg_routing_key")],
                  id="trailing_colon_none_opts_normalizes_to_empty"),
            param(["dynamo_headers", {"dynamo_nvext": {"timeout_seconds": 60}}],
                  [_entry("dynamo_headers"), _entry("dynamo_nvext", timeout_seconds=60)],
                  id="mixed_names_and_mappings"),
            param(["dynamo_headers", {"sglang_session": {"field": "skey"}}],
                  [_entry("dynamo_headers"), _entry("sglang_session", field="skey")],
                  id="stacked_presets_resolve_disjoint_plan"),
        ],
    )  # fmt: skip
    def test_accepted_form_resolves_expected_plan(self, session_routing, expected_plan):
        assert (
            _config(session_routing=session_routing).session_routing_plan
            == expected_plan
        )

    def test_inline_opts_canonicalized_to_typed_values(self):
        config = _config(session_routing=[{"dynamo_nvext": {"timeout_seconds": "600"}}])
        assert config.session_routing_plan[0].opts == {"timeout_seconds": 600}
        assert isinstance(config.session_routing_plan[0].opts["timeout_seconds"], int)

    @pytest.mark.parametrize(
        "session_routing, match",
        [
            # A YAML forgotten dash folds two presets into one mapping item.
            param([{"dynamo_headers": None, "smg_routing_key": None}], r"forget a '-'",
                  id="multi_key_mapping_suggests_missing_dash"),
            param([{"dynamo_nvext": 5}], "opts must be a mapping", id="non_mapping_opts"),
            param(["dynamo_headers", "dynamo_headers"], "duplicate preset", id="duplicate_preset"),
            param("not_a_preset", "not found", id="unknown_preset_with_available_list"),
            # Cross-emitter invariants (header conflicts) fail at config time.
            param(["smg_routing_key", {"custom": {"headers": {"X-SMG-Routing-Key": "root"}}}],
                  "conflict", id="plan_validation_fires_at_config_load"),
        ],
    )  # fmt: skip
    def test_rejected_form(self, session_routing, match):
        with pytest.raises(ValueError, match=match):
            _config(session_routing=session_routing)


class TestSessionRoutingOptKeyGrammar:
    """Spec B: --session-routing-opt key resolution rules."""

    @pytest.mark.parametrize(
        "kwargs, expected_plan",
        [
            param({"session_routing": "custom", "session_routing_opt": ["headers.X-Affinity=session"]},
                  [_entry("custom", headers={"X-Affinity": "session"})], id="headers_prefix_routes_to_custom"),
            # headers. consumes exactly one segment; dots in the name survive.
            param({"session_routing": "custom", "session_routing_opt": ["headers.x-svc.route=session"]},
                  [_entry("custom", headers={"x-svc.route": "session"})],
                  id="headers_prefix_dotted_header_name_verbatim"),
            param({"session_routing": "custom", "session_routing_opt": ["body.nvext.session_id=session"]},
                  [_entry("custom", body={"nvext": {"session_id": "session"}})], id="body_prefix_descends_dots"),
            param({"session_routing": "custom", "session_routing_opt": ["headers.X-A=session", "headers.X-B=root"]},
                  [_entry("custom", headers={"X-A": "session", "X-B": "root"})],
                  id="two_headers_assignments_merge"),
            param({"session_routing": "dynamo_nvext", "session_routing_opt": ["dynamo_nvext.timeout_seconds=600"]},
                  [_entry("dynamo_nvext", timeout_seconds=600)], id="namespaced_key_with_single_preset"),
            param({"session_routing": ["dynamo_nvext", "session_id_header"],
                   "session_routing_opt": ["dynamo_nvext.timeout_seconds=600", "session_id_header.header_name=X-A"]},
                  [_entry("dynamo_nvext", timeout_seconds=600), _entry("session_id_header", header_name="X-A")],
                  id="namespaced_keys_with_multiple_presets"),
            param({"session_routing": "dynamo_nvext", "session_routing_opt": ["timeout_seconds=600"]},
                  [_entry("dynamo_nvext", timeout_seconds=600)], id="bare_key_binds_to_sole_preset"),
            param({"session_routing": "custom", "session_routing_opt": ["headers.X-Src=header:x-source-id"]},
                  [_entry("custom", headers={"X-Src": "header:x-source-id"})], id="colons_in_value_are_inert"),
            param({"session_routing": "dynamo_nvext", "session_routing_opts": {"timeout_seconds": 600}},
                  [_entry("dynamo_nvext", timeout_seconds=600)], id="flat_opts_with_single_preset"),
            # Legacy channel precedence: --session-routing-opt overrides the
            # flat session_routing_opts dict for the same key (required so
            # canonicalized configs re-validate identically).
            param({"session_routing": "dynamo_nvext", "session_routing_opts": {"timeout_seconds": 5},
                   "session_routing_opt": ["timeout_seconds=600"]},
                  [_entry("dynamo_nvext", timeout_seconds=600)], id="cli_opt_wins_over_flat_same_key"),
        ],
    )  # fmt: skip
    def test_opt_key_resolves_expected_plan(self, kwargs, expected_plan):
        assert _config(**kwargs).session_routing_plan == expected_plan

    @pytest.mark.parametrize(
        "kwargs, match",
        [
            param({"session_routing": "dynamo_headers", "session_routing_opt": ["headers.X-A=session"]},
                  "'custom' is not among", id="headers_prefix_without_custom"),
            param({"session_routing": "dynamo_headers", "session_routing_opt": ["body.nvext.session_id=session"]},
                  "'custom' is not among", id="body_prefix_without_custom"),
            param({"session_routing": "custom", "session_routing_opt": ["headers.=session"]},
                  "header name", id="headers_prefix_requires_header_name"),
            param({"session_routing": "custom", "session_routing_opt": ["body.nvext..x=session"]},
                  "empty segment", id="body_prefix_rejects_empty_segment"),
            param({"session_routing": "dynamo_nvext", "session_routing_opt": ["dynamo_nvext.=600"]},
                  "option key", id="namespaced_key_requires_option_key"),
            param({"session_routing": ["dynamo_nvext", "session_id_header"],
                   "session_routing_opt": ["timeout_seconds=600"]},
                  r"dynamo_nvext.*session_id_header", id="bare_key_with_two_presets_lists_names"),
            # A namespaced key naming a real-but-unconfigured preset is a config
            # error pointing at the reserved custom-assignment forms, not a
            # baffling unknown-option failure.
            param({"session_routing": "custom",
                   "session_routing_opt": ["sglang_session.body.nvext.session_id=header:x-a"]},
                  r"sglang_session.*not configured", id="unconfigured_registry_preset_namespace"),
            param({"session_routing": "dynamo_nvext",
                   "session_routing_opt": ["timeout_seconds=1", "dynamo_nvext.timeout_seconds=2"]},
                  r"'timeout_seconds'.*'dynamo_nvext\.timeout_seconds'",
                  id="duplicate_via_bare_and_namespaced_names_both_spellings"),
            param({"session_routing": [{"dynamo_nvext": {"timeout_seconds": 5}}],
                   "session_routing_opts": {"timeout_seconds": 6}},
                  r"session_routing entry.*session_routing_opts",
                  id="duplicate_via_flat_and_inline_names_both_spellings"),
            param({"session_routing": [{"dynamo_nvext": {"timeout_seconds": 5}}],
                   "session_routing_opt": ["timeout_seconds=6"]},
                  r"session_routing entry", id="duplicate_via_inline_and_cli"),
            param({"session_routing": ["dynamo_headers", "session_id_header"],
                   "session_routing_opts": {"header_name": "X-A"}},
                  r"dynamo_headers.*session_id_header", id="flat_opts_with_two_presets_lists_names"),
            # Mixing the JSON headers= form and per-header headers.<name> keys
            # writes overlapping option paths from two spellings.
            param({"session_routing": "custom",
                   "session_routing_opt": ['headers={"X-A":"session"}', "headers.X-B=root"]},
                  r"headers", id="json_blob_and_reserved_prefix_conflict"),
            param({"session_routing_opt": ["timeout_seconds=600"]},
                  "--session-routing-opt requires", id="opts_without_presets"),
            param({"session_routing_opts": {"timeout_seconds": 600}},
                  "requires --session-routing", id="flat_opts_without_presets"),
        ],
    )  # fmt: skip
    def test_opt_key_rejected(self, kwargs, match):
        with pytest.raises(ValueError, match=match):
            _config(**kwargs)


class TestSessionRoutingEndpointContext:
    """Spec C: validations needing endpoint context (urls, content type)."""

    @pytest.mark.parametrize(
        "kwargs, expected_plan",
        [
            param({"session_routing": "url_index_header",
                   "urls": ["http://server1:8000", "http://server2:8000"]},
                  [_entry("url_index_header")], id="url_index_with_multiple_urls"),
            param({"session_routing": "dynamo_headers"}, [_entry("dynamo_headers")],
                  id="single_url_without_url_index"),
            param({"type": "video_generation", "request_content_type": "multipart/form-data",
                   "session_routing": "dynamo_headers"},
                  [_entry("dynamo_headers")], id="header_only_plan_with_multipart"),
        ],
    )  # fmt: skip
    def test_endpoint_context_accepted(self, kwargs, expected_plan):
        assert _config(**kwargs).session_routing_plan == expected_plan

    @pytest.mark.parametrize(
        "kwargs, match",
        [
            param({"session_routing": "url_index_header"}, _URL_INDEX_RECIPE,
                  id="url_index_with_single_url_names_recipe"),
            param({"session_routing": "custom", "session_routing_opt": ["headers.X-Rank=url_index"]},
                  _URL_INDEX_RECIPE, id="url_index_custom_source_with_single_url"),
            param({"type": "video_generation", "request_content_type": "multipart/form-data",
                   "session_routing": [{"sglang_session": None}]},
                  "multipart", id="body_mutating_plan_with_multipart"),
        ],
    )  # fmt: skip
    def test_endpoint_context_rejected(self, kwargs, match):
        with pytest.raises(ValueError, match=match):
            _config(**kwargs)


class TestSessionRoutingUserHeaderCollision:
    """Spec 5.2 v3: a plan-emitted header colliding case-insensitively with a
    user-configured --header is a config-load error (the case-sensitive header
    merge chain would put both case-variants on the wire with different
    values)."""

    @pytest.mark.parametrize(
        "headers, expected_substrs",
        [
            param({"X-Session-ID": "static-value"},
                  ["entry[0] (session_id_header)", "X-Session-ID", "--header", "case-variants"],
                  id="exact_case_collision_names_entry_and_header"),
            param({"x-session-id": "static-value"}, ["x-session-id"], id="case_variant_collision"),
        ],
    )  # fmt: skip
    def test_collision_rejected(self, headers, expected_substrs):
        with pytest.raises(ValueError) as exc:
            _user_config(session_routing="session_id_header", headers=headers)
        msg = str(exc.value)
        for substr in expected_substrs:
            assert substr in msg

    @pytest.mark.parametrize(
        "kwargs, expected_plan",
        [
            param({"session_routing": "session_id_header", "headers": {"X-Unrelated": "static-value"}},
                  [_entry("session_id_header")], id="non_colliding_header_with_plan"),
            param({"headers": {"X-Session-ID": "static-value"}}, [], id="user_headers_without_plan"),
        ],
    )  # fmt: skip
    def test_accepted(self, kwargs, expected_plan):
        assert _user_config(**kwargs).endpoint.session_routing_plan == expected_plan


class TestSessionRoutingRoundTrip:
    """Spec D: canonicalized configs re-validate to the identical plan."""

    @pytest.mark.parametrize(
        "kwargs",
        [
            param({"session_routing": "dynamo_nvext", "session_routing_opt": ["timeout_seconds=600"]},
                  id="single_mode_cli_opt"),
            param({"session_routing": "custom", "session_routing_opt": ['headers={"X-A":"session"}']},
                  id="custom_json_blob"),
            param({"session_routing": "custom",
                   "session_routing_opt": ["headers.X-A=session", "body.nvext.session_id=root"]},
                  id="custom_reserved_prefix"),
            param({"session_routing": ["dynamo_headers", {"dynamo_nvext": {"timeout_seconds": 60}}]},
                  id="stacked_inline_opts"),
            param({"session_routing": "dynamo_nvext", "session_routing_opts": {"timeout_seconds": 60}},
                  id="flat_opts"),
        ],
    )  # fmt: skip
    def test_model_dump_reconstruct_identical_plan(self, kwargs):
        config = _config(**kwargs)
        # exclude_unset: EndpointConfig has unrelated fields whose coherence
        # validators reject explicitly-passed defaults (wait_for_model_*).
        rebuilt = EndpointConfig(**config.model_dump(exclude_unset=True))
        assert rebuilt.session_routing_plan == config.session_routing_plan
