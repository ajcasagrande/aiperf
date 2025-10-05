<!--
SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
SPDX-License-Identifier: Apache-2.0
-->

# Integration Testing Guide for AIPerf

Complete guide for writing integration tests for AIPerf benchmarks.

## Overview

AIPerf integration tests run the complete benchmark pipeline as a subprocess against the FakeAI mock server, validating end-to-end behavior. All test data uses **Pydantic models** for type safety and validation.

## Quick Start

### Minimal Test

```python
import pytest
from tests.integration.conftest import run_and_validate_benchmark
from tests.integration.result_validators import BenchmarkResult

@pytest.mark.integration
@pytest.mark.asyncio
class TestMyFeature:
    async def test_basic_benchmark(
        self, base_profile_args, aiperf_runner, validate_aiperf_output
    ):
        """Validates basic chat endpoint."""
        args = [*base_profile_args, "--endpoint-type", "chat",
                "--request-count", "10", "--concurrency", "2"]

        output = await run_and_validate_benchmark(
            aiperf_runner, validate_aiperf_output, args, min_requests=8
        )

        BenchmarkResult.from_directory(output.actual_dir) \
            .assert_metric_exists("request_latency", "output_sequence_length")
```

**That's it!** 15 lines for a complete integration test.

## Core Concepts

### 1. Pydantic Models

All data in integration tests uses type-safe Pydantic models:

```python
from tests.integration.test_models import AIPerfRunResult, ValidatedOutput

# Running AIPerf returns a Pydantic model
result: AIPerfRunResult = await aiperf_runner(args)
assert result.returncode == 0  # Type-safe access
print(result.stdout)           # IDE autocomplete works

# Validation returns a Pydantic model
output: ValidatedOutput = validate_aiperf_output(result.output_dir)
print(output.actual_dir)   # Type-safe
print(output.json_file)    # Type-safe
```

### 2. Fixtures

**`base_profile_args`** - Standard profile arguments with simple UI:
```python
['profile', '--model', 'openai/gpt-oss-20b', '--url', 'http://...', '--ui', 'simple']
```

**`dashboard_profile_args`** - Same but with dashboard UI:
```python
['profile', '--model', 'openai/gpt-oss-20b', '--url', 'http://...', '--ui', 'dashboard']
```

**`aiperf_runner`** - Async function to run AIPerf:
```python
result: AIPerfRunResult = await aiperf_runner(args, timeout=60.0)
```

**`validate_aiperf_output`** - Validates output files exist:
```python
output: ValidatedOutput = validate_aiperf_output(output_dir)
```

### 3. Helper Function

**`run_and_validate_benchmark()`** - Combines running and basic validation:

```python
from tests.integration.conftest import run_and_validate_benchmark

output: ValidatedOutput = await run_and_validate_benchmark(
    aiperf_runner,
    validate_aiperf_output,
    args,
    timeout=60.0,           # Optional, default 60
    min_requests=10,        # Optional, validates request count
    limit_workers=True      # Optional, adds --workers-max 2 for parallel safety
)
```

This automatically:
- Runs the benchmark
- Prints stdout/stderr on failure
- Validates returncode == 0
- Validates minimum request count (if specified)
- Adds `--workers-max 2` by default (prevents resource exhaustion)
- Returns typed `ValidatedOutput`

### 4. BenchmarkResult - Fluent Pydantic API

The `BenchmarkResult` class provides type-safe validation using Pydantic models:

```python
from tests.integration.result_validators import BenchmarkResult

validator = BenchmarkResult.from_directory(output.actual_dir)
```

**All properties return Pydantic models:**
```python
from aiperf.common.models import MetricResult, InputsFile, ErrorDetailsCount
from aiperf.common.config import UserConfig

# Get typed models
metric: MetricResult = validator.get_metric("ttft")
config: UserConfig = validator.input_config
inputs: InputsFile = validator.inputs_file
errors: list[ErrorDetailsCount] = validator.error_summary

# Access type-safe properties
print(metric.avg, metric.p99, metric.std)  # IDE autocomplete!
print(config.endpoint.streaming)
print(len(inputs.data))
```

## Common Patterns

### Pattern 1: Basic Chat Test

