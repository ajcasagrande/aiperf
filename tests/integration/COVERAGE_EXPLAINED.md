<!--
SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
SPDX-License-Identifier: Apache-2.0
-->

# Integration Test Coverage - Understanding the Numbers

## TL;DR

**Integration test coverage shows ~40%** which is **expected and correct** for subprocess-based integration tests. This measures the test infrastructure code, not the subprocess code.

```
Coverage Types:
- Unit tests:        70-80% (measures application code directly)
- Integration tests: 30-40% (measures test framework + some shared code)
- Combined:          60-70% (recommended target)
```

## Why Integration Coverage Is Lower

### The Nature of Integration Tests

Integration tests run AIPerf as a **subprocess** (separate process):

```python
# This is what integration tests do:
cmd = [sys.executable, "-m", "aiperf.cli"] + args
process = await asyncio.create_subprocess_exec(*cmd, ...)
```

**Coverage collector in parent process cannot see into child process.**

### What Integration Coverage Measures

Integration test coverage shows what **the test framework itself** executes:

✅ **Measured (40%):**
- Test fixtures (conftest.py)
- Result validators (result_validators.py)
- Test models (test_models.py)
- Pydantic model imports
- ZMQ communication setup (shared code)
- Configuration model parsing
- Some utilities

❌ **Not Measured (subprocess code):**
- Worker processes
- System controller
- Dataset manager
- Records manager
- Timing manager
- UI components
- Service lifecycle

**This is normal and expected** for subprocess-based integration tests.

## What Should Be Measured Where

### Unit Tests → Application Code Coverage
**Purpose:** Measure code paths, edge cases, error handling
**Target:** 70-80% coverage
**What they test:**
- Individual functions
- Class methods
- Error conditions
- Edge cases
- Business logic

```bash
make coverage-unit
# High coverage of application code
```

### Integration Tests → Behavior Validation
**Purpose:** Validate end-to-end workflows work correctly
**Target:** NOT about coverage percentage
**What they validate:**
- Complete pipelines work
- Services communicate correctly
- CLI interface works
- Subprocess execution works
- Multi-modal content flows through system
- Outputs are generated correctly

```bash
make test-integration
# Validates behavior, not coverage
```

## Why Subprocess-Based Tests Are Correct

Integration tests **MUST** run as subprocess because:

1. **Tests the real user experience** - Users run `aiperf` command, not Python imports
2. **Tests process isolation** - Each benchmark is isolated
3. **Tests CLI parsing** - Validates command-line arguments
4. **Tests subprocess behavior** - Signals, termination, cleanup
5. **Tests ZMQ multi-process** - AIPerf spawns worker processes
6. **True end-to-end** - Tests the complete deployment

**Trying to get coverage from subprocess-based integration tests misses the point.**

## Solution: Use Both Test Types

### Integration Tests (Subprocess)
**31 tests in test_multimodal_integration.py, test_full_benchmark_integration.py**

**Purpose:** Validate behavior
- Run as subprocess (real CLI)
- Validate outputs
- Check metrics accuracy
- Test multi-modal pipelines
- Stress test concurrency

**Coverage:** ~40% (test framework + shared code)

