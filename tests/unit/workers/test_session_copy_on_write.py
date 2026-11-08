# SPDX-FileCopyrightText: Copyright (c) 2025-2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Sessions share the worker's decoded conversation and copy a turn on write.

The worker hands every session replaying a trace the *same* decoded
``Conversation`` (``Worker._borrow_conversation_for_session``). Cache-bust
writes must therefore land in a session-private copy of the turn
(``UserSession.own_turn``), never in the shared one: a marker leaking into the
shared turn would put session A's marker on session B's wire and break the
cache isolation the marker exists to provide.
"""

from __future__ import annotations

import pytest
from pytest import param

from aiperf.common.enums import (
    CacheBustTarget,
    ConversationContextMode,
    CreditPhase,
)
from aiperf.common.models.dataset_models import Conversation, Image, Text, Turn
from aiperf.credit.structs import Credit
from aiperf.endpoints.openai_chat import ChatEndpoint
from aiperf.plugin.enums import EndpointType
from aiperf.timing.strategies.cache_bust import build_cache_bust_marker
from aiperf.workers.payload_fragments import encode_payload_bytes
from aiperf.workers.session_manager import UserSession, UserSessionManager
from aiperf.workers.worker import _apply_cache_bust
from tests.unit.endpoints.conftest import create_model_endpoint, create_request_info

_SCREEN = "data:image/png;base64,QUFB"


def _raw_messages_conversation(
    context_mode: ConversationContextMode | None = None,
) -> Conversation:
    """Two delta turns: system + multimodal user, then a follow-up user turn."""
    return Conversation(
        session_id="traj-0",
        context_mode=context_mode,
        turns=[
            Turn(
                raw_messages=[
                    {"role": "system", "content": "You are an agent."},
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": "Open the settings."},
                            {
                                "type": "image_url",
                                "image_url": {"url": _SCREEN},
                                "uuid": "1111",
                            },
                        ],
                    },
                ],
                images=[Image(contents=[_SCREEN], uuids=["1111"])],
            ),
            Turn(raw_messages=[{"role": "user", "content": "Now close it."}]),
        ],
    )


def _texts_conversation() -> Conversation:
    """Synthetic-path conversation: no ``raw_messages``, the user text is ``texts``."""
    return Conversation(
        session_id="traj-0",
        turns=[
            Turn(texts=[Text(contents=["hello"])]),
            Turn(texts=[Text(contents=["bye"])]),
        ],
    )


def _marker(recycle_pass: int, target: CacheBustTarget) -> str:
    marker = build_cache_bust_marker(
        "bench", recycle_pass, recycle_pass, "traj-0", target=target
    )
    assert marker is not None
    return marker


def _credit(marker: str, target: CacheBustTarget, x_correlation_id: str) -> Credit:
    return Credit(
        id=0,
        phase=CreditPhase.PROFILING,
        conversation_id="traj-0",
        x_correlation_id=x_correlation_id,
        turn_index=0,
        num_turns=2,
        issued_at_ns=0,
        cache_bust_marker=marker,
        cache_bust_target=target,
    )


def _bust(session: UserSession, marker: str, target: CacheBustTarget) -> None:
    _apply_cache_bust(
        session,
        _credit(marker, target, session.x_correlation_id),
        session.conversation.system_message,
    )


def _body(session: UserSession) -> bytes:
    """The wire body the worker would send for this session right now."""
    endpoint = ChatEndpoint(create_model_endpoint(EndpointType.CHAT))
    request_info = create_request_info(
        endpoint.model_endpoint,
        turns=list(session.turn_list),
        system_message=session.conversation.system_message,
    )
    return encode_payload_bytes(endpoint.format_payload(request_info))


def _snapshot(conversation: Conversation) -> list[dict]:
    return [turn.model_dump() for turn in conversation.turns]


def _start(
    manager: UserSessionManager, name: str, conversation: Conversation
) -> UserSession:
    session = manager.create_and_store(name, conversation, len(conversation.turns))
    session.advance_turn(0)
    return session


@pytest.mark.parametrize(
    "conversation_factory, target",
    [
        param(_raw_messages_conversation, CacheBustTarget.SYSTEM_PREFIX, id="raw-system-prefix"),
        param(_raw_messages_conversation, CacheBustTarget.SYSTEM_SUFFIX, id="raw-system-suffix"),
        param(_raw_messages_conversation, CacheBustTarget.FIRST_TURN_PREFIX, id="raw-first-turn"),
        param(_texts_conversation, CacheBustTarget.FIRST_TURN_PREFIX, id="texts-first-turn"),
        param(_texts_conversation, CacheBustTarget.SYSTEM_PREFIX, id="texts-system-fallback"),
    ],
)  # fmt: skip
def test_busting_one_session_leaves_other_sessions_pristine(
    conversation_factory, target: CacheBustTarget
) -> None:
    """Session A's marker must not reach B, the shared turns, or a later session C."""
    conversation = conversation_factory()
    pristine_turns = _snapshot(conversation)
    manager = UserSessionManager()
    session_a = _start(manager, "a", conversation)
    session_b = _start(manager, "b", conversation)
    pristine_body = _body(session_b)
    marker_a = _marker(0, target)

    _bust(session_a, marker_a, target)

    # A really was marked, in a private copy of turn 0.
    marker_text = marker_a.strip().encode()
    assert marker_text in _body(session_a)
    assert session_a.turn_list[0] is not conversation.turns[0]
    # B still points at the shared turn, and its wire body is unchanged.
    assert session_b.turn_list[0] is conversation.turns[0]
    assert _body(session_b) == pristine_body
    assert marker_text not in _body(session_b)
    # The shared decoded conversation itself is untouched.
    assert _snapshot(conversation) == pristine_turns
    # A session created after the bust starts from the pristine conversation.
    session_c = _start(manager, "c", conversation)
    assert _body(session_c) == pristine_body

    # And B's own bust does not reach back into A.
    marker_b = _marker(1, target)
    _bust(session_b, marker_b, target)
    assert marker_b.strip().encode() in _body(session_b)
    assert marker_b.strip().encode() not in _body(session_a)
    assert marker_text in _body(session_a)
    assert _body(session_c) == pristine_body
    assert _snapshot(conversation) == pristine_turns


