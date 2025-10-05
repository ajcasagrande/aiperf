<!--
SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
SPDX-License-Identifier: Apache-2.0
-->

# Makefile Guide for AIPerf Integration Tests

## Quick Reference

```bash
# Run integration tests (parallel, fast!)
make test-integration                    # ~35 seconds

# Run with coverage
make coverage-integration                # ~40 seconds, generates HTML report

# Run all tests with combined coverage
make coverage-all                        # ~60 seconds, unit + integration

# View coverage report
open htmlcov/integration/index.html      # Integration coverage only
open htmlcov/index.html                  # Combined coverage
```

## Integration Test Commands

### Basic Testing

**`make test-integration`** - Parallel execution (default, recommended)
```bash
make test-integration
# ✓ Runs pytest with -n auto (automatic parallelization)
# ✓ ~35 seconds for 31 tests
# ✓ Quiet output (clean summary)
# ✓ Best for development workflow
```

**`make test-integration-verbose`** - Sequential with real-time output
```bash
make test-integration-verbose
# ✓ Shows AIPerf subprocess output in real-time
# ✓ Progress bars visible
# ✓ ~3 minutes (slower, but good for debugging)
# ✓ Use when you need to see what's happening
```

**`make test-integration-parallel`** - Alias for test-integration
```bash
make test-integration-parallel
# Same as make test-integration
```

### Coverage Commands

**`make coverage-integration`** - Integration tests with coverage
```bash
make coverage-integration
# ✓ Runs integration tests in parallel
# ✓ Generates coverage report for code hit by integration tests
# ✓ Creates HTML report: htmlcov/integration/index.html
# ✓ Creates XML report: coverage-integration.xml
# ✓ Shows terminal summary
# ✓ ~40 seconds
```

**`make coverage-unit`** - Unit tests with coverage
```bash
make coverage-unit
# ✓ Runs unit tests only (no integration)
# ✓ Creates HTML report: htmlcov/unit/index.html
# ✓ Creates XML report: coverage-unit.xml
# ✓ ~30 seconds
```

**`make coverage-all`** - Combined coverage (unit + integration)
```bash
make coverage-all
# ✓ Runs ALL tests (unit + integration)
# ✓ Combined coverage report
# ✓ Creates HTML report: htmlcov/index.html
# ✓ Creates XML report: coverage.xml
# ✓ Most comprehensive coverage
# ✓ ~60 seconds
```

**`make coverage`** or **`make coverage-report`** - Alias for coverage-all
```bash
make coverage
# Same as make coverage-all
```

### Coverage Utilities

**`make coverage-clean`** - Remove all coverage data
```bash
make coverage-clean
# Removes: .coverage, .coverage.*, htmlcov/, coverage*.xml
```

**`make coverage-html`** - Generate HTML from existing .coverage file
```bash
# First run tests to generate .coverage
pytest tests/integration/ --integration --cov=aiperf

# Then generate HTML report
make coverage-html
# Creates: htmlcov/index.html
```

**`make coverage-xml`** - Generate XML for CI/CD
```bash
make coverage-xml
# Creates: coverage.xml (for CI/CD pipelines)
```

## Coverage Reports Explained

### What Gets Measured

Integration tests measure coverage of:
- ✓ **End-to-end code paths** - Full system integration
- ✓ **Service coordination** - Worker/manager/dataset/records managers
- ✓ **ZMQ communication** - Message bus, pub/sub, push/pull
- ✓ **CLI layer** - Command line interface and subprocess execution
- ✓ **Export pipelines** - JSON/CSV exporters
- ✓ **Configuration** - Config parsing and validation
- ✓ **Metric computation** - From raw responses to aggregated metrics

### Current Integration Test Coverage

```
Total Coverage: ~35%
```

**High Coverage Areas:**
- ZMQ communication: ~30-75%
- Configuration: High
- Models: 100% (all parsed)
- Exporters: High

**Lower Coverage Areas (expected):**
- UI components: 0% (not tested in integration, tested separately)
- Internal utilities: Variable
- Some edge cases: Unit tested instead

### Understanding Coverage Output

```
Name                                      Stmts   Miss  Cover
------------------------------------------------------------
aiperf/cli/cli.py                           234     89    62%
aiperf/common/config/user_config.py         156     23    85%
aiperf/dataset/dataset_manager.py           178     45    75%
aiperf/workers/worker.py                    157     89    43%
aiperf/zmq/pub_client.py                     34     18    47%
------------------------------------------------------------
TOTAL                                     10362   6132    35%
```

**How to read:**
- **Stmts** - Total lines of executable code
- **Miss** - Lines not covered by tests
- **Cover** - Percentage covered

### HTML Coverage Report

After running `make coverage-integration`, open the HTML report:

```bash
open htmlcov/integration/index.html
```

**Features:**
- ✓ Line-by-line coverage highlighting
- ✓ Green = covered by tests
- ✓ Red = not covered
- ✓ Click files to see exact lines
- ✓ Branch coverage shown
- ✓ Per-test context (which test hit which line)

### Coverage with Context

The `--cov-context=test` flag enables seeing **which specific test** hit each line:

```bash
# After running with --cov-context=test
coverage html --show-contexts

# Then view htmlcov/index.html
# Hover over lines to see which tests executed them!
```

## Advanced Usage

### Custom Coverage Thresholds

Add to pytest.ini or pyproject.toml:
```ini
[tool.coverage.report]
fail_under = 40
show_missing = true
skip_covered = false
```

Then coverage will fail if below 40%.