```python
async def test_chat_endpoint(
    self, base_profile_args, aiperf_runner, validate_aiperf_output
):
    """Validates chat endpoint."""
    args = [*base_profile_args, "--endpoint-type", "chat",
            "--request-count", "20", "--concurrency", "5"]

    output = await run_and_validate_benchmark(
        aiperf_runner, validate_aiperf_output, args, min_requests=18
    )

    BenchmarkResult.from_directory(output.actual_dir) \
        .assert_metric_exists("output_sequence_length")
```

### Pattern 2: Streaming Test

```python
from tests.integration.conftest import run_and_validate_benchmark
from tests.integration.result_validators import BenchmarkResult

async def test_streaming(
    self, base_profile_args, aiperf_runner, validate_aiperf_output
):
    """Validates streaming metrics."""
    args = [*base_profile_args, "--endpoint-type", "chat", "--streaming",
            "--request-count", "10", "--concurrency", "2"]

    output = await run_and_validate_benchmark(
        aiperf_runner, validate_aiperf_output, args
    )

    BenchmarkResult.from_directory(output.actual_dir) \
        .assert_metric_exists("ttft", "inter_token_latency") \
        .assert_metric_in_range("ttft", min_value=0, max_value=10000)
```

### Pattern 3: Multi-Modal Test

```python
from tests.integration.conftest import IMAGE_64, AUDIO_SHORT, run_and_validate_benchmark
from tests.integration.result_validators import BenchmarkResult

async def test_multimodal(
    self, base_profile_args, aiperf_runner, validate_aiperf_output
):
    """Validates multi-modal content."""
    args = [*base_profile_args, "--endpoint-type", "chat",
            "--request-count", "10", "--concurrency", "2",
            *IMAGE_64, *AUDIO_SHORT]

    output = await run_and_validate_benchmark(
        aiperf_runner, validate_aiperf_output, args
    )

    BenchmarkResult.from_directory(output.actual_dir) \
        .assert_inputs_json_has_images() \
        .assert_inputs_json_has_audio()
```

### Pattern 4: Dashboard UI Test

```python
async def test_dashboard(
    self, dashboard_profile_args, aiperf_runner, validate_aiperf_output
):
    """Validates dashboard UI."""
    args = [*dashboard_profile_args, "--endpoint-type", "chat",
            "--request-count", "20", "--concurrency", "5"]

    output = await run_and_validate_benchmark(
        aiperf_runner, validate_aiperf_output, args
    )

    BenchmarkResult.from_directory(output.actual_dir).assert_all_artifacts_exist()
```

### Pattern 5: Stress Test (High Concurrency)

```python
async def test_high_concurrency(
    self, base_profile_args, aiperf_runner, validate_aiperf_output
):
    """Validates 1000 concurrent workers."""
    args = [*base_profile_args, "--endpoint-type", "chat", "--streaming",
            "--request-count", "1000", "--concurrency", "1000"]

    output = await run_and_validate_benchmark(
        aiperf_runner, validate_aiperf_output, args,
        timeout=180.0,
        min_requests=950,
        limit_workers=False  # Don't limit workers for stress test
    )

    BenchmarkResult.from_directory(output.actual_dir) \
        .assert_all_artifacts_exist() \
        .assert_metric_exists("ttft")
```

## Available Constants

Use these constants for common flag patterns:

```python
from tests.integration.conftest import (
    DEFAULT_REQUEST_COUNT,  # "5"
    DEFAULT_CONCURRENCY,    # "2"
    IMAGE_64,              # ["--image-width-mean", "64", "--image-height-mean", "64"]
    AUDIO_SHORT,           # ["--audio-length-mean", "0.1"]
    MAX_WORKERS,           # ["--workers-max", "2"]
)

# Usage:
args = [*base_profile_args, "--endpoint-type", "chat",
        "--request-count", DEFAULT_REQUEST_COUNT,
        "--concurrency", DEFAULT_CONCURRENCY,
        *IMAGE_64, *AUDIO_SHORT]
```

## BenchmarkResult API Reference

### Metric Assertions

```python
validator = BenchmarkResult.from_directory(output.actual_dir)

# Check metrics exist
validator.assert_metric_exists("ttft", "request_latency")

# Validate metric ranges
validator.assert_metric_in_range("ttft", min_value=0, max_value=10000)
validator.assert_metric_in_range("ttft", stat="p99", max_value=15000)

# Validate exact values (with tolerance)
validator.assert_metric_value("ttft", "avg", 25.0, tolerance=0.20)  # ±20%

# Validate request count
validator.assert_request_count(min_count=10, max_count=20)
validator.assert_request_count(exact=15)
```

