# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

from pathlib import Path

import orjson
import pytest

from aiperf.cli_commands.synthesize import dynamo_trace
from aiperf.dataset.loader.weka_trace_models import WekaTrace


def _record(
    session_id: str,
    received_ms: int,
    hashes: list[int],
    *,
    parent_id: str | None = None,
    input_length: int | None = None,
) -> dict:
    context = {"session_id": session_id}
    if parent_id is not None:
        context["parent_session_id"] = parent_id
    return {
        "event": {
            "event_type": "request_end",
            "agent_context": context,
            "request": {
                "model": "test-model",
                "input_tokens": input_length
                if input_length is not None
                else len(hashes) * 16,
                "output_tokens": 8,
                "request_received_ms": received_ms,
                "total_time_ms": 100,
                "replay": {
                    "trace_block_size": 16,
                    "input_length": input_length
                    if input_length is not None
                    else len(hashes) * 16,
                    "input_sequence_hashes": hashes,
                },
            },
        }
    }


def _write_trace(path: Path, records: list[dict]) -> None:
    path.write_bytes(b"\n".join(orjson.dumps(record) for record in records) + b"\n")


def test_dynamo_trace_writes_all_lineages_with_agent_topology(tmp_path: Path) -> None:
    input_file = tmp_path / "trace.jsonl"
    output = tmp_path / "weka"
    _write_trace(
        input_file,
        [
            _record("root-a", 1_000, [10, 20, 99], input_length=33),
            _record("root-b", 1_500, [10, 50]),
            _record("child-a", 2_000, [10, 20, 30], parent_id="root-a"),
            _record("child-a", 3_000, [10, 20, 30, 31], parent_id="root-a"),
            _record("root-a", 5_000, [10, 40]),
        ],
    )

    dynamo_trace(input_file, output=output)

    traces = [
        WekaTrace.model_validate(orjson.loads(path.read_bytes()))
        for path in sorted(output.glob("trace_*.json"))
    ]
    assert [trace.id for trace in traces] == ["root-a", "root-b"]
    root_a, root_b = traces
    assert root_a.hash_id_scope == root_b.hash_id_scope == "global"
    assert [request.type for request in root_a.requests] == ["n", "subagent", "n"]
    assert [request.t for request in root_a.requests] == [0.0, 1.0, 4.0]
    assert root_a.requests[0].hash_ids == [10, 20]
    child = root_a.requests[1]
    assert child.agent_id == "child-a"
    assert child.requests[0].hash_ids[:2] == root_a.requests[0].hash_ids
    assert child.requests[-1].stop == "end_turn"
    assert root_a.requests[-1].hash_ids[0] == root_a.requests[0].hash_ids[0]
    assert root_a.requests[-1].hash_ids[-1] != child.requests[0].hash_ids[-1]
    assert root_a.requests[-1].stop == "end_turn"
    assert root_b.requests[0].t == 0.5
    assert root_b.requests[0].hash_ids[0] == root_a.requests[0].hash_ids[0]


def test_dynamo_trace_rejects_nested_sessions(tmp_path: Path) -> None:
    input_file = tmp_path / "trace.jsonl"
    records = [
        _record("root", 1_000, [1]),
        _record("child", 2_000, [1, 2], parent_id="root"),
        _record("grandchild", 3_000, [1, 2, 3], parent_id="child"),
    ]
    _write_trace(input_file, records)

    with pytest.raises(ValueError):
        dynamo_trace(input_file, output=tmp_path / "weka")


def test_dynamo_trace_validates_output_before_conversion(tmp_path: Path) -> None:
    output = tmp_path / "weka"
    output.touch()

    with pytest.raises(ValueError, match="Output path must be a directory"):
        dynamo_trace(tmp_path / "missing.jsonl", output=output)
