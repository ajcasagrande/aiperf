<!--
SPDX-FileCopyrightText: Copyright (c) 2024-2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
SPDX-License-Identifier: Apache-2.0
-->

# Working with Profile Exports

This guide demonstrates how to programmatically work with AIPerf benchmark output files using the native Pydantic data models.

## Overview

AIPerf generates multiple output formats after each benchmark run, each optimized for different analysis workflows:

- **`profile_export.jsonl`** - Per-request metric records in JSON Lines format
- **`profile_export_aiperf.json`** - Aggregated statistics as a single JSON object
- **`profile_export_aiperf.csv`** - Aggregated statistics in CSV format
- **`inputs.json`** - Complete input dataset with formatted payloads for each request

All output files are type-safe and can be parsed using AIPerf's built-in Pydantic models, enabling robust data analysis pipelines.

## Output File Formats

### Per-Request Records (JSONL)

**File:** `profile_export.jsonl`

The JSONL output contains one record per line, providing complete detail for each request sent during the benchmark. Each record includes request metadata, computed metrics, and error information if the request failed.

**Structure:**
```json
{
  "metadata": { ... },
  "metrics": { ... },
  "error": null | { ... }
}
```

### Aggregated Statistics (JSON)

**File:** `profile_export_aiperf.json`

A single JSON object containing statistical summaries (min, max, mean, percentiles) for all metrics across the entire benchmark run.

### Aggregated Statistics (CSV)

**File:** `profile_export_aiperf.csv`

Contains the same aggregated statistics as the JSON format, but in a spreadsheet-friendly structure with one metric per row.

### Input Dataset (JSON)

**File:** `inputs.json`

A structured representation of all input data sent to the model during the benchmark run. This file contains the complete formatted payloads that were used for each request, organized by conversation sessions.

**Structure:**
```json
{
  "data": [
    {
      "session_id": "a5cdb1fe-19a3-4ed0-9e54-ed5ed6dc5578",
      "payloads": [
        {
          "messages": [
            {
              "role": "user",
              "name": "text",
              "content": "Your prompt text here..."
            }
          ],
          "model": "openai/gpt-oss-20b",
          "stream": true
        }
      ]
    }
  ]
}
```

**Key fields:**
- `session_id`: Unique identifier for the conversation session
- `payloads`: Array of formatted request payloads (one per turn in multi-turn conversations)
- `messages`: Chat messages with role and content (for chat endpoints)
- `model`: Model name used for the benchmark
- `stream`: Whether streaming was enabled

## Data Models

AIPerf uses Pydantic models for type-safe parsing and validation of all benchmark output files. These models ensure data integrity and provide IDE autocompletion support.

### Core Models

```python
from aiperf.common.models import (
    MetricRecordInfo,
    MetricRecordMetadata,
    MetricValue,
    ErrorDetails,
    InputsFile,
    SessionPayloads,
)
```

<table style="width:100%; border-collapse: collapse;">
  <thead>
    <tr>
      <th style="width:25%; text-align: left;">Model</th>
      <th style="width:50%; text-align: left;">Description</th>
      <th style="width:25%; text-align: left;">Source</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td><code>MetricRecordInfo</code></td>
      <td>Complete per-request record including metadata, metrics, and error information</td>
      <td><a href="../aiperf/common/models/record_models.py#L97">record_models.py:97</a></td>
    </tr>
    <tr>
      <td><code>MetricRecordMetadata</code></td>
      <td>Request metadata: timestamps, IDs, worker identifiers, and phase information</td>
      <td><a href="../aiperf/common/models/record_models.py#L66">record_models.py:66</a></td>
    </tr>
    <tr>
      <td><code>MetricValue</code></td>
      <td>Individual metric value with associated unit of measurement</td>
      <td><a href="../aiperf/common/models/record_models.py#L59">record_models.py:59</a></td>
    </tr>
    <tr>
      <td><code>ErrorDetails</code></td>
      <td>Error information including HTTP code, error type, and descriptive message</td>
      <td><a href="../aiperf/common/models/error_models.py#L11">error_models.py:11</a></td>
    </tr>
    <tr>
      <td><code>InputsFile</code></td>
      <td>Container for all input dataset sessions with formatted payloads for each turn</td>
      <td><a href="../aiperf/common/models/dataset_models.py#L98">dataset_models.py:98</a></td>
    </tr>
    <tr>
      <td><code>SessionPayloads</code></td>
      <td>Single conversation session with session ID and list of formatted request payloads</td>
      <td><a href="../aiperf/common/models/dataset_models.py#L86">dataset_models.py:86</a></td>
    </tr>
  </tbody>