### CSV Assertions

```python
# Check CSV contains specific text
validator.assert_csv_contains("Request Latency", "Time to First Token")
```

### Artifact Assertions

```python
# Verify all files exist
validator.assert_all_artifacts_exist()  # JSON, CSV, log

# Check log has content
validator.assert_log_not_empty()
```

### inputs.json Assertions

```python
# Verify inputs.json exists and has sessions
validator.assert_inputs_json_exists()
validator.assert_inputs_json_has_sessions(min_sessions=10)

# Verify multi-modal content
validator.assert_inputs_json_has_images()
validator.assert_inputs_json_has_audio()
```

### Configuration Assertions

```python
# Check configuration values (dot notation)
validator.assert_config_value("endpoint.streaming", True)
validator.assert_config_value("loadgen.concurrency", 5)
```

### Error Assertions

```python
# Verify no errors
validator.assert_no_errors()

# Verify error count in range
validator.assert_error_count(min_errors=1, max_errors=5)
```

### Chaining

All methods return `self` for chaining:

```python
BenchmarkResult.from_directory(output.actual_dir) \
    .assert_all_artifacts_exist() \
    .assert_metric_exists("ttft", "request_latency") \
    .assert_metric_in_range("ttft", min_value=0) \
    .assert_request_count(min_count=10) \
    .assert_csv_contains("Request Throughput") \
    .assert_no_errors()
```

## Advanced: Direct Pydantic Access

For custom validation, access the Pydantic models directly:

```python
from aiperf.common.models import MetricResult, InputsFile
from aiperf.common.config import UserConfig

validator = BenchmarkResult.from_directory(output.actual_dir)

# Get specific metric (returns MetricResult Pydantic model)
ttft: MetricResult = validator.get_metric("ttft")
assert ttft.avg > 0
assert ttft.p99 < 10000
assert ttft.std is not None

# Access config (UserConfig Pydantic model)
config: UserConfig = validator.input_config
assert config.endpoint.endpoint_type == "chat"
assert config.loadgen.concurrency == 5

# Access inputs.json (InputsFile Pydantic model)
inputs: InputsFile = validator.inputs_file
for session in inputs.data:  # Type-safe iteration
    assert session.session_id
    for payload in session.payloads:
        print(payload)  # Each payload is a dict (flexible for different endpoints)

# Access errors (list of ErrorDetailsCount Pydantic models)
from aiperf.common.models import ErrorDetailsCount

errors: list[ErrorDetailsCount] = validator.error_summary
total_errors = sum(e.count for e in errors)
for error in errors:
    print(f"{error.error_type}: {error.count}")
```

## Testing Multi-Modal Content

### Images

```python
from tests.integration.conftest import IMAGE_64

args = [*base_profile_args, "--endpoint-type", "chat",
        *IMAGE_64,  # Adds 64x64 images
        "--image-format", "png"]  # or "jpeg"

# Validate
BenchmarkResult.from_directory(output.actual_dir) \
    .assert_inputs_json_has_images()
```

### Audio

```python
from tests.integration.conftest import AUDIO_SHORT

args = [*base_profile_args, "--endpoint-type", "chat",
        *AUDIO_SHORT,  # Adds 0.1 second audio
        "--audio-format", "wav",  # or "mp3"
        "--audio-sample-rates", "16.0"]

# Validate
BenchmarkResult.from_directory(output.actual_dir) \
    .assert_inputs_json_has_audio()
```

### Combined Multi-Modal

```python
from tests.integration.conftest import IMAGE_64, AUDIO_SHORT

args = [*base_profile_args, "--endpoint-type", "chat",
        *IMAGE_64, *AUDIO_SHORT]

# Validate both
BenchmarkResult.from_directory(output.actual_dir) \
    .assert_inputs_json_has_images() \
    .assert_inputs_json_has_audio()
```

## Testing Different Scenarios

### Streaming vs Non-Streaming

