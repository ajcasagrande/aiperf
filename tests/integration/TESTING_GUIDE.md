<!--
SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
SPDX-License-Identifier: Apache-2.0
-->

# Integration Testing Guide

## Quick Start

```python
from tests.integration.conftest import IMAGE_64, AUDIO_SHORT, run_and_validate_benchmark
from tests.integration.result_validators import BenchmarkResult

# Build args with constants
args = [*base_profile_args, "--endpoint-type", "chat",
        "--request-count", "10", "--concurrency", "5",
        *IMAGE_64, *AUDIO_SHORT]

# Run and validate (handles errors automatically)
output = await run_and_validate_benchmark(
    aiperf_runner, validate_aiperf_output, args, min_requests=8
)

# Fluent Pydantic-powered validation
BenchmarkResult.from_directory(output["actual_dir"]) \
    .assert_metric_exists("ttft") \
    .assert_metric_in_range("ttft", min_value=0) \
    .assert_inputs_json_has_images()
```

## Architecture

**BenchmarkResult uses Pydantic models internally:**
- `UserConfig` - Input configuration (fully typed)
- `InputsFile` - inputs.json (typed sessions and payloads)
- `ErrorDetailsCount` - Error summary (typed error counts)
- Records - Raw dict (metrics have varying types: float, int, datetime strings)

This provides **type safety where it matters** while staying flexible for metrics.

## BenchmarkResult API

### Core Methods

**Metrics:**
- `assert_metric_exists(*tags)` - Check metrics exist
- `assert_metric_in_range(tag, stat="avg", min_value=None, max_value=None)` - Validate range
- `assert_metric_value(tag, stat, expected, tolerance=0.01)` - Exact match ±1%
- `assert_request_count(min_count=None, max_count=None, exact=None)` - Validate count

**CSV:**
- `assert_csv_contains(*patterns)` - Check text patterns
- `assert_csv_has_metric(name)` - Check metric in CSV (alias)

**Artifacts:**
- `assert_all_artifacts_exist()` - Verify JSON, CSV, log files
- `assert_log_not_empty()` - Log has content

**inputs.json:**
- `assert_inputs_json_exists()` - File exists
- `assert_inputs_json_has_sessions(min_sessions=1)` - Session count
- `assert_inputs_json_has_images()` - Contains image_url content
- `assert_inputs_json_has_audio()` - Contains input_audio content

**Configuration:**
- `assert_config_value(path, value)` - Check config (e.g., `"endpoint.streaming"`)

**Errors:**
- `assert_no_errors()` - No errors in summary
- `assert_error_count(min_errors=0, max_errors=None)` - Error count range

### Properties (Pydantic-Powered)

- `.records` - Dict of metrics (raw dict for flexibility)
- `.input_config` - UserConfig Pydantic model
- `.error_summary` - List[ErrorDetailsCount] Pydantic models
- `.inputs_file` - InputsFile Pydantic model
- `.csv_content` - CSV text (string)
- `.was_cancelled` - Cancellation status (bool)

## ConsoleOutputValidator API

For stdout/stderr validation:

```python
console = ConsoleOutputValidator(result["stdout"])
console.assert_contains("NVIDIA AIPerf", "Metric") \
    .assert_not_contains("ERROR", "FAILED") \
    .assert_metric_displayed("Request Latency") \
    .assert_table_displayed() \
    .assert_error_summary_displayed()  # if errors expected
```

## Patterns

### Basic Test (Use Helper)
```python
# run_and_validate_benchmark handles error printing and basic validation
output = await run_and_validate_benchmark(
    aiperf_runner, validate_aiperf_output, args, min_requests=10
)

BenchmarkResult.from_directory(output["actual_dir"]) \
    .assert_all_artifacts_exist() \
    .assert_metric_exists("request_latency")
```

### Streaming Test
```python
BenchmarkResult.from_directory(output["actual_dir"]) \
    .assert_metric_exists("ttft", "inter_token_latency") \
    .assert_metric_in_range("ttft", min_value=0, max_value=10000) \
    .assert_csv_contains("Time to First Token", "Inter Token Latency")
```

### Multi-Modal Test
```python
validator = BenchmarkResult.from_directory(output["actual_dir"])
validator.assert_inputs_json_has_images()
validator.assert_inputs_json_has_audio()
validator.assert_csv_contains("Output Sequence Length")
```

### Deterministic Test (Using Pydantic Models)
```python
v1 = BenchmarkResult.from_directory(output_dir_1)
v2 = BenchmarkResult.from_directory(output_dir_2)

v1.assert_inputs_json_exists()
v2.assert_inputs_json_exists()

# Access typed InputsFile Pydantic models
inputs_1 = v1.inputs_file  # InputsFile model
inputs_2 = v2.inputs_file  # InputsFile model

# Session IDs differ (UUIDs), payloads identical
for s1, s2 in zip(inputs_1.data, inputs_2.data):
    assert s1.session_id != s2.session_id  # Type-safe access
    assert s1.payloads == s2.payloads  # Identical with same seed
```

