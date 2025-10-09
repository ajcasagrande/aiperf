<!--
SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
SPDX-License-Identifier: Apache-2.0
-->

# Raw Records Export

AIPerf can export detailed per-request data including raw request/response content and all computed metrics to JSONL files for deep analysis and debugging.

## Overview

This feature exports **COMPLETE** data for every request:
- **Request data**: Complete prompts, parameters, timestamps
- **Response data**: Token counts, timing information, and **FULL response content** (all tokens/text)
- **Per-record metrics**: **ALL** metrics computed for each individual request (TTFT, ITL, latency, etc.)
- **Error information**: Complete error details for failed requests

⚠️ **WARNING**: This exports the FULL response content for every request. Files can become very large (hundreds of MB to GB) depending on:
- Number of requests
- Response lengths (output tokens)
- Number of response chunks (streaming mode)

## Enabling Raw Record Export

Use `--export-level raw` to enable raw record export:

```bash
aiperf profile \
  --model Qwen/Qwen3-0.6B \
  --url http://localhost:8000 \
  --endpoint-type chat \
  --streaming \
  --concurrency 10 \
  --request-count 100 \
  --export-level raw  # Enable raw record export
```

**Note:** This is the most detailed export level. See [Export Levels](export-levels.md) for other options.

## Output Location

Raw records are written to:
```
<artifact-directory>/raw_records/raw_records_<processor-id>.jsonl
```

For example:
```
artifacts/my-benchmark/raw_records/raw_records_record-processor-1.jsonl
artifacts/my-benchmark/raw_records/raw_records_record-processor-2.jsonl
```

**Important**: Each RecordProcessor instance writes to its own file. In distributed setups, you'll have multiple files (one per processor).

## File Format

### JSONL (Newline-Delimited JSON)

Each line is a complete JSON object representing one request/response:

```jsonl
{"worker_id": "worker-1", "processor_id": "processor-1", "parsed_record": {...}, "metrics": {...}}
{"worker_id": "worker-1", "processor_id": "processor-1", "parsed_record": {...}, "metrics": {...}}
```

### Record Structure

Each record contains:

```json
{
  "worker_id": "worker-1",
  "processor_id": "record-processor-1",
  "parsed_record": {
    "request": {
      "turn": {
        "turn_id": "turn-123",
        "model": "Qwen/Qwen3-0.6B",
        "max_tokens": 100,
        "role": "user",
        "texts": [
          {
            "name": "content",
            "contents": ["What is machine learning?"]
          }
        ],
        "images": [],
        "audios": [],
        "timestamp": null,
        "delay": null
      },
      "timestamp_ns": 1704067200000000000,
      "start_perf_ns": 1234567890,
      "end_perf_ns": 1234987654,
      "recv_start_perf_ns": 1234568000,
      "credit_phase": "profiling",
      "turn_index": 0,
      "responses": [
        {
          "perf_ns": 1234568100,
          "event": "data",
          "data": "{\"id\":\"chatcmpl-123\",\"object\":\"chat.completion.chunk\",\"created\":1704067200,\"model\":\"Qwen/Qwen3-0.6B\",\"choices\":[{\"index\":0,\"delta\":{\"role\":\"assistant\",\"content\":\"Machine\"},\"index\":0,\"finish_reason\":null}]}"
        },
        {
          "perf_ns": 1234568200,
          "event": "data",
          "data": "{\"id\":\"chatcmpl-123\",\"object\":\"chat.completion.chunk\",\"created\":1704067200,\"model\":\"Qwen/Qwen3-0.6B\",\"choices\":[{\"index\":0,\"delta\":{\"content\":\" learning\"},\"index\":0,\"finish_reason\":null}]}"
        },
        "... (94 more response chunks with FULL data) ...",
        {
          "perf_ns": 1234987654,
          "event": "data",
          "data": "{\"id\":\"chatcmpl-123\",\"object\":\"chat.completion.chunk\",\"created\":1704067200,\"model\":\"Qwen/Qwen3-0.6B\",\"choices\":[{\"index\":0,\"delta\":{},\"finish_reason\":\"stop\"}]}"
        }
      ],
      "error": null
    },
    "responses": [
      {
        "perf_ns": 1234568100,
        "data": {
          "id": "chatcmpl-123",
          "object": "chat.completion.chunk",
          "created": 1704067200,
          "model": "Qwen/Qwen3-0.6B",
          "choices": [{"index": 0, "delta": {"role": "assistant", "content": "Machine"}, "finish_reason": null}]
        }
      },
      "... (all parsed response data objects) ..."
    ],
    "input_token_count": 12,
    "output_token_count": 95,
    "reasoning_token_count": null
  },
  "metrics": {
    "ttft": 200.5,
    "ttst": 10.2,
    "request_latency": 4196.64,
    "inter_token_latency": 45.3,
    "output_sequence_length": 95,
    "input_sequence_length": 12,
    "output_token_count": 95,
    "input_token_count": 12
  }
}
```

