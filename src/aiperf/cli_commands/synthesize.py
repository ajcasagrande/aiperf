# SPDX-FileCopyrightText: Copyright (c) 2025-2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""CLI command for synthesizing datasets."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, Any, Literal

import orjson
from cyclopts import App, Parameter
from rich.console import Console

from aiperf.dataset.loader.weka_trace_models import WekaTrace

app = App(name="synthesize")


@app.command(name="dynamo-trace")
def dynamo_trace(
    input_file: Path,
    *,
    output: Path,
    root_trajectory_id: str | None = None,
) -> None:
    """Convert canonical Dynamo request traces into replayable Weka traces.

    Args:
        input_file: Dynamo ``dynamo.request.trace.v1`` JSONL file.
        output: Empty directory for generated Weka trace files.
        root_trajectory_id: Optional root lineage to select instead of converting all roots.
    """
    traces = _dynamo_traces_to_weka(input_file, root_trajectory_id)
    if output.exists() and any(output.iterdir()):
        raise ValueError(f"Output directory must be empty: {output}")
    output.mkdir(parents=True, exist_ok=True)
    for index, trace in enumerate(traces):
        (output / f"trace_{index:06d}.json").write_bytes(
            orjson.dumps(
                trace.model_dump(by_alias=True, exclude_none=True),
                option=orjson.OPT_INDENT_2 | orjson.OPT_APPEND_NEWLINE,
            )
        )

    Console().print(f"[green]Weka traces: {len(traces)} written to {output}[/green]")


_TraceRow = dict[str, Any]


def _validate_identity(trajectory_id: Any, parent_id: Any, line_number: int) -> None:
    if not isinstance(trajectory_id, str) or not trajectory_id:
        raise ValueError(
            f"Line {line_number}: trajectory_id must be a non-empty string"
        )
    if parent_id is not None and (not isinstance(parent_id, str) or not parent_id):
        raise ValueError(f"Line {line_number}: parent_trajectory_id must be a string")


def _validate_request_fields(
    *,
    received_ms: Any,
    block_size: Any,
    input_length: Any,
    output_length: Any,
    hashes: Any,
    model: Any,
    total_time_ms: Any,
    line_number: int,
) -> None:
    if not isinstance(received_ms, (int, float)):
        raise ValueError(f"Line {line_number}: request_received_ms must be numeric")
    for field, value in (
        ("trace_block_size", block_size),
        ("input_length", input_length),
        ("output_tokens", output_length),
    ):
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            raise ValueError(
                f"Line {line_number}: {field} must be a non-negative integer"
            )
    if block_size == 0:
        raise ValueError(f"Line {line_number}: trace_block_size must be positive")
    if not isinstance(hashes, list) or not all(
        isinstance(item, int) and not isinstance(item, bool) for item in hashes
    ):
        raise ValueError(f"Line {line_number}: input_sequence_hashes must be integers")
    if not isinstance(model, str) or not model:
        raise ValueError(f"Line {line_number}: model must be a non-empty string")
    if total_time_ms is not None and not isinstance(total_time_ms, (int, float)):
        raise ValueError(f"Line {line_number}: total_time_ms must be numeric")


def _parse_dynamo_record(record: Any, line_number: int) -> _TraceRow | None:
    event = record.get("event") if isinstance(record, dict) else None
    if not isinstance(event, dict) or event.get("event_type") != "request_end":
        return None
    context = event.get("agent_context")
    if not isinstance(context, dict) or not context.get("trajectory_id"):
        return None
    request = event.get("request")
    replay = request.get("replay") if isinstance(request, dict) else None
    if not isinstance(request, dict) or not isinstance(replay, dict):
        raise ValueError(
            f"Line {line_number}: agent request is missing replay metadata"
        )

    trajectory_id = context["trajectory_id"]
    parent_id = context.get("parent_trajectory_id")
    received_ms = request.get("request_received_ms")
    block_size = replay.get("trace_block_size")
    input_length = replay.get("input_length")
    output_length = request.get("output_tokens")
    hashes = replay.get("input_sequence_hashes")
    model = request.get("model")
    total_time_ms = request.get("total_time_ms")
    _validate_identity(trajectory_id, parent_id, line_number)
    _validate_request_fields(
        received_ms=received_ms,
        block_size=block_size,
        input_length=input_length,
        output_length=output_length,
        hashes=hashes,
        model=model,
        total_time_ms=total_time_ms,
        line_number=line_number,
    )
    return {
        "trajectory_id": trajectory_id,
        "parent_trajectory_id": parent_id,
        "received_ms": float(received_ms),
        "block_size": block_size,
        "input_length": input_length,
        "output_length": output_length,
        "hashes": hashes,
        "model": model,
        "total_time_ms": float(total_time_ms) if total_time_ms is not None else None,
    }


