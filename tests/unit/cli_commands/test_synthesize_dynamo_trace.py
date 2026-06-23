# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

from pathlib import Path

import orjson
import pytest

from aiperf.cli_commands.synthesize import dynamo_trace
from aiperf.dataset.loader.weka_trace_models import WekaTrace


def _record(
    trajectory_id: str,
    received_ms: int,
    hashes: list[int],
    *,
    parent_id: str | None = None,
    final: bool = False,
) -> dict:
    context = {"trajectory_id": trajectory_id}
    if parent_id is not None:
        context["parent_trajectory_id"] = parent_id
    if final:
        context["trajectory_final"] = True
    return {
        "event": {
            "event_type": "request_end",
            "agent_context": context,
            "request": {
                "model": "test-model",
                "input_tokens": len(hashes) * 16,
                "output_tokens": 8,
                "request_received_ms": received_ms,
                "total_time_ms": 100,
                "replay": {
                    "trace_block_size": 16,
                    "input_length": len(hashes) * 16,
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
            _record("root-a", 1_000, [10, 20]),
            _record("root-b", 1_500, [50], final=True),
            _record("child-a", 2_000, [10, 20, 30], parent_id="root-a"),
            _record("child-a", 3_000, [10, 20, 30, 31], parent_id="root-a", final=True),
            _record("root-a", 5_000, [10, 40], final=True),
        ],
    )

    dynamo_trace(input_file, output=output)

    traces = [
        WekaTrace.model_validate(orjson.loads(path.read_bytes()))
        for path in sorted(output.glob("trace_*.json"))
    ]
    assert [trace.id for trace in traces] == ["root-a", "root-b"]
    root_a, root_b = traces
    assert [request.type for request in root_a.requests] == ["n", "subagent", "n"]
    assert [request.t for request in root_a.requests] == [0.0, 1.0, 4.0]
    assert root_a.requests[0].hash_ids == [1, 2]
    child = root_a.requests[1]
    assert child.agent_id == "child-a"
    assert child.requests[0].hash_ids[:2] == root_a.requests[0].hash_ids
    assert child.requests[-1].stop == "end_turn"
    assert root_a.requests[-1].hash_ids[0] == root_a.requests[0].hash_ids[0]
    assert root_a.requests[-1].hash_ids[-1] != child.requests[0].hash_ids[-1]
    assert root_a.requests[-1].stop == "end_turn"
    assert root_b.requests[0].t == 0.5


@pytest.mark.parametrize("malformed", ["incomplete", "nested"])
def test_dynamo_trace_rejects_unrepresentable_trajectories(
    tmp_path: Path, malformed: str
) -> None:
    input_file = tmp_path / "trace.jsonl"
    records = [_record("root", 1_000, [1], final=True)]
    if malformed == "incomplete":
        records[0]["event"]["agent_context"].pop("trajectory_final")
    else:
        records.extend(
            [
                _record("child", 2_000, [1, 2], parent_id="root", final=True),
                _record("grandchild", 3_000, [1, 2, 3], parent_id="child", final=True),
            ]
        )
    _write_trace(input_file, records)

    with pytest.raises(ValueError):
        dynamo_trace(input_file, output=tmp_path / "weka")