### Field Descriptions

Each exported record has three main sections:

#### Top-level Fields
- `worker_id`: ID of the worker that sent this request
- `processor_id`: ID of the RecordProcessor that processed this record

#### `parsed_record` (Complete ParsedResponseRecord model)

This is the **FULL** Pydantic model dumped to JSON, containing:

**request** (RequestRecord):
- `turn`: Complete turn data with texts, images, audios, model, max_tokens, role
- `timestamp_ns`: Request timestamp in nanoseconds
- `start_perf_ns`: Request start timestamp (perf_counter)
- `end_perf_ns`: Request end timestamp (perf_counter)
- `recv_start_perf_ns`: First byte received timestamp
- `credit_phase`: Phase when request was sent (warmup/profiling)
- `turn_index`: Turn index for multi-turn conversations
- `responses`: **ALL raw response objects with FULL content** (SSEMessage, TextResponse, etc.)
- `error`: Error details if request failed

**responses** (Parsed responses):
- Array of parsed response data objects (extracted/parsed from raw responses)

**Token counts**:
- `input_token_count`: Number of input tokens
- `output_token_count`: Number of output tokens
- `reasoning_token_count`: Number of reasoning tokens (if applicable)

**Computed properties**:
- `valid`: Whether the response is valid (no errors, proper format)
- `end_perf_ns`: Final response timestamp
- `request_duration_ns`: Total duration

**Note**: The `parsed_record` contains the **complete** RequestRecord and all parsed data. In streaming mode, `request.responses` includes EVERY SSE message with full data.

#### `metrics` (Per-Record Metrics)

All metrics computed for this specific request:
- `ttft`: Time to First Token (ms)
- `ttst`: Time to Second Token (ms)
- `request_latency`: Total request latency (ms)
- `inter_token_latency`: Average inter-token latency (ms)
- `output_sequence_length`: Output tokens
- `input_sequence_length`: Input tokens
- `output_token_count`: Output token count
- `input_token_count`: Input token count
- Plus any other per-record metrics

## Use Cases

### 1. Debugging Individual Requests

Find slow requests and analyze what caused them:

```python
import json

# Load all records
records = []
with open('artifacts/my-run/raw_records/raw_records_record-processor-1.jsonl') as f:
    for line in f:
        records.append(json.loads(line))

# Find requests with TTFT > 1000ms
slow_requests = [r for r in records if r['metrics'].get('ttft', 0) > 1000]

for req in slow_requests:
    parsed = req['parsed_record']
    print(f"Worker: {req['worker_id']}")
    print(f"TTFT: {req['metrics']['ttft']}ms")
    print(f"Prompt: {parsed['request']['turn']['texts'][0]['contents'][0][:100]}...")
    print(f"Input tokens: {parsed['input_token_count']}")
    print(f"Output tokens: {parsed['output_token_count']}")
    print()
```

### 2. Analyzing Token Distribution