def _load_dynamo_rows(input_file: Path) -> list[_TraceRow]:
    if not input_file.is_file():
        raise ValueError(f"Dynamo trace does not exist: {input_file}")
    rows = []
    with input_file.open("rb") as trace_file:
        for line_number, line in enumerate(trace_file, 1):
            if not line.strip():
                continue
            try:
                record = orjson.loads(line)
            except orjson.JSONDecodeError as error:
                raise ValueError(
                    f"Invalid JSON on line {line_number} of {input_file}"
                ) from error
            row = _parse_dynamo_record(record, line_number)
            if row is not None:
                rows.append(row)
    if not rows:
        raise ValueError(f"No replayable agent requests found in {input_file}")
    return sorted(rows, key=lambda row: row["received_ms"])


def _group_trajectories(
    rows: list[_TraceRow],
) -> tuple[dict[str, list[_TraceRow]], dict[str, str | None]]:
    grouped: dict[str, list[_TraceRow]] = {}
    for row in rows:
        grouped.setdefault(row["trajectory_id"], []).append(row)

    parents: dict[str, str | None] = {}
    for trajectory_id, trajectory_rows in grouped.items():
        parent_ids = {row["parent_trajectory_id"] for row in trajectory_rows}
        if len(parent_ids) != 1:
            raise ValueError(f"Trajectory has inconsistent parents: {trajectory_id}")
        parent_id = next(iter(parent_ids))
        if parent_id == trajectory_id:
            raise ValueError(f"Trajectory cannot parent itself: {trajectory_id}")
        if parent_id is not None and parent_id not in grouped:
            raise ValueError(
                f"Trajectory {trajectory_id} references missing parent {parent_id}"
            )
        parents[trajectory_id] = parent_id

    return grouped, parents


def _lineage_roots(
    grouped: dict[str, list[_TraceRow]],
    parents: dict[str, str | None],
    requested_root: str | None,
) -> list[str]:
    roots = sorted(
        (trajectory_id for trajectory_id, parent in parents.items() if parent is None),
        key=lambda trajectory_id: grouped[trajectory_id][0]["received_ms"],
    )
    if requested_root is not None:
        if requested_root not in roots:
            raise ValueError(f"Root trajectory not found: {requested_root}")
        roots = [requested_root]

    for trajectory_id, parent_id in parents.items():
        if parent_id is not None and parents[parent_id] is not None:
            raise ValueError(
                "Nested subagents are not representable by the Weka trace schema: "
                f"{trajectory_id}"
            )
    return roots


def _weka_request(
    row: _TraceRow,
    *,
    origin_ms: float,
    final: bool,
    normalized_hashes: dict[int, int],
) -> dict[str, Any]:
    hashes = [
        normalized_hashes.setdefault(raw_hash, len(normalized_hashes) + 1)
        for raw_hash in row["hashes"]
    ]
    request = {
        "t": round((row["received_ms"] - origin_ms) / 1000, 6),
        "type": "n",
        "model": row["model"],
        "in": row["input_length"],
        "out": row["output_length"],
        "hash_ids": hashes,
        "stop": "end_turn" if final else "tool_use",
    }
    if row["total_time_ms"] is not None:
        request["api_time"] = row["total_time_ms"] / 1000
    return request


