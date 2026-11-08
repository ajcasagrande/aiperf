# SPDX-FileCopyrightText: Copyright (c) 2025-2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""The chat fragment splice must be byte-identical to a whole-payload encode.

The fast path exists only to avoid re-encoding conversation history, so its
single contract is that it never changes the wire bytes. Every test here
therefore compares against ``orjson.dumps`` rather than against a golden string.
"""

import orjson
import pytest

from aiperf.workers.payload_fragments import (
    _FragmentCache,
    encode_payload_bytes,
    reset_payload_fragment_cache,
)


@pytest.fixture(autouse=True)
def _isolate_cache():
    reset_payload_fragment_cache()
    yield
    reset_payload_fragment_cache()


def chat_payload(messages, **extra):
    payload = {"messages": messages, "model": "deepseek-v4.1-flash", "stream": True}
    payload.update(extra)
    return payload


def assert_identical(payload):
    encoded = encode_payload_bytes(payload)
    assert encoded == orjson.dumps(payload)
    return encoded


class TestByteEquality:
    def test_single_message(self):
        assert_identical(chat_payload([{"role": "user", "content": "hi"}]))

    def test_multi_turn_history(self):
        messages = [
            {"role": "system", "content": "you are a coding agent"},
            {"role": "user", "content": "read the file"},
            {"role": "assistant", "content": None, "tool_calls": [{"id": "c1"}]},
            {"role": "tool", "content": "def main(): ...", "tool_call_id": "c1"},
        ]
        assert_identical(chat_payload(messages))

    def test_unicode_and_escapes(self):
        messages = [
            {"role": "user", "content": 'quote " backslash \\ newline \n tab \t'},
            {"role": "user", "content": "emoji \U0001f680 kanji 漢字"},
            {"role": "user", "content": "\x00\x01\x1f control"},
        ]
        assert_identical(chat_payload(messages))

    def test_nested_content_parts(self):
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "describe"},
                    {"type": "image_url", "image_url": {"url": "data:image/png;base64,AA"}},
                ],
            }
        ]
        assert_identical(chat_payload(messages))

    def test_numbers_and_bools_keep_orjson_form(self):
        payload = chat_payload(
            [{"role": "user", "content": "x"}],
            max_completion_tokens=4096,
            temperature=0.0,
            top_p=1.0,
            logprobs=False,
        )
        assert_identical(payload)

    def test_stream_options_tail(self):
        payload = chat_payload(
            [{"role": "user", "content": "x"}],
            stream_options={"include_usage": True},
        )
        assert_identical(payload)

    def test_messages_only_payload(self):
        assert_identical({"messages": [{"role": "user", "content": "x"}]})

    def test_large_body_with_expensive_escapes(self):
        # AgentX prompts run to megabytes and are full of quotes and newlines.
        body = ('{ "key": "value" }\n' * 40000)
        assert_identical(chat_payload([{"role": "user", "content": body}]))


class TestCacheBust:
    def test_replaced_first_message_is_reencoded(self):
        """Cache-bust replaces the first dict, so its fragment must be rebuilt."""
        shared = {"role": "user", "content": "original"}
        assert_identical(chat_payload([shared]))

        busted = {**shared, "content": "cache-bust-marker-original"}
        assert busted is not shared
        encoded = assert_identical(chat_payload([busted]))
        assert b"cache-bust-marker" in encoded

    def test_original_fragment_not_served_for_busted_dict(self):
        shared = {"role": "user", "content": "original"}
        encode_payload_bytes(chat_payload([shared]))
        busted = {**shared, "content": "marker:original"}
        encoded = encode_payload_bytes(chat_payload([busted]))
        assert b'"original"' not in encoded
        assert encoded == orjson.dumps(chat_payload([busted]))

    def test_growing_history_reuses_earlier_fragments(self):
        messages = [{"role": "user", "content": "turn 1"}]
        assert_identical(chat_payload(messages))
        messages.append({"role": "assistant", "content": "reply 1"})
        assert_identical(chat_payload(messages))
        messages.append({"role": "user", "content": "turn 2"})
        assert_identical(chat_payload(messages))


class TestFallback:
    def test_messages_not_first_key(self):
        payload = {"model": "m", "messages": [{"role": "user", "content": "x"}]}
        assert encode_payload_bytes(payload) == orjson.dumps(payload)

    def test_non_dict_message_falls_back(self):
        payload = chat_payload(["not a dict"])
        assert encode_payload_bytes(payload) == orjson.dumps(payload)

    def test_messages_not_a_list(self):
        payload = {"messages": "nope", "model": "m"}
        assert encode_payload_bytes(payload) == orjson.dumps(payload)

    def test_empty_messages_falls_back(self):
        payload = {"messages": [], "model": "m"}
        assert encode_payload_bytes(payload) == orjson.dumps(payload)

    def test_no_messages_key(self):
        payload = {"prompt": "completions style"}
        assert encode_payload_bytes(payload) == orjson.dumps(payload)

    def test_dict_subclass_message_falls_back(self):
        class MyDict(dict):
            pass

        payload = chat_payload([MyDict(role="user", content="x")])
        assert encode_payload_bytes(payload) == orjson.dumps(payload)


class TestFragmentCache:
    def test_get_requires_same_object(self):
        cache = _FragmentCache(budget_bytes=1 << 20)
        message = {"role": "user", "content": "x"}
        cache.put(message, b"frag")
        assert cache.get(message) == b"frag"
        assert cache.get({"role": "user", "content": "x"}) is None

    def test_eviction_respects_budget(self):
        cache = _FragmentCache(budget_bytes=10)
        kept = []
        for index in range(10):
            message = {"role": "user", "content": str(index)}
            kept.append(message)
            cache.put(message, b"12345")
        assert cache._retained_bytes <= 10
        # The newest entry always survives so a single large message still caches.
        assert cache.get(kept[-1]) == b"12345"

    def test_evicted_message_is_reencoded_not_corrupted(self):
        cache = _FragmentCache(budget_bytes=1)
        first = {"role": "user", "content": "a"}
        second = {"role": "user", "content": "b"}
        cache.put(first, b"aaaa")
        cache.put(second, b"bbbb")
        assert cache.get(first) is None
        assert cache.get(second) == b"bbbb"
