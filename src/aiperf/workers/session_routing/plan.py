# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Resolved emitter plans: validate a preset stack into a runnable plan.

A plan is an ordered list of :class:`PlanEntry` (preset name + opts). Resolution
looks each preset up, validates its opts against the preset's ``Options`` model,
collects the preset's emitters, and enforces cross-emitter invariants so the wire
output is well-formed regardless of which presets are combined:

- header-token hygiene (RFC 9110 field-name grammar) plus a hard reject of the
  ``x-request-id`` / ``x-correlation-id`` reserved names (case-insensitive);
- prefix-freedom: no two emitters may write the same header (case-insensitive)
  or overlapping body paths (case-sensitive, equal-or-prefix in either
  direction) -- overlap would make the merge order-dependent;
- duplicate preset names in one plan are rejected.

Every failure raises :class:`SessionRoutingConfigError`, naming the offending
entries as ``entry[<idx>] (<preset>)`` so a misconfigured YAML points at itself.
"""

from __future__ import annotations

import inspect
import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from pydantic import ValidationError

from aiperf.common.config.routing_plan import PlanEntry, SessionRoutingConfigError
from aiperf.workers.session_routing.facts import DispatchFacts
from aiperf.workers.session_routing.sources import (
    HEADER_SOURCE_PREFIX,
    is_header_source,
)

if TYPE_CHECKING:
    from aiperf.common.models.model_endpoint_info import EndpointInfo

# RFC 9110 field-name token grammar (tchar). Header names must match this.
_HEADER_TOKEN_RE = re.compile(r"^[!#$%&'*+.^_`|~0-9A-Za-z-]+$")

# Reserved header names the plan layer never lets a preset own (compared lower).
_RESERVED_HEADERS = frozenset({"x-request-id", "x-correlation-id"})

_VALID_MISSING = frozenset({"error", "skip"})

__all__ = [
    "BodyTransformDiagnostics",
    "PlanEntry",
    "ResolvedPlan",
    "SessionRoutingConfigError",
    "SessionRoutingEmitterError",
    "resolve_plan",
    "resolve_plan_from_endpoint",
]


@dataclass(slots=True)
class BodyTransformDiagnostics:
    """Per-request body-write observations surfaced by ``transform_body``.

    Each item is ``(entry label, dotted body path)``. The plan layer only
    reports; the caller (InferenceClient) decides what to log and how often
    (spec section 5.4 mandates once-per-worker warnings for each kind).
    """

    overwrites: list[tuple[str, str]] = field(default_factory=list)
    """Leaf writes that replaced an existing non-None payload value."""

    non_dict_replacements: list[tuple[str, str]] = field(default_factory=list)
    """Merge paths that discarded a non-dict intermediate value."""


def _peek_write_target(
    payload: dict[str, Any], path: tuple[str, ...]
) -> tuple[Any, bool]:
    """(existing leaf value, non-dict intermediate present) at ``path``.

    Read-only walk of the pre-transform payload so diagnostics never depend
    on emitter cooperation (emitters stay pure). A missing key or an explicit
    None intermediate is benign; a non-None non-dict intermediate would be
    discarded by the merge and is flagged.
    """
    node: Any = payload
    for key in path[:-1]:
        child = node.get(key)
        if not isinstance(child, dict):
            return None, key in node and child is not None
        node = child
    return node.get(path[-1]), False


class SessionRoutingEmitterError(RuntimeError):
    """An emitter or source failed at dispatch time.

    The message names the owning preset entry (``entry[<idx>] (<preset>)``)
    and the failing phase (``headers()`` / ``transform_body()``), so the
    resulting error record points at the misbehaving plan entry rather than
    the inference server.
    """


class ResolvedPlan:
    """A validated, runnable session-routing plan.

    Holds the ordered preset instances and their emitters, each tagged with
    its owning entry label. ``headers`` and ``transform_body`` fan the
    dispatch facts across every emitter; the flags ``mutates_body`` /
    ``reads_turn_headers`` let callers skip work when a plan touches neither
    the body nor the dispatch turn's headers.
    """

    def __init__(
        self,
        entries: list[PlanEntry],
        preset_instances: list[tuple[str, Any]],
        header_emitters: list[tuple[str, Any]],
        body_emitters: list[tuple[str, Any]],
        *,
        mutates_body: bool,
        reads_turn_headers: bool,
        uses_url_index: bool,
    ) -> None:
        self.entries = entries
        self._preset_instances = preset_instances
        self._header_emitters = header_emitters
        self._body_emitters = body_emitters
        self.mutates_body = mutates_body
        self.reads_turn_headers = reads_turn_headers
        self.uses_url_index = uses_url_index
        # Lowered header name -> owning entry label. Prefix-freedom guarantees
        # one owner per name in plans built by resolve_plan.
        self._header_owners: dict[str, str] = {
            name: label
            for label, emitter in header_emitters
            for name in emitter.write_set()
        }

    @property
    def header_names(self) -> frozenset[str]:
        """Lowercased names of every header this plan can write."""
        return frozenset(self._header_owners)

    def header_owner(self, name: str) -> str | None:
        """Entry label owning a plan-written header (any casing); None if unowned."""
        return self._header_owners.get(name.lower())

    def required_turn_headers(self) -> list[tuple[str, str]]:
        """(lowered header name, owning entry label) the plan hard-requires.

        Covers every ``header:<name>`` source with ``missing="error"`` across
        header and body emitters -- dataset-authored dispatch-turn headers
        whose absence fails the request at dispatch. Dataset-load fail-fast
        scans use this to refuse a run whose turns cannot satisfy the plan
        before any request is sent; ``missing="skip"`` sources are excluded
        (absence there is a silent per-request skip). Deduped by header name
        (order preserved, first owning label wins).
        """
        required: list[tuple[str, str]] = []
        seen: set[str] = set()
        for label, emitter in (*self._header_emitters, *self._body_emitters):
            spec = getattr(emitter, "source_spec", None)
            if spec is None or not is_header_source(spec):
                continue
            if getattr(emitter, "missing", "error") != "error":
                continue
            name = spec[len(HEADER_SOURCE_PREFIX) :].lower()
            if name not in seen:
                seen.add(name)
                required.append((name, label))
        return required

    def headers(self, facts: DispatchFacts) -> dict[str, str]:
        """Emit every plan header for this request (skipped emitters drop out).

        An emitter exception is re-raised as :class:`SessionRoutingEmitterError`
        naming the owning entry and this phase.
        """
        result: dict[str, str] = {}
        for label, emitter in self._header_emitters:
            try:
                emitted = emitter.emit(facts)
            except Exception as e:
                raise SessionRoutingEmitterError(
                    f"session-routing {label} failed in headers(): {e!r}"
                ) from e
            if emitted is not None:
                name, value = emitted
                result[name] = value
        return result

    def transform_body(
        self,
        payload: dict[str, Any],
        facts: DispatchFacts,
        diagnostics: BodyTransformDiagnostics | None = None,
    ) -> dict[str, Any]:
        """Apply every body emitter in entry order, copy-on-write.

        An emitter exception is re-raised as :class:`SessionRoutingEmitterError`
        naming the owning entry and this phase. When ``diagnostics`` is given,
        each write that replaced an existing non-None leaf value or discarded a
        non-dict intermediate is recorded on it (entry label + dotted path);
        the pre-write payload is inspected here so emitters stay pure.
        """
        for label, emitter in self._body_emitters:
            before = payload
            try:
                payload = emitter.apply(payload, facts)
            except Exception as e:
                raise SessionRoutingEmitterError(
                    f"session-routing {label} failed in transform_body(): {e!r}"
                ) from e
            # Emitters return the input object unchanged on a skip, so an
            # identity match means nothing was written (nothing to diagnose).
            if diagnostics is None or payload is before:
                continue
            path = emitter.write_path()
            leaf, replaced_non_dict = _peek_write_target(before, path)
            dotted = ".".join(path)
            if leaf is not None:
                diagnostics.overwrites.append((label, dotted))
            if replaced_non_dict:
                diagnostics.non_dict_replacements.append((label, dotted))
        return payload

    def notify_session_end(
        self, x_correlation_id: str
    ) -> list[tuple[str, Awaitable[None]]]:
        """Fire each preset's ``on_session_end`` hook for a finished session.

        Sync hooks run inline (their exceptions propagate). Async hooks return
        a coroutine/awaitable that is collected -- unawaited -- together with
        its owning entry label (``entry[<idx>] (<preset>)``) so the caller can
        schedule it and attribute failures.
        """
        labeled: list[tuple[str, Awaitable[None]]] = []
        for label, instance in self._preset_instances:
            hook = getattr(instance, "on_session_end", None)
            if hook is None:
                continue
            result = hook(x_correlation_id)
            if inspect.isawaitable(result):
                labeled.append((label, result))
        return labeled


def _default_preset_lookup(name: str) -> type:
    from aiperf.plugin import plugins
    from aiperf.plugin.enums import PluginType

    return plugins.get_class(PluginType.SESSION_ROUTING, name)


def _entry_label(idx: int, preset: str) -> str:
    return f"entry[{idx}] ({preset})"


def _write_keys(emitter: Any) -> list[tuple[str, ...]]:
    """Normalize an emitter's write declaration to prefix-freedom keys."""
    if hasattr(emitter, "write_set"):
        return [("header", name) for name in emitter.write_set()]
    return [("body", *emitter.write_path())]


