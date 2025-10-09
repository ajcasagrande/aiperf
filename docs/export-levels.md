<!--
SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
SPDX-License-Identifier: Apache-2.0
-->

# Export Levels

AIPerf provides three levels of data export to balance detail vs file size. Choose the level that matches your analysis needs.

## Overview

| Level | What's Exported | File Size | Use Case |
|-------|----------------|-----------|----------|
| **summary** | Aggregated metrics only | Smallest (~10KB) | Standard benchmarking |
| **records** | Per-record metrics (display units) | Medium (~1-10MB) | Metric analysis, debugging |
| **raw** | Full request/response + metrics | Largest (~100MB-GB) | Deep debugging, request replay |

## Configuration

Set the export level using the `--export-level` flag:

```bash
# Default: summary (aggregated metrics only)
aiperf profile --model MODEL --url URL --endpoint-type chat

# Records: per-record metrics
aiperf profile --model MODEL --url URL --endpoint-type chat --export-level records

# Raw: full request/response data
aiperf profile --model MODEL --url URL --endpoint-type chat --export-level raw
```

---

## Level 1: Summary (Default)

**What's exported:**
- Aggregated metrics (avg, min, max, p50, p90, p95, p99, std)
- Summary statistics
- Error counts

**Files created:**
```
artifacts/my-benchmark/
├── profile_export_aiperf.json  # Aggregated metrics
└── profile_export_aiperf.csv   # Same data in CSV format
```

**File size:** ~10-50 KB

**When to use:**
- ✅ Standard benchmarking
- ✅ Performance comparisons
- ✅ SLA validation
- ✅ Quick performance checks

**Example output (profile_export_aiperf.json):**
```json
{
  "records": {
    "ttft": {
      "tag": "ttft",
      "header": "Time to First Token",
      "unit": "ms",
      "avg": 18.26,
      "min": 11.22,
      "max": 106.32,
      "p50": 15.34,
      "p90": 27.76,
      "p95": 45.21,
      "p99": 68.82,
      "std": 12.07
    },
    "request_latency": { ... },
    "output_token_throughput": { ... }
  }
}
```

---

## Level 2: Records

**What's exported:**
- **Per-record metrics** (one entry per request)
- Converted to display units (e.g., ns → ms)
- Filtered (excludes experimental/internal metrics by default)

**Files created:**
```
artifacts/my-benchmark/
├── profile_export_aiperf.json     # Summary (same as level 1)
├── profile_export_aiperf.csv      # Summary CSV
└── record_metrics/
    └── record_metrics.jsonl       # Per-record metrics ← NEW
```

**File size:**
- ~50-200 bytes per record
- 1,000 requests: ~50-200 KB
- 10,000 requests: ~500KB - 2MB
- 100,000 requests: ~5-20 MB

**When to use:**
- ✅ Analyzing latency distributions
- ✅ Finding outliers and anomalies
- ✅ Debugging specific slow requests
- ✅ Understanding metric correlations
- ✅ Statistical analysis

**Enable records export:**
```bash
aiperf profile \
  --model Qwen/Qwen3-0.6B \
  --url http://localhost:8000 \
  --endpoint-type chat \
  --streaming \
  --concurrency 10 \
  --request-count 1000 \
  --export-level records  # ← Enable per-record export
```

**Example output (record_metrics.jsonl):**

Each line is one request's metrics:
```jsonl
{"ttft": {"value": 18.5, "unit": "ms", "header": "Time to First Token"}, "request_latency": {"value": 487.2, "unit": "ms", "header": "Request Latency"}, "inter_token_latency": {"value": 11.3, "unit": "ms", "header": "Inter Token Latency"}, "output_sequence_length": {"value": 42, "unit": "tokens", "header": "Output Sequence Length"}}
{"ttft": {"value": 22.1, "unit": "ms", "header": "Time to First Token"}, "request_latency": {"value": 512.8, "unit": "ms", "header": "Request Latency"}, "inter_token_latency": {"value": 12.1, "unit": "ms", "header": "Inter Token Latency"}, "output_sequence_length": {"value": 48, "unit": "tokens", "header": "Output Sequence Length"}}
```

**Analysis example:**
```python
import json
import pandas as pd

# Load per-record metrics
records = []
with open('artifacts/my-run/record_metrics/record_metrics.jsonl') as f:
    for line in f:
        records.append(json.loads(line))

# Extract specific metrics
data = []
for record in records:
    data.append({
        'ttft': record['ttft']['value'],
        'latency': record['request_latency']['value'],
        'output_tokens': record['output_sequence_length']['value'],
    })

df = pd.DataFrame(data)

# Find outliers
print("Slowest TTFT requests:")
print(df.nlargest(10, 'ttft'))

# Correlation analysis
print("\nCorrelation between output length and latency:")
print(df[['output_tokens', 'latency']].corr())
```

