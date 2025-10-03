<!--
SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
SPDX-License-Identifier: Apache-2.0
-->

# Raw Record Export

AIPerf supports exporting raw request records for post-processing and delayed metrics analysis.

## Overview

The raw record export feature writes complete `RequestRecord` objects to JSONL files before any parsing or metric computation occurs. This enables:

- **Delayed metrics processing** - Process metrics after the benchmark completes
- **Custom analysis** - Analyze raw records with custom tools
- **Debugging** - Inspect full request/response data including timing
- **Archival** - Store complete benchmark data for future analysis

## Architecture

Raw records are written in the **Record Processor** layer, not in Workers:

```
Worker → [RequestRecord] → Record Processor → [writes RAW JSONL + computes metrics] → Records Manager
```

This design:
- ✅ Preserves timing accuracy in workers
- ✅ Distributes I/O load across record processors
- ✅ Keeps workers focused on accurate request execution
- ✅ Enables independent scaling of processing vs execution

## Usage

Enable raw record export by setting the export level to `raw`:

```bash
aiperf \
  --model-name test-model \
  --endpoint-url http://localhost:8000/v1/chat/completions \
  --export-level raw \
  --concurrency 10 \
  --num-requests 100
```

### Export Levels

AIPerf supports three export levels:

| Level | Description | Output |
|-------|-------------|--------|
| `summary` | Aggregated metrics only (most compact) | CSV, JSON with summary stats |
| `records` | Per-record metrics with display units (default) | JSONL with computed metrics |
| `raw` | Raw records with full request/response data | JSONL with complete RequestRecord objects |

## Output Files

When using `--export-level raw`, AIPerf creates per-processor JSONL files:

```
artifacts/
├── profile_export_raw_processor-1.jsonl
├── profile_export_raw_processor-2.jsonl
└── profile_export_raw_processor-N.jsonl
```

Each line contains a complete `RequestRecord` object serialized as JSON.

### RequestRecord Schema

Each raw record contains:

```python
{
    "model_name": str,              # Model that handled the request
    "conversation_id": str,         # Conversation ID (if applicable)
    "turn_index": int,              # Turn index in conversation
    "timestamp_ns": int,            # Wall clock timestamp (time.time_ns)
    "start_perf_ns": int,           # Performance counter start (perf_counter_ns)
    "end_perf_ns": int,             # Performance counter end
    "recv_start_perf_ns": int,      # Stream start time (if streaming)
    "status": int,                  # HTTP status code
    "responses": [...],             # Raw responses (SSE messages, text)
    "error": {...},                 # Error details (if failed)
    "delayed_ns": int,              # Request delay from expected time
    "credit_phase": str,            # "warmup" or "profiling"
    "credit_drop_latency": int,     # Internal latency from credit drop
    "was_cancelled": bool,          # Request cancellation status
    "cancel_after_ns": int,         # Cancellation timeout
    "x_request_id": str,            # Unique request ID
    "x_correlation_id": str,        # Credit drop correlation ID
    "turn": {...}                   # Request turn data
}
```

## Post-Processing Raw Records

Example script to process raw records:

```python
import orjson
from pathlib import Path

def process_raw_records(artifact_dir: Path):
    """Process raw record files and compute custom metrics."""
    records = []

    # Read all processor files
    for jsonl_file in artifact_dir.glob("profile_export_raw_*.jsonl"):
        with open(jsonl_file, "rb") as f:
            for line in f:
                record = orjson.loads(line)
                records.append(record)

    # Compute custom metrics
    latencies = [
        (r["end_perf_ns"] - r["start_perf_ns"]) / 1e9
        for r in records
        if not r.get("error")
    ]

    print(f"Total records: {len(records)}")
    print(f"Valid records: {len(latencies)}")
    print(f"Average latency: {sum(latencies) / len(latencies):.3f}s")
    print(f"P95 latency: {sorted(latencies)[int(len(latencies) * 0.95)]:.3f}s")

if __name__ == "__main__":
    process_raw_records(Path("./artifacts"))
```

## Performance Considerations

### Worker Performance

Raw record export has **zero impact on worker timing accuracy**:
- Workers send records via async ZMQ PUSH (fire-and-forget)
- All timing measurements occur before sending
- No file I/O in the worker process

### Record Processor Performance

Record processors handle I/O efficiently:
- **Buffered writes** - Records batched to reduce I/O overhead (default batch size: 10)
- **Async I/O** - Uses `aiofiles` for non-blocking writes
- **Distributed load** - Each processor writes to its own file
- **Independent scaling** - Processors scale separately from workers (1:4 ratio)

### Disk Space

Raw records consume more disk space than computed metrics:
- Each record: ~500 bytes to 5KB depending on response size
- Streaming responses with many tokens: larger records
- Estimate: ~1-10 MB per 1000 requests

## Migration from Records Export

Switching from `--export-level records` to `--export-level raw`:

**Before (RECORDS):**
```bash
aiperf --export-level records ...
# Output: profile_export.jsonl with computed metrics
```

**After (RAW):**
```bash
aiperf --export-level raw ...
# Output: profile_export_raw_processor-*.jsonl with raw records
```

The raw records contain **more data** than computed metrics:
- Full request/response payloads
- All timing measurements
- Error details
- Internal metadata

You can compute the same metrics from raw records using custom post-processing scripts.

## Best Practices

1. **Use RAW for debugging** - Full visibility into request/response data
2. **Use RAW for archival** - Complete data for future analysis
3. **Use RECORDS for production** - Computed metrics with less disk space
4. **Consolidate files** - Merge per-processor files for easier analysis
5. **Filter by phase** - Process only `credit_phase: "profiling"` records for metrics

## Example: Consolidate Raw Records

```python
import orjson
from pathlib import Path

def consolidate_raw_records(artifact_dir: Path, output_file: Path):
    """Consolidate per-processor raw records into a single file."""
    with open(output_file, "wb") as out:
        for jsonl_file in sorted(artifact_dir.glob("profile_export_raw_*.jsonl")):
            with open(jsonl_file, "rb") as f:
                for line in f:
                    out.write(line)

if __name__ == "__main__":
    consolidate_raw_records(
        Path("./artifacts"),
        Path("./artifacts/profile_export_raw_consolidated.jsonl")
    )
```

## Troubleshooting

### No raw record files generated

**Cause:** Export level not set to `raw`

**Solution:** Add `--export-level raw` to your command

### Incomplete records after benchmark

**Cause:** Record processors shutdown before flushing buffers

**Solution:** This shouldn't happen - record processors flush on shutdown. If it does, report as a bug.

### High disk I/O during benchmark

**Cause:** Large batch size or very high request rate

**Solution:** This is normal. Raw record writing is buffered and async to minimize impact.

## Related Documentation

- [CLI Options](cli_options.md) - Complete CLI reference
- [Architecture](architecture.md) - System architecture overview
- [Examples](../examples/README.md) - Example scripts and usage

