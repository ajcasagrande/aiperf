<!--
SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
SPDX-License-Identifier: Apache-2.0
-->

# Integration Test Cleanup - Transformation Summary

## Code Reduction: 50%

```
Before: 1,978 lines
After:    980 lines
Saved:    998 lines
```

### File Breakdown

| File | Before | After | Reduction |
|------|--------|-------|-----------|
| test_multimodal_integration.py | 825 | 291 | **534 lines (65%)** |
| result_validators.py | 617 | 232 | **385 lines (62%)** |
| conftest.py | 536 | 457 | **79 lines (15%)** |

## Eliminations

### ❌ Raw Dict Access: 100% → 0%
**Before:**
```python
records = output["json_results"]["records"]
assert_basic_metrics(records, "request_count", "request_latency")
completed = records["request_count"].get("avg", 0)
assert completed >= 10
```

**After:**
```python
BenchmarkResult.from_directory(output["actual_dir"]) \
    .assert_request_count(min_count=10)
```

### ❌ Error Printing Blocks: 12 → 0
**Before (repeated 12x):**
```python
result = await aiperf_runner(args)
if result["returncode"] != 0:
    print(f"\n=== STDOUT ===\n{result['stdout']}")
    print(f"\n=== STDERR ===\n{result['stderr']}")
assert result["returncode"] == 0
output = validate_aiperf_output(result["output_dir"])
```

**After:**
```python
output = await run_and_validate_benchmark(
    aiperf_runner, validate_aiperf_output, args, min_requests=10
)
```

### ❌ UI Replacement Logic: 2 → 0
**Before:**
```python
args_without_ui = []
skip_next = False
for i, arg in enumerate(base_profile_args):
    if skip_next:
        skip_next = False
        continue
    if arg == "--ui":
        skip_next = True
        continue
    args_without_ui.append(arg)

dashboard_args = [*args_without_ui, "--ui", "dashboard", ...]
```

**After:**
```python
args = [*dashboard_profile_args, "--endpoint-type", "chat", ...]
```

### ❌ Verbose Docstrings: 4 bullets → 1 line
**Before:**
```python
"""Test chat endpoint with synthetic image content.

WHY TEST THIS:
- Validates image content handling end-to-end
- Ensures AIPerf's built-in synthetic image generation works
- Verifies image data does not break the benchmark pipeline
- Tests production code path users would follow
"""
```

**After:**
```python
"""Validates synthetic image generation and end-to-end image handling."""
```

### ❌ Repeated Flag Patterns
**Before (repeated in every test):**
```python
"--image-width-mean", "64",
"--image-height-mean", "64",
```

**After:**
```python
*IMAGE_64
```

### ❌ String Conversions
**Before:**
```python
"--request-count", str(DEFAULT_REQUEST_COUNT),
"--concurrency", str(DEFAULT_CONCURRENCY),
```

**After:**
```python
DEFAULT_REQUEST_COUNT = "5"  # Already string
DEFAULT_CONCURRENCY = "2"     # Already string

"--request-count", DEFAULT_REQUEST_COUNT,
"--concurrency", DEFAULT_CONCURRENCY,
```

### ❌ Deterministic Test Complexity: 118 lines → 30 lines
**Before:** 50+ lines of nested loops comparing payloads

**After:**
```python
# Payloads identical, session_ids differ (UUIDs)
for s1, s2 in zip(inputs_1.data, inputs_2.data):
    assert s1.session_id != s2.session_id
    assert s1.payloads == s2.payloads
```

## New Features

### ✅ Helper Function
```python
async def run_and_validate_benchmark(
    aiperf_runner, validate_aiperf_output, args, timeout=60.0, min_requests=None
) -> dict
```
Replaces 12 blocks of error handling code.

### ✅ Constants
```python
IMAGE_64 = ["--image-width-mean", "64", "--image-height-mean", "64"]
AUDIO_SHORT = ["--audio-length-mean", "0.1"]
```

### ✅ Dashboard Fixture
```python
@pytest.fixture
def dashboard_profile_args(mock_server) -> list[str]
```

### ✅ 100% Pydantic Models
- `MetricResult` - Type-safe `.avg`, `.p99`, etc.
- `UserConfig` - Full config validation
- `InputsFile` - Type-safe sessions/payloads
- `ErrorDetailsCount` - Type-safe error counts

## Before/After Comparison

### Typical Test

**Before (31 lines):**
```python
async def test_chat_endpoint_with_image_content(
    self,
    base_profile_args,
    aiperf_runner,
    validate_aiperf_output,
):
    """Test chat endpoint with synthetic image content.

    WHY TEST THIS:
    - Validates image content handling end-to-end
    - Ensures AIPerf's built-in synthetic image generation works
    - Verifies image data does not break the benchmark pipeline
    - Tests production code path users would follow
    """
    args = [
        *base_profile_args,
        "--endpoint-type", "chat",
        "--request-count", str(DEFAULT_REQUEST_COUNT),
        "--concurrency", str(DEFAULT_CONCURRENCY),
        "--image-width-mean", "64",
        "--image-height-mean", "64",
        "--image-format", "png",
    ]

    result = await aiperf_runner(args)
    if result["returncode"] != 0:
        print(f"\n=== STDOUT ===\n{result['stdout']}")
        print(f"\n=== STDERR ===\n{result['stderr']}")
    assert result["returncode"] == 0

    output = validate_aiperf_output(result["output_dir"])
    records = output["json_results"]["records"]
    assert_basic_metrics(records, "request_count")
```

**After (12 lines):**
```python
async def test_chat_endpoint_with_image_content(
    self, base_profile_args, aiperf_runner, validate_aiperf_output
):
    """Validates synthetic image generation and end-to-end image handling."""
    args = [*base_profile_args, "--endpoint-type", "chat",
            "--request-count", DEFAULT_REQUEST_COUNT, "--concurrency", DEFAULT_CONCURRENCY,
            *IMAGE_64, "--image-format", "png"]

    output = await run_and_validate_benchmark(
        aiperf_runner, validate_aiperf_output, args, min_requests=3
    )

    BenchmarkResult.from_directory(output["actual_dir"]) \
        .assert_metric_exists("output_sequence_length") \
        .assert_inputs_json_has_images()
```

**Reduction: 61%**

## Impact

✅ **Readability:** Tests are now 50% shorter and easier to understand
✅ **Maintainability:** No duplicated code, changes in one place
✅ **Type Safety:** 100% Pydantic models, zero raw dicts
✅ **Consistency:** All tests use same patterns
✅ **DRY:** Single source of truth for common patterns

## Test Results

```
15 passed in ~103s
0 raw dict access
0 error print blocks
0 warnings
100% Pydantic validation
```

## Developer Experience

**Old way (verbose):**
- Write 30+ lines per test
- Copy-paste error handling
- Manual dict navigation
- Verbose docstrings

**New way (concise):**
- Write 10-15 lines per test
- Use `run_and_validate_benchmark()`
- Fluent Pydantic API
- One-line docstrings

**Result:** Tests that are clean, concise, type-safe, and maintainable.
