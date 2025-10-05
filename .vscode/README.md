<!--
# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
-->
# AIPerf VS Code Configuration (2025)

This directory contains comprehensive VS Code configurations for AIPerf development, including task automation, debugging, and workflow optimization.

## Files Overview

- **`tasks.json`**: Task automation and workflow configurations
- **`launch.json`**: Debugging and profiling configurations
- **`settings.json`**: Workspace-specific settings
- **`extensions.json`**: Recommended extensions for AIPerf development

## Quick Start

### Running Tasks

Press `Ctrl+Shift+P` (or `Cmd+Shift+P` on macOS) and type "Tasks: Run Task" to see all available tasks.

**Quick Access:**
- `Ctrl+Shift+B` - Run default build task
- `Ctrl+Shift+T` - Run default test task

### Common Tasks

#### Testing
```
Test: Unit Tests                  - Run unit tests (default, parallel)
Test: Unit Tests (Verbose)        - Run with DEBUG logging
Test: Fast (Fail Fast)            - Run tests, stop on first failure
Test: Critical Behavioral         - Run critical behavioral tests
Test: Integration Tests           - Run integration tests (~4 minutes)
Test: Documentation Validation    - Validate documentation structure
Test: Examples Validation         - Validate example code
Test: All (Complete Suite)        - Run all tests including integration
Test: Current File                - Run tests in current file
```

#### Code Quality
```
Lint: Check with Ruff            - Check code for linting errors
Lint: Fix with Ruff              - Auto-fix linting errors
Format: Check with Ruff          - Check code formatting
Format: Apply with Ruff          - Apply code formatting
```

#### Coverage
```
Coverage: Generate Report        - Generate coverage report
Coverage: Open HTML Report       - Open coverage report in browser
```

#### Documentation
```
Docs: Build                      - Build documentation
Docs: Serve                      - Serve documentation (background task)
Docs: Stop Server                - Stop documentation server
```

#### Mock Server
```
Mock Server: Start               - Start mock server (background)
Mock Server: Stop                - Stop mock server
Mock Server: Install             - Install mock server dependencies
```

#### Workflows (Compound Tasks)
```
Workflow: Quick Validation       - Format check + Lint + Fast tests
Workflow: Full Validation        - Complete validation suite
Workflow: Pre-commit Check       - Format + Lint + Tests
Workflow: Test with Coverage     - Tests + Coverage report
Workflow: Integration Test Setup - Install + Start mock server
```

#### Utilities
```
Clean: Remove Caches             - Clean pytest/ruff caches
Install: Project Dependencies    - Install project with dev dependencies
Init: Generate __init__.py Files - Run mkinit
```

## Task Features

### Problem Matchers

The configuration includes custom problem matchers for:

1. **Pytest Problem Matcher**
   - Captures test failures and errors
   - Shows file, line, and message in Problems panel
   - Background task detection for test runs

2. **Ruff Problem Matcher**
   - Captures linting errors and warnings
   - Shows file, line, column, severity, and message
   - Supports error codes (e.g., F401, E501)

### Background Tasks

Background tasks run continuously and detect when they're ready:

- **`Docs: Serve`**: Starts mkdocs server, detects when ready
- **`Mock Server: Start`**: Starts integration test server, detects startup

These tasks use `isBackground: true` with pattern matching to detect start/completion.

### Compound Tasks

Compound tasks orchestrate multiple tasks with `dependsOn`:

- **Sequential Execution**: Tasks run one after another with `dependsOrder: "sequence"`
- **Parallel Execution**: Tasks run simultaneously (default)

Example: `Workflow: Full Validation` runs all validation checks in sequence.

### Task Groups

Tasks are organized into groups:

- **`test`**: Testing tasks (default group for Ctrl+Shift+T)
- **`build`**: Build and validation tasks (default group for Ctrl+Shift+B)

## Debugging Configurations

### Quick Start Debugging

1. Open a Python file
2. Press `F5` to start debugging
3. Or use `Run and Debug` sidebar (Ctrl+Shift+D)

### Available Configurations

#### Main AIPerf Debugging
- **AIPerf: Debug Main Process** - Debug main CLI with single worker
- **AIPerf: Debug with Multiprocess (Workers)** - Debug with multiple workers
- **AIPerf: Debug Current File** - Debug currently open Python file
- **AIPerf: Debug System Controller** - Debug system controller module
- **AIPerf: Debug Worker Process** - Debug worker process module
- **AIPerf: Debug with Config File** - Debug using YAML config

