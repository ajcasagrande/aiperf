# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Emitters: write one wire-surface region from DispatchFacts.

Scalar emitters are declarative (source -> header/body path); structured
emitters (nvext session_control) carry conditional structure in code.
``apply``/``emit`` must be synchronous, non-blocking, and never mutate inputs.

Missing-policy rule: ``missing`` applies ONLY to ``header:`` sources -- a
header authored on the dispatch turn that the plan expects to route on. A None
from any other source (e.g. ``parent`` on a root session) is always a silent
skip, because absence there is a structural fact, not a misconfiguration.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from aiperf.workers.session_routing.facts import DispatchFacts
from aiperf.workers.session_routing.sources import (
    HEADER_SOURCE_PREFIX,
    SourceFn,
    is_header_source,
    resolve_source,
)


class MissingTurnHeaderError(ValueError):
    """A header:<name> source found no such header on the dispatch turn."""


def merge_at_path(
    payload: dict[str, Any], path: tuple[str, ...], value: Any
) -> dict[str, Any]:
    """Return a NEW payload with ``value`` set at ``path``, copy-on-write.

    Every dict along ``path`` is shallow-copied so siblings are preserved and
    the input (a shared cached dataset object) is never mutated. A non-dict
    intermediate is replaced by a fresh dict. The leaf is overwritten.
    """
    merged = dict(payload)
    node = merged
    for key in path[:-1]:
        child = node.get(key)
        node[key] = dict(child) if isinstance(child, dict) else {}
        node = node[key]
    node[path[-1]] = value
    return merged


@dataclass(slots=True, frozen=True)
class HeaderEmitter:
    """Writes one HTTP header from a source value; skips on None."""

    name: str
    source_spec: str
    missing: str = "error"
    _source: SourceFn = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "_source", resolve_source(self.source_spec))

    def emit(self, facts: DispatchFacts) -> tuple[str, str] | None:
        value = self._source(facts)
        if value is None:
            if is_header_source(self.source_spec) and self.missing == "error":
                raise MissingTurnHeaderError(
                    f"emitter header:{self.name}: dispatch turn has no "
                    f"{self.source_spec[len(HEADER_SOURCE_PREFIX) :]!r} header "
                    "(missing=error)"
                )
            return None
        return (self.name, value)

    def write_set(self) -> frozenset[str]:
        return frozenset({self.name.lower()})


@dataclass(slots=True, frozen=True)
class BodyEmitter:
    """Writes one scalar value into the request body at ``path``; skips on None."""

    path: tuple[str, ...]
    source_spec: str
    missing: str = "error"
    _source: SourceFn = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "_source", resolve_source(self.source_spec))

    def apply(self, payload: dict[str, Any], facts: DispatchFacts) -> dict[str, Any]:
        value = self._source(facts)
        if value is None:
            if is_header_source(self.source_spec) and self.missing == "error":
                raise MissingTurnHeaderError(
                    f"emitter body:{'.'.join(self.path)}: dispatch turn has no "
                    f"{self.source_spec[len(HEADER_SOURCE_PREFIX) :]!r} header "
                    "(missing=error)"
                )
            return payload
        return merge_at_path(payload, self.path, value)

    def write_path(self) -> tuple[str, ...]:
        return self.path


@dataclass(slots=True, frozen=True)
class NvextSessionControlEmitter:
    """Writes Dynamo ``nvext.session_control`` bind/close body metadata.

    Ported from the legacy ``DynamoNvextRouting.transform_body``. ``bind``
    (carrying the inactivity ``timeout``) on every non-close turn, ``close``
    on the terminal turn. Any pre-existing ``nvext`` content is preserved and
    a pre-existing ``session_control`` dict is merged under (plugin values win).

    ``scope`` selects the affinity key and the close discipline:
    - ``conversation`` (default): keyed by this session's correlation ID;
      ``close`` on ``is_final_turn``.
    - ``lineage``: keyed by the tree ROOT's correlation ID so the whole
      lineage co-locates; ``close`` ONLY on ``is_tree_final`` (not
      ``is_final_turn``), otherwise the session_control TTL reclaims the key.
    """

    timeout_seconds: int
    scope: str = "conversation"

    def __post_init__(self) -> None:
        if self.scope not in ("conversation", "lineage"):
            raise ValueError(
                f"invalid scope {self.scope!r}: expected 'conversation' or 'lineage'"
            )

    def apply(self, payload: dict[str, Any], facts: DispatchFacts) -> dict[str, Any]:
        if self.scope == "lineage":
            session_id = facts.root_correlation_id or facts.x_correlation_id
            is_close = facts.is_tree_final
        else:
            session_id = facts.x_correlation_id
            is_close = facts.is_final_turn
        if is_close:
            session_control: dict[str, Any] = {
                "session_id": session_id,
                "action": "close",
            }
        else:
            session_control = {
                "session_id": session_id,
                "action": "bind",
                "timeout": self.timeout_seconds,
            }
        merged = dict(payload)
        raw_nvext = merged.get("nvext")
        if raw_nvext is None:
            merged["nvext"] = {"session_control": session_control}
            return merged
        nvext = dict(raw_nvext) if isinstance(raw_nvext, dict) else {}
        raw_sc = nvext.get("session_control")
        if isinstance(raw_sc, dict):
            session_control = {**raw_sc, **session_control}
        nvext["session_control"] = session_control
        merged["nvext"] = nvext
        return merged

    def write_path(self) -> tuple[str, ...]:
        return ("nvext", "session_control")
