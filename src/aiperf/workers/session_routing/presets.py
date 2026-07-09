# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Session-routing presets: registered one-word emitter stacks.

A preset is a named, options-validated bundle of emitters. Presets carry no
per-request logic of their own -- everything on the wire is expressed as
:mod:`emitters` over :mod:`sources`, so ``resolve_plan`` can validate
cross-emitter invariants uniformly regardless of which presets are combined.

Contracts:
- ``__init__`` must be side-effect-free: plans resolve at three sites (config
  validation, dataset-manager gating, worker init).
- ``Options`` models set ``extra="forbid"`` so unknown opt keys fail fast.
- ``on_session_end`` fires strictly AFTER the session's last worker-side
  activity, on every terminal path, and MUST be idempotent. It may return an
  awaitable, which the caller schedules.
"""

from __future__ import annotations

from collections.abc import Awaitable
from typing import Annotated, Any, ClassVar, Literal

import orjson
from pydantic import BeforeValidator, ConfigDict, Field, model_validator
from typing_extensions import Self

from aiperf.common.models import AIPerfBaseModel
from aiperf.workers.session_routing.emitters import (
    BodyEmitter,
    HeaderEmitter,
    NvextSessionControlEmitter,
)
from aiperf.workers.session_routing.sources import is_header_source, resolve_source

Emitter = HeaderEmitter | BodyEmitter | NvextSessionControlEmitter


class EmptyRoutingOptions(AIPerfBaseModel):
    """Options model for parameterless presets; rejects every opt key."""

    model_config = ConfigDict(extra="forbid")


class SessionRoutingPreset:
    """Base for session-routing presets (``session_routing`` plugin category)."""

    Options: ClassVar[type[AIPerfBaseModel]] = EmptyRoutingOptions
    """Per-preset options model, populated from --session-routing-opt
    key=value pairs. Every Options model must set extra='forbid'."""

    def __init__(self, options: AIPerfBaseModel) -> None:
        self.options = options

    def emitters(self) -> list[Emitter]:
        """The emitters this preset contributes to the resolved plan."""
        return []

    def on_session_end(self, x_correlation_id: str) -> None | Awaitable[None]:
        """Post-session cleanup: no further requests will be sent for this
        session by this worker. Idempotent; default sync no-op."""
        return None


def _validate_source_spec(spec: str) -> str:
    """Pydantic-level source validation: unknown specs fail at config time
    with the registry's own error message instead of at plan resolution."""
    resolve_source(spec)
    return spec


_SourceSpec = Annotated[str, BeforeValidator(_validate_source_spec)]


class _SourcedOptions(AIPerfBaseModel):
    """Shared shape for presets reading one configurable source.

    ``missing`` applies ONLY to ``header:`` sources (a dataset-authored header
    the plan expects to route on); for every other source, absence is a
    structural fact and always a silent skip -- so an explicit ``missing`` on a
    non-header source is a misconfiguration, rejected here.
    """

    model_config = ConfigDict(extra="forbid")

    source: _SourceSpec = Field(
        default="session",
        description="Value source: session, parent, root, url_index, agent, "
        "agent_parent, or header:<name> (a dataset-authored dispatch-turn header).",
    )
    missing: Literal["error", "skip"] = Field(
        default="error",
        description="Policy when a header:<name> source finds no such header "
        "on the dispatch turn: 'error' fails the request, 'skip' drops the "
        "emission. Only legal when source is a header:<name> spec.",
    )

    @model_validator(mode="after")
    def validate_missing_requires_header_source(self) -> Self:
        if "missing" in self.model_fields_set and not is_header_source(self.source):
            raise ValueError(
                f"'missing' applies only to header:<name> sources; "
                f"source={self.source!r} is skipped or emitted structurally"
            )
        return self


class DynamoHeaders(SessionRoutingPreset):
    """Dynamo session affinity via X-Dynamo-Session-ID / X-Dynamo-Parent-Session-ID.

    Pair with a Dynamo frontend running ``--router-session-affinity-ttl-secs``.
    """

    def emitters(self) -> list[Emitter]:
        return [
            HeaderEmitter("X-Dynamo-Session-ID", "session"),
            HeaderEmitter("X-Dynamo-Parent-Session-ID", "parent"),
        ]