def _keys_conflict(a: tuple[str, ...], b: tuple[str, ...]) -> bool:
    shorter, longer = (a, b) if len(a) <= len(b) else (b, a)
    return longer[: len(shorter)] == shorter


def _validate_emitter(emitter: Any, idx: int, preset: str) -> None:
    """Per-emitter checks: missing-policy value and header-name hygiene."""
    missing = getattr(emitter, "missing", None)
    if missing is not None and missing not in _VALID_MISSING:
        raise SessionRoutingConfigError(
            f"{_entry_label(idx, preset)}: emitter missing="
            f"{missing!r} is not one of 'error' or 'skip'"
        )
    if hasattr(emitter, "write_set"):
        for lowered in emitter.write_set():
            if lowered in _RESERVED_HEADERS:
                raise SessionRoutingConfigError(
                    f"{_entry_label(idx, preset)}: header "
                    f"{lowered!r} is reserved and cannot be routed"
                )
            if not _HEADER_TOKEN_RE.match(lowered):
                raise SessionRoutingConfigError(
                    f"{_entry_label(idx, preset)}: header "
                    f"{lowered!r} is not a valid RFC 9110 header token"
                )


def _check_prefix_freedom(
    declarations: list[tuple[tuple[str, ...], int, str, int]],
) -> None:
    """Reject any two emitters writing the same or overlapping targets."""
    for i in range(len(declarations)):
        key_i, idx_i, preset_i, eid_i = declarations[i]
        for j in range(i + 1, len(declarations)):
            key_j, idx_j, preset_j, eid_j = declarations[j]
            if eid_i == eid_j:
                continue
            if _keys_conflict(key_i, key_j):
                if key_i[0] == "header":
                    # Header keys are lowered names; a conflict means both
                    # emitters write the same (case-insensitive) header.
                    surface = "header"
                    detail = f"both write header {key_i[1]!r}"
                else:
                    surface = "body path"
                    path_i, path_j = ".".join(key_i[1:]), ".".join(key_j[1:])
                    detail = (
                        f"both write body path {path_i!r}"
                        if path_i == path_j
                        else f"body path {path_i!r} overlaps {path_j!r}"
                    )
                raise SessionRoutingConfigError(
                    f"{surface} conflict between {_entry_label(idx_i, preset_i)} and "
                    f"{_entry_label(idx_j, preset_j)}: {detail}"
                )