#### Example Scripts
- **Example: Simple Benchmark** - Debug basic benchmark example
- **Example: Streaming Benchmark** - Debug streaming example
- **Example: Trace Replay** - Debug trace replay example

#### Testing
- **Pytest: Debug All Tests** - Debug all unit tests
- **Pytest: Debug Current File** - Debug tests in current file
- **Pytest: Debug Integration Tests** - Debug integration tests
- **Pytest: Debug Async Tests** - Debug async/await tests
- **Pytest: Debug with Coverage** - Debug tests with coverage
- **Pytest: Debug Single Test Function** - Debug specific test
- **Pytest: Debug Parallel Tests** - Debug parallel test execution

#### Performance Profiling
- **Profile: cProfile Current File** - Profile with cProfile
- **Profile: cProfile AIPerf Main** - Profile main AIPerf execution
- **Profile: Memory with tracemalloc** - Profile memory usage
- **Profile: Line Profiler** - Line-by-line profiling

#### Remote Debugging
- **Remote: Attach to Process** - Attach to running process
- **Remote: Attach to Docker Container** - Attach to containerized process
- **Remote: Attach to Worker Process** - Attach to specific worker

#### ZMQ Communication
- **ZMQ: Debug Communication Flow** - Debug inter-process communication
- **ZMQ: Debug Message Bus** - Debug message bus

#### Specialized Scenarios
- **Debug: Async Workflow** - Debug with async debugging enabled
- **Debug: Performance Bottleneck Investigation** - Debug performance issues
- **Debug: Critical Test Suite** - Debug critical behavioral tests

## Workspace Settings

### Python Configuration

- **Interpreter**: Uses `.venv/bin/python` from workspace
- **Testing**: pytest enabled, auto-discovery disabled
- **Formatting**: Ruff formatter with format-on-save

### Editor Configuration

- **Rulers**: 88 characters (matches Ruff line length)
- **Tab Size**: 4 spaces
- **Format on Save**: Enabled
- **Trim Whitespace**: Enabled

### File Exclusions

Hidden from file explorer:
- `__pycache__`, `*.pyc`
- `.pytest_cache`, `.ruff_cache`, `.mypy_cache`
- `htmlcov`, `.coverage`
- `site` (mkdocs output)

### Task Configuration

- **Auto-detect**: Enabled
- **Quick Open**: Shows task details and history
- **Problem Matchers**: Never prompt for python/ruff

## Recommended Extensions

### Essential Extensions

1. **Python** (`ms-python.python`) - Python language support
2. **Pylance** (`ms-python.vscode-pylance`) - Language server
3. **Ruff** (`charliermarsh.ruff`) - Fast linter and formatter
4. **Python Debugger** (`ms-python.debugpy`) - Debugging support

### Recommended Extensions

- **Coverage Gutters** - Visualize test coverage
- **Markdown All in One** - Markdown editing
- **GitLens** - Git integration
- **Docker** - Container management
- **YAML** - YAML language support
- **EditorConfig** - .editorconfig support

### Unwanted Extensions

The configuration explicitly avoids:
- `black-formatter` (conflicts with Ruff)
- `flake8` (replaced by Ruff)
- `pylint` (replaced by Ruff)
- `isort` (integrated in Ruff)

## Tips and Best Practices

### Task Tips

1. **Use Task Quick Open**: Press `Ctrl+Shift+P`, type "run task"
2. **Pin Frequent Tasks**: Add them to keybindings in `keybindings.json`
3. **Use Workflows**: Run compound tasks for common operations
4. **Background Tasks**: Use for long-running servers

### Debugging Tips

1. **Set Breakpoints**: Click in gutter or press `F9`
2. **Conditional Breakpoints**: Right-click breakpoint, add condition
3. **Log Points**: Add logging without modifying code
4. **Watch Expressions**: Monitor variable values
5. **Debug Console**: Execute code in debug context

### Testing Tips

1. **Run Current File**: Use `Test: Current File` task
2. **Fail Fast**: Use `Test: Fast (Fail Fast)` for quick feedback
3. **Verbose Mode**: Use verbose tasks for debugging test failures
4. **Coverage**: Run `Workflow: Test with Coverage` to check coverage

### Integration Testing

