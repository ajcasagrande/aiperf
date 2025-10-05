<!--
# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
-->
# AIPerf VS Code Tasks Cheatsheet (2025)

Quick reference guide for all available VS Code tasks in the AIPerf project.

## How to Run Tasks

| Method | Command |
|--------|---------|
| **Task Menu** | `Ctrl+Shift+P` → "Tasks: Run Task" |
| **Default Build** | `Ctrl+Shift+B` |
| **Default Test** | `Ctrl+Shift+T` (if configured) |
| **Quick Open** | `Ctrl+P` → type "task" |

## Task Categories

- [Testing Tasks](#testing-tasks)
- [Code Quality Tasks](#code-quality-tasks)
- [Coverage Tasks](#coverage-tasks)
- [Documentation Tasks](#documentation-tasks)
- [Mock Server Tasks](#mock-server-tasks)
- [Workflow Tasks](#workflow-tasks-compound)
- [Utility Tasks](#utility-tasks)

---

## Testing Tasks

### Test: Unit Tests ⭐ (Default)
**Command:** `pytest -n auto -m "not integration"`
- Runs all unit tests in parallel
- Excludes integration tests
- Default test task (Ctrl+Shift+T)
- Shows problems in Problems panel

### Test: Unit Tests (Verbose)
**Command:** `pytest -n auto -v -s --log-cli-level DEBUG -m "not integration"`
- Runs unit tests with verbose output
- Shows DEBUG logs
- Dedicated output panel
- Use for debugging test failures

### Test: Fast (Fail Fast)
**Command:** `pytest tests/ -x -m "not integration"`
- Runs tests sequentially
- Stops on first failure
- Fast feedback for quick iterations
- No parallel execution

### Test: Critical Behavioral
**Command:** `pytest tests/critical/ -v`
- Runs critical behavioral tests only
- Located in `tests/critical/`
- Tests core invariants and contracts
- Must pass before commits

### Test: Integration Tests
**Command:** `pytest tests/integration/ --integration -v -s --log-cli-level=INFO`
- Runs integration tests (~4 minutes)
- Requires mock server running
- Real subprocess execution
- Shows progress bars and logs

### Test: Documentation Validation
**Command:** `pytest tests/test_documentation.py -v`
- Validates documentation structure
- Checks file existence
- Verifies links and references

### Test: Examples Validation
**Command:** `pytest tests/test_examples.py -v`
- Validates example code
- Ensures examples are working
- Tests example configurations

### Test: All (Complete Suite)
**Command:** `pytest tests/ --integration -v`
- Runs ALL tests including integration
- Complete test suite (~4-5 minutes)
- Use before major releases

### Test: Current File
**Command:** `pytest ${file} -v`
- Runs tests in currently open file
- Quick iteration on specific tests
- Uses current VS Code file path

---

## Code Quality Tasks

### Lint: Check with Ruff ⭐
**Command:** `ruff check .`
- Checks code for linting errors
- Shows problems in Problems panel
- Custom Ruff problem matcher
- No modifications made

**Problem Matcher:** Captures file, line, column, severity, code, message

### Lint: Fix with Ruff
**Command:** `ruff check . --fix`
- Auto-fixes linting errors
- Modifies files in place
- Use before commits
- Safe auto-fixes only

### Format: Check with Ruff
**Command:** `ruff format . --check`
- Checks code formatting
- No modifications made
- Returns exit code 1 if formatting needed
- Use in CI/CD

### Format: Apply with Ruff
**Command:** `ruff format .`
- Applies code formatting
- Modifies files in place
- Consistent with Black style
- 88 character line length

---

## Coverage Tasks

### Coverage: Generate Report
**Command:** `pytest -n auto --cov=aiperf --cov-branch --cov-report=html --cov-report=xml --cov-report=term -m "not integration"`
- Generates coverage report
- HTML, XML, and terminal output
- Branch coverage included
- Opens in dedicated panel

**Output Files:**
- `htmlcov/index.html` - HTML report
- `coverage.xml` - XML report
- `.coverage` - Coverage data

### Coverage: Open HTML Report
**Command:** `xdg-open htmlcov/index.html`
- Opens HTML coverage report in browser
- Visual coverage analysis
- Line-by-line coverage view
- Run after "Coverage: Generate Report"

---

## Documentation Tasks

### Docs: Build
**Command:** `mkdocs build --strict`
- Builds documentation
- Strict mode (fails on warnings)
- Output to `site/` directory
- Validates all links

### Docs: Serve 🔄 (Background)
**Command:** `mkdocs serve`
- Starts local documentation server
- Runs on http://127.0.0.1:8000
- Live reload on file changes
- Background task with detection

**Detection:**
- Begins: "Building documentation"
- Ends: "Documentation built"

### Docs: Stop Server
**Command:** `pkill -f "mkdocs serve"`
- Stops documentation server
- Kills background process
- Silent execution

---

## Mock Server Tasks

### Mock Server: Start 🔄 (Background)
**Command:** `cd integration-tests && python -m mock_server.main --port 8000`
- Starts OpenAI-compatible mock server
- Runs on port 8000
- Required for integration tests
- Background task with detection

**Detection:**
- Begins: "Started server process"
- Ends: "Application startup complete"

### Mock Server: Stop
**Command:** `pkill -f "mock_server.main"`
- Stops mock server
- Kills background process
- Silent execution

### Mock Server: Install
**Command:** `cd integration-tests && uv pip install -e '.[dev]'`
- Installs mock server dependencies
- Editable installation
- First-time setup requirement

---

## Workflow Tasks (Compound)

### Workflow: Quick Validation ⚡
**Dependencies:** (Sequential)
1. Format: Check with Ruff
2. Lint: Check with Ruff
3. Test: Fast (Fail Fast)

**Use Case:** Quick pre-commit check (~1-2 minutes)

### Workflow: Full Validation 🎯
**Dependencies:** (Sequential)
1. Format: Check with Ruff
2. Lint: Check with Ruff
3. Test: Critical Behavioral
4. Test: Unit Tests
5. Test: Documentation Validation
6. Test: Examples Validation

**Use Case:** Complete validation before PR (~3-4 minutes)

### Workflow: Pre-commit Check ✅
**Dependencies:** (Sequential)
1. Format: Apply with Ruff
2. Lint: Fix with Ruff
3. Test: Unit Tests

**Use Case:** Automated pre-commit workflow

### Workflow: Test with Coverage 📊
**Dependencies:** (Sequential)
1. Coverage: Generate Report
2. Coverage: Open HTML Report

**Use Case:** Generate and view coverage report

### Workflow: Integration Test Setup 🚀
**Dependencies:** (Sequential)
1. Mock Server: Install
2. Mock Server: Start

**Use Case:** Prepare environment for integration testing

---

## Utility Tasks

### Clean: Remove Caches 🧹
**Command:** `rm -rf .pytest_cache/ .ruff_cache/ htmlcov/ site/ && find . -type f -name '*.pyc' -delete && ...`
- Removes all cache directories
- Deletes `.pyc` files
- Deletes `__pycache__` directories
- Cleans coverage reports

**Removes:**
- `.pytest_cache/`
- `.ruff_cache/`
- `.mypy_cache/`
- `htmlcov/`
- `site/`
- `*.pyc`
- `__pycache__/`
- `.coverage`

### Install: Project Dependencies 📦
**Command:** `uv pip install -e '.[dev]'`
- Installs AIPerf with dev dependencies
- Editable installation
- Uses `uv` package manager
- Installs from `pyproject.toml`

### Init: Generate __init__.py Files 🔧
**Command:** `tools/generate_init_files.sh`
- Generates `__init__.py` files using mkinit
- Updates module exports
- Required after structural changes
- Run before commits if structure changed

---

## Task Features Legend

| Symbol | Meaning |
|--------|---------|
| ⭐ | Default/Primary task |
| 🔄 | Background task (runs continuously) |
| ⚡ | Fast execution |
| 🎯 | Comprehensive validation |
| ✅ | Pre-commit workflow |
| 📊 | Generates reports |
| 🚀 | Setup/initialization |
| 🧹 | Cleanup task |
| 📦 | Installation task |
| 🔧 | Code generation |

---

## Quick Reference Table

| Task | Category | Duration | When to Use |
|------|----------|----------|-------------|
| Test: Fast | Testing | ~30s | Quick iteration |
| Test: Unit Tests | Testing | ~1-2m | Regular development |
| Test: Critical | Testing | ~1m | Before commits |
| Test: Integration | Testing | ~4m | Before PR/Release |
| Lint: Check | Quality | ~5s | Pre-commit |
| Lint: Fix | Quality | ~10s | Auto-fix errors |
| Format: Apply | Quality | ~5s | Before commits |
| Coverage: Generate | Coverage | ~2m | Periodic checks |
| Docs: Build | Docs | ~30s | Documentation changes |
| Docs: Serve | Docs | Background | Documentation development |
| Quick Validation | Workflow | ~2m | Pre-commit |
| Full Validation | Workflow | ~4m | Before PR |

---

## Common Workflows

### 1. Starting Development Session

```
1. Install: Project Dependencies
2. Mock Server: Start (if doing integration work)
3. Docs: Serve (if working on docs)
```

### 2. Before Committing

```
Option A (Quick):
- Workflow: Quick Validation

Option B (Manual):
1. Format: Apply with Ruff
2. Lint: Fix with Ruff
3. Test: Fast (Fail Fast)
```

### 3. Before Creating PR

```
1. Workflow: Full Validation
2. Test: Integration Tests (optional)
3. Coverage: Generate Report (optional)
```

### 4. After Structural Changes

```
1. Init: Generate __init__.py Files
2. Test: Unit Tests
3. Lint: Check with Ruff
```

### 5. Debugging Test Failures

```
1. Test: Current File (to isolate)
2. Test: Unit Tests (Verbose) (for details)
3. Use Debug configuration (F5)
```

### 6. Performance Investigation

```
1. Coverage: Generate Report
2. Profile: cProfile AIPerf Main (from launch.json)
3. Analyze with profiling tools
```

---

## Tips and Tricks

### Running Tasks Efficiently

1. **Pin Frequent Tasks**: Add keybindings for your most-used tasks
2. **Use Quick Open**: `Ctrl+P` → type "task " to filter tasks
3. **Task History**: VS Code remembers recent tasks
4. **Background Tasks**: Let them run while you work

### Understanding Output

1. **Problems Panel**: `Ctrl+Shift+M` to view all problems
2. **Terminal Output**: Check "Terminal" tab for full output
3. **Problem Matchers**: Automatically parsed into Problems panel
4. **Exit Codes**: Green checkmark = success, red X = failure

### Troubleshooting

| Issue | Solution |
|-------|----------|
| Task not found | Reload window (`Ctrl+Shift+P` → "Reload Window") |
| Virtual env issues | Run "Install: Project Dependencies" |
| Background task stuck | Use corresponding "Stop" task |
| Problems not showing | Check problem matcher is defined |

### Performance Tips

1. **Parallel Execution**: Unit tests run in parallel by default
2. **Fail Fast**: Use when iterating on specific feature
3. **Current File**: Test single file instead of whole suite
4. **Verbose Mode**: Only when debugging, slower due to output

---

## Related Documentation

- [VS Code Tasks README](./README.md) - Complete documentation
- [Debug Guide](./DEBUG_GUIDE.md) - Debugging configurations
- [AIPerf Makefile](../../Makefile) - Command-line alternatives
- [Makefile Commands](../../MAKEFILE_COMMANDS.md) - Makefile documentation

---

## Notes

- All tasks assume `.venv` is activated
- Tasks run from workspace root by default
- Background tasks must be manually stopped
- Compound tasks run dependencies in sequence
- Problem matchers parse output for errors/warnings

---

**Last Updated:** 2025-10-04
**VS Code Version:** 1.90+
**AIPerf Version:** 0.1.1
