# Chapter 38: Development Environment

<!--
# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
-->

## Overview

A well-configured development environment is essential for productive AIPerf development. This chapter covers everything from initial Python environment setup to IDE configuration, from pre-commit hooks to debugging tools, from profiling setup to Docker development containers.

Whether you are contributing to AIPerf core, developing custom metrics, or building extensions, this guide provides the complete development environment setup.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Python Environment Management](#python-environment-management)
3. [Installing AIPerf for Development](#installing-aiperf-for-development)
4. [Development Dependencies](#development-dependencies)
5. [Pre-Commit Hooks](#pre-commit-hooks)
6. [VS Code Setup](#vs-code-setup)
7. [PyCharm Setup](#pycharm-setup)
8. [Docker Development Container](#docker-development-container)
9. [Debugging Configuration](#debugging-configuration)
10. [Profiling Tools](#profiling-tools)
11. [Testing Environment](#testing-environment)
12. [Git Workflow](#git-workflow)
13. [Code Navigation](#code-navigation)
14. [Productivity Tools](#productivity-tools)
15. [Troubleshooting Setup](#troubleshooting-setup)
16. [Key Takeaways](#key-takeaways)

## Prerequisites

### System Requirements

**Operating System:**
- Linux (Ubuntu 20.04+, RHEL 8+, or similar)
- macOS 12+ (limited GPU support)
- Windows 10+ with WSL2 (for full functionality)

**Hardware:**
- CPU: 4+ cores recommended
- RAM: 16GB+ recommended (8GB minimum)
- Disk: 10GB+ free space
- GPU: Optional (NVIDIA GPU with CUDA for inference testing)

**Software:**
- Python 3.10 or 3.11 (3.12 not yet fully tested)
- Git 2.30+
- Optional: Docker 20.10+ for container development

### Verify Prerequisites

```bash
# Check Python version
python3 --version
# Expected: Python 3.10.x or 3.11.x

# Check Git version
git --version
# Expected: git version 2.30.0 or higher

# Check Docker (if using containers)
docker --version
# Expected: Docker version 20.10.0 or higher

# Check available disk space
df -h .
# Expected: At least 10GB free
```

## Python Environment Management

AIPerf supports multiple Python environment managers: venv, conda, and uv.

### Option 1: venv (Recommended)

Python's built-in virtual environment tool:

```bash
# Create virtual environment
python3 -m venv ~/.venv/aiperf

# Activate environment
source ~/.venv/aiperf/bin/activate

# Verify Python is from venv
which python
# Expected: /home/user/.venv/aiperf/bin/python

# Upgrade pip
pip install --upgrade pip setuptools wheel
```

**Pros:**
- Built into Python (no extra installation)
- Lightweight and fast
- Official Python recommendation

**Cons:**
- Python version must be pre-installed
- No built-in Python version management

### Option 2: conda

Conda provides both environment and Python version management:

```bash
# Create conda environment with Python 3.11
conda create -n aiperf python=3.11

# Activate environment
conda activate aiperf

# Verify Python version
python --version
# Expected: Python 3.11.x

# Update conda
conda update conda
```

**Pros:**
- Manages Python versions
- Handles complex dependencies well
- Good for data science workflows

**Cons:**
- Slower than venv
- Larger disk footprint
- Additional tool to install

### Option 3: uv (Modern Alternative)

uv is a fast Rust-based Python package installer:

```bash
# Install uv
curl -LsSf https://astral.sh/uv/install.sh | sh

# Create virtual environment
uv venv ~/.venv/aiperf

# Activate environment
source ~/.venv/aiperf/bin/activate

# Install packages with uv
uv pip install -e ".[dev]"
```

**Pros:**
- Extremely fast (10-100x faster than pip)
- Modern dependency resolution
- Compatible with pip

**Cons:**
- Relatively new tool
- Less mature ecosystem
- Requires separate installation

### Activation Scripts

Add to your `~/.bashrc` or `~/.zshrc`:

```bash
# Automatically activate AIPerf environment
alias aiperf-dev='source ~/.venv/aiperf/bin/activate && cd ~/projects/aiperf'

# Or with conda
alias aiperf-dev='conda activate aiperf && cd ~/projects/aiperf'
```

### Managing Multiple Environments

For working on multiple Python projects:

```bash
# Create project-specific environments
python3 -m venv ~/.venv/aiperf-main
python3 -m venv ~/.venv/aiperf-feature

# Use direnv for automatic activation (install direnv first)
echo 'source ~/.venv/aiperf-main/bin/activate' > .envrc
direnv allow
```

## Installing AIPerf for Development

Install AIPerf in editable mode to enable live code changes.

### Clone Repository

```bash
# Clone AIPerf repository
git clone https://github.com/NVIDIA/aiperf.git
cd aiperf

# Or if you have SSH keys configured
git clone git@github.com:NVIDIA/aiperf.git
cd aiperf
```

### Install in Editable Mode

```bash
# Activate your virtual environment first
source ~/.venv/aiperf/bin/activate

# Install AIPerf with development dependencies
pip install -e ".[dev]"

# Verify installation
aiperf --version

# Verify editable installation
pip show aiperf | grep Location
# Expected: Location: /path/to/your/cloned/aiperf
```

### What Editable Mode Means

With `pip install -e .`:
- Code changes take effect immediately (no reinstall needed)
- Python imports resolve to your local source directory
- You can debug directly into source code
- Great for rapid development iteration

### Development Dependencies

The `[dev]` extra installs these tools (from `/home/anthony/nvidia/projects/aiperf/pyproject.toml`):

```toml
[project.optional-dependencies]
dev = [
  "black>=25.1.0",          # Code formatter
  "mkinit>=1.1.0",          # __init__ file generator
  "pre-commit>=4.2.0",      # Git hook framework
  "pytest-asyncio",         # Async test support
  "pytest-cov",             # Coverage reporting
  "pytest>=7.0.0",          # Test framework
  "pytest-xdist>=3.8.0",    # Parallel testing
  "ruff>=0.0.0",            # Linter
  "scipy>=1.13.0",          # Scientific computing (for tests)
]
```

### Verify Installation

```bash
# Test basic functionality
aiperf profile --help

# Run a simple profile (requires a model server)
# aiperf profile -m gpt2 --max-workers 1

# Run tests
pytest tests/ -v
```

## Development Dependencies

Understanding the development toolchain:

### Black (Code Formatter)

From `/home/anthony/nvidia/projects/aiperf/pyproject.toml`:

```toml
black>=25.1.0
```

Black formats Python code automatically:

```bash
# Format all files
black aiperf/ tests/

# Check formatting without changes
black --check aiperf/ tests/

# Format specific file
black aiperf/workers/worker.py
```

**Configuration:**
- Line length: 88 characters (default)
- No additional configuration needed
- Enforced by pre-commit hooks

### Ruff (Linter)

From `/home/anthony/nvidia/projects/aiperf/pyproject.toml`:

```toml
[tool.ruff]
line-length = 88
indent-width = 4
exclude = ["__pycache__", "build", "dist", ".venv", "venv"]

[tool.ruff.lint]
select = [
    # pycodestyle (except E501)
    "E",
    # Pyflakes
    "F",
    # pyupgrade
    "UP",
    # flake8-bugbear
    "B",
    # flake8-simplify
    "SIM",
    # isort
    "I",
]
# Ignore line length errors, ruff format will handle this but
# can have some lines that are slightly over due to the way formatting works
ignore = ["E501"]
```

Ruff provides fast linting:

```bash
# Check all files
ruff check aiperf/ tests/

# Auto-fix issues
ruff check --fix aiperf/ tests/

# Format code (Black-compatible)
ruff format aiperf/ tests/
```

**Key Rules:**
- E: PEP 8 style errors
- F: Pyflakes errors (undefined names, unused imports)
- UP: Modern Python syntax (f-strings, type hints)
- B: Bug-prone patterns
- SIM: Code simplification opportunities
- I: Import ordering

### Pytest (Testing)

From `/home/anthony/nvidia/projects/aiperf/pyproject.toml`:

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "auto"
asyncio_default_fixture_loop_scope = "function"
```

Run tests:

```bash
# Run all tests
pytest tests/

# Run with coverage
pytest tests/ --cov=aiperf --cov-report=html

# Run specific test file
pytest tests/logging/test_aiperf_logger.py

# Run specific test
pytest tests/logging/test_aiperf_logger.py::TestAIPerfLogger::test_logger_initialization

# Run in parallel (faster)
pytest tests/ -n auto

# Run with verbose output
pytest tests/ -v

# Run with output capture disabled
pytest tests/ -s
```

### Pre-Commit (Git Hooks)

From `/home/anthony/nvidia/projects/aiperf/pyproject.toml`:

```toml
pre-commit>=4.2.0
```

Pre-commit runs checks before each commit.

### Mkinit (Init File Generator)

Automatically generates `__init__.py` files:

```bash
# Generate __init__ files for entire project
mkinit --recursive aiperf/
```

This is run automatically by pre-commit hooks.

## Pre-Commit Hooks

Pre-commit hooks enforce code quality before commits.

### Installation

```bash
# Install pre-commit hooks
pre-commit install

# Verify installation
pre-commit --version
```

### Configuration

From `/home/anthony/nvidia/projects/aiperf/.pre-commit-config.yaml`:

```yaml
repos:
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v5.0.0
    hooks:
      - id: check-added-large-files
        args: ['--maxkb=5000']
      - id: check-case-conflict
      - id: check-executables-have-shebangs
      - id: check-merge-conflict
      - id: check-json
        exclude: ^\.devcontainer/devcontainer\.json$
      - id: check-toml
      - id: check-yaml
      - id: check-shebang-scripts-are-executable
      - id: end-of-file-fixer
        types_or: [cuda, proto, textproto, python]
      - id: mixed-line-ending
      - id: no-commit-to-branch
        args: [--branch, main]
      - id: requirements-txt-fixer
      - id: trailing-whitespace

  - repo: https://github.com/codespell-project/codespell
    rev: v2.2.4
    hooks:
    - id: codespell
      additional_dependencies: [tomli]
      args: ["--toml", "pyproject.toml"]

  - repo: local
    hooks:
      - id: add-license
        name: add-license
        entry: python tools/add_copyright.py
        language: python
        require_serial: true
      - id: mkinit
        name: mkinit
        entry: bash tools/generate_init_files.sh
        language: system
        types: [python]
        pass_filenames: false

  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.11.8
    hooks:
      - id: ruff
        args: [--fix, --exit-non-zero-on-fix]
        types_or: [python, pyi]
      - id: ruff-format
        types_or: [python, pyi]
```

### Hook Execution

Pre-commit runs automatically on `git commit`:

```bash
# Make changes
vim aiperf/workers/worker.py

# Stage changes
git add aiperf/workers/worker.py

# Commit (hooks run automatically)
git commit -m "Fix worker initialization"

# Hooks will run:
# 1. Check for large files
# 2. Check for merge conflicts
# 3. Fix trailing whitespace
# 4. Add copyright headers
# 5. Run ruff linting and formatting
# 6. Generate __init__ files
```

### Manual Hook Execution

Run hooks manually:

```bash
# Run all hooks on all files
pre-commit run --all-files

# Run specific hook
pre-commit run ruff --all-files

# Run hooks on staged files only
pre-commit run

# Skip hooks (use sparingly)
git commit --no-verify -m "Emergency fix"
```

### Common Hook Failures

**Ruff formatting changes:**
```
ruff-format..........................................................Failed
- hook id: ruff-format
- files were modified by this hook

aiperf/workers/worker.py
```

**Solution:** Hook auto-fixed the file, re-add and commit:
```bash
git add aiperf/workers/worker.py
git commit -m "Fix worker initialization"
```

**Missing copyright header:**
```
add-license..........................................................Failed
- hook id: add-license

Added copyright header to: aiperf/workers/new_file.py
```

**Solution:** Hook added the header, re-add and commit:
```bash
git add aiperf/workers/new_file.py
git commit -m "Add new file"
```

**Direct commit to main:**
```
no-commit-to-branch..................................................Failed
- hook id: no-commit-to-branch
```

**Solution:** Create a feature branch:
```bash
git checkout -b feature/my-feature
git commit -m "Add feature"
```

## VS Code Setup

Visual Studio Code is a popular lightweight editor with excellent Python support.

### Install VS Code

```bash
# Ubuntu/Debian
sudo snap install code --classic

# Or download from https://code.visualstudio.com/
```

### Recommended Extensions

Install these extensions:

```bash
# Python extension pack
code --install-extension ms-python.python
code --install-extension ms-python.pylint
code --install-extension ms-python.vscode-pylance

# Ruff
code --install-extension charliermarsh.ruff

# Git
code --install-extension eamodio.gitlens

# YAML
code --install-extension redhat.vscode-yaml

# Docker
code --install-extension ms-azuretools.vscode-docker
```

### Workspace Settings

Create `.vscode/settings.json`:

```json
{
    "python.defaultInterpreterPath": "${workspaceFolder}/.venv/bin/python",
    "python.linting.enabled": true,
    "python.linting.pylintEnabled": true,
    "python.linting.ruffEnabled": true,
    "python.formatting.provider": "ruff",
    "editor.formatOnSave": true,
    "editor.codeActionsOnSave": {
        "source.organizeImports": true
    },
    "files.trimTrailingWhitespace": true,
    "files.insertFinalNewline": true,
    "[python]": {
        "editor.rulers": [88],
        "editor.tabSize": 4
    },
    "python.testing.pytestEnabled": true,
    "python.testing.pytestArgs": [
        "tests"
    ]
}
```

### Launch Configuration

From `/home/anthony/nvidia/projects/aiperf/.vscode/launch.json`:

```json
{
    "configurations": [
        {
            "name": "aiperf",
            "type": "debugpy",
            "request": "launch",
            "cwd": "${workspaceFolder}",
            "module": "aiperf.cli",
            "args": [
                "profile",
                "-m",
                "gpt2",
                "--log-level",
                "DEBUG",
                "--max-workers",
                "1"
            ]
        },
        {
            "name": "pytest",
            "type": "debugpy",
            "request": "launch",
            "cwd": "${workspaceFolder}",
            "module": "pytest",
            "args": [
                "-n",
                "auto"
            ]
        }
    ],
    "version": "0.2.0"
}
```

### Keyboard Shortcuts

Useful VS Code shortcuts:

- `Ctrl+Shift+P`: Command palette
- `Ctrl+P`: Quick file open
- `F5`: Start debugging
- `Shift+F5`: Stop debugging
- `F9`: Toggle breakpoint
- `F10`: Step over
- `F11`: Step into
- `Shift+F11`: Step out
- `Ctrl+/`: Toggle comment
- `Ctrl+Shift+F`: Search in files
- `Ctrl+Click`: Go to definition
- `Alt+F12`: Peek definition

### Python REPL

Open integrated terminal and run Python:

```bash
# Start Python REPL with AIPerf imported
python
>>> from aiperf.workers.worker import WorkerService
>>> help(WorkerService)
```

### Debugging Tips

**Set conditional breakpoints:**
Right-click breakpoint → Edit Breakpoint → Add condition:
```python
conversation_id == "specific-id"
```

**Watch expressions:**
Add variables to Watch panel to monitor values.

**Debug console:**
Execute Python expressions during debugging:
```python
len(self.requests)
vars(self)
```

## PyCharm Setup

PyCharm is a full-featured Python IDE from JetBrains.

### Install PyCharm

```bash
# Download PyCharm Professional or Community from:
# https://www.jetbrains.com/pycharm/download/

# Or use snap:
sudo snap install pycharm-community --classic
```

### Configure Python Interpreter

1. Open PyCharm
2. File → Settings → Project → Python Interpreter
3. Click gear icon → Add
4. Select "Virtualenv Environment"
5. Choose "Existing environment"
6. Browse to `~/.venv/aiperf/bin/python`
7. Click OK

### Enable Automatic Formatting

1. File → Settings → Tools → Actions on Save
2. Enable "Reformat code"
3. Enable "Optimize imports"
4. Enable "Run code cleanup"

### Configure Ruff

1. File → Settings → Tools → External Tools
2. Click + to add new tool
3. Name: "Ruff Check"
4. Program: `$ProjectFileDir$/.venv/bin/ruff`
5. Arguments: `check --fix $FilePath$`
6. Working directory: `$ProjectFileDir$`

### Run Configuration

Create run configurations:

**AIPerf Profile:**
1. Run → Edit Configurations
2. Click + → Python
3. Name: "AIPerf Profile"
4. Module: `aiperf.cli`
5. Parameters: `profile -m gpt2 --log-level DEBUG --max-workers 1`
6. Working directory: project root

**Pytest:**
1. Run → Edit Configurations
2. Click + → Python tests → pytest
3. Name: "All Tests"
4. Target: `tests/`
5. Options: `-n auto`

### Keyboard Shortcuts

Useful PyCharm shortcuts:

- `Shift+Shift`: Search everywhere
- `Ctrl+Shift+A`: Find action
- `Shift+F10`: Run
- `Shift+F9`: Debug
- `Ctrl+F8`: Toggle breakpoint
- `F7`: Step into
- `F8`: Step over
- `Shift+F8`: Step out
- `Ctrl+Alt+L`: Reformat code
- `Ctrl+B`: Go to declaration
- `Ctrl+Alt+B`: Go to implementation
- `Ctrl+Shift+F`: Find in files
- `Alt+Enter`: Show intention actions

### Remote Development

PyCharm Professional supports remote development:

1. Tools → Deployment → Configuration
2. Add SFTP server
3. Configure automatic upload on save
4. Run remotely with remote interpreter

## Docker Development Container

Docker containers provide consistent development environments.

### Container Configuration

From `/home/anthony/nvidia/projects/aiperf/.devcontainer/devcontainer.json`:

```json
{
    "name": "NVIDIA AIPerf Development",
    "remoteUser": "appuser",
    "updateRemoteUserUID": true,
    "build": {
        "dockerfile": "../Dockerfile",
        "context": ".",
        "target": "local-dev"
    },
    "runArgs": [
        "--gpus=all",
        "--network=host",
        "--ipc=host",
        "--cap-add=SYS_PTRACE",
        "--shm-size=10G",
        "--ulimit=memlock=-1",
        "--ulimit=stack=67108864",
        "--ulimit=nofile=65536:65536"
    ],
    "service": "aiperf",
    "customizations": {
        "vscode": {
            "extensions": [
                "ms-python.python",
                "ms-python.pylint",
                "ms-python.vscode-pylance",
                "charliermarsh.ruff",
                "eamodio.gitlens"
            ],
            "settings": {
                "terminal.integrated.defaultProfile.linux": "bash",
                "terminal.integrated.cwd": "/home/appuser/aiperf",
                "python.defaultInterpreterPath": "/home/appuser/.venv/bin/python",
                "python.linting.pylintEnabled": true,
                "python.linting.ruffEnabled": true,
                "python.formatting.provider": "ruff",
                "editor.formatOnSave": true,
                "editor.codeActionsOnSave": {
                    "source.organizeImports": true
                },
                "files.trimTrailingWhitespace": true,
                "files.insertFinalNewline": true
            }
        }
    },
    "workspaceFolder": "/home/appuser/aiperf",
    "workspaceMount": "source=${localWorkspaceFolder},target=/home/appuser/aiperf,type=bind,consistency=cached",
    "postCreateCommand": "/bin/bash /home/appuser/aiperf/.devcontainer/post-create.sh",
    "mounts": [
        "source=/tmp/,target=/tmp/,type=bind",
        "source=appuser-aiperf-bashhistory,target=/home/appuser/.commandhistory,type=volume",
        "source=appuser-aiperf-precommit-cache,target=/home/appuser/.cache/pre-commit,type=volume",
        "source=appuser-aiperf-venv,target=/home/appuser/.venv,type=volume"
    ]
}
```

### Using Dev Containers in VS Code

1. Install "Remote - Containers" extension
2. Open AIPerf folder in VS Code
3. Press `Ctrl+Shift+P`
4. Select "Remote-Containers: Reopen in Container"
5. Wait for container build and initialization
6. Development environment is ready

### Benefits of Dev Containers

- Consistent environment across team members
- GPU support configured automatically
- All dependencies pre-installed
- Isolated from host system
- Reproducible builds

### Manual Docker Development

Without VS Code dev containers:

```bash
# Build dev container
docker build -f Dockerfile --target local-dev -t aiperf-dev .

# Run container
docker run -it --gpus=all \
  --network=host \
  --ipc=host \
  -v $(pwd):/workspace \
  -v aiperf-venv:/home/appuser/.venv \
  aiperf-dev bash

# Inside container
cd /workspace
source /home/appuser/.venv/bin/activate
pip install -e ".[dev]"
pytest tests/
```

## Debugging Configuration

Effective debugging setup for multiprocess applications.

### Debugging Single Process

From `.vscode/launch.json`:

```json
{
    "name": "aiperf",
    "type": "debugpy",
    "request": "launch",
    "cwd": "${workspaceFolder}",
    "module": "aiperf.cli",
    "args": [
        "profile",
        "-m",
        "gpt2",
        "--log-level",
        "DEBUG",
        "--max-workers",
        "1"
    ]
}
```

**Key Settings:**
- `--max-workers 1`: Single worker for easier debugging
- `--log-level DEBUG`: Verbose output
- Module mode: Runs via `python -m aiperf.cli`

### Debugging Multiprocess

Debugging multiprocess applications is challenging. Strategies:

**1. Single Worker Mode:**
```bash
aiperf profile -m gpt2 --max-workers 1 --log-level DEBUG
```

**2. Service-Specific Logging:**
```bash
aiperf profile -m gpt2 --trace-services worker --log-level INFO
```

**3. Attach to Child Process (Advanced):**

Add to worker initialization:

```python
import debugpy
debugpy.listen(("localhost", 5678 + worker_id))
print(f"Worker {worker_id} waiting for debugger on port {5678 + worker_id}")
debugpy.wait_for_client()
```

Then attach VS Code to specific port.

### Debugging Tests

From `.vscode/launch.json`:

```json
{
    "name": "pytest",
    "type": "debugpy",
    "request": "launch",
    "cwd": "${workspaceFolder}",
    "module": "pytest",
    "args": [
        "tests/logging/test_aiperf_logger.py::TestAIPerfLogger::test_logger_initialization",
        "-v",
        "-s"
    ]
}
```

**Key Settings:**
- Specific test path for focused debugging
- `-v`: Verbose output
- `-s`: Disable output capture (see print statements)

### Conditional Breakpoints

Set breakpoints that only trigger on conditions:

```python
# Break only for specific conversation
if conversation_id == "conv_123":
    pass  # Set breakpoint here

# Break only on errors
try:
    risky_operation()
except Exception as e:
    pass  # Set breakpoint here
```

Or use conditional breakpoint feature in IDE:
```python
conversation_id == "conv_123"
len(self.requests) > 1000
error is not None
```

### Post-Mortem Debugging

Debug crashes with pdb:

```python
import sys
import pdb

def main():
    try:
        run_benchmark()
    except Exception:
        pdb.post_mortem(sys.exc_info()[2])

if __name__ == "__main__":
    main()
```

## Profiling Tools

Performance profiling identifies bottlenecks.

### Yappi (CPU Profiling)

Install yappi:

```bash
pip install yappi
```

Profile AIPerf:

```python
import yappi

yappi.start()

# Run benchmark
run_aiperf_benchmark()

yappi.stop()

# Print stats
yappi.get_func_stats().print_all()

# Save to file
yappi.get_func_stats().save("profile.yappi", type="callgrind")
```

View with kcachegrind:

```bash
pip install qcachegrind
qcachegrind profile.yappi
```

### cProfile (Standard Library)

Built-in Python profiler:

```bash
python -m cProfile -o profile.prof -m aiperf.cli profile -m gpt2

# Analyze results
python -m pstats profile.prof
>>> sort time
>>> stats 20
```

### py-spy (Sampling Profiler)

Non-intrusive profiler:

```bash
# Install py-spy
pip install py-spy

# Profile running process
py-spy top --pid <aiperf_pid>

# Record and generate flamegraph
py-spy record -o profile.svg --pid <aiperf_pid>

# Profile command
py-spy record -o profile.svg -- aiperf profile -m gpt2
```

### Memory Profiling with memory_profiler

```bash
pip install memory_profiler

# Add @profile decorator to functions
@profile
def memory_intensive_function():
    large_list = [0] * 10000000
    return sum(large_list)

# Run with memory profiler
python -m memory_profiler aiperf/script.py
```

### Profiling Tests

Profile specific tests:

```bash
pytest tests/metrics/test_ttft_metric.py --profile

# Or with pytest-profiling
pip install pytest-profiling
pytest tests/ --profile-svg
```

## Testing Environment

Running and managing tests effectively.

### Running Tests

From `/home/anthony/nvidia/projects/aiperf/pyproject.toml`:

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "auto"
asyncio_default_fixture_loop_scope = "function"
```

Basic test execution:

```bash
# Run all tests
pytest tests/

# Run specific test file
pytest tests/logging/test_aiperf_logger.py

# Run specific test
pytest tests/logging/test_aiperf_logger.py::TestAIPerfLogger::test_logger_initialization

# Run tests matching pattern
pytest tests/ -k "test_logger"

# Run with verbose output
pytest tests/ -v

# Run with output capture disabled
pytest tests/ -s
```

### Parallel Testing

Speed up tests with xdist:

```bash
# Run with automatic worker count
pytest tests/ -n auto

# Run with specific worker count
pytest tests/ -n 4

# Distribute by file
pytest tests/ -n auto --dist=loadfile
```

### Coverage Testing

Generate coverage reports:

```bash
# Run with coverage
pytest tests/ --cov=aiperf

# Generate HTML report
pytest tests/ --cov=aiperf --cov-report=html

# Open report
open htmlcov/index.html

# Show missing lines
pytest tests/ --cov=aiperf --cov-report=term-missing
```

### Test Markers

AIPerf uses custom markers (from `/home/anthony/nvidia/projects/aiperf/tests/conftest.py`):

```python
@pytest.mark.performance
def test_performance():
    """Performance test (disabled by default)."""
    pass

@pytest.mark.integration
def test_integration():
    """Integration test (disabled by default)."""
    pass
```

Run marked tests:

```bash
# Run performance tests
pytest tests/ --performance

# Run integration tests
pytest tests/ --integration

# Run both
pytest tests/ --performance --integration
```

### Test Output

Control test output:

```bash
# Minimal output
pytest tests/ -q

# Verbose output
pytest tests/ -v

# Very verbose output
pytest tests/ -vv

# Show local variables on failure
pytest tests/ -l

# Show print statements
pytest tests/ -s

# Stop on first failure
pytest tests/ -x

# Drop into debugger on failure
pytest tests/ --pdb
```

## Git Workflow

Effective Git workflow for AIPerf development.

### Branch Naming

Follow naming conventions:

```bash
# Feature branches
git checkout -b feature/add-custom-metric
git checkout -b feature/improve-logging

# Bug fix branches
git checkout -b fix/queue-overflow
git checkout -b fix/worker-crash

# Documentation branches
git checkout -b docs/update-readme
git checkout -b docs/add-examples
```

### Commit Messages

Write clear commit messages:

```bash
# Good commit messages
git commit -m "feat: Add support for custom metrics registration"
git commit -m "fix: Resolve queue overflow in multiprocess logging"
git commit -m "docs: Update installation instructions for Python 3.11"
git commit -m "refactor: Simplify worker initialization logic"
git commit -m "test: Add coverage for credit system edge cases"

# Bad commit messages (avoid these)
git commit -m "fix"
git commit -m "update"
git commit -m "changes"
```

### Pre-Push Checks

Before pushing:

```bash
# Run all pre-commit hooks
pre-commit run --all-files

# Run tests
pytest tests/

# Check formatting
ruff check aiperf/ tests/

# Verify build
pip install -e .
aiperf --version
```

### Pull Request Workflow

1. Create feature branch
2. Make changes with good commits
3. Run pre-commit hooks and tests
4. Push to your fork
5. Create pull request
6. Address review feedback
7. Merge after approval

### Useful Git Commands

```bash
# View commit history
git log --oneline --graph --all

# Show changes
git diff
git diff --staged

# Interactive rebase (clean up commits)
git rebase -i HEAD~3

# Stash changes
git stash
git stash pop

# Amend last commit
git commit --amend

# Cherry-pick commit
git cherry-pick <commit-hash>

# Reset to remote
git fetch origin
git reset --hard origin/main
```

## Code Navigation

Efficiently navigate the AIPerf codebase.

### Project Structure

```
aiperf/
├── aiperf/
│   ├── cli/                    # CLI entry points
│   ├── workers/                # Worker services
│   ├── controller/             # System controller
│   ├── clients/                # HTTP/OpenAI clients
│   ├── metrics/                # Metric implementations
│   ├── common/                 # Shared utilities
│   │   ├── config/            # Configuration
│   │   ├── logging.py         # Log management
│   │   ├── messages/          # Message types
│   │   └── mixins/            # Reusable mixins
│   ├── ui/                     # Dashboard UI
│   └── exporters/             # Data exporters
├── tests/                      # Test suite
├── docs/                       # Documentation
└── tools/                      # Development tools
```

### Find Files

```bash
# Find Python files
find aiperf/ -name "*.py"

# Find test files
find tests/ -name "test_*.py"

# Find files containing text
grep -r "AIPerfLogger" aiperf/

# Find files by pattern
fd "worker" aiperf/
```

### IDE Navigation

**VS Code:**
- `Ctrl+P`: Quick file open
- `Ctrl+T`: Symbol search
- `Ctrl+Shift+F`: Search in files
- `Ctrl+Click`: Go to definition
- `Alt+F12`: Peek definition
- `F12`: Go to definition
- `Shift+F12`: Find all references

**PyCharm:**
- `Shift+Shift`: Search everywhere
- `Ctrl+N`: Go to class
- `Ctrl+Shift+N`: Go to file
- `Ctrl+Alt+Shift+N`: Go to symbol
- `Ctrl+B`: Go to declaration
- `Ctrl+Alt+B`: Go to implementation
- `Ctrl+Alt+F7`: Find usages

### Code Structure Understanding

**Read in this order:**
1. `aiperf/__init__.py` - Entry point
2. `aiperf/cli/` - CLI commands
3. `aiperf/controller/system_controller.py` - Main controller
4. `aiperf/workers/worker.py` - Worker implementation
5. `aiperf/common/config/` - Configuration system
6. `aiperf/metrics/` - Metrics implementation

## Productivity Tools

Tools to boost development productivity.

### Command-Line Tools

```bash
# ripgrep (faster grep)
rg "AIPerfLogger" aiperf/

# fd (faster find)
fd "worker" aiperf/

# bat (better cat)
bat aiperf/workers/worker.py

# exa (better ls)
exa -lah aiperf/

# hyperfine (benchmarking)
hyperfine "pytest tests/logging/"

# jq (JSON processing)
cat results.json | jq '.metrics[] | select(.tag == "ttft")'
```

### VS Code Extensions

Additional useful extensions:

- **Python Docstring Generator**: Auto-generate docstrings
- **Python Test Explorer**: Visual test running
- **GitLens**: Enhanced Git integration
- **Error Lens**: Inline error display
- **Todo Tree**: Track TODO comments
- **Bracket Pair Colorizer**: Visualize bracket pairs

### Shell Aliases

Add to `~/.bashrc`:

```bash
# AIPerf development aliases
alias ap-dev='cd ~/projects/aiperf && source .venv/bin/activate'
alias ap-test='pytest tests/ -n auto'
alias ap-cov='pytest tests/ --cov=aiperf --cov-report=html'
alias ap-fmt='ruff format aiperf/ tests/ && ruff check --fix aiperf/ tests/'
alias ap-lint='ruff check aiperf/ tests/'
alias ap-profile='aiperf profile -m gpt2 --log-level DEBUG --max-workers 1'
```

### tmux/screen for Remote Development

```bash
# Start tmux session
tmux new -s aiperf-dev

# Split panes
Ctrl+b %  # vertical split
Ctrl+b "  # horizontal split

# Navigate panes
Ctrl+b arrow-keys

# Detach
Ctrl+b d

# Reattach
tmux attach -t aiperf-dev

# Multiple windows
Ctrl+b c  # create window
Ctrl+b n  # next window
Ctrl+b p  # previous window
```

## Troubleshooting Setup

Common development environment issues.

### ImportError: No module named 'aiperf'

**Cause:** AIPerf not installed or wrong Python environment.

**Solution:**
```bash
# Verify Python path
which python

# Verify virtual environment
echo $VIRTUAL_ENV

# Reinstall in editable mode
pip install -e ".[dev]"

# Verify installation
pip show aiperf
```

### Pre-commit hooks not running

**Cause:** Hooks not installed.

**Solution:**
```bash
# Install hooks
pre-commit install

# Verify installation
ls .git/hooks/pre-commit

# Test hooks
pre-commit run --all-files
```

### Tests failing with import errors

**Cause:** Missing test dependencies.

**Solution:**
```bash
# Install dev dependencies
pip install -e ".[dev]"

# Verify pytest installation
pytest --version

# Check installed packages
pip list
```

### Debugger not stopping at breakpoints

**Cause:** Wrong Python interpreter in IDE.

**Solution:**
- VS Code: Select correct interpreter (`Ctrl+Shift+P` → "Python: Select Interpreter")
- PyCharm: File → Settings → Project → Python Interpreter
- Verify: `which python` in IDE terminal should match venv

### Ruff/Black conflicts

**Cause:** Conflicting formatting tools.

**Solution:**
```bash
# Use Ruff for both linting and formatting
ruff format aiperf/ tests/
ruff check --fix aiperf/ tests/

# Remove Black from workflow
pip uninstall black

# Update settings.json
"python.formatting.provider": "ruff"
```

### Docker container build failures

**Cause:** Network issues, missing dependencies, or caching problems.

**Solution:**
```bash
# Clear Docker cache
docker system prune -a

# Build with no cache
docker build --no-cache -f Dockerfile --target local-dev -t aiperf-dev .

# Check build logs
docker build -f Dockerfile --target local-dev -t aiperf-dev . 2>&1 | tee build.log
```

### Permission errors on Linux

**Cause:** File ownership mismatch in Docker or virtual environment.

**Solution:**
```bash
# Fix ownership
sudo chown -R $USER:$USER ~/projects/aiperf

# Fix venv permissions
chmod -R u+w ~/.venv/aiperf
```

## Key Takeaways

1. **Use Python 3.10 or 3.11** for AIPerf development, with virtual environments (venv, conda, or uv) for isolation.

2. **Install AIPerf in editable mode** (`pip install -e ".[dev]"`) to enable live code changes without reinstallation.

3. **Pre-commit hooks enforce code quality** automatically, running ruff, adding copyright headers, and checking for common issues before each commit.

4. **VS Code and PyCharm** are both well-supported with launch configurations, test integration, and debugging support for AIPerf.

5. **Docker dev containers provide consistent environments** across team members, with GPU support and all dependencies pre-configured.

6. **Debug multiprocess applications** by using single worker mode (`--max-workers 1`) or service-specific logging (`--trace-services worker`).

7. **Profile performance with yappi, cProfile, or py-spy** to identify bottlenecks in CPU-intensive code paths.

8. **Run tests in parallel with pytest-xdist** (`pytest tests/ -n auto`) to speed up test execution significantly.

9. **Use coverage reporting** (`pytest tests/ --cov=aiperf --cov-report=html`) to ensure comprehensive test coverage.

10. **Follow Git workflow best practices**: feature branches, descriptive commit messages, pre-push checks, and pull request reviews.

11. **Navigate code efficiently** with IDE shortcuts, file search tools (fd, ripgrep), and understanding the project structure.

12. **Shell aliases and tmux** boost productivity for common development tasks and remote development workflows.

13. **Ruff provides both linting and formatting**, replacing multiple tools (Black, isort, Flake8) with a single fast tool.

14. **The .vscode/launch.json and .devcontainer/devcontainer.json files** provide ready-to-use configurations for debugging and containerized development.

15. **Troubleshooting setup issues** usually involves verifying the Python environment, checking installations, and ensuring correct IDE configuration.

---

[Previous: Chapter 37 - Log Management](chapter-37-log-management.md) | [Index](INDEX.md) | [Next: Chapter 39 - Code Style Guide](chapter-39-code-style-guide.md)
