# SPDX-FileCopyrightText: Copyright (c) 2025-2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Lanes replaying one trace share a single decoded conversation per worker.

The LRU in ``Worker._borrow_conversation_for_session`` only bounds what is kept
when no session holds it. Anything a live session still references must be
found again through the weak-value registry, so a lane starting on a trace
other lanes are replaying borrows their decode instead of making its own.
"""

from __future__ import annotations

import asyncio
import gc
import weakref
from collections import OrderedDict
from types import SimpleNamespace

from aiperf.common.models.dataset_models import Conversation, Turn
from aiperf.workers import worker as worker_module
from aiperf.workers.worker import Worker


class _FakeWorker:
    """Just the state ``_borrow_conversation_for_session`` reads and writes."""

    def __init__(self) -> None:
        self._conversation_cache: OrderedDict[tuple[str, int], Conversation] = (
            OrderedDict()
        )
        self._live_conversations: weakref.WeakValueDictionary[
            tuple[str, int], Conversation
        ] = weakref.WeakValueDictionary()
        self.decodes: list[str] = []
        self.decode_gate: asyncio.Event | None = None

    async def _retrieve_conversation_for_session(self, *, credit_context):
        conversation_id = credit_context.credit.conversation_id
        self.decodes.append(conversation_id)
        if self.decode_gate is not None:
            await self.decode_gate.wait()
        return Conversation(
            session_id=conversation_id,
            turns=[Turn(role="user") for _ in range(credit_context.credit.num_turns)],
        )

    async def borrow(self, conversation_id: str, num_turns: int = 2) -> Conversation:
        credit_context = SimpleNamespace(
            credit=SimpleNamespace(conversation_id=conversation_id, num_turns=num_turns)
        )
        return await Worker._borrow_conversation_for_session(
            self, credit_context=credit_context
        )


async def test_live_conversation_evicted_from_lru_is_shared_not_redecoded(
    monkeypatch,
) -> None:
    monkeypatch.setattr(worker_module, "_CONVERSATION_CACHE_MAX_ENTRIES", 1)
    worker = _FakeWorker()

    held = await worker.borrow("trace-a")
    # A second trace pushes trace-a out of the one-entry LRU while a session
    # (``held``) is still replaying it.
    await worker.borrow("trace-b")
    assert ("trace-a", 2) not in worker._conversation_cache

    again = await worker.borrow("trace-a")

    assert again is held
    assert worker.decodes == ["trace-a", "trace-b"]


async def test_released_conversation_is_not_retained_by_the_registry(
    monkeypatch,
) -> None:
    monkeypatch.setattr(worker_module, "_CONVERSATION_CACHE_MAX_ENTRIES", 1)
    worker = _FakeWorker()

    await worker.borrow("trace-a")
    await worker.borrow("trace-b")  # evicts trace-a; no session holds it
    gc.collect()

    assert ("trace-a", 2) not in worker._live_conversations
    await worker.borrow("trace-a")
    assert worker.decodes == ["trace-a", "trace-b", "trace-a"]


async def test_num_turns_is_part_of_the_shared_key() -> None:
    worker = _FakeWorker()

    short = await worker.borrow("trace-a", num_turns=2)
    long = await worker.borrow("trace-a", num_turns=3)

    assert short is not long
    assert len(long.turns) == 3


async def test_concurrent_decodes_of_one_trace_converge_on_one_copy() -> None:
    worker = _FakeWorker()
    worker.decode_gate = asyncio.Event()

    first = asyncio.create_task(worker.borrow("trace-a"))
    second = asyncio.create_task(worker.borrow("trace-a"))
    await asyncio.sleep(0)
    worker.decode_gate.set()

    assert (await first) is (await second)