```python
# Non-streaming
args = [*base_profile_args, "--endpoint-type", "chat"]
validator.assert_metric_exists("request_latency", "output_sequence_length")

# Streaming
args = [*base_profile_args, "--endpoint-type", "chat", "--streaming"]
validator.assert_metric_exists("ttft", "inter_token_latency")
```

### Dashboard UI

```python
async def test_dashboard_ui(
    self, dashboard_profile_args, aiperf_runner, validate_aiperf_output
):
    """Use dashboard_profile_args instead of base_profile_args."""
    args = [*dashboard_profile_args, "--endpoint-type", "chat"]
    # ...
```

### Duration-Based Tests

```python
args = [*base_profile_args, "--endpoint-type", "chat",
        "--benchmark-duration", "10",  # 10 seconds
        "--concurrency", "5"]

output = await run_and_validate_benchmark(
    aiperf_runner, validate_aiperf_output, args,
    timeout=30.0,  # Give extra time for cleanup
    min_requests=5  # At least a few requests in 10 seconds
)
```

### High Concurrency Stress Tests

```python
async def test_stress(
    self, base_profile_args, aiperf_runner, validate_aiperf_output
):
    """Validates extreme concurrency."""
    args = [*base_profile_args, "--endpoint-type", "chat", "--streaming",
            "--request-count", "1000", "--concurrency", "1000"]

    output = await run_and_validate_benchmark(
        aiperf_runner, validate_aiperf_output, args,
        timeout=180.0,
        min_requests=950,
        limit_workers=False  # Allow many workers for stress test
    )

    BenchmarkResult.from_directory(output.actual_dir) \
        .assert_metric_exists("ttft", "request_latency") \
        .assert_inputs_json_has_sessions(min_sessions=10)
```

## Validating Specific Metrics

### Example: TTFT Validation

```python
validator = BenchmarkResult.from_directory(output.actual_dir)

# Method 1: Simple existence check
validator.assert_metric_exists("ttft")

# Method 2: Range validation
validator.assert_metric_in_range("ttft", min_value=1, max_value=1000)

# Method 3: Multiple stats
validator.assert_metric_in_range("ttft", stat="avg", max_value=500)
validator.assert_metric_in_range("ttft", stat="p99", max_value=2000)

# Method 4: Get metric and check manually (Pydantic model)
ttft: MetricResult = validator.get_metric("ttft")
assert ttft.avg > 0
assert ttft.p99 < 10000
assert ttft.std is not None
assert ttft.count == 10
```

## Complete Test Example

Here's a complete, production-quality integration test:

```python
import pytest
from tests.integration.conftest import IMAGE_64, AUDIO_SHORT, run_and_validate_benchmark
from tests.integration.result_validators import BenchmarkResult

@pytest.mark.integration
@pytest.mark.asyncio
class TestMultiModalStreaming:
    """Integration tests for multi-modal streaming benchmarks."""

    async def test_streaming_with_images_and_audio(
        self, base_profile_args, aiperf_runner, validate_aiperf_output
    ):
        """Validates streaming benchmark with images and audio."""
        args = [
            *base_profile_args,
            "--endpoint-type", "chat",
            "--streaming",
            "--request-count", "20",
            "--concurrency", "5",
            *IMAGE_64,
            *AUDIO_SHORT,
            "--random-seed", "42",  # For reproducibility
        ]

        output = await run_and_validate_benchmark(
            aiperf_runner, validate_aiperf_output, args,
            timeout=120.0,
            min_requests=18
        )

        # Fluent validation
        validator = BenchmarkResult.from_directory(output.actual_dir)
        validator.assert_all_artifacts_exist() \
            .assert_log_not_empty() \
            .assert_metric_exists("ttft", "inter_token_latency", "request_latency") \
            .assert_metric_in_range("ttft", min_value=0, max_value=10000) \
            .assert_metric_in_range("inter_token_latency", min_value=0) \
            .assert_request_count(min_count=18) \
            .assert_csv_contains("Time to First Token", "Request Throughput") \
            .assert_inputs_json_has_images() \
            .assert_inputs_json_has_audio() \
            .assert_no_errors()

        # Advanced: Access Pydantic models directly
        assert validator.input_config.endpoint.streaming is True
        assert len(validator.inputs_file.data) >= 10
        assert validator.was_cancelled is False
```

**18 lines of test code + comprehensive validation!**

## Best Practices