1. **Start Mock Server**: Run `Mock Server: Start` first
2. **Run Integration Tests**: Use `Test: Integration Tests`
3. **Or Use Workflow**: `Workflow: Integration Test Setup` does both

### Code Quality

1. **Format Before Commit**: Run `Format: Apply with Ruff`
2. **Fix Linting**: Run `Lint: Fix with Ruff`
3. **Quick Check**: Use `Workflow: Quick Validation`
4. **Full Check**: Use `Workflow: Full Validation` before PR

## Customization

### Adding Custom Tasks

Edit `.vscode/tasks.json`:

```json
{
    "label": "My Custom Task",
    "type": "shell",
    "command": ". .venv/bin/activate && my-command",
    "args": ["arg1", "arg2"],
    "options": {
        "cwd": "${workspaceFolder}"
    },
    "group": "test",
    "problemMatcher": "$python"
}
```

### Adding Custom Keybindings

Edit `.vscode/keybindings.json` (create if needed):

```json
[
    {
        "key": "ctrl+shift+u",
        "command": "workbench.action.tasks.runTask",
        "args": "Test: Unit Tests"
    }
]
```

### Modifying Problem Matchers

Problem matchers use regex to capture output:

```json
"problemMatcher": {
    "owner": "my-tool",
    "fileLocation": ["relative", "${workspaceFolder}"],
    "pattern": {
        "regexp": "^(.+):(\\d+):(\\d+):\\s+(.+)$",
        "file": 1,
        "line": 2,
        "column": 3,
        "message": 4
    }
}
```

## Troubleshooting

### Tasks Not Running

1. **Check Virtual Environment**: Ensure `.venv` exists
2. **Activate Environment**: Run `. .venv/bin/activate`
3. **Install Dependencies**: Run `Install: Project Dependencies` task

### Problem Matchers Not Working

1. **Check Output Format**: Ensure tool output matches pattern
2. **Test Regex**: Use regex tester with sample output
3. **Enable Debug**: Add `"showOutput": "always"` to task

### Background Tasks Not Stopping

1. **Use Stop Task**: Run corresponding "Stop" task
2. **Manual Kill**: Use `pkill` or process manager
3. **Check Processes**: Run `ps aux | grep <process>`

### Tests Not Found

1. **Check Test Path**: Ensure `testpaths` in pyproject.toml is correct
2. **Disable Auto-discovery**: Set in settings.json
3. **Run Discovery**: Press `Ctrl+Shift+P`, "Python: Discover Tests"

## Advanced Features

### Variable Substitution

Tasks support VS Code variables:

- `${workspaceFolder}` - Workspace root directory
- `${file}` - Current file path
- `${fileBasename}` - Current file name
- `${fileDirname}` - Current file directory
- `${input:variableName}` - User input variable

### Input Variables

Defined in `launch.json` for dynamic debugging:

```json
"inputs": [
    {
        "id": "testFunction",
        "type": "promptString",
        "description": "Test function name"
    }
]
```

### Presentation Options

Control task output panel:

```json
"presentation": {
    "echo": true,           // Show command being executed
    "reveal": "always",     // When to reveal panel
    "focus": false,         // Focus panel on execution
    "panel": "shared",      // Panel reuse strategy
    "showReuseMessage": true,
    "clear": false          // Clear previous output
}
```

### Conditional Tasks

Use `when` clauses for platform-specific tasks:

```json
{
    "label": "Linux Only Task",
    "type": "shell",
    "command": "...",
    "linux": {
        "command": "linux-specific-command"
    },
    "windows": {
        "command": "windows-specific-command"
    }
}
```

## Resources

- [VS Code Tasks Documentation](https://code.visualstudio.com/docs/editor/tasks)
- [VS Code Debugging](https://code.visualstudio.com/docs/editor/debugging)
- [Problem Matchers](https://code.visualstudio.com/docs/editor/tasks#_defining-a-problem-matcher)
- [AIPerf Documentation](https://aiperf.readthedocs.io/)
- [AIPerf Makefile Commands](../../MAKEFILE_COMMANDS.md)

## Contributing

When adding new tasks or debugging configurations:

1. Follow the existing naming conventions
2. Add appropriate problem matchers
3. Document in this README
4. Test on Linux, macOS, and Windows if possible
5. Consider adding to compound workflows

## License

Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
SPDX-License-Identifier: Apache-2.0