def _weka_subagent(
    child_id: str,
    child_rows: list[_TraceRow],
    *,
    origin_ms: float,
    normalized_hashes: dict[int, int],
) -> dict[str, Any]:
    requests = [
        _weka_request(
            row,
            origin_ms=origin_ms,
            final=index == len(child_rows) - 1,
            normalized_hashes=normalized_hashes,
        )
        for index, row in enumerate(child_rows)
    ]
    child_end_ms = child_rows[-1]["received_ms"] + (
        child_rows[-1]["total_time_ms"] or 0
    )
    return {
        "t": requests[0]["t"],
        "type": "subagent",
        "agent_id": child_id,
        "subagent_type": "agent",
        "duration_ms": round(child_end_ms - child_rows[0]["received_ms"]),
        "total_tokens": sum(
            row["input_length"] + row["output_length"] for row in child_rows
        ),
        "status": "completed",
        "requests": requests,
        "models": sorted({row["model"] for row in child_rows}),
        "tool_tokens": 0,
        "system_tokens": 0,
    }


def _build_weka_trace(
    root_id: str,
    grouped: dict[str, list[_TraceRow]],
    parents: dict[str, str | None],
    origin_ms: float,
) -> WekaTrace:
    child_ids = sorted(
        (
            trajectory_id
            for trajectory_id, parent in parents.items()
            if parent == root_id
        ),
        key=lambda trajectory_id: grouped[trajectory_id][0]["received_ms"],
    )
    selected_ids = [root_id, *child_ids]
    selected_rows = [row for item in selected_ids for row in grouped[item]]
    block_sizes = {row["block_size"] for row in selected_rows}
    if len(block_sizes) != 1:
        raise ValueError(f"Lineage must use one trace block size: {root_id}")

    normalized_hashes: dict[int, int] = {}
    timeline: list[tuple[float, int, dict[str, Any]]] = []
    root_rows = grouped[root_id]
    for index, row in enumerate(root_rows):
        timeline.append(
            (
                row["received_ms"],
                0,
                _weka_request(
                    row,
                    origin_ms=origin_ms,
                    final=index == len(root_rows) - 1,
                    normalized_hashes=normalized_hashes,
                ),
            )
        )

    for child_id in child_ids:
        child_rows = grouped[child_id]
        timeline.append(
            (
                child_rows[0]["received_ms"],
                1,
                _weka_subagent(
                    child_id,
                    child_rows,
                    origin_ms=origin_ms,
                    normalized_hashes=normalized_hashes,
                ),
            )
        )

    return WekaTrace.model_validate(
        {
            "id": root_id,
            "models": sorted({row["model"] for row in selected_rows}),
            "block_size": next(iter(block_sizes)),
            "hash_id_scope": "local",
            "tool_tokens": 0,
            "system_tokens": 0,
            "requests": [
                item[2]
                for item in sorted(timeline, key=lambda item: (item[0], item[1]))
            ],
            "totals": {
                "requests": len(selected_rows),
                "subagents": len(child_ids),
                "input_tokens": sum(row["input_length"] for row in selected_rows),
                "output_tokens": sum(row["output_length"] for row in selected_rows),
            },
        }
    )


def _dynamo_traces_to_weka(
    input_file: Path, root_trajectory_id: str | None = None
) -> list[WekaTrace]:
    rows = _load_dynamo_rows(input_file)
    grouped, parents = _group_trajectories(rows)
    roots = _lineage_roots(grouped, parents, root_trajectory_id)
    origin_ms = min(row["received_ms"] for row in rows)
    return [
        _build_weka_trace(root_id, grouped, parents, origin_ms) for root_id in roots
    ]


@app.default
def synthesize(
    target: Annotated[
        Literal["agentic-code"],
        Parameter(help="Dataset workload to synthesize"),
    ],
    *,
    num_sessions: int = 1000,
    output: Path = Path("."),
    config: str | None = None,
    seed: int = 42,
    max_isl: int | None = None,
    max_osl: int | None = None,
) -> None:
    """Synthesize a dataset workload.

    Args:
        target: Dataset workload to synthesize.
        num_sessions: Number of sessions to generate.
        output: Parent directory for the run directory.
        config: Path to config/manifest JSON.
        seed: Random seed for reproducibility.
        max_isl: Maximum input sequence length.
        max_osl: Maximum output sequence length.
    """
    match target:
        case "agentic-code":
            from aiperf.dataset.agentic_code_gen.cli import synthesize as _synthesize

            _synthesize(
                num_sessions=num_sessions,
                output=output,
                config=config,
                seed=seed,
                max_isl=max_isl,
                max_osl=max_osl,
            )
