# SPDX-FileCopyrightText: Copyright (c) 2025-2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""The decoded-conversation cache is keyed on conversation id alone.

A cached conversation's turn list has exactly the length of the ``num_turns``
it was reconstructed with (the PAYLOAD_BYTES path loops ``range(num_turns)``).
Encoding the count in the key stopped a wrong-sized object being served, but it
also let one conversation occupy several entries. The count is asserted on the
hit path instead: a disagreement is reported once and served uncached, so one
conversation is one entry and a varying count is visible rather than multiplied.
"""

from collections import OrderedDict
from unittest.mock import AsyncMock, MagicMock

import pytest

from aiperf.common.models import Conversation, Turn
from aiperf.credit.structs import Credit
from aiperf.workers.worker import Worker


def _conversation(conversation_id: str, turns: int) -> Conversation:
    return Conversation(
        session_id=conversation_id,
        turns=[Turn(role="user") for _ in range(turns)],
    )


def _credit(conversation_id: str, num_turns: int) -> Credit:
    from aiperf.common.enums import CreditPhase

    return Credit(
        id=1,
        phase=CreditPhase.PROFILING,
        conversation_id=conversation_id,
        x_correlation_id="corr",
        turn_index=0,
        num_turns=num_turns,
        issued_at_ns=0,
    )


class _Cache:
    """Just enough of Worker to exercise ``_borrow_conversation_for_session``."""

    _borrow_conversation_for_session = Worker._borrow_conversation_for_session

    def __init__(self, built: dict[tuple[str, int], Conversation]) -> None:
        self._conversation_cache: OrderedDict[str, Conversation] = OrderedDict()
        self._reported_turn_count_mismatches: set[tuple[str, int, int]] = set()
        self.warning = MagicMock()
        self._retrieve_conversation_for_session = AsyncMock(
            side_effect=lambda *, credit_context: built[
                (credit_context.credit.conversation_id, credit_context.credit.num_turns)
            ]
        )


def _ctx(credit: Credit):
    from types import SimpleNamespace

    return SimpleNamespace(credit=credit)


@pytest.mark.asyncio
async def test_one_conversation_is_one_entry() -> None:
    built = {("conv", 3): _conversation("conv", 3)}
    cache = _Cache(built)

    await cache._borrow_conversation_for_session(credit_context=_ctx(_credit("conv", 3)))
    await cache._borrow_conversation_for_session(credit_context=_ctx(_credit("conv", 3)))

    assert list(cache._conversation_cache) == ["conv"]
    # Second call hit the cache; the reconstruction ran once.
    assert cache._retrieve_conversation_for_session.await_count == 1


@pytest.mark.asyncio
async def test_turn_count_disagreement_is_served_uncached_and_reported_once() -> None:
    built = {
        ("conv", 3): _conversation("conv", 3),
        ("conv", 5): _conversation("conv", 5),
    }
    cache = _Cache(built)

    await cache._borrow_conversation_for_session(credit_context=_ctx(_credit("conv", 3)))
    # Same id, different count: must not be handed the 3-turn object.
    served = await cache._borrow_conversation_for_session(
        credit_context=_ctx(_credit("conv", 5))
    )
    await cache._borrow_conversation_for_session(credit_context=_ctx(_credit("conv", 5)))

    assert len(served.turns) == 5
    assert cache.warning.call_count == 1
    # The mismatched count did not create a second cache entry.
    assert list(cache._conversation_cache) == ["conv"]