**Filtering:**

By default, experimental and internal metrics are excluded:
```bash
# Default: excludes experimental/internal
--export-level records

# Include all metrics (developer mode only)
--export-level records --show-internal-metrics
```

---

## Level 3: Raw

**What's exported:**
- **Complete ParsedResponseRecord** (full Pydantic model dump)
- **All request data** (prompts, parameters, timestamps)
- **All response data** (every SSE chunk, full content)
- **All per-record metrics** (unfiltered)

**Files created:**
```
artifacts/my-benchmark/
├── profile_export_aiperf.json     # Summary
├── profile_export_aiperf.csv      # Summary CSV
└── raw_records/
    ├── raw_records_record-processor-1.jsonl  # ← NEW (distributed)
    ├── raw_records_record-processor-2.jsonl  # ← NEW
    └── raw_records_record-processor-3.jsonl  # ← NEW
```

**File size:** ⚠️ **LARGE**
- Streaming mode: ~10-30 KB per request
- Non-streaming: ~500-1000 bytes per request
- 1,000 requests (streaming): ~10-30 MB
- 10,000 requests (streaming): ~100-300 MB
- 100,000 requests (streaming): ~1-3 GB

**When to use:**
- ✅ Deep debugging (analyzing specific requests)
- ✅ Request replay (reproducing issues)
- ✅ Response content analysis
- ✅ Validating model outputs
- ⚠️ Small runs only (< 10,000 requests recommended)

**Enable raw export:**
```bash
aiperf profile \
  --model Qwen/Qwen3-0.6B \
  --url http://localhost:8000 \
  --endpoint-type chat \
  --streaming \
  --concurrency 10 \
  --request-count 100 \
  --export-level raw  # ← Enable raw export
```

**Example output (raw_records_record-processor-1.jsonl):**

Each line is one complete request/response:
```json
{
  "worker_id": "worker-1",
  "processor_id": "record-processor-1",
  "parsed_record": {
    "request": {
      "turn": {
        "turn_id": "turn-abc123",
        "model": "Qwen/Qwen3-0.6B",
        "max_tokens": 100,
        "role": "user",
        "texts": [{"name": "content", "contents": ["What is machine learning?"]}],
        "images": [],
        "audios": []
      },
      "timestamp_ns": 1704067200000000000,
      "start_perf_ns": 1234567890,
      "end_perf_ns": 1234987654,
      "responses": [
        {"perf_ns": 1234568100, "event": "data", "data": "{\"id\":\"chatcmpl-123\",...}"},
        {"perf_ns": 1234568200, "event": "data", "data": "{\"id\":\"chatcmpl-123\",...}"},
        "... (all response chunks with FULL content) ..."
      ],
      "error": null
    },
    "responses": [
      {"perf_ns": 1234568100, "data": {"id": "chatcmpl-123", "choices": [...]}},
      "... (all parsed responses) ..."
    ],
    "input_token_count": 12,
    "output_token_count": 95
  },
  "metrics": {
    "ttft": 200.5,
    "request_latency": 4196.64,
    "inter_token_latency": 45.3,
    "output_sequence_length": 95
  }
}
```

---

## Comparison

### Summary vs Records vs Raw

**Use summary when:**
- You only need aggregated statistics
- Comparing overall performance
- Generating reports
- File size matters

**Use records when:**
- You need per-request metric analysis
- Finding outliers and patterns
- Statistical analysis (distributions, correlations)
- File size is moderate concern

**Use raw when:**
- You need to inspect actual request/response content
- Debugging specific requests
- Replaying requests
- Validating model outputs
- File size is not a concern

### File Size Comparison (10,000 requests, streaming)

| Level | File Size | Ratio |
|-------|-----------|-------|
| Summary | ~30 KB | 1x |
| Records | ~2 MB | ~67x |
| Raw | ~200 MB | ~6,667x |

### What Each Level Contains

| Data | Summary | Records | Raw |
|------|---------|---------|-----|
| Aggregated metrics (avg, p99, etc.) | ✅ | ✅ | ✅ |
| Per-record metric values | ❌ | ✅ | ✅ |
| Request prompts | ❌ | ❌ | ✅ |
| Response content | ❌ | ❌ | ✅ |
| All response chunks | ❌ | ❌ | ✅ |
| Display unit conversion | ✅ | ✅ | ❌ |
| Filtered metrics | ✅ | ✅ | ❌ |

