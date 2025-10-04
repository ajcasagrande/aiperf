<!--
# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
-->
# Contributing to AIPerf

Thank you for your interest in contributing to AIPerf! This document provides guidelines and best practices for contributing to the project.

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Process](#development-process)
- [Code Standards](#code-standards)
- [Testing Requirements](#testing-requirements)
- [Documentation](#documentation)
- [Submitting Changes](#submitting-changes)
- [Review Process](#review-process)

## Code of Conduct

We are committed to providing a welcoming and inclusive environment. Please be respectful and professional in all interactions.

## Getting Started

### Prerequisites

- Python 3.10 or higher
- Git
- Basic understanding of async Python
- Familiarity with AI inference concepts

### Development Setup

```bash
# Clone the repository
git clone https://github.com/ai-dynamo/aiperf.git
cd aiperf

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install in editable mode with development dependencies
pip install -e ".[dev]"

# Install pre-commit hooks
pre-commit install

# Verify installation
pytest tests/ --maxfail=1
```

### Understanding the Codebase

Before contributing, please read:

1. **[CLAUDE.md](CLAUDE.md)** - Core development principles and patterns (15 min read)
2. **[Developer's Guidebook](guidebook/INDEX.md)** - Comprehensive technical reference
   - Start with Chapters 1-5 for architecture overview
   - Read subsystem chapters relevant to your work
3. **[Examples](examples/README.md)** - Working code examples

## Development Process

### 1. Find or Create an Issue

- Check [existing issues](https://github.com/ai-dynamo/aiperf/issues)
- For new features, create an issue first to discuss approach
- Reference issue number in commits and PRs

### 2. Create a Branch

```bash
# Create feature branch from main
git checkout main
git pull origin main
git checkout -b feature/your-feature-name

# Or for bug fixes
git checkout -b fix/issue-number-description
```

Branch naming:
- `feature/` - New features
- `fix/` - Bug fixes
- `docs/` - Documentation only
- `refactor/` - Code refactoring
- `test/` - Test improvements

### 3. Make Changes

Follow the guidelines in this document and [CLAUDE.md](CLAUDE.md).

### 4. Test Your Changes

```bash
# Run affected tests
pytest tests/path/to/relevant/tests/ -v

# Run all tests
pytest tests/

# Check coverage
pytest tests/ --cov=aiperf --cov-report=term-missing

# Coverage should not decrease
pytest tests/ --cov=aiperf --cov-fail-under=80
```

### 5. Commit Your Changes

Follow [Conventional Commits](https://www.conventionalcommits.org/):

```bash
# Format: <type>(<scope>): <description>

git commit -m "feat(metrics): add custom percentile metric"
git commit -m "fix(workers): prevent credit leak on error"
git commit -m "docs(guidebook): update metrics chapter"
git commit -m "test(dataset): add multi-turn loader tests"
git commit -m "refactor(zmq): simplify proxy configuration"
```

Types:
- `feat` - New feature
- `fix` - Bug fix
- `docs` - Documentation only
- `test` - Test changes
- `refactor` - Code refactoring
- `perf` - Performance improvement
- `style` - Code style changes
- `chore` - Maintenance tasks

### 6. Push and Create PR

```bash
git push origin feature/your-feature-name
```

Then create a Pull Request on GitHub.

## Code Standards

### Follow AIPerf Principles

Read [CLAUDE.md](CLAUDE.md) for detailed guidance. Key principles:

1. **Every line of code is a liability** - Only add code that solves real problems
2. **Simplicity over cleverness** - Prefer obvious solutions
3. **Type safety** - Use type hints everywhere
4. **Async/await** - No blocking operations
5. **DRY, KISS, SOLID** - Follow established patterns

### Python Style

AIPerf follows PEP 8 with these tools:

**Black** (formatting):
```bash
black aiperf/ tests/
```
- Line length: 88 characters
- Runs automatically via pre-commit

**Ruff** (linting):
```bash
ruff check aiperf/ tests/
```
- Checks: E (pycodestyle), F (pyflakes), UP (pyupgrade), B (bugbear), SIM (simplify), I (isort)
- Runs automatically via pre-commit

**Configuration**: See `pyproject.toml`

### Type Hints

Type hints are required for all public APIs:

```python
# Good
def process_record(record: ParsedResponseRecord) -> MetricRecordDict:
    ...

# Bad
def process_record(record):
    ...
```

Use modern syntax (Python 3.10+):
```python
# Good
def get_value(x: int | None) -> str:
    ...

# Avoid (old style)
from typing import Optional, Union
def get_value(x: Optional[int]) -> str:
    ...
```

### Docstrings

Use Google-style docstrings for public APIs:

```python
def process_request(
    self,
    request: RequestRecord,
    timeout: float = 30.0,
) -> ProcessedRecord:
    """Process a single request record.

    Args:
        request: The request record to process
        timeout: Maximum time to wait for response in seconds

    Returns:
        Processed record with parsed responses

    Raises:
        ValueError: If request is invalid
        TimeoutError: If request exceeds timeout
    """
```

### Imports

Organized by isort (runs via pre-commit):

```python
# Standard library
import asyncio
import sys
from pathlib import Path

# Third-party
import numpy as np
from pydantic import Field

# Local imports
from aiperf.common.config import UserConfig
from aiperf.metrics import BaseRecordMetric
```

### Async/Await

Always use async/await, never blocking operations:

```python
# Good
async def fetch_data(self):
    await asyncio.sleep(1)
    async with aiohttp.ClientSession() as session:
        return await session.get(url)

# Bad
async def fetch_data(self):
    time.sleep(1)  # Blocks event loop!
    return requests.get(url)  # Blocking I/O!
```

### Error Handling

Be explicit and informative:

```python
# Good
try:
    result = await operation()
except ValueError as e:
    logger.error(f"Invalid configuration: {e}")
    raise
except Exception as e:
    logger.exception("Unexpected error in operation")
    raise ServiceError("Operation failed") from e

# Bad
try:
    result = await operation()
except:  # Bare except!
    pass  # Silently fails!
```

## Testing Requirements

### Test Coverage

- New code must include tests
- Coverage should not decrease
- Aim for >90% coverage on new code
- Integration tests for complex features

### Test Structure

```python
# File: tests/metrics/test_my_metric.py

import pytest
from aiperf.metrics.types.my_metric import MyMetric

class TestMyMetric:
    """Test suite for MyMetric."""

    def test_basic_computation(self):
        """Test basic metric computation."""
        record = create_test_record(...)
        metric = MyMetric()

        result = metric.parse_record(record, MetricRecordDict())

        assert result == expected_value

    def test_missing_data(self):
        """Test metric handles missing data correctly."""
        record = create_test_record(responses=[])
        metric = MyMetric()

        with pytest.raises(NoMetricValue):
            metric.parse_record(record, MetricRecordDict())

    @pytest.mark.parametrize("input,expected", [
        (10, 20),
        (20, 40),
        (30, 60),
    ])
    def test_parametrized(self, input, expected):
        """Test various input values."""
        assert compute(input) == expected
```

### Running Tests

```bash
# Run all tests
pytest tests/

# Run specific test file
pytest tests/metrics/test_my_metric.py

# Run with coverage
pytest tests/ --cov=aiperf --cov-report=html

# Run in parallel (faster)
pytest tests/ -n auto

# Run only failed tests from last run
pytest tests/ --lf
```

### Test Fixtures

Use `conftest.py` for shared fixtures:

```python
# tests/conftest.py or tests/metrics/conftest.py

@pytest.fixture
def user_config():
    """Standard user config for tests."""
    return UserConfig(
        endpoint=EndpointConfig(...),
        loadgen=LoadGeneratorConfig(...),
    )
```

## Documentation

### Code Documentation

- Public APIs require docstrings
- Use Google-style format
- Include examples for complex functions
- Explain why, not just what

### Updating Guidebook

If your changes affect architecture or usage:

1. Update relevant guidebook chapter(s)
2. Update examples if needed
3. Update CLAUDE.md if patterns change

### Comments

Explain WHY, not WHAT:

```python
# Good: Explains reasoning
# Acquire semaphore before recv to enable ZMQ load balancing
await self.semaphore.acquire()

# Bad: States the obvious
# Acquire the semaphore
await self.semaphore.acquire()
```

## Submitting Changes

### Before Submitting

Pre-commit hooks will run automatically, but you can run manually:

```bash
# Run all pre-commit checks
pre-commit run --all-files

# Or run specific checks
black aiperf/ tests/
ruff check aiperf/ tests/
pytest tests/
```

### Pull Request Guidelines

**PR Title**: Follow conventional commits format
```
feat(workers): add connection retry logic
fix(metrics): correct TTFT calculation for multi-turn
docs(guidebook): add custom dataset chapter
```

**PR Description**: Include:
- Summary of changes
- Related issue number(s)
- Testing performed
- Breaking changes (if any)
- Screenshots (for UI changes)

**PR Template**:
```markdown
## Summary
Brief description of changes

## Related Issues
Fixes #123
Related to #456

## Changes
- Added feature X
- Fixed bug in Y
- Updated documentation for Z

## Testing
- [ ] Unit tests added/updated
- [ ] Integration tests added/updated
- [ ] All tests pass locally
- [ ] Coverage maintained or improved

## Checklist
- [ ] Code follows style guidelines
- [ ] Documentation updated
- [ ] Tests added
- [ ] Pre-commit hooks pass
- [ ] No breaking changes (or documented)
```

### Commit Message Guidelines

Good commit message:
```
feat(metrics): add thinking efficiency metric

Add new metric to compute ratio of reasoning tokens to output tokens.
Useful for evaluating reasoning model efficiency.

- Add ThinkingEfficiencyMetric class
- Add unit tests
- Update metrics guidebook chapter
- Add example to custom-metrics/
```

Bad commit message:
```
fixed stuff
```

## Review Process

### What Reviewers Look For

1. **Correctness**: Does it work as intended?
2. **Tests**: Adequate test coverage?
3. **Documentation**: Is it documented?
4. **Style**: Follows code standards?
5. **Architecture**: Fits with existing design?
6. **Performance**: No regressions?
7. **Simplicity**: Is this the simplest solution?

### Responding to Feedback

- Be responsive to review comments
- Ask questions if feedback is unclear
- Make requested changes promptly
- Mark conversations as resolved when addressed

### Approval Requirements

- At least one maintainer approval
- All CI checks passing
- No unresolved review comments
- Up-to-date with main branch

## Specific Contribution Guides

### Adding a New Metric

See [guidebook/chapter-44-custom-metrics-development.md](guidebook/chapter-44-custom-metrics-development.md) and [examples/custom-metrics/](examples/custom-metrics/).

**Quick steps**:
1. Create `aiperf/metrics/types/my_metric.py`
2. Inherit from `BaseRecordMetric`, `BaseAggregateMetric`, or `BaseDerivedMetric`
3. Set `tag`, `header`, `unit`, `flags`
4. Implement `_parse_record()` or `_derive_value()`
5. Add tests in `tests/metrics/test_my_metric.py`
6. Update guidebook if significant

### Adding a New Dataset Type

See [guidebook/chapter-45-custom-dataset-development.md](guidebook/chapter-45-custom-dataset-development.md) and [examples/custom-datasets/](examples/custom-datasets/).

**Quick steps**:
1. Create model in `aiperf/dataset/loader/models.py`
2. Create loader in `aiperf/dataset/loader/my_loader.py`
3. Register with `@CustomDatasetFactory.register()`
4. Implement `load_dataset()` and `convert_to_conversations()`
5. Add tests in `tests/dataset/test_my_loader.py`

### Adding a New Configuration Option

See [guidebook/chapter-29-configuration-architecture.md](guidebook/chapter-29-configuration-architecture.md).

**Quick steps**:
1. Add field to config class with `Field()` and `CLIParameter()`
2. Add default to defaults class
3. Add validator if needed
4. Update tests in `tests/config/`
5. Update guidebook if user-facing

### Reporting Bugs

Use the [issue tracker](https://github.com/ai-dynamo/aiperf/issues) with:

- AIPerf version
- Python version
- Operating system
- Complete error message
- Minimal reproduction steps
- Expected vs actual behavior

## Resources

### Documentation
- [Developer's Guidebook](guidebook/INDEX.md) - Complete technical reference
- [CLAUDE.md](CLAUDE.md) - Quick development guide
- [Examples](examples/README.md) - Working code examples

### Community
- [GitHub Discussions](https://github.com/ai-dynamo/aiperf/discussions) - Questions and discussions
- [Discord Server](https://discord.gg/D92uqZRjCZ) - Real-time chat
- [Issue Tracker](https://github.com/ai-dynamo/aiperf/issues) - Bugs and features

### Architecture References
- [Architecture Overview](docs/architecture.md) - High-level design
- [Metrics Flow](docs/diagrams/metrics-flow.md) - Metrics pipeline
- [Mixins](docs/diagrams/mixins.md) - Mixin architecture

## License

By contributing, you agree that your contributions will be licensed under the Apache 2.0 License.

## Questions?

If you have questions:
1. Check the [guidebook](guidebook/INDEX.md)
2. Search [existing issues](https://github.com/ai-dynamo/aiperf/issues)
3. Ask in [Discord](https://discord.gg/D92uqZRjCZ)
4. Open a [discussion](https://github.com/ai-dynamo/aiperf/discussions)

## Thank You

Your contributions help make AIPerf better for everyone. We appreciate your time and effort!
