# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Per-request dispatch facts handed to session-routing sources.

Field naming mirrors ``RequestInfo`` verbatim. Growth policy: add-only.
``url_index`` is post-fallback (the value that also selects the actual URL);
``RequestInfo.url_index is None`` normalizes to ``0`` at construction.
``turn_extra_headers`` must be a read-only mapping (``MappingProxyType``) --
the underlying dict is a shared dataset object under recycling.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass


@dataclass(slots=True, frozen=True)
class DispatchFacts:
    x_correlation_id: str
    """This session's stable key (same on every turn)."""
    parent_correlation_id: str | None
    """Immediate parent session's key; None for root sessions."""
    root_correlation_id: str
    """Session-tree root key; equals x_correlation_id for root sessions."""
    is_final_turn: bool
    """True when this is the current session's last request."""
    is_parent_final: bool | None
    """True when the parent already returned its final turn; None for roots/unknown."""
    is_tree_final: bool
    """Best-effort: True only when provably the tree's last request."""
    url_index: int
    """Assigned round-robin URL slot, post-fallback; None normalized to 0."""
    turn_extra_headers: Mapping[str, str]
    """Read-only view of the dispatch turn's extra_headers (empty when absent)."""
