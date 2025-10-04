<!--
# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
-->
# AIPerf Makefile Commands Reference

## Quick Reference

All commands follow the pattern: `make <command>`

### Testing Commands

```bash
# Fast unit tests (13 seconds)
make test

# Fail-fast mode (stop on first failure)
make test-fast

# Critical behavioral tests (0.09 seconds)
make test-critical

# Full integration tests with real subprocess execution (4 minutes)
# Shows AIPerf output in real-time with progress bars
make test-integration

# Documentation structure validation
make test-docs

# Example code validation
make test-examples

# All tests including integration (4 minutes)
make test-all

# Coverage report (HTML + terminal)
make coverage
```

### Code Quality Commands

```bash
# Run linters (ruff)
make lint

# Auto-fix linter errors
make lint-fix

# Format code (ruff format)
make format

# Check formatting without changes
make check-format

# Complete validation (lint + format + tests + docs + examples)
# Recommended before creating PR
make validate-all
```

### Documentation Commands

```bash
# Build documentation with mkdocs
make docs

# Serve documentation at http://127.0.0.1:8000
make docs-serve
```

### Setup Commands

```bash
# Install project in editable mode
make install

# Complete first-time setup (venv + dependencies + pre-commit)
make first-time-setup

# Setup virtual environment only
make setup-venv
```

### Utility Commands

```bash
# Clean all caches and artifacts
make clean

# Show all available commands
make help

# Show project version
make version

# Generate __init__.py files
make init-files
```

### Docker Commands

```bash
# Build Docker image
make docker

# Run Docker container
make docker-run
```

---

## Command Details

### make test

**Purpose**: Run unit tests excluding integration tests

**Execution**:
- Uses pytest-xdist for parallel execution
- Excludes integration tests (-m "not integration")
- Fast feedback during development

**Time**: ~13 seconds

**Use When**:
- Active development
- Quick validation
- Pre-commit checks

---

### make test-critical

**Purpose**: Run critical behavioral tests that verify fundamental guarantees

**What It Tests**:
- Credit return guarantee (finally block pattern)
- Timing precision (perf_counter_ns usage)
- Exception handling (robustness)
- Service-specific logging (debugging)
- Phase completion logic

**Time**: ~0.09 seconds

**Use When**:
- Verifying core correctness
- Before refactoring critical code
- Ensuring fundamental patterns preserved

**Output**: Colored output showing test names and results

---

### make test-integration

**Purpose**: Run full end-to-end integration tests with mock server

**What It Does**:
- Spawns actual mock server subprocess
- Runs AIPerf as actual subprocess (not mocked)
- Validates complete pipeline
- Shows real-time progress with --ui simple
- Displays INFO level logs

**What It Tests**:
- Simple benchmark end-to-end
- Streaming metrics (TTFT, ITL)
- Concurrency enforcement
- Warmup and profiling phases
- JSON and CSV export
- Multiple worker coordination
- Metric computation accuracy
- Error handling
- Output file creation

**Time**: ~4 minutes (230 seconds)

**Why Slow**: Real subprocess execution per test
- Mock server startup: 2s
- AIPerf benchmark: 10-18s
- Teardown: 1s
- Per test: 15-25s
- 10 tests × 20s = ~4 minutes

**Output**: Real-time subprocess output with progress bars

**Use When**:
- Before merging PR
- Validating major changes
- Full system verification
- CI/CD pipeline

**Flags Used**:
- `--integration`: Include integration tests
- `-v`: Verbose test names
- `-s`: Show subprocess output (not captured)

---

### make test-docs

**Purpose**: Validate documentation structure and completeness

**What It Tests**:
- All 50 chapters exist
- All chapters have content (>100 lines)
- All chapters have titles
- Navigation links present
- Cross-references valid
- README references guidebook
- CONTRIBUTING.md exists
- CLAUDE.md exists
- examples/README.md exists

**Time**: ~0.02 seconds

**Use When**:
- After updating documentation
- Before documentation deployment
- Verifying guidebook structure

---

### make test-examples

**Purpose**: Validate all example code is correct and runnable

**What It Tests**:
- All examples have shebang
- All examples have docstrings with "Usage:"
- All examples are syntactically valid
- All examples have main guard
- All examples use correct imports
- All 14 documented examples exist

**Time**: ~0.03 seconds

**Use When**:
- After creating new examples
- Before committing example changes
- Verifying example quality

---

### make test-all

