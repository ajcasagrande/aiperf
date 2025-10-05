<!--
SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
SPDX-License-Identifier: Apache-2.0
-->

# Integration Testing Guide

## Quick Start

```python
from tests.integration.result_validators import BenchmarkResult, ConsoleOutputValidator

# Run benchmark
result = await aiperf_runner(args)
assert result["returncode"] == 0

# Validate with fluent API (chainable)
BenchmarkResult.from_directory(output["actual_dir"]) \
    .assert_all_artifacts_exist() \
    .assert_metric_exists("ttft", "request_latency") \
    .assert_metric_in_range("ttft", min_value=0, max_value=5000) \
    .assert_request_count(min_count=95, max_count=105) \
    .assert_csv_contains("Time to First Token", "Request Latency") \
    .assert_inputs_json_has_images() \
    .assert_no_errors()
```

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

### Properties

- `.records` - Dict of metrics
- `.json_data` - Full JSON export
- `.csv_content` - CSV text
- `.inputs_json` - inputs.json dict

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

### Basic Test
```python
output = validate_aiperf_output(result["output_dir"])
BenchmarkResult.from_directory(output["actual_dir"]) \
    .assert_all_artifacts_exist() \
    .assert_metric_exists("request_latency") \
    .assert_request_count(min_count=10)
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

### Deterministic Test
```python
v1 = BenchmarkResult.from_directory(output_dir_1)
v2 = BenchmarkResult.from_directory(output_dir_2)

# Compare inputs.json payloads
inputs_1 = v1.inputs_json
inputs_2 = v2.inputs_json

# Session IDs differ (UUIDs), payloads identical
for s1, s2 in zip(inputs_1["data"], inputs_2["data"]):
    assert s1["session_id"] != s2["session_id"]
    assert s1["payloads"] == s2["payloads"]  # Identical with same seed
```

## Rules

1. **Always use fluent API** - Chainable assertions are clearer
2. **Use `actual_dir` not `output_dir`** - From `validate_aiperf_output()`
3. **Test artifacts exist** - Call `assert_all_artifacts_exist()` early
4. **Validate both JSON and CSV** - Different export formats may have bugs
5. **Check inputs.json for multi-modal** - Verify content made it through pipeline
6. **Use ranges not exact values** - Timing varies, allow tolerance
7. **Don't validate internal metrics** - Only test user-facing metrics

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

    # Use fluent API for comprehensive validation
    BenchmarkResult.from_directory(output["actual_dir"]) \
        .assert_all_artifacts_exist() \
        .assert_log_not_empty() \
        .assert_metric_exists("ttft", "inter_token_latency", "request_latency") \
        .assert_metric_in_range("ttft", min_value=0, max_value=10000) \
        .assert_request_count(min_count=18) \
        .assert_csv_contains("Time to First Token", "Request Throughput") \
        .assert_inputs_json_has_images() \
        .assert_inputs_json_has_audio() \
        .assert_no_errors()

    # Validate console output
    ConsoleOutputValidator(result["stdout"]) \
        .assert_table_displayed() \
        .assert_metric_displayed("Time to First Token")
```

That's it. Smart defaults. Chainable. Clean.