### Integration Tests for Specific Files

```bash
# Run tests and see coverage for specific modules
make coverage-integration args="--cov=aiperf/workers --cov=aiperf/zmq"
```

### Parallel Workers Control

```bash
# Control number of parallel workers
make test-integration args="-n 4"  # Use 4 workers

# Or use auto-detection
make test-integration args="-n auto"  # Default
```

### Pass Additional pytest Args

All make targets support additional arguments:

```bash
# Run specific test with coverage
make coverage-integration args="-k test_multimodal"

# Run with verbose output
make coverage-integration args="-v"

# Fail fast (stop on first failure)
make test-integration args="-x"

# Show specific test
make test-integration args="tests/integration/test_multimodal_integration.py::TestMultiModalIntegration::test_chat_endpoint_with_image_content -v"
```

## Integration with CI/CD

### GitHub Actions Example

```yaml
name: Integration Tests with Coverage

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.12'

      - name: Install dependencies
        run: make install

      - name: Run integration tests with coverage
        run: make coverage-integration

      - name: Upload coverage to Codecov
        uses: codecov/codecov-action@v4
        with:
          file: ./coverage-integration.xml
          flags: integration
          name: integration-coverage
```

### GitLab CI Example

```yaml
integration-tests:
  stage: test
  script:
    - make install
    - make coverage-integration
  coverage: '/TOTAL.*\s+(\d+%)$/'
  artifacts:
    reports:
      coverage_report:
        coverage_format: cobertura
        path: coverage-integration.xml
    paths:
      - htmlcov/integration/
    expire_in: 30 days
```

## Workflow Examples

### Development Workflow

```bash
# 1. Make changes to code
vim aiperf/workers/worker.py

# 2. Run integration tests quickly
make test-integration                    # 35 seconds

# 3. If tests fail, run verbose mode to debug
make test-integration-verbose            # See real-time output

# 4. Once fixed, check coverage
make coverage-integration                # See what you covered

# 5. View coverage report in browser
open htmlcov/integration/index.html
```

### Pre-Commit Workflow

```bash
# Run all validations before committing
make validate-all

# Or just integration tests
make test-integration
```

### Release Workflow

```bash
# Generate complete coverage report for release
make coverage-all

# View combined unit + integration coverage
open htmlcov/index.html

# Ensure it meets threshold (e.g., 40%+)
```

## Tips & Tricks

### Quick Integration Test Development

```bash
# Run specific test class
make test-integration args="-k TestMultiModalIntegration -v"

# Run and see coverage for specific module
pytest tests/integration/ --integration -n auto \
  --cov=aiperf/dataset \
  --cov-report=term-missing

# This shows which lines in aiperf/dataset/ are NOT covered
```

### Coverage Report Formats

```bash
# Terminal output only
pytest tests/integration/ --integration --cov=aiperf --cov-report=term

# HTML only
pytest tests/integration/ --integration --cov=aiperf --cov-report=html

# Multiple formats
pytest tests/integration/ --integration --cov=aiperf \
  --cov-report=term \
  --cov-report=html \
  --cov-report=xml
```

### Coverage with Missing Lines

```bash
# Show which lines are NOT covered
make coverage-integration args="--cov-report=term-missing"

# Output shows line numbers that weren't executed
```

### Combining Coverage from Multiple Runs

```bash
# Run unit tests
pytest -m "not integration" --cov=aiperf --cov-append

# Run integration tests (append to same .coverage file)
pytest tests/integration/ --integration --cov=aiperf --cov-append

# Generate combined report
coverage html
```

## Troubleshooting

### Coverage shows 0% for everything

**Issue:** No .coverage file generated

**Solution:**
```bash
# Ensure pytest-cov is installed
pip list | grep pytest-cov

# Run with coverage explicitly
pytest tests/integration/ --integration --cov=aiperf --cov-report=term
```

### "No source for code" warnings

**Issue:** Coverage can't find source files

**Solution:** Ensure running from project root:
```bash
cd /path/to/aiperf
make coverage-integration
```

### Integration tests timeout in coverage mode

**Issue:** Coverage adds ~10-15% overhead

**Solution:** Increase timeouts in conftest.py or use:
```bash
make test-integration  # No coverage, faster
```

### Can't open HTML report

**Issue:** File not found

**Solution:**
```bash
# Check if report was generated
ls -lh htmlcov/integration/index.html

# Regenerate if needed
make coverage-integration

# Open with default browser
python3 -m webbrowser htmlcov/integration/index.html
```

## Coverage Goals

### Recommended Thresholds

- **Unit Tests:** 70-80% coverage (fast, comprehensive)
- **Integration Tests:** 30-40% coverage (end-to-end critical paths)
- **Combined:** 60-70% coverage (balanced)

### What Integration Tests Should Cover

✓ **Critical paths:** User-facing workflows
✓ **Service integration:** Inter-service communication
✓ **End-to-end flows:** Complete benchmark pipelines
✓ **Error handling:** Graceful failure scenarios

✗ **Not needed in integration:**
- Edge cases (unit test these)
- UI rendering (integration tests run headless)
- Internal utilities (unit test these)

## Summary

The enhanced Makefile provides:
- ✅ Separate coverage for unit vs integration tests
- ✅ Combined coverage reports
- ✅ Parallel execution by default (5x faster!)
- ✅ HTML, XML, and terminal reports
- ✅ Easy-to-use commands
- ✅ CI/CD friendly
- ✅ Comprehensive documentation

**Run `make help` to see all available commands!**