def test_a_turn_is_copied_once_and_untouched_turns_are_never_copied() -> None:
    """Re-marking on later credits is idempotent and must not clone again."""
    conversation = _raw_messages_conversation(
        ConversationContextMode.DELTAS_WITH_RESPONSES
    )
    manager = UserSessionManager()
    session = _start(manager, "a", conversation)
    target = CacheBustTarget.SYSTEM_PREFIX
    marker = _marker(0, target)

    _bust(session, marker, target)
    private_first = session.turn_list[0]
    body_after_first = _body(session)
    _bust(session, marker, target)
    assert session.turn_list[0] is private_first
    assert _body(session) == body_after_first

    session.advance_turn(1)
    _bust(session, marker, target)
    assert session.turn_list[0] is private_first
    # Turn 1 carries no system message: nothing writes it.
    assert session.turn_list[1] is conversation.turns[1]


def test_own_turn_returns_the_same_copy_for_original_and_copy() -> None:
    conversation = _raw_messages_conversation()
    session = _start(UserSessionManager(), "a", conversation)
    shared = conversation.turns[0]

    private = session.own_turn(shared)

    assert private is not shared
    assert session.turn_list[0] is private
    assert session.own_turn(shared) is private
    assert session.own_turn(private) is private
    # Containers are private; the message dicts are still shared.
    assert private.raw_messages is not shared.raw_messages
    assert all(
        mine is theirs
        for mine, theirs in zip(private.raw_messages, shared.raw_messages, strict=True)
    )


def test_message_array_mode_drops_copies_of_replaced_turns() -> None:
    """Each message-array turn holds its full history; past copies must not pile up."""
    conversation = _raw_messages_conversation(
        ConversationContextMode.MESSAGE_ARRAY_WITH_RESPONSES
    )
    session = _start(UserSessionManager(), "a", conversation)
    target = CacheBustTarget.FIRST_TURN_PREFIX
    marker = _marker(0, target)
    _bust(session, marker, target)
    assert session.turn_list[0] is not conversation.turns[0]

    session.advance_turn(1)

    assert session.turn_list == [conversation.turns[1]]
    assert session.turn_list[0] is conversation.turns[1]
    assert session._cow == {}