### ✅ DO:

1. **Use `run_and_validate_benchmark()`** for all tests
2. **Use constants** (`IMAGE_64`, `AUDIO_SHORT`, etc.)
3. **Chain assertions** with the fluent API
4. **Type hint** when getting Pydantic models
5. **Use meaningful test names** that describe what's being validated
6. **Keep docstrings concise** (one line)

```python
# Good
async def test_chat_endpoint_with_images(
    self, base_profile_args, aiperf_runner, validate_aiperf_output
):
    """Validates chat endpoint with synthetic images."""
    args = [*base_profile_args, "--endpoint-type", "chat", *IMAGE_64]
    output = await run_and_validate_benchmark(aiperf_runner, validate_aiperf_output, args)
    BenchmarkResult.from_directory(output.actual_dir).assert_inputs_json_has_images()
```

### ❌ DON'T:

1. **Access dicts directly** - Use Pydantic models
2. **Manual error printing** - `run_and_validate_benchmark()` handles it
3. **Verbose docstrings** - Keep it to one line
4. **Hardcode values** - Use constants
5. **Manual string conversions** - Constants are already strings

```python
# Bad - Don't do this!
result = await aiperf_runner(args)
if result["returncode"] != 0:  # Bad! Not type-safe
    print(result["stdout"])    # Bad! Use result.stdout
records = output["json_results"]["records"]  # Bad! Use BenchmarkResult
avg = records["ttft"]["avg"]  # Bad! Use Pydantic model
```

## Running Tests

### Run all integration tests:
```bash
pytest tests/integration/ --integration -n auto -q
```

### Run specific test class:
```bash
pytest tests/integration/test_multimodal_integration.py::TestMultiModalIntegration --integration -v
```

### Run single test:
```bash
pytest tests/integration/test_multimodal_integration.py::TestMultiModalIntegration::test_chat_endpoint_with_image_content --integration -v
```

### Sequential execution (debugging):
```bash
pytest tests/integration/ --integration -v  # No -n flag
```

## Parallel Execution

Tests support `pytest -n auto` for parallel execution:

- **Automatic worker limiting:** Tests add `--workers-max 2` by default
- **Mock server ports:** OS-assigned (port 0) to avoid conflicts
- **Resource safety:** Limited workers prevent exhaustion
- **5x speedup:** ~35s parallel vs ~170s sequential

To disable worker limiting for stress tests:
```python
await run_and_validate_benchmark(..., limit_workers=False)
```

## Troubleshooting

### Test fails with "No records found"

The benchmark failed to produce output. Check:
1. Is the mock server running? (fixture should handle this)
2. Did the benchmark crash? (check stdout/stderr in test output)
3. Is the endpoint type correct?

### Test fails with "Metric 'X' not found"

The metric wasn't computed. Common reasons:
1. Wrong endpoint type (e.g., embeddings don't have ttft)
2. Non-streaming when expecting streaming metrics
3. Benchmark completed too quickly (0 requests)

### ValidationError when parsing inputs.json

The payload format doesn't match. This is expected for:
- Non-chat endpoints (embeddings, rankings, etc.)
- The code gracefully skips these with try/except

### Tests fail in parallel but pass sequentially

Increase timeout or reduce concurrency:
```python
await run_and_validate_benchmark(..., timeout=180.0)
```

## File Structure

```
tests/integration/
├── __init__.py
├── conftest.py                        # Fixtures and helpers
├── test_models.py                     # Pydantic models for test data
├── result_validators.py               # BenchmarkResult fluent API
├── test_multimodal_integration.py     # Multi-modal tests (15 tests)
├── test_full_benchmark_integration.py # Core benchmark tests (14 tests)
├── README.md                          # This file
├── TESTING_GUIDE.md                   # Quick reference
├── MULTIMODAL_TESTS_SUMMARY.md        # Multi-modal test details
└── CLEANUP_SUMMARY.md                 # Implementation details
```

## Summary

Writing integration tests for AIPerf is:
- **Simple:** 10-15 lines per test
- **Type-safe:** 100% Pydantic models
- **Fast:** Parallel execution with -n auto
- **Maintainable:** DRY principles throughout
- **Powerful:** Fluent API for comprehensive validation

**No boilerplate. No worslop. Just clean, type-safe tests.**