**Purpose**: Run complete test suite including integration tests

**Execution**:
- All unit tests
- All critical tests
- All integration tests
- Documentation tests
- Example tests

**Time**: ~4 minutes

**Use When**:
- Before major release
- Complete validation
- CI pipeline
- Weekly validation

---

### make validate-all

**Purpose**: Run complete validation pipeline (recommended before PR)

**Steps**:
1. Check code format (black, ruff)
2. Run linters (ruff)
3. Run critical tests
4. Run unit tests
5. Validate documentation
6. Validate examples

**Time**: ~1 minute (excludes slow integration tests)

**Output**: Progress indicators and success banner

**Use When**:
- Before creating PR
- Pre-commit validation
- Quick comprehensive check

**Does NOT Include**: Integration tests (too slow for pre-commit)

---

### make coverage

**Purpose**: Generate HTML coverage report

**Output**:
- HTML report in `htmlcov/`
- XML report in `coverage.xml`
- Terminal summary

**Excludes**: Integration tests (coverage not meaningful for subprocess tests)

**View Report**:
```bash
make coverage
open htmlcov/index.html
```

---

### make docs

**Purpose**: Build documentation with mkdocs in strict mode

**Output**: `site/` directory with built documentation

**Features**:
- Strict mode (fails on warnings)
- Material theme
- 50+ pages indexed
- Search enabled
- Syntax highlighting

**Deploy**:
```bash
make docs
mkdocs gh-deploy  # Deploy to GitHub Pages
```

---

### make docs-serve

**Purpose**: Serve documentation locally for preview

**Output**: Development server at http://127.0.0.1:8000

**Features**:
- Live reload on changes
- Full navigation
- Search functional
- Dark/light mode toggle

**Use When**:
- Writing documentation
- Previewing changes
- Testing navigation

---

## Recommended Workflows

### During Development

```bash
# Quick feedback loop
make test-fast

# Every few commits
make test

# Critical code changes
make test-critical
```

### Before Committing

```bash
# Format code
make format

# Validate
make validate-all
```

### Before Creating PR

```bash
# Full validation (fast)
make validate-all

# Optional: Full integration
make test-integration
```

### Weekly/Before Release

```bash
# Complete validation
make test-all

# Build docs
make docs
```

---

## Integration Test Output

### What You'll See

When running `make test-integration`, you'll see:

```
Running integration tests with mock server...
Note: Integration tests take ~4 minutes due to subprocess execution
Output from AIPerf subprocesses will be shown in real-time

===== test session starts =====

tests/integration/test_full_benchmark_integration.py::TestFullBenchmarkIntegration::test_simple_benchmark_completes_successfully

[AIPerf subprocess output will appear here in real-time]
Starting AIPerf System
Worker Manager: Starting 2 workers
[Progress bars show benchmark progress]
Benchmark completed: 10 requests in X.XX seconds

PASSED

[Next test...]
```

### Real-Time Progress

With `--ui simple` and `-s` flag:
- See AIPerf INFO logs
- See progress bars
- See benchmark completion
- See metric summaries
- See any errors immediately

### Captured vs Streaming Output

**Captured** (default for most tests):
- Output stored in variables
- Validated in assertions
- Clean test output

**Streaming** (integration tests with `-s`):
- Output goes directly to terminal
- Real-time progress visible
- Better debugging
- Shows actual AIPerf behavior

---

## Tips

### Running Specific Tests

```bash
# Single test
make test-fast args="tests/metrics/test_ttft_metric.py"

# Test class
make test args="tests/metrics/test_ttft_metric.py::TestTTFTMetric"

# With keyword filter
make test args="-k ttft"
```

### Debugging Test Failures

```bash
# Verbose output
make test-verbose

# Show print statements
make test args="-s"

# Stop on first failure
make test-fast

# Show full traceback
make test args="--tb=long"
```

### Integration Test Debugging

```bash
# Run single integration test with output
pytest tests/integration/test_full_benchmark_integration.py::TestFullBenchmarkIntegration::test_simple_benchmark_completes_successfully --integration -v -s

# Increase timeout for debugging
pytest tests/integration/ --integration -v -s --timeout=300
```

---

## See Also

- **Testing Philosophy**: `TESTING_PHILOSOPHY.md`
- **Integration Test Status**: `INTEGRATION_TEST_STATUS.md`
- **Contributing Guide**: `CONTRIBUTING.md`
- **Developer Guidebook**: `guidebook/INDEX.md`