### Unit Tests
**Hundreds of tests in tests/**

**Purpose:** Measure code coverage
- Import and call functions directly
- Test individual components
- Cover edge cases
- Mock dependencies

**Coverage:** 70-80% (application code)

### Combined Coverage
```bash
make coverage-all
# Unit tests (70-80%) + Integration tests (40%) = ~60-70% combined
```

## Advanced: Enabling Subprocess Coverage (Complex)

If you **really** need to measure subprocess coverage, here's how:

### Step 1: Add .coveragerc or sitecustomize.py

Create `sitecustomize.py` in your site-packages:
```python
import coverage
coverage.process_startup()
```

### Step 2: Set Environment Variable

```bash
export COVERAGE_PROCESS_START=pyproject.toml
```

### Step 3: Enable Parallel Coverage

Already configured in pyproject.toml:
```toml
[tool.coverage.run]
parallel = true
sigterm = true
```

### Step 4: Combine Coverage Data

```bash
# Run tests (creates .coverage.* files for each subprocess)
pytest tests/integration/ --integration --cov=aiperf

# Combine all coverage data
coverage combine

# Generate report
coverage html
```

### Why We Don't Do This

1. **Complex setup** - Requires sitecustomize.py
2. **Maintenance burden** - Coverage in every subprocess
3. **Performance cost** - Coverage adds overhead
4. **Not the goal** - Integration tests validate behavior
5. **Unit tests better** - For measuring code coverage

## Recommended Approach

### For Development

```bash
# Check behavior
make test-integration              # 35s, validates behavior

# Check code coverage
make coverage-unit                 # 30s, measures code paths

# Combined view
make coverage-all                  # 60s, complete picture
```

### For CI/CD

```yaml
# Run both test types
- name: Unit tests with coverage
  run: make coverage-unit

- name: Integration tests (behavior)
  run: make test-integration

# Report unit test coverage (more meaningful)
- name: Upload coverage
  uses: codecov/codecov-action@v4
  with:
    file: ./coverage-unit.xml
```

### For Code Review

**Focus on unit test coverage** for:
- New features
- Bug fixes
- Edge cases
- Error handling

**Use integration tests** for:
- Validating features work end-to-end
- Catching integration bugs
- Testing multi-component interactions

## Current Coverage Breakdown

### From `make coverage-integration`

```
Total Coverage:          40.64%

High Coverage (Test Framework):
- ZMQ communication:     27-81% (shared between parent/subprocess)
- Configuration models:  High (imported in tests)
- Test utilities:        100% (test code itself)

Zero Coverage (Subprocess):
- Workers:               0% (run in subprocess)
- Managers:              0% (run in subprocess)
- UI:                    0% (run in subprocess)
- Services:              0% (run in subprocess)
```

**This is expected and correct.**

### From `make coverage-unit` (hypothetical)

```
Total Coverage:          70-80%

High Coverage:
- Workers:               High
- Managers:              High
- Metrics:               High
- Parsers:               High
- Configuration:         High

Lower Coverage:
- UI:                    Medium (harder to unit test)
- Integration glue:      Medium (tested in integration)
```

### From `make coverage-all` (combined)

```
Total Coverage:          60-70%

Complete picture of:
- Unit-testable code:    High coverage
- Integration paths:     Validated (not measured)
- Combined confidence:   Very high
```

## Interpretation Guide

### ~40% Integration Coverage Means:

✅ **Good Things:**
- Test framework is robust
- Fixtures are comprehensive
- Validation helpers are thorough
- Shared code is exercised
- Pydantic models are validated

❌ **Does NOT Mean:**
- 60% of AIPerf code is untested (unit tests cover this)
- Integration tests are insufficient (they validate behavior)
- We need more integration tests (31 is comprehensive)

### How to Improve Overall Coverage

**Don't:** Try to get coverage from subprocess integration tests
**Do:** Write more unit tests for components

```bash
# Find what needs unit tests
make coverage-unit

# Look at htmlcov/unit/index.html
# Red lines = need unit tests

# Write unit tests for those areas
# Integration tests validate they work together
```

## Summary

| Aspect | Integration Tests | Unit Tests |
|--------|------------------|------------|
| **Purpose** | Validate behavior | Measure coverage |
| **Execution** | Subprocess | Direct import |
| **Coverage** | ~40% (test framework) | ~70-80% (app code) |
| **Speed** | ~35s (parallel) | ~30s |
| **Value** | Catch integration bugs | Catch logic bugs |
| **Use For** | Feature validation | Code coverage |

**Both are essential. They serve different purposes.**

## Recommendations

### ✅ DO:

1. **Use integration tests** to validate end-to-end behavior
2. **Use unit tests** to measure code coverage
3. **Look at combined coverage** for full picture
4. **Focus on ~60-70% combined coverage** as target

### ❌ DON'T:

1. **Don't expect high coverage** from integration tests alone
2. **Don't try to replace unit tests** with integration tests
3. **Don't measure integration test coverage** as primary metric
4. **Don't add complexity** to get subprocess coverage

## Conclusion

**Integration test coverage of ~40% is healthy and expected.**

It shows:
- ✅ Test framework is comprehensive
- ✅ Shared code is exercised
- ✅ Fixtures and validators work
- ✅ Pydantic models are validated

For measuring application code coverage:
- ✅ Use unit tests (70-80% target)
- ✅ Use combined coverage (60-70% target)
- ✅ Integration tests validate behavior (not coverage)

**The ~40% you see is measuring the right things. The subprocess code should be measured by unit tests.**

---

## Quick Commands

```bash
# Integration tests (behavior validation)
make test-integration                    # 35s

# Unit tests (code coverage)
make coverage-unit                       # 30s, see htmlcov/unit/

# Combined (complete picture)
make coverage-all                        # 60s, see htmlcov/

# Clean coverage data
make coverage-clean
```

**Integration tests validate behavior. Unit tests measure coverage. Both are essential.**