## Helper Functions

### run_and_validate_benchmark

Replaces repetitive boilerplate:
```python
# OLD (repetitive):
result = await aiperf_runner(args)
if result["returncode"] != 0:
    print(f"\n=== STDOUT ===\n{result['stdout']}")
    print(f"\n=== STDERR ===\n{result['stderr']}")
assert result["returncode"] == 0
output = validate_aiperf_output(result["output_dir"])

# NEW (clean):
output = await run_and_validate_benchmark(
    aiperf_runner, validate_aiperf_output, args, min_requests=10
)
```

### Fixtures

- `base_profile_args` - Simple UI (for most tests)
- `dashboard_profile_args` - Dashboard UI (no manual UI replacement needed)

## Rules

1. **Use `run_and_validate_benchmark()`** - Eliminates error printing boilerplate
2. **Use `dashboard_profile_args` for dashboard tests** - No manual UI replacement
3. **Use fluent API for validation** - Chainable assertions are clearer
4. **Use `actual_dir` not `output_dir`** - From `validate_aiperf_output()`
5. **Validate both JSON and CSV** - Different export formats may have bugs
6. **Check inputs.json for multi-modal** - Verify content made it through pipeline
7. **Use ranges not exact values** - Timing varies, allow tolerance
8. **Trust Pydantic validation** - Use `.input_config`, `.inputs_file`, `.error_summary` for type-safe access

## Anti-Patterns

❌ **Don't do manual dict traversal:**
```python
# Bad
assert output["json_results"]["records"]["ttft"]["avg"] > 0
```

✅ **Use fluent API:**
```python
# Good
BenchmarkResult.from_directory(dir).assert_metric_in_range("ttft", min_value=0)
```

❌ **Don't check exact metric values:**
```python
# Bad - timing varies
assert records["ttft"]["avg"] == 25.0
```

✅ **Use ranges or tolerance:**
```python
# Good
result.assert_metric_in_range("ttft", min_value=10, max_value=100)
# Or
result.assert_metric_value("ttft", "avg", 25.0, tolerance=0.20)  # ±20%
```

## Example: Complete Multi-Modal Test

```python
async def test_multimodal_streaming(
    base_profile_args, aiperf_runner, validate_aiperf_output
):
    args = [
        *base_profile_args,
        "--endpoint-type", "chat",
        "--streaming",
        "--request-count", "20",
        "--concurrency", "5",
        "--image-width-mean", "128",
        "--audio-length-mean", "0.2",
        "--random-seed", "42",  # For reproducibility
    ]

    result = await aiperf_runner(args)
    assert result["returncode"] == 0
    output = validate_aiperf_output(result["output_dir"])

    # Use fluent API for comprehensive validation (Pydantic-powered)
    validator = BenchmarkResult.from_directory(output["actual_dir"])
    validator.assert_all_artifacts_exist() \
        .assert_log_not_empty() \
        .assert_metric_exists("ttft", "inter_token_latency", "request_latency") \
        .assert_metric_in_range("ttft", min_value=0, max_value=10000) \
        .assert_request_count(min_count=18) \
        .assert_csv_contains("Time to First Token", "Request Throughput") \
        .assert_inputs_json_has_images() \
        .assert_inputs_json_has_audio() \
        .assert_no_errors()

    # Access Pydantic models directly for custom validation
    assert validator.input_config.endpoint.streaming is True
    assert len(validator.inputs_file.data) >= 10
    assert validator.was_cancelled is False

    # Validate console output
    ConsoleOutputValidator(result["stdout"]) \
        .assert_table_displayed() \
        .assert_metric_displayed("Time to First Token")
```

## Advanced: Direct Pydantic Model Access

```python
validator = BenchmarkResult.from_directory(output_dir)

# Type-safe Pydantic model access
config: UserConfig = validator.input_config
assert config.endpoint.endpoint_type == "chat"
assert config.loadgen.concurrency == 5

# Type-safe inputs.json access
inputs: InputsFile = validator.inputs_file
for session in inputs.data:  # session is SessionPayloads (typed)
    assert session.session_id is not None
    for payload in session.payloads:
        assert "messages" in payload

# Type-safe error access
errors: list[ErrorDetailsCount] = validator.error_summary
total = sum(e.count for e in errors)  # Type-safe count access
```

That's it. Smart defaults. Chainable. Pydantic-powered. Clean.