</table>

## Record Structure Examples

### Successful Request Record

```json
{
  "metadata": {
    "session_num": 45,
    "x_request_id": "7609a2e7-aa53-4ab1-98f4-f35ecafefd25",
    "x_correlation_id": "32ee4f33-cfca-4cfc-988f-79b45408b909",
    "conversation_id": "77aa5b0e-b305-423f-88d5-c00da1892599",
    "turn_index": 0,
    "request_start_ns": 1759813207532900363,
    "request_ack_ns": 1759813207650730976,
    "request_end_ns": 1759813207838764604,
    "worker_id": "worker_359d423a",
    "record_processor_id": "record_processor_1fa47cd7",
    "benchmark_phase": "profiling"
  },
  "metrics": {
    "input_sequence_length": {"value": 550, "unit": "tokens"},
    "ttft": {"value": 255.88656799999998, "unit": "ms"},
    "request_count": {"value": 1, "unit": "requests"},
    "request_latency": {"value": 297.52522799999997, "unit": "ms"},
    "min_request_timestamp": {"value": 1759813207532900363, "unit": "ns"},
    "output_token_count": {"value": 9, "unit": "tokens"},
    "ttst": {"value": 4.8984369999999995, "unit": "ms"},
    "inter_chunk_latency": {"value": [4.898437, 5.316006, 4.801489, 5.674918, 4.811467, 5.097998, 5.504797, 5.533548], "unit": "ms"},
    "output_sequence_length": {"value": 9, "unit": "tokens"},
    "max_response_timestamp": {"value": 1759813207830425591, "unit": "ns"},
    "inter_token_latency": {"value": 5.2048325, "unit": "ms"},
    "output_token_throughput_per_user": {"value": 192.1291415237666, "unit": "tokens/sec/user"}
  },
  "error": null
}
```

**Key Metadata Fields:**
- `x_request_id`: Unique identifier for this specific request
- `conversation_id`: Groups requests belonging to the same conversation
- `turn_index`: Position within a multi-turn conversation (0-indexed)
- `request_start_ns`: Timestamp when request was initiated (nanoseconds)
- `request_ack_ns`: Timestamp when server acknowledged the request
- `request_end_ns`: Timestamp when response completed
- `session_num`: Sequential request number across the entire benchmark

**Common Metrics:**
- `ttft` (Time to First Token): Latency until first response token
- `ttst` (Time to Second Token): Latency between first and second tokens
- `inter_token_latency`: Average time between consecutive tokens
- `request_latency`: Total end-to-end request latency
- `output_token_throughput_per_user`: Tokens generated per second per concurrent user

### Failed Request Record

```json
{
  "metadata": {
    "session_num": 18,
    "x_request_id": "b54c487e-7fcd-4a69-9ceb-9b71f419a236",
    "x_correlation_id": "27ecc8af-2b70-45ec-b9a7-fcabf109e26a",
    "conversation_id": "65fa3614-cf6a-4e57-a82a-3e5953ac3c19",
    "turn_index": 0,
    "request_start_ns": 1759813207531990596,
    "request_ack_ns": null,
    "request_end_ns": 4440670232134296,
    "worker_id": "worker_8e556c42",
    "record_processor_id": "record_processor_2279e08e",
    "benchmark_phase": "profiling"
  },
  "metrics": {
    "error_request_count": {"value": 1, "unit": "requests"}
  },
  "error": {
    "code": 499,
    "type": "RequestCancellationError",
    "message": "Request was cancelled after 0.000 seconds"
  }
}
```

**Error Fields:**
- `code`: HTTP status code or custom error code
- `type`: Classification of the error (e.g., timeout, cancellation, server error)
- `message`: Human-readable error description

## Working with Output Data

AIPerf output files can be parsed using the native Pydantic models for type-safe data handling and analysis.

### Synchronous Loading

For standard workflows and smaller datasets, use synchronous file I/O:

```python
from aiperf.common.models import MetricRecordInfo

def load_records(file_path: Path) -> list[MetricRecordInfo]:
    """Load profile_export.jsonl file into structured Pydantic models in sync mode."""
    records = []
    with open(file_path, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                record = MetricRecordInfo.model_validate_json(line)
                records.append(record)
    return records
```

### Asynchronous Loading

For large benchmark runs with thousands of requests, use async file I/O for better performance:

```python
import aiofiles
from aiperf.common.models import MetricRecordInfo

async def process_streaming_records_async(file_path: Path) -> None:
    """Load profile_export.jsonl file into structured Pydantic models in async mode and process the streaming records."""
    async with aiofiles.open(file_path, encoding="utf-8") as f:
        async for line in f:
            if line.strip():
                record = MetricRecordInfo.model_validate_json(line)
                # ... Process the streaming records here ...
```

### Working with Input Datasets

Load and analyze the `inputs.json` file to understand what data was sent during the benchmark:

```python
import json
from pathlib import Path
from aiperf.common.models import InputsFile

def load_inputs_file(file_path: Path) -> InputsFile:
    """Load inputs.json file into structured Pydantic model."""
    with open(file_path, encoding="utf-8") as f:
        data = json.load(f)
    return InputsFile.model_validate(data)

# Load inputs
inputs = load_inputs_file(Path("artifacts/my-run/inputs.json"))

# Analyze input characteristics
total_sessions = len(inputs.data)
total_turns = sum(len(session.payloads) for session in inputs.data)
multi_turn_sessions = sum(1 for session in inputs.data if len(session.payloads) > 1)

print(f"Total sessions: {total_sessions}")
print(f"Total turns: {total_turns}")
print(f"Multi-turn conversations: {multi_turn_sessions}")

# Extract prompt lengths for chat endpoints
for session in inputs.data:
    for turn_idx, payload in enumerate(session.payloads):
        if "messages" in payload:
            for message in payload["messages"]:
                content_length = len(message["content"])
                print(f"Session {session.session_id}, Turn {turn_idx}: {content_length} characters")
```

### Correlating Inputs with Results

Combine `inputs.json` with `profile_export.jsonl` for deeper analysis:

```python
from pathlib import Path
from aiperf.common.models import InputsFile, MetricRecordInfo
import json

def correlate_inputs_and_results(inputs_path: Path, results_path: Path):
    """Correlate input prompts with performance metrics."""
    # Load inputs
    with open(inputs_path, encoding="utf-8") as f:
        inputs = InputsFile.model_validate(json.load(f))

    # Create session lookup
    session_inputs = {session.session_id: session for session in inputs.data}

    # Process results and correlate
    with open(results_path, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                record = MetricRecordInfo.model_validate_json(line)

                # Skip failed requests
                if record.error is not None:
                    continue

                # Find corresponding input
                conv_id = record.metadata.conversation_id
                if conv_id in session_inputs:
                    session = session_inputs[conv_id]
                    turn_idx = record.metadata.turn_index

                    if turn_idx < len(session.payloads):
                        payload = session.payloads[turn_idx]
                        input_tokens = record.metrics.get("input_sequence_length", {}).get("value", 0)
                        latency = record.metrics.get("request_latency", {}).get("value", 0)

                        print(f"Conv {conv_id}, Turn {turn_idx}: "
                              f"{input_tokens} tokens, {latency:.2f}ms latency")

correlate_inputs_and_results(
    Path("artifacts/my-run/inputs.json"),
    Path("artifacts/my-run/profile_export.jsonl")
)
```

## Best Practices

### Data Validation

Always use Pydantic models for type-safe parsing and automatic validation:

```python
from aiperf.common.models import MetricRecordInfo, InputsFile

# Recommended: Type-safe parsing with validation
record = MetricRecordInfo.model_validate_json(line)
inputs = InputsFile.model_validate(json.load(f))

# Avoid: Raw JSON parsing without validation
import json
raw_data = json.loads(line)  # No type checking or validation
```

### Handling Missing Metrics

Not all metrics are present in every record. Always check for existence:

```python
if 'ttft' in record.metrics:
    ttft_value = record.metrics['ttft'].value
else:
    # Handle missing metric (e.g., failed request, non-streaming response)
    ttft_value = None
```

### Error Analysis

Separate successful and failed requests for accurate analysis:

```python
from collections import Counter

successful_records = [r for r in records if r.error is None]
failed_records = [r for r in records if r.error is not None]

print(f"Success rate: {len(successful_records) / len(records) * 100:.2f}%")
print(f"Failed requests by type:")
for error_type, count in Counter(r.error.type for r in failed_records).items():
    print(f"  {error_type}: {count}")
```

## Related Documentation

- [Tutorial: Basic Profiling](tutorial.md) - Run your first benchmark and generate outputs
- [Architecture: Record Processor](architecture.md#record-processor) - How metrics are computed and recorded
- [CLI Options](cli_options.md) - Configure output file locations and formats