```python
import json
import matplotlib.pyplot as plt

# Load metrics
input_tokens = []
output_tokens = []
latencies = []

with open('raw_records.jsonl') as f:
    for line in f:
        record = json.loads(line)
        parsed = record['parsed_record']
        if parsed['valid']:
            input_tokens.append(parsed['input_token_count'])
            output_tokens.append(parsed['output_token_count'])
            latencies.append(record['metrics']['request_latency'])

# Plot
fig, axes = plt.subplots(1, 3, figsize=(15, 5))
axes[0].hist(input_tokens, bins=30)
axes[0].set_title('Input Token Distribution')
axes[1].hist(output_tokens, bins=30)
axes[1].set_title('Output Token Distribution')
axes[2].scatter(output_tokens, latencies, alpha=0.5)
axes[2].set_xlabel('Output Tokens')
axes[2].set_ylabel('Latency (ms)')
axes[2].set_title('Latency vs Output Length')
plt.tight_layout()
plt.show()
```

### 3. Error Analysis

```python
import json
from collections import Counter

# Collect error types
errors = []
with open('raw_records.jsonl') as f:
    for line in f:
        record = json.loads(line)
        parsed = record['parsed_record']
        if parsed['request']['error']:
            errors.append(parsed['request']['error']['type'])

# Count error types
error_counts = Counter(errors)
print("Error Summary:")
for error_type, count in error_counts.most_common():
    print(f"  {error_type}: {count}")
```

### 4. Request Replay

Use raw records to replay specific requests for debugging:

```python
import json
import requests

# Load a specific record
with open('raw_records.jsonl') as f:
    record = json.loads(f.readline())

parsed = record['parsed_record']
turn = parsed['request']['turn']

# Replay the request
payload = {
    "model": turn['model'],
    "messages": [
        {
            "role": turn['role'],
            "content": turn['texts'][0]['contents'][0]
        }
    ],
    "max_tokens": turn['max_tokens'],
    "stream": True
}

response = requests.post(
    "http://localhost:8000/v1/chat/completions",
    json=payload,
    stream=True
)

# Compare with original
print(f"Original TTFT: {record['metrics']['ttft']}ms")
print("Replaying request...")
```

## Performance Considerations

### File Size

⚠️ **Raw record files will be LARGE** because they contain FULL response content:

**Streaming Mode (most common):**
- **Per-token overhead**: ~150-200 bytes per token (SSE JSON wrapper)
- **100-token response**: ~15-20 KB of response data
- **1000 requests × 100 tokens**: ~15-20 MB per file
- **10,000 requests × 100 tokens**: ~150-200 MB per file
- **100,000 requests**: Can exceed 1-2 GB per file

**Non-Streaming Mode:**
- **Smaller overhead**: Full response in single JSON object
- **100-token response**: ~500-1000 bytes
- **More manageable**: 10x smaller than streaming

**Example calculation:**
```
Streaming benchmark with:
- 50,000 requests
- Average 150 output tokens per request
- 3 RecordProcessors

File size per processor: ~50,000/3 × 150 tokens × 180 bytes ≈ 450 MB
Total size: ~1.35 GB across 3 files
```

**Recommendation**: Use `--export-raw-records` selectively for debugging runs, not production-scale benchmarks with hundreds of thousands of requests.

### I/O Overhead

Writing raw records adds minimal overhead:
- **Async I/O**: Non-blocking file writes
- **Parallel writes**: Each processor writes to its own file
- **Streaming format**: JSONL allows incremental writes
- **Estimated overhead**: < 1% of total benchmark time

### Recommendations

- ✅ **Enable for debugging**: Deep analysis of specific issues
- ✅ **Enable for small runs**: < 1,000 requests (files typically < 100 MB)
- ⚠️ **Caution for medium runs**: 1,000-10,000 requests (files 100 MB - 1 GB)
- ❌ **Avoid for large runs**: > 10,000 requests (files can exceed multiple GB)
- ❌ **Disable for production**: Not needed for regular benchmarking
- 💡 **Disk space**: Ensure you have sufficient disk space (estimate: requests × avg_tokens × 200 bytes)

## Distributed Setups

### Local Mode (Multiprocessing)

