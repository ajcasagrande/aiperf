# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Session-routing config surface: plan entries and the opt-key grammar.

``PlanEntry`` / ``SessionRoutingConfigError`` live here (not in
``aiperf.workers.session_routing``) because both the config layer
(``EndpointConfig.session_routing_plan``) and the worker-side plan resolver
need them, and ``aiperf.common.config`` must not import ``aiperf.workers``
(whose plan module pulls in ``aiperf.common.models``, which imports
``aiperf.common.config`` -- a cycle). ``PlanEntry`` is deliberately a plain
pydantic ``BaseModel``: importing ``AIPerfBaseModel`` would trigger the same
cycle through the ``aiperf.common.models`` package init.
``aiperf.workers.session_routing`` re-exports both names.

The rest of the module is the ``--session-routing`` / ``--session-routing-opt``
normalization grammar used by ``EndpointConfig.validate_session_routing``:
entry-list normalization, opt-key resolution (reserved ``headers.``/``body.``
custom assignments, ``<preset>.<key>`` namespacing, bare keys), and the
cross-channel opt merge with duplicate detection.
"""

from typing import Any

from pydantic import BaseModel, Field


class SessionRoutingConfigError(ValueError):
    """A session-routing plan failed resolution or cross-emitter validation."""


class PlanEntry(BaseModel):
    """One preset in an ordered session-routing plan."""

    preset: str = Field(description="Registered session-routing preset name.")
    opts: dict[str, Any] = Field(
        default_factory=dict,
        description="Preset-specific options, validated by the preset's Options model.",
    )


# --session-routing-opt keys starting with these prefixes are assignments for
# the 'custom' preset; consequently no registered preset may use these names
# ('header' is also reserved to keep the singular/plural typo unambiguous).
_RESERVED_OPT_PREFIXES = ("headers", "body")
_FORBIDDEN_PRESET_NAMES = frozenset({"headers", "body", "header"})

# Opt-merge channels, in application order. FLAT is the legacy
# ``session_routing_opts`` dict; CLI silently overrides FLAT on equal (or
# covering) paths so a canonicalized config re-validates identically; every
# other same-path pair is a config error naming both spellings.
_CH_INLINE = "inline"
_CH_FLAT = "flat"
_CH_CLI = "cli"

# Per-preset opt leaves: dotted path -> (value, human spelling, channel).
_OptLeaves = dict[tuple[str, ...], tuple[Any, str, str]]


def normalize_session_routing_entries(
    raw: list[str | dict[str, Any]],
) -> list[tuple[str, dict[str, Any]]]:
    """Normalize the raw ``session_routing`` list to (preset, inline opts).

    Accepts preset names and single-key ``{preset: opts}`` mappings;
    ``{preset: None}`` (a YAML trailing colon) means no opts. A mapping with
    more than one key is almost always a YAML list item missing its ``-``, so
    the error says exactly that.
    """
    entries: list[tuple[str, dict[str, Any]]] = []
    for item in raw:
        if isinstance(item, str):
            name, opts = item.strip(), {}
        else:
            if len(item) != 1:
                raise SessionRoutingConfigError(
                    f"session_routing list entries must be single-key "
                    f"mappings of preset -> opts; got {len(item)} keys "
                    f"({', '.join(map(str, item))}). In YAML each preset is "
                    f"its own '- ' list item -- did you forget a '-'?"
                )
            raw_name, opts = next(iter(item.items()))
            name = str(raw_name).strip()
            if opts is None:
                opts = {}
            if not isinstance(opts, dict):
                raise SessionRoutingConfigError(
                    f"session_routing entry {name!r}: opts must be a mapping "
                    f"of option -> value, got {type(opts).__name__}"
                )
        if name in _FORBIDDEN_PRESET_NAMES:
            raise SessionRoutingConfigError(
                f"{name!r} cannot be a session-routing preset name; it is "
                f"reserved for --session-routing-opt 'headers.'/'body.' "
                f"custom assignments."
            )
        if any(name == existing for existing, _ in entries):
            raise SessionRoutingConfigError(
                f"duplicate preset: session_routing lists {name!r} more than once"
            )
        entries.append((name, opts))
    return entries


def _is_registered_preset(name: str) -> bool:
    """True when ``name`` is a registered session-routing preset."""
    # Lazy import to avoid circular dependency
    from aiperf.plugin import plugins
    from aiperf.plugin.enums import PluginType
    from aiperf.plugin.types import TypeNotFoundError

    try:
        plugins.get_class(PluginType.SESSION_ROUTING, name)
    except TypeNotFoundError:
        return False
    return True


def resolve_routing_opt_key(
    key: str, configured_presets: list[str]
) -> tuple[str, tuple[str, ...]]:
    """Resolve a ``--session-routing-opt`` key to ``(preset, opt path)``.

    Grammar, in priority order:
    1. ``headers.<name>`` / ``body.<dotted.path>`` are assignments for the
       ``custom`` preset. ``headers.`` consumes exactly one prefix segment;
       the remainder is the header name verbatim (dots included). ``body.``
       descends on dots into a nested body path.
    2. ``<preset>.<key>`` where ``<preset>`` is a CONFIGURED preset is the
       namespaced form (always accepted, even with a single preset).
    3. A bare key binds to the sole configured preset; ambiguous (and an
       error listing the configured names) when more than one is configured.
    """
    prefix, dot, rest = key.partition(".")
    if dot and prefix in _RESERVED_OPT_PREFIXES:
        if "custom" not in configured_presets:
            raise SessionRoutingConfigError(
                f"--session-routing-opt key {key!r}: '{prefix}.' keys are "
                f"assignments for the 'custom' preset, but 'custom' is not among "
                f"the configured session-routing presets "
                f"({', '.join(configured_presets)})."
            )
        if prefix == "headers":
            if not rest:
                raise SessionRoutingConfigError(
                    f"--session-routing-opt key {key!r}: expected a header name "
                    f"after 'headers.'"
                )
            return "custom", ("headers", rest)
        segments = tuple(rest.split("."))
        if not rest or any(not segment for segment in segments):
            raise SessionRoutingConfigError(
                f"--session-routing-opt key {key!r}: empty segment in body path"
            )
        return "custom", ("body", *segments)
    if dot and prefix in configured_presets:
        if not rest:
            raise SessionRoutingConfigError(
                f"--session-routing-opt key {key!r}: expected an option key "
                f"after '{prefix}.'"
            )
        return prefix, (rest,)
    probe = prefix if dot else key
    if probe not in configured_presets and _is_registered_preset(probe):
        raise SessionRoutingConfigError(
            f"--session-routing-opt key {key!r} names session-routing preset "
            f"{probe!r}, which is not configured (configured: "
            f"{', '.join(configured_presets)}). Add it to --session-routing, or "
            f"use 'headers.<name>' / 'body.<path>' keys for 'custom' assignments."
        )
    if len(configured_presets) == 1:
        return configured_presets[0], (key,)
    raise SessionRoutingConfigError(
        f"--session-routing-opt key {key!r} is ambiguous: multiple "
        f"session-routing presets are configured "
        f"({', '.join(configured_presets)}); namespace it as '<preset>.{key}'."
    )


def _flatten_opt_dict(
    opts: dict[str, Any], prefix: tuple[str, ...] = ()
) -> list[tuple[tuple[str, ...], Any]]:
    """Flatten a nested opts mapping into (path, leaf value) pairs.

    Non-empty dict values descend; everything else (including empty dicts)
    is a leaf. Rebuilding the paths reproduces the original mapping, so the
    round-trip through leaves is lossless.
    """
    leaves: list[tuple[tuple[str, ...], Any]] = []
    for key, value in opts.items():
        path = (*prefix, str(key))
        if isinstance(value, dict) and value:
            leaves.extend(_flatten_opt_dict(value, path))
        else:
            leaves.append((path, value))
    return leaves


def _paths_overlap(a: tuple[str, ...], b: tuple[str, ...]) -> bool:
    shorter, longer = (a, b) if len(a) <= len(b) else (b, a)
    return longer[: len(shorter)] == shorter


def _add_opt_leaf(
    leaves: _OptLeaves,
    *,
    preset: str,
    path: tuple[str, ...],
    value: Any,
    spelling: str,
    channel: str,
) -> None:
    """Insert one opt leaf, enforcing cross-channel duplicate rules.

    Any same-or-overlapping path supplied twice is a config error naming both
    spellings, with one legacy exception: a CLI opt whose path equals (or
    covers) a FLAT ``session_routing_opts`` leaf silently wins, preserving the
    pre-plan ``{**flat, **cli}`` merge so canonicalized configs re-validate.
    """
    for existing_path in list(leaves):
        if not _paths_overlap(existing_path, path):
            continue
        _, existing_spelling, existing_channel = leaves[existing_path]
        if (
            channel == _CH_CLI
            and existing_channel == _CH_FLAT
            and len(path) <= len(existing_path)
        ):
            del leaves[existing_path]
            continue
        raise SessionRoutingConfigError(
            f"session-routing option conflict for preset {preset!r}: "
            f"{existing_spelling} and {spelling} both set option "
            f"'{'.'.join(path)}'."
        )
    leaves[path] = (value, spelling, channel)


def _rebuild_opt_dict(leaves: _OptLeaves) -> dict[str, Any]:
    """Rebuild a nested opts mapping from prefix-free leaves."""
    opts: dict[str, Any] = {}
    for path, (value, _spelling, _channel) in leaves.items():
        node = opts
        for segment in path[:-1]:
            node = node.setdefault(segment, {})
        node[path[-1]] = value
    return opts


def build_plan_entries(
    entries: list[tuple[str, dict[str, Any]]],
    flat_opts: dict[str, Any],
    cli_opts: dict[str, str],
) -> tuple[list[PlanEntry], bool]:
    """Merge the three opt channels into ordered plan entries.

    Channels apply in order: inline entry opts, the flat legacy
    ``session_routing_opts`` dict (sole-preset only), then
    ``--session-routing-opt`` pairs resolved through the key grammar.
    Returns the entries plus whether any inline opts were present (the flat
    canonical-opts mirror must be skipped in that case).
    """
    presets = [name for name, _opts in entries]
    leaves_by_preset: dict[str, _OptLeaves] = {name: {} for name in presets}

    has_inline_opts = False
    for name, inline_opts in entries:
        for path, value in _flatten_opt_dict(inline_opts):
            has_inline_opts = True
            _add_opt_leaf(
                leaves_by_preset[name],
                preset=name,
                path=path,
                value=value,
                spelling=f"session_routing entry '{name}' opts '{'.'.join(path)}'",
                channel=_CH_INLINE,
            )

    if flat_opts:
        if len(presets) > 1:
            raise SessionRoutingConfigError(
                f"session_routing_opts applies to a single session-routing "
                f"preset, but {len(presets)} are configured "
                f"({', '.join(presets)}); set opts inline on the "
                f"session_routing entries or namespace --session-routing-opt "
                f"keys instead."
            )
        for path, value in _flatten_opt_dict(flat_opts):
            _add_opt_leaf(
                leaves_by_preset[presets[0]],
                preset=presets[0],
                path=path,
                value=value,
                spelling=f"session_routing_opts '{'.'.join(path)}'",
                channel=_CH_FLAT,
            )

    for raw_key, value in cli_opts.items():
        preset, path = resolve_routing_opt_key(raw_key, presets)
        _add_opt_leaf(
            leaves_by_preset[preset],
            preset=preset,
            path=path,
            value=value,
            spelling=f"--session-routing-opt '{raw_key}'",
            channel=_CH_CLI,
        )

    return [
        PlanEntry(preset=name, opts=_rebuild_opt_dict(leaves_by_preset[name]))
        for name in presets
    ], has_inline_opts