---

## Analysis Examples

### Summary Level Analysis

```python
import json

# Load summary
with open('artifacts/my-run/profile_export_aiperf.json') as f:
    data = json.load(f)

# Check performance
ttft_p99 = data['records']['ttft']['p99']
throughput = data['records']['output_token_throughput']['avg']

print(f"TTFT p99: {ttft_p99}ms")
print(f"Throughput: {throughput} tokens/sec")
```

### Records Level Analysis

```python
import json
import pandas as pd

# Load per-record metrics
records = []
with open('artifacts/my-run/record_metrics/record_metrics.jsonl') as f:
    for line in f:
        records.append(json.loads(line))

# Convert to DataFrame
data = {
    'ttft': [r['ttft']['value'] for r in records],
    'latency': [r['request_latency']['value'] for r in records],
    'tokens': [r['output_sequence_length']['value'] for r in records],
}
df = pd.DataFrame(data)

# Statistical analysis
print(df.describe())
print(f"\nTTFT > 100ms: {(df['ttft'] > 100).sum()} requests")
print(f"Latency > 1000ms: {(df['latency'] > 1000).sum()} requests")
```

### Raw Level Analysis

```python
import json

# Load raw records
with open('artifacts/my-run/raw_records/raw_records_record-processor-1.jsonl') as f:
    for line in f:
        record = json.loads(line)

        # Access full request/response
        prompt = record['parsed_record']['request']['turn']['texts'][0]['contents'][0]
        responses = record['parsed_record']['request']['responses']

        # Analyze response content
        if record['metrics']['ttft'] > 1000:
            print(f"Slow request found!")
            print(f"Prompt: {prompt[:100]}...")
            print(f"Response chunks: {len(responses)}")
            print(f"First chunk timing: {responses[0]['perf_ns']}")
```

---

## Developer Mode

When running in developer mode with `--show-internal-metrics`, the `records` level will include:
- Internal metrics (normally hidden)
- Experimental metrics (normally hidden)

```bash
# Enable developer mode
export AIPERF_DEV_MODE=1

# Export records with internal metrics
aiperf profile \
  --model MODEL \
  --url URL \
  --endpoint-type chat \
  --export-level records \
  --show-internal-metrics
```

---

## Migration from Previous Version

If you were using `--export-raw-records`:

**Old:**
```bash
--export-raw-records  # Boolean flag
```

**New:**
```bash
--export-level raw  # Enum value
```

---

## Best Practices

### Choose the Right Level

```
Need to...
├─ Compare overall performance? → summary
├─ Find slow requests? → records
├─ Debug specific request? → raw
├─ Analyze metric distributions? → records
├─ Replay requests? → raw
├─ Validate model outputs? → raw
└─ Generate reports? → summary
```

### Manage Disk Space

**Summary:**
- ✅ Always safe, minimal space

**Records:**
- ✅ Safe for < 100,000 requests
- ⚠️ Monitor disk for > 100,000 requests

**Raw:**
- ✅ Safe for < 1,000 requests
- ⚠️ Careful with 1,000-10,000 requests
- ❌ Avoid for > 10,000 requests

### Performance Impact

| Level | CPU Overhead | I/O Overhead | Network Impact |
|-------|--------------|--------------|----------------|
| Summary | Minimal | Minimal | None |
| Records | < 1% | < 1% | None |
| Raw | 1-2% | 2-5% | None (local writes) |

---

## FAQ

**Q: Can I export multiple levels at once?**

A: No, `--export-level` accepts a single value. Run separate benchmarks if you need multiple formats.

**Q: Which level should I use for production monitoring?**

A: Use `summary` (default). It provides all essential metrics with minimal overhead.

**Q: Which level for debugging performance issues?**

A: Start with `records` to identify problematic requests. If you need to see actual content, use `raw` on a small reproduction case.

**Q: Do all three levels include the same metrics?**

A:
- Summary: Aggregated metrics only
- Records: Per-record metrics (filtered by default)
- Raw: All per-record metrics (unfiltered) + full data

**Q: Can I convert between formats after export?**

A: You can convert up (raw → records, records → summary) but not down (summary → records/raw).

---

## See Also

- [Metrics Reference](metrics_reference.md) - Understanding all metrics
- [CLI Options](cli_options.md) - All command-line flags
- [Raw Records Export](raw-records-export.md) - Deep dive into raw level

