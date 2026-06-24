# SPDX-FileCopyrightText: Copyright (c) 2025-2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Per-tree inner-session concurrency limiter for agentic replay.

One ``asyncio.Semaphore(P)`` per session tree (keyed by root_correlation_id),
sized to the trajectory's session-achievable peak. Acquire gates wire entry;
release is idempotent (a double release does NOT inflate P). Trees without a
limiter (timestamp-less) are unbounded no-ops.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass


@dataclass
class _Token:
    root_corr: str
    generation: int
    released: bool = False


@dataclass
class _TreeLimiter:
    sem: asyncio.Semaphore
    peak: int
    generation: int
    in_flight: int = 0
    queued: int = 0


class InnerSessionLimiter:
    """Registry of per-tree semaphores. Not thread-safe; single-loop use."""

    def __init__(self) -> None:
        self._trees: dict[str, _TreeLimiter] = {}
        # Monotonic, never-reused open generation. A token is stamped with the
        # generation of the tree it acquired from; release ignores a token whose
        # generation no longer matches the live tree, so a stale token from a
        # closed/reopened tree (same root_corr reused) can never release the new
        # tree's semaphore and inflate its capacity.
        self._next_generation: int = 0

    def open_tree(self, root_corr: str, peak: int) -> None:
        """Create a fresh semaphore of size ``max(1, peak)`` for this tree.

        Reopening an existing key mints a NEW generation, so any in-flight token
        from the prior incarnation is treated as stale on release.
        """
        p = max(1, peak)
        self._next_generation += 1
        self._trees[root_corr] = _TreeLimiter(
            sem=asyncio.Semaphore(p), peak=p, generation=self._next_generation
        )

    def close_tree(self, root_corr: str) -> None:
        """Discard a tree's limiter (drain/recycle). Late tokens become no-ops."""
        self._trees.pop(root_corr, None)

    async def acquire(self, root_corr: str) -> _Token | None:
        tree = self._trees.get(root_corr)
        if tree is None:
            return None  # unbounded (timestamp-less / no limiter): no-op
        tree.queued += 1
        try:
            await tree.sem.acquire()
        finally:
            tree.queued -= 1
        tree.in_flight += 1
        return _Token(root_corr=root_corr, generation=tree.generation)

    def release(self, token: _Token | None) -> None:
        if token is None or token.released:
            return  # idempotent: no over-release, no P inflation
        token.released = True
        tree = self._trees.get(token.root_corr)
        if tree is None or tree.generation != token.generation:
            return  # tree closed (recycle) or reopened under a new generation:
            # the token belongs to a dead incarnation -> drop the late release
        tree.sem.release()
        tree.in_flight -= 1

    def in_flight(self, root_corr: str) -> int:
        tree = self._trees.get(root_corr)
        return tree.in_flight if tree else 0

    def queued(self, root_corr: str) -> int:
        tree = self._trees.get(root_corr)
        return tree.queued if tree else 0