All files are written to the local filesystem in the artifact directory. Easy to access and analyze.

### Kubernetes Mode

Each RecordProcessor runs in a separate pod. Raw record files are written to the container filesystem.

**To persist files in Kubernetes:**

1. **Mount a persistent volume**:
```yaml
volumeMounts:
  - name: aiperf-data
    mountPath: /app/artifacts
volumes:
  - name: aiperf-data
    persistentVolumeClaim:
      claimName: aiperf-pvc
```

2. **Copy files from pods** (before they terminate):
```bash
# List pods
kubectl get pods -l app=aiperf-record-processor

# Copy from each pod
for pod in $(kubectl get pods -l app=aiperf-record-processor -o name); do
    kubectl cp $pod:/app/artifacts/raw_records ./raw_records_$(basename $pod)/
done
```

3. **Use object storage** (S3, GCS, etc.):
Modify `RawRecordWriter` to write to object storage instead of local filesystem.

## Combining Multiple Files

If you have multiple raw record files from different processors:

```python
import json
from pathlib import Path

# Combine all JSONL files
all_records = []
for file in Path('artifacts/my-run/raw_records').glob('*.jsonl'):
    with open(file) as f:
        for line in f:
            all_records.append(json.loads(line))

print(f"Total records: {len(all_records)}")

# Sort by timestamp
all_records.sort(key=lambda r: r['metadata']['timestamp_ns'])

# Write combined file
with open('combined_raw_records.jsonl', 'w') as f:
    for record in all_records:
        f.write(json.dumps(record) + '\n')
```

## Schema

The raw record export follows a strict schema. For programmatic analysis, you can validate records:

```python
import json
from jsonschema import validate

schema = {
    "type": "object",
    "required": ["worker_id", "processor_id", "parsed_record", "metrics"],
    "properties": {
        "worker_id": {"type": "string"},
        "processor_id": {"type": "string"},
        "parsed_record": {
            "type": "object",
            "required": ["request", "responses", "input_token_count", "output_token_count"],
            "properties": {
                "request": {"type": "object"},
                "responses": {"type": "array"},
                "input_token_count": {"type": ["integer", "null"]},
                "output_token_count": {"type": ["integer", "null"]},
                "valid": {"type": "boolean"}
            }
        },
        "metrics": {"type": "object"}
    }
}

# Validate a record
with open('raw_records.jsonl') as f:
    record = json.loads(f.readline())
    validate(instance=record, schema=schema)
```

## Limitations

1. **File size**: FULL content is exported - files can be very large (GB scale)
2. **Warmup phase**: Only profiling phase records are exported (warmup excluded)
3. **File format**: JSONL only (no CSV, Parquet, etc.)
4. **Storage**: Files remain on local filesystem (not automatically uploaded)
5. **Disk I/O**: Writing large files may impact benchmark performance slightly (< 1-2%)

## FAQ

**Q: Why are there multiple raw_records_*.jsonl files?**

A: Each RecordProcessor writes to its own file for efficient parallel I/O. Combine them if needed for analysis.

**Q: The files are huge! Can I reduce the size?**

A: Yes - the feature exports FULL content by design. If you only need metrics and metadata, use the standard JSON/CSV exports instead. For partial content, you can modify `RawRecordWriter._serialize_response()` to limit response data.

**Q: Why don't I see warmup requests?**

A: Only profiling phase records are exported, as warmup data is excluded from metrics.

**Q: How do I export in a different format?**

A: Parse the JSONL files and convert:
```python
import json
import pandas as pd

records = []
with open('raw_records.jsonl') as f:
    for line in f:
        records.append(json.loads(line))

# Flatten to pandas DataFrame
df = pd.json_normalize(records)
df.to_csv('raw_records.csv', index=False)
df.to_parquet('raw_records.parquet')
```

## See Also

- [Metrics Reference](metrics_reference.md) - Understanding computed metrics
- [CLI Options](cli_options.md) - All command-line flags
- [Architecture](architecture.md) - System architecture overview

