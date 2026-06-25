# SPDX-FileCopyrightText: Copyright (c) 2025-2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

from aiperf.workers.dynamo_session_control import (
    build_session_control,
    merge_session_control,
)


def test_non_final_turn_binds_with_timeout() -> None:
    assert build_session_control(
        session_id="conv-1", is_final_turn=False, timeout_seconds=300
    ) == {"session_id": "conv-1", "action": "bind", "timeout": 300}


def test_final_turn_closes_without_timeout() -> None:
    assert build_session_control(
        session_id="conv-1", is_final_turn=True, timeout_seconds=300
    ) == {"session_id": "conv-1", "action": "close"}


def test_merge_preserves_existing_nvext_without_mutating_input() -> None:
    payload = {"nvext": {"trace": "keep"}}
    merged = merge_session_control(
        payload, {"session_id": "conv-1", "action": "bind", "timeout": 300}
    )
    assert payload == {"nvext": {"trace": "keep"}}
    assert merged["nvext"] == {
        "trace": "keep",
        "session_control": {
            "session_id": "conv-1",
            "action": "bind",
            "timeout": 300,
        },
    }
