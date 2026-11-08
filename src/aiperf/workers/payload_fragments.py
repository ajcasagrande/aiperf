# SPDX-FileCopyrightText: Copyright (c) 2025-2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Encode an OpenAI chat payload by joining pre-encoded message fragments.

AgentX replays a long conversation turn by turn, and every turn re-sends the
whole accumulated history. Encoding that body from scratch costs
``O(total context bytes)`` of ``orjson`` work on *every* request, so the cost
grows with turn number.

The Rust port does not pay this. It serializes each message once at
composition time and, at send time, reserves the exact length and writes
``{"messages":[`` + each message's pre-encoded wire bytes joined by ``,``
(``crates/dataset/segment-store/src/materialize.rs:89-110``). This module is
the Python equivalent for the chat path.

Why a per-message cache rather than a per-session joined prefix: the worker
already decodes each conversation once and every session points at that shared
copy; a cache-bust write clones only the written turn's containers and keeps
its message dicts (``session_manager.py`` ``UserSession.own_turn``).
Message dicts are therefore shared process-wide, so one encoded fragment serves
every session replaying that trace. A per-session joined-prefix buffer would
instead store one full copy of the conversation per live session, which is the
same memory blow-up the conversation cache bound exists to prevent.

Bounding: entries are strong-referenced (so ``id()`` cannot be reused while an
entry lives) and evicted least-recently-used once the retained encoded bytes
exceed a per-process budget. An eviction only costs a re-encode.

Byte equality: ``orjson`` emits compact output with no spaces and serializes
list elements independently, so ``orjson.dumps(payload)`` equals
``b'{"messages":[' + b",".join(orjson.dumps(m) for m in messages) + b"]"``
plus the remaining keys. That only holds while ``messages`` is the first key in
insertion order, which this module verifies and otherwise declines the fast
path.
"""

from __future__ import annotations

import os
from collections import OrderedDict
from typing import Any

import orjson

_MESSAGES_KEY = "messages"
_ENVELOPE_HEAD = b'{"messages":['
_ENVELOPE_SEP = b","
_ENVELOPE_TAIL = b"]"

#: Per-process budget for retained encoded fragments. A miss re-encodes one
#: message, so this only trades a little CPU for a hard memory ceiling.
DEFAULT_FRAGMENT_BUDGET_BYTES = 64 * 1024 * 1024
_BUDGET_ENV = "AIPERF_PAYLOAD_FRAGMENT_BUDGET_BYTES"


class _FragmentCache:
    """Least-recently-used cache of ``id(message) -> encoded bytes``.

    Holds a strong reference to each cached message so CPython cannot recycle
    its address, which is what makes keying on ``id()`` sound.
    """

    __slots__ = ("_entries", "_refs", "_retained_bytes", "_budget_bytes")

    def __init__(self, budget_bytes: int) -> None:
        self._entries: OrderedDict[int, bytes] = OrderedDict()
        self._refs: dict[int, dict[Any, Any]] = {}
        self._retained_bytes = 0
        self._budget_bytes = budget_bytes

    def get(self, message: dict[Any, Any]) -> bytes | None:
        key = id(message)
        fragment = self._entries.get(key)
        if fragment is None:
            return None
        # Reject a recycled address whose occupant is a different dict.
        if self._refs[key] is not message:
            self._discard(key)
            return None
        self._entries.move_to_end(key)
        return fragment

    def put(self, message: dict[Any, Any], fragment: bytes) -> None:
        key = id(message)
        if key in self._entries:
            self._retained_bytes -= len(self._entries[key])
            self._entries[key] = fragment
            self._entries.move_to_end(key)
        else:
            self._entries[key] = fragment
            self._refs[key] = message
        self._retained_bytes += len(fragment)
        self._evict_to_budget()

    def _evict_to_budget(self) -> None:
        while self._retained_bytes > self._budget_bytes and len(self._entries) > 1:
            oldest_key, oldest = self._entries.popitem(last=False)
            self._retained_bytes -= len(oldest)
            self._refs.pop(oldest_key, None)

    def _discard(self, key: int) -> None:
        fragment = self._entries.pop(key, None)
        self._refs.pop(key, None)
        if fragment is not None:
            self._retained_bytes -= len(fragment)

    def clear(self) -> None:
        self._entries.clear()
        self._refs.clear()
        self._retained_bytes = 0


def _resolve_budget() -> int:
    raw = os.environ.get(_BUDGET_ENV)
    if not raw:
        return DEFAULT_FRAGMENT_BUDGET_BYTES
    try:
        budget = int(raw)
    except ValueError:
        return DEFAULT_FRAGMENT_BUDGET_BYTES
    return budget if budget > 0 else DEFAULT_FRAGMENT_BUDGET_BYTES


_fragment_cache = _FragmentCache(_resolve_budget())


def reset_payload_fragment_cache() -> None:
    """Drop every cached fragment. Test isolation and post-run cleanup."""
    _fragment_cache.clear()


def _encode_messages(messages: list[Any]) -> bytes | None:
    """Join the messages array, reusing cached fragments.

    Returns ``None`` when an element is not a plain dict, which forces the
    caller onto the whole-payload encode path.
    """
    fragments: list[bytes] = []
    for message in messages:
        if type(message) is not dict:
            return None
        fragment = _fragment_cache.get(message)
        if fragment is None:
            fragment = orjson.dumps(message)
            _fragment_cache.put(message, fragment)
        fragments.append(fragment)
    return _ENVELOPE_SEP.join(fragments)


def encode_payload_bytes(payload: dict[str, Any]) -> bytes:
    """Serialize a request payload, splicing pre-encoded chat fragments.

    Falls back to ``orjson.dumps`` for anything that is not a plain chat body;
    the fast path is a pure optimization and never changes the bytes.
    """
    messages = payload.get(_MESSAGES_KEY)
    if type(messages) is not list or not messages:
        return orjson.dumps(payload)
    # ``orjson`` serializes in insertion order, so the splice is only valid
    # when ``messages`` really is the first key.
    if next(iter(payload), None) != _MESSAGES_KEY:
        return orjson.dumps(payload)

    joined = _encode_messages(messages)
    if joined is None:
        return orjson.dumps(payload)

    body = [_ENVELOPE_HEAD, joined, _ENVELOPE_TAIL]
    remainder = [(key, value) for key, value in payload.items() if key != _MESSAGES_KEY]
    if remainder:
        # Strip the braces off the remainder's own object so it can be spliced
        # as the rest of the payload's members, preserving their key order.
        body.append(_ENVELOPE_SEP)
        body.append(orjson.dumps(dict(remainder))[1:-1])
    body.append(b"}")
    return b"".join(body)