class DynamoNvextOptions(AIPerfBaseModel):
    """Options for the deprecated-upstream nvext.session_control transport."""

    model_config = ConfigDict(extra="forbid")

    timeout_seconds: int = Field(
        default=300,
        ge=1,
        description="Dynamo session_control inactivity timeout carried on every bind.",
    )
    scope: Literal["conversation", "lineage"] = Field(
        default="conversation",
        description="Affinity-key scope. 'conversation' (default) binds each "
        "session with its own correlation ID and closes on its final turn. "
        "'lineage' binds every session in an agent tree with the tree ROOT's "
        "correlation ID so the whole lineage co-locates on the worker holding "
        "the shared parent prefix (for Dynamo deployments without KV-event "
        "prefix indexing); the shared key is closed only on a request stamped "
        "provably-last for the whole tree (is_tree_final, agentic replay) -- "
        "otherwise the session_control TTL reclaims it.",
    )


class DynamoNvext(SessionRoutingPreset):
    """Dynamo session affinity via nvext.session_control request-body metadata.

    Modern contract only: 'bind' on every non-close turn (idempotent on the
    router, refreshes the TTL), 'close' on the terminal turn. Targets Dynamo
    builds that implement session_control; current upstream Dynamo main does
    not (use dynamo_headers there).
    """

    Options: ClassVar[type[AIPerfBaseModel]] = DynamoNvextOptions

    def emitters(self) -> list[Emitter]:
        options: DynamoNvextOptions = self.options
        return [
            NvextSessionControlEmitter(
                timeout_seconds=options.timeout_seconds, scope=options.scope
            )
        ]


class SmgRoutingKey(SessionRoutingPreset):
    """SGLang Model Gateway stickiness via X-SMG-Routing-Key.

    Serves both routing-key SMG policies: ``manual`` and ``consistent_hashing``.
    """

    Options: ClassVar[type[AIPerfBaseModel]] = _SourcedOptions

    def emitters(self) -> list[Emitter]:
        options: _SourcedOptions = self.options
        return [HeaderEmitter("X-SMG-Routing-Key", options.source, options.missing)]


class SessionIdHeaderOptions(AIPerfBaseModel):
    """Options for the additive session-ID header preset."""

    model_config = ConfigDict(extra="forbid")

    header_name: str = Field(
        default="X-Session-ID",
        description="Header name carrying the session's correlation ID.",
    )


class SessionIdHeader(SessionRoutingPreset):
    """Additive session-ID header carrying the session's correlation ID."""

    Options: ClassVar[type[AIPerfBaseModel]] = SessionIdHeaderOptions

    def emitters(self) -> list[Emitter]:
        options: SessionIdHeaderOptions = self.options
        return [HeaderEmitter(options.header_name, "session")]


class SglangSessionOptions(_SourcedOptions):
    """Options for the SGLang body-field session key."""

    field: str = Field(
        default="session_id",
        description="Top-level request-body key to write the session key into. "
        "A literal key: dots are NOT interpreted as nesting.",
    )


class SglangSession(SessionRoutingPreset):
    """Session key written into a top-level request-body field (SGLang-style)."""

    Options: ClassVar[type[AIPerfBaseModel]] = SglangSessionOptions

    def emitters(self) -> list[Emitter]:
        options: SglangSessionOptions = self.options
        return [BodyEmitter((options.field,), options.source, options.missing)]


class UrlIndexHeaderOptions(AIPerfBaseModel):
    """Options for the URL-slot index header preset."""

    model_config = ConfigDict(extra="forbid")

    header_name: str = Field(
        default="X-URL-Index",
        description="Header name carrying the request's assigned round-robin "
        "URL slot index (post-fallback).",
    )


class UrlIndexHeader(SessionRoutingPreset):
    """Header carrying the request's assigned round-robin URL slot index."""

    Options: ClassVar[type[AIPerfBaseModel]] = UrlIndexHeaderOptions

    def emitters(self) -> list[Emitter]:
        options: UrlIndexHeaderOptions = self.options
        return [HeaderEmitter(options.header_name, "url_index")]