def resolve_plan(
    entries: list[PlanEntry],
    *,
    preset_lookup: Callable[[str], type] | None = None,
) -> ResolvedPlan:
    """Resolve and validate a session-routing plan into a runnable form."""
    lookup = preset_lookup if preset_lookup is not None else _default_preset_lookup

    seen: dict[str, int] = {}
    for idx, entry in enumerate(entries):
        if entry.preset in seen:
            first = seen[entry.preset]
            raise SessionRoutingConfigError(
                f"duplicate preset: {_entry_label(first, entry.preset)} and "
                f"{_entry_label(idx, entry.preset)} name the same preset"
            )
        seen[entry.preset] = idx

    preset_instances: list[tuple[str, Any]] = []
    header_emitters: list[tuple[str, Any]] = []
    body_emitters: list[tuple[str, Any]] = []
    # (key, idx, preset, emitter_id) for every write declaration, for
    # prefix-freedom. emitter_id is unique per emitter across the whole plan so
    # a multi-key emitter is never compared against itself.
    declarations: list[tuple[tuple[str, ...], int, str, int]] = []
    emitter_id = 0

    for idx, entry in enumerate(entries):
        label = _entry_label(idx, entry.preset)
        preset_cls = lookup(entry.preset)
        if preset_cls is None:
            raise SessionRoutingConfigError(f"{label}: unknown session-routing preset")
        options_cls = preset_cls.Options
        try:
            options = options_cls.model_validate(entry.opts)
        except ValidationError as exc:
            raise SessionRoutingConfigError(f"{label}: invalid options: {exc}") from exc

        instance = preset_cls(options)
        preset_instances.append((label, instance))

        for emitter in instance.emitters():
            _validate_emitter(emitter, idx, entry.preset)
            if hasattr(emitter, "write_set"):
                header_emitters.append((label, emitter))
            else:
                body_emitters.append((label, emitter))

            for key in _write_keys(emitter):
                declarations.append((key, idx, entry.preset, emitter_id))
            emitter_id += 1

    _check_prefix_freedom(declarations)

    all_emitters = [emitter for _, emitter in (*header_emitters, *body_emitters)]
    mutates_body = bool(body_emitters)
    reads_turn_headers = any(
        is_header_source(emitter.source_spec)
        for emitter in all_emitters
        if hasattr(emitter, "source_spec")
    )
    uses_url_index = any(
        getattr(emitter, "source_spec", None) == "url_index" for emitter in all_emitters
    )

    return ResolvedPlan(
        list(entries),
        preset_instances,
        header_emitters,
        body_emitters,
        mutates_body=mutates_body,
        reads_turn_headers=reads_turn_headers,
        uses_url_index=uses_url_index,
    )


def resolve_plan_from_endpoint(endpoint_info: EndpointInfo) -> ResolvedPlan | None:
    """Adapter: canonical endpoint plan entries -> a resolved plan.

    Returns None when routing is off (empty plan). Works with any object
    carrying a ``session_routing_plan`` list of :class:`PlanEntry`
    (``EndpointInfo`` and ``EndpointConfig`` both do).
    """
    entries = endpoint_info.session_routing_plan
    if not entries:
        return None
    return resolve_plan(list(entries))
