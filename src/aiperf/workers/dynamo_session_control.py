# SPDX-FileCopyrightText: Copyright (c) 2025-2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Deprecated ``nvext.session_control`` compatibility helpers."""

from __future__ import annotations

from typing import Any


def build_session_control(
    *,
    session_id: str,
    is_final_turn: bool,
    timeout_seconds: int,
) -> dict[str, Any]:
    """Build one bind/close session-control payload."""
    if is_final_turn:
        return {"session_id": session_id, "action": "close"}
    return {
        "session_id": session_id,
        "action": "bind",
        "timeout": timeout_seconds,
    }


def merge_session_control(
    payload: dict[str, Any],
    session_control: dict[str, Any],
) -> dict[str, Any]:
    """Return a copy of ``payload`` with ``session_control`` under ``nvext``."""
    merged = dict(payload)
    raw_nvext = merged.get("nvext")
    nvext = dict(raw_nvext) if isinstance(raw_nvext, dict) else {}
    raw_session_control = nvext.get("session_control")
    merged_session_control = (
        dict(raw_session_control) if isinstance(raw_session_control, dict) else {}
    )
    merged_session_control.update(session_control)
    nvext["session_control"] = merged_session_control
    merged["nvext"] = nvext
    return merged