class ClaudeCodeHeadersOptions(AIPerfBaseModel):
    """Options for the Claude Code agent-tree identity headers."""

    model_config = ConfigDict(extra="forbid")

    session_header_name: str = Field(
        default="x-claude-code-session-id",
        description="Header carrying the session-tree ROOT's correlation ID "
        "on every request (the session's own ID for root sessions).",
    )
    agent_header_name: str = Field(
        default="x-claude-code-agent-id",
        description="Header carrying the session's own correlation ID; "
        "emitted only for subagent sessions (depth >= 1).",
    )
    parent_header_name: str = Field(
        default="x-claude-code-parent-agent-id",
        description="Header carrying the immediate parent's correlation ID; "
        "emitted only at depth >= 2 (omitted when the parent is the root).",
    )


class ClaudeCodeHeaders(SessionRoutingPreset):
    """Claude Code agent-tree identity headers (root / agent / parent-agent)."""

    Options: ClassVar[type[AIPerfBaseModel]] = ClaudeCodeHeadersOptions

    def emitters(self) -> list[Emitter]:
        options: ClaudeCodeHeadersOptions = self.options
        return [
            HeaderEmitter(options.session_header_name, "root"),
            HeaderEmitter(options.agent_header_name, "agent"),
            HeaderEmitter(options.parent_header_name, "agent_parent"),
        ]


def _parse_json_if_str(value: Any) -> Any:
    """--session-routing-opt values arrive as strings; accept JSON there."""
    if isinstance(value, str):
        try:
            return orjson.loads(value)
        except orjson.JSONDecodeError as exc:
            raise ValueError(f"invalid JSON: {exc}") from exc
    return value


def _flatten_body_assignments(
    body: dict[str, Any], prefix: tuple[str, ...] = ()
) -> list[tuple[tuple[str, ...], str]]:
    """Flatten a nested body map into (path, source) assignments.

    A string leaf is a source spec; a mapping descends. Anything else is a
    config error naming the offending path.
    """
    assignments: list[tuple[tuple[str, ...], str]] = []
    for key, value in body.items():
        if not isinstance(key, str):
            raise ValueError(
                f"body map keys must be strings; got {key!r} under "
                f"{'.'.join(prefix) or '<root>'}"
            )
        path = (*prefix, key)
        if isinstance(value, dict):
            assignments.extend(_flatten_body_assignments(value, path))
        elif isinstance(value, str):
            assignments.append((path, value))
        else:
            raise ValueError(
                f"body assignment at {'.'.join(path)}: expected a source "
                f"string or nested mapping, got {type(value).__name__}"
            )
    return assignments


class CustomOptions(AIPerfBaseModel):
    """Options for the fully generic emitter map.

    At least one assignment across ``headers`` and ``body`` is required: an
    empty custom preset routes nothing and is always a misconfiguration.
    """

    model_config = ConfigDict(extra="forbid")

    headers: Annotated[dict[str, str], BeforeValidator(_parse_json_if_str)] = Field(
        default_factory=dict,
        description="Header assignments: header name -> source spec (session, "
        "parent, root, url_index, agent, agent_parent, header:<name>). On the "
        "CLI, pass as JSON: --session-routing-opt "
        'headers={"X-Affinity":"session"}.',
    )
    body: Annotated[dict[str, Any], BeforeValidator(_parse_json_if_str)] = Field(
        default_factory=dict,
        description="Body assignments as a nested map: a string leaf is a "
        "source spec, a nested mapping descends into the payload. On the CLI, "
        'pass as JSON: --session-routing-opt body={"nvext":{"session_id":"session"}}.',
    )

    @model_validator(mode="after")
    def validate_assignments(self) -> Self:
        for source in self.headers.values():
            resolve_source(source)
        body_assignments = _flatten_body_assignments(self.body)
        for _path, source in body_assignments:
            resolve_source(source)
        if not self.headers and not body_assignments:
            raise ValueError("custom requires at least one header or body assignment")
        return self


class Custom(SessionRoutingPreset):
    """Fully generic emitter map: any header or body path from any source.

    ``header:`` sources here are always ``missing="error"`` -- a dataset-
    authored header the plan is told to route on is a hard requirement.
    """

    Options: ClassVar[type[AIPerfBaseModel]] = CustomOptions

    def emitters(self) -> list[Emitter]:
        options: CustomOptions = self.options
        emitters: list[Emitter] = [
            HeaderEmitter(name, source) for name, source in options.headers.items()
        ]
        emitters.extend(
            BodyEmitter(path, source)
            for path, source in _flatten_body_assignments(options.body)
        )
        return emitters
