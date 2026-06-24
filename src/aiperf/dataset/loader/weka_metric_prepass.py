# SPDX-FileCopyrightText: Copyright (c) 2025-2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Shared theoretical prefix-cache pre-pass for Weka traces (spec §5.5).

The caller groups records by the declared hash namespace: one trace file for
``local`` scope or all same-block-size files for ``global`` scope. This module
computes values over that shared seen-set in timestamp order.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True, frozen=True)
class MetricRecord:
    """One request's contribution to a shared hash-scope seen-set."""

    sort_key: tuple[float, int, int, int]
    """(absolute_t, outer_idx, stream_idx, k) — deterministic global order."""
    session_id: str
    """Conversation the value is looked up under at emission time."""
    k: int
    """Turn index within that conversation."""
    hash_ids: list[int]
    """The request's input hash blocks."""


def compute_shared_prefix_cache_metrics(
    records: list[MetricRecord],
) -> dict[tuple[str, int], tuple[int, int]]:
    """Compute ``(hit_blocks, total_blocks)`` over one hash scope."""
    out: dict[tuple[str, int], tuple[int, int]] = {}
    seen: set[int] = set()
    for rec in sorted(records, key=lambda r: r.sort_key):
        hits = 0
        for hid in rec.hash_ids:
            if hid not in seen:
                break
            hits += 1
        out[(rec.session_id, rec.k)] = (hits, len(rec.hash_ids))
        seen.update(rec.hash_ids)
    return out
