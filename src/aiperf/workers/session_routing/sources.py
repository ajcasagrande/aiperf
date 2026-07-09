# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Source vocabulary: pure functions DispatchFacts -> str | None.

None means "skip this emission". Conditionality that is a pure function of
DispatchFacts belongs here as a derived source (``agent``, ``agent_parent``);
conditionality over payload structure or lifecycle belongs in a coded emitter.
``header:<name>`` reads the DISPATCH TURN's dataset-authored extra_headers
only (case-insensitive; first case-insensitive match in iteration order wins)
-- never plan-emitted headers.
"""

from __future__ import annotations

from collections.abc import Callable

from aiperf.workers.session_routing.facts import DispatchFacts

SourceFn = Callable[[DispatchFacts], str | None]

HEADER_SOURCE_PREFIX = "header:"


def _agent(facts: DispatchFacts) -> str | None:
    if facts.x_correlation_id != facts.root_correlation_id:
        return facts.x_correlation_id
    return None


def _agent_parent(facts: DispatchFacts) -> str | None:
    parent = facts.parent_correlation_id
    if parent is not None and parent != facts.root_correlation_id:
        return parent
    return None


_BUILTIN: dict[str, SourceFn] = {
    "session": lambda f: f.x_correlation_id,
    "parent": lambda f: f.parent_correlation_id,
    "root": lambda f: f.root_correlation_id,
    "url_index": lambda f: str(f.url_index),
    "agent": _agent,
    "agent_parent": _agent_parent,
}

SOURCE_NAMES: tuple[str, ...] = tuple(_BUILTIN)


def resolve_source(spec: str) -> SourceFn:
    """Resolve a source spec to its value function; unknown specs raise."""
    if spec in _BUILTIN:
        return _BUILTIN[spec]
    if spec.startswith(HEADER_SOURCE_PREFIX):
        name = spec[len(HEADER_SOURCE_PREFIX) :]
        if not name:
            raise ValueError(
                "header: source requires a header name, e.g. header:x-src-id"
            )
        lowered = name.lower()

        def _from_turn_header(facts: DispatchFacts) -> str | None:
            for key, value in facts.turn_extra_headers.items():
                if key.lower() == lowered:
                    return value
            return None

        return _from_turn_header
    raise ValueError(
        f"unknown session-routing source {spec!r}; valid sources: "
        f"{', '.join(SOURCE_NAMES)}, header:<name>"
    )


def is_header_source(spec: str) -> bool:
    """True when the spec reads a dataset-authored dispatch-turn header."""
    return spec.startswith(HEADER_SOURCE_PREFIX)
