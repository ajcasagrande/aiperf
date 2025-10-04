# Chapter 39: Code Style Guide

## Overview

Consistent code style is essential for maintaining a large, collaborative codebase like AIPerf. This chapter documents the comprehensive code style guide that governs all AIPerf code, from PEP 8 compliance and 88-character line lengths to type hints, docstring standards, and async/await conventions.

Following these guidelines ensures code is readable, maintainable, and consistent across the entire project.

## Table of Contents

1. [Philosophy and Principles](#philosophy-and-principles)
2. [PEP 8 Compliance](#pep-8-compliance)
3. [Black Formatting](#black-formatting)
4. [Ruff Linting Rules](#ruff-linting-rules)
5. [Import Organization](#import-organization)
6. [Type Hints](#type-hints)
7. [Naming Conventions](#naming-conventions)
8. [Docstring Standards](#docstring-standards)
9. [Comment Guidelines](#comment-guidelines)
10. [Async/Await Conventions](#asyncawait-conventions)
11. [Error Handling Patterns](#error-handling-patterns)
12. [Logging Conventions](#logging-conventions)
13. [File Organization](#file-organization)
14. [Module Structure](#module-structure)
15. [Code Review Checklist](#code-review-checklist)
16. [Anti-Patterns to Avoid](#anti-patterns-to-avoid)
17. [Key Takeaways](#key-takeaways)

## Philosophy and Principles

### Core Principles

1. **Readability Counts**: Code is read far more often than it is written.
2. **Explicit is Better Than Implicit**: Clear code trumps clever code.
3. **Consistency is Key**: Follow existing patterns in the codebase.
4. **Simplicity Over Complexity**: Choose simple solutions when possible.
5. **Practicality Beats Purity**: Pragmatic decisions are acceptable when justified.

### The Zen of AIPerf

```python
# Beautiful is better than ugly
async def process_request(self, request: Request) -> Response:
    """Process a single request and return response."""
    result = await self.client.post_request(request)
    return result

# Not:
async def process_request(self,request:Request)->Response:result=await self.client.post_request(request);return result

# Explicit is better than implicit
from aiperf.common.aiperf_logger import AIPerfLogger
logger = AIPerfLogger(__name__)

# Not:
from aiperf.common.aiperf_logger import *

# Simple is better than complex
if request.is_valid:
    process(request)

# Not:
process(request) if hasattr(request, 'is_valid') and request.is_valid else None

# Readability counts
worker_count = config.max_workers
if worker_count > MAX_WORKERS:
    logger.warning(f"Worker count {worker_count} exceeds maximum {MAX_WORKERS}")

# Not:
if config.max_workers>MAX_WORKERS:logger.warning(f"Worker count {config.max_workers} exceeds maximum {MAX_WORKERS}")
```

## PEP 8 Compliance

AIPerf follows [PEP 8](https://www.python.org/dev/peps/pep-0008/) with specific adaptations.

### Line Length

88 characters maximum (Black default):

```python
# Good: 88 characters or less
result = await self.client.post_request(
    url=endpoint.url, body=request_body, headers=headers
)

# Acceptable: Split long lines
logger.debug(
    lambda: f"Processing conversation {conv_id} with {len(turns)} turns "
    f"and {token_count} tokens"
)

# Bad: Exceeds 88 characters
result = await self.client.post_request(url=endpoint.url, body=request_body, headers=headers, timeout=30.0)
```

### Indentation

4 spaces per level:

```python
# Good
def process_records(records: list[Record]) -> dict[str, MetricResult]:
    results = {}
    for record in records:
        if record.is_valid:
            result = compute_metric(record)
            results[record.id] = result
    return results

# Bad: 2 spaces
def process_records(records: list[Record]) -> dict[str, MetricResult]:
  results = {}
  for record in records:
    if record.is_valid:
      result = compute_metric(record)
      results[record.id] = result
  return results
```

### Blank Lines

From PEP 8:

```python
# Two blank lines before top-level classes and functions
import logging
from typing import Optional


class WorkerService:
    """Worker service implementation."""


def create_worker(config: ServiceConfig) -> WorkerService:
    """Factory function to create worker."""


# One blank line between methods
class MetricComputer:
    def compute_ttft(self, record: Record) -> float:
        """Compute time to first token."""
        return record.first_token_time - record.start_time

    def compute_tpot(self, record: Record) -> float:
        """Compute time per output token."""
        return (record.end_time - record.first_token_time) / record.token_count


# No blank line between single-line methods (optional)
class Constants:
    MAX_WORKERS = 1000
    DEFAULT_TIMEOUT = 30.0
```

### Whitespace

```python
# Good: Whitespace around operators
result = (a + b) * (c - d)
if x == y and z != w:
    process()

# Bad: Missing whitespace
result=(a+b)*(c-d)
if x==y and z!=w:
    process()

# Good: No whitespace before function calls
function(arg1, arg2)
dict_value = my_dict["key"]
list_item = my_list[0]

# Bad: Extra whitespace
function (arg1, arg2)
dict_value = my_dict ["key"]
list_item = my_list [0]

# Good: Keyword arguments
def function(arg1: str, arg2: int = 10) -> None:
    pass

# Bad: Whitespace around = in keyword args
def function(arg1: str, arg2: int = 10) -> None:
    pass
```

## Black Formatting

AIPerf uses [Black](https://black.readthedocs.io/) for automatic code formatting.

### Configuration

From `/home/anthony/nvidia/projects/aiperf/pyproject.toml`:

```toml
[project.optional-dependencies]
dev = [
  "black>=25.1.0",
  # ...
]
```

Black uses default settings:
- Line length: 88 characters
- Python version: Latest supported
- String quote: Double quotes

### Running Black

```bash
# Format all files
black aiperf/ tests/

# Check without modifying
black --check aiperf/ tests/

# Show what would change
black --diff aiperf/ tests/

# Format specific file
black aiperf/workers/worker.py
```

### Black's Formatting Rules

**String quotes:**
```python
# Black prefers double quotes
message = "Hello, world"

# Unless string contains double quotes
message = 'He said "Hello"'

# For docstrings, always double quotes
def function():
    """This is a docstring."""
    pass
```

**Line breaking:**
```python
# Black breaks long lines intelligently
result = some_long_function_name(
    argument1, argument2, argument3, argument4, argument5
)

# Trailing commas trigger vertical formatting
data = [
    "item1",
    "item2",
    "item3",
]

# Without trailing comma, stays horizontal if fits
data = ["item1", "item2", "item3"]
```

**Function signatures:**
```python
# Fits on one line
def short_function(arg1: str, arg2: int) -> bool:
    pass

# Breaks when too long
def long_function_name(
    argument1: str,
    argument2: int,
    argument3: dict[str, Any],
    argument4: Optional[float] = None,
) -> tuple[bool, str]:
    pass
```

### Don't Fight Black

Let Black handle formatting:

```python
# Don't manually format this
result = {
    "key1"   : value1,
    "key2"   : value2,
    "longer" : value3,
}

# Black will format to:
result = {"key1": value1, "key2": value2, "longer": value3}

# Or if too long:
result = {
    "key1": value1,
    "key2": value2,
    "longer": value3,
}
```

## Ruff Linting Rules

AIPerf uses [Ruff](https://github.com/astral-sh/ruff) for linting and formatting.

### Configuration

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

### Rule Categories

**E (pycodestyle):**
- PEP 8 style violations
- Whitespace errors
- Indentation issues
- Naming violations

**F (Pyflakes):**
- Undefined names
- Unused imports
- Unused variables
- Import errors

**UP (pyupgrade):**
- Modern Python syntax
- f-strings over .format()
- Type hint modernization
- Deprecated syntax

**B (flake8-bugbear):**
- Bug-prone patterns
- Mutable default arguments
- Unused loop variables
- Exception handling issues

**SIM (flake8-simplify):**
- Code simplification
- Dictionary get() vs KeyError
- Boolean comparisons
- Redundant operations

**I (isort):**
- Import ordering
- Import grouping
- Import formatting

### Running Ruff

```bash
# Check all files
ruff check aiperf/ tests/

# Auto-fix issues
ruff check --fix aiperf/ tests/

# Format code (Black-compatible)
ruff format aiperf/ tests/

# Check specific file
ruff check aiperf/workers/worker.py

# Show all errors (including fixed)
ruff check --fix --show-fixes aiperf/
```

### Common Ruff Fixes

**F401: Unused import**
```python
# Bad
import os
import sys
from typing import Optional

def function():
    return sys.platform

# Good
import sys

def function():
    return sys.platform
```

**F841: Unused variable**
```python
# Bad
result = expensive_computation()
return True

# Good
_ = expensive_computation()  # Explicitly unused
return True

# Or remove
expensive_computation()
return True
```

**UP: Use modern syntax**
```python
# Bad
from typing import Dict, List, Optional

def function(items: List[str]) -> Dict[str, int]:
    pass

# Good (Python 3.10+)
def function(items: list[str]) -> dict[str, int]:
    pass
```

**B006: Mutable default argument**
```python
# Bad
def function(items=[]):
    items.append(1)
    return items

# Good
def function(items=None):
    if items is None:
        items = []
    items.append(1)
    return items
```

**SIM: Simplify code**
```python
# Bad
if condition:
    return True
else:
    return False

# Good
return condition

# Bad
try:
    value = dict_obj[key]
except KeyError:
    value = default

# Good
value = dict_obj.get(key, default)
```

## Import Organization

AIPerf follows strict import ordering using isort (via Ruff).

### Import Order

1. Standard library imports
2. Related third-party imports
3. Local application imports

```python
# Standard library
import asyncio
import logging
import multiprocessing
from pathlib import Path
from typing import Any, Optional

# Third-party
import aiohttp
import pytest
from rich.console import Console

# Local application
from aiperf.common.aiperf_logger import AIPerfLogger
from aiperf.common.config import ServiceConfig, UserConfig
from aiperf.common.enums import ServiceType
from aiperf.workers.worker import WorkerService
```

### Import Formatting

```python
# Good: Separate groups with blank lines
import sys
from pathlib import Path

import pytest

from aiperf.common.config import ServiceConfig

# Bad: No separation
import sys
from pathlib import Path
import pytest
from aiperf.common.config import ServiceConfig

# Good: Alphabetical within groups
from aiperf.common.config import ServiceConfig, UserConfig
from aiperf.common.enums import ServiceType
from aiperf.workers.worker import WorkerService

# Good: Long imports broken across lines
from aiperf.common.models import (
    Conversation,
    ErrorDetails,
    RequestRecord,
    ResponseRecord,
    Text,
    Turn,
)

# Good: Relative imports for same package
from .base_metric import BaseMetric
from .metric_registry import MetricRegistry

# Avoid: Wildcard imports
from aiperf.common.enums import *  # Bad
```

### Import Aliases

```python
# Good: Standard aliases
import numpy as np
import pandas as pd

# Good: Disambiguate similar names
from aiperf.clients.http import AioHttpClient as HttpClient
from aiperf.clients.openai import OpenAIClient as AIClient

# Good: Shorten long module names
from aiperf.common.models import RequestRecord as ReqRec  # If used frequently

# Bad: Unnecessary aliases
import sys as s
from pathlib import Path as P
```

### Conditional Imports

```python
# Good: Type checking imports
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from aiperf.controller.system_controller import SystemController

# Good: Optional dependencies
try:
    import yappi
    YAPPI_AVAILABLE = True
except ImportError:
    YAPPI_AVAILABLE = False

# Good: Platform-specific imports
import sys
if sys.platform == "linux":
    import resource
```

## Type Hints

AIPerf requires type hints for all public APIs.

### Function Signatures

```python
# Good: Complete type hints
def compute_ttft(
    record: RequestRecord,
    baseline_ns: int,
) -> float:
    """Compute time to first token in seconds."""
    return (record.first_token_ns - baseline_ns) / 1e9

# Good: Generic types (Python 3.10+)
def process_batch(
    records: list[RequestRecord],
    config: dict[str, Any],
) -> dict[str, MetricResult]:
    """Process a batch of records."""
    results = {}
    for record in records:
        results[record.id] = process(record, config)
    return results

# Good: Optional parameters
def create_worker(
    config: ServiceConfig,
    log_queue: multiprocessing.Queue | None = None,
) -> WorkerService:
    """Create a worker service."""
    return WorkerService(config, log_queue)

# Bad: Missing type hints
def compute_ttft(record, baseline_ns):
    return (record.first_token_ns - baseline_ns) / 1e9
```

### Class Attributes

```python
class WorkerService:
    """Worker service for processing requests."""

    # Good: Class attributes with type hints
    worker_id: str
    config: ServiceConfig
    request_count: int = 0
    _logger: AIPerfLogger

    def __init__(self, worker_id: str, config: ServiceConfig) -> None:
        self.worker_id = worker_id
        self.config = config
        self._logger = AIPerfLogger(__name__)
```

### Complex Types

```python
from collections.abc import Callable
from typing import Any

# Good: Callable types
CallbackType = Callable[[RequestRecord], None]
AsyncCallbackType = Callable[[RequestRecord], Awaitable[None]]

def register_callback(callback: CallbackType) -> None:
    """Register a callback function."""
    pass

# Good: Union types (Python 3.10+)
def process_input(data: str | bytes | Path) -> str:
    """Process input from various sources."""
    if isinstance(data, (str, bytes)):
        return data.decode() if isinstance(data, bytes) else data
    return data.read_text()

# Good: Generic classes
from typing import Generic, TypeVar

T = TypeVar("T")

class Queue(Generic[T]):
    """Generic queue implementation."""

    def put(self, item: T) -> None:
        """Add item to queue."""
        pass

    def get(self) -> T:
        """Get item from queue."""
        pass
```

### Type Aliases

```python
# Good: Define complex type aliases
from typing import TypeAlias

MessageTypeT: TypeAlias = type["Message"]
MetricTagT: TypeAlias = str
ConfigDict: TypeAlias = dict[str, Any]

def process_message(msg_type: MessageTypeT) -> None:
    """Process a message of given type."""
    pass

def compute_metric(tag: MetricTagT) -> float:
    """Compute metric by tag."""
    pass
```

### Async Type Hints

```python
from collections.abc import Awaitable

# Good: Async functions
async def process_request(request: Request) -> Response:
    """Process request asynchronously."""
    result = await self.client.post_request(request)
    return result

# Good: Async generators
from collections.abc import AsyncIterator

async def stream_responses() -> AsyncIterator[Response]:
    """Stream responses asynchronously."""
    while True:
        response = await self.get_response()
        if response is None:
            break
        yield response

# Good: Async context managers
from typing import Self

class AsyncResource:
    async def __aenter__(self) -> Self:
        await self.acquire()
        return self

    async def __aexit__(self, *args) -> None:
        await self.release()
```

## Naming Conventions

AIPerf follows PEP 8 naming conventions with specific patterns.

### General Rules

```python
# Variables and functions: lowercase_with_underscores
worker_count = 10
request_timeout = 30.0

def compute_metric(record: RequestRecord) -> float:
    pass

# Constants: UPPERCASE_WITH_UNDERSCORES
MAX_WORKERS = 1000
DEFAULT_TIMEOUT = 30.0
LOG_QUEUE_MAXSIZE = 1000

# Classes: PascalCase
class WorkerService:
    pass

class RequestRecord:
    pass

class AIPerfLogger:
    pass

# Private attributes: _leading_underscore
class Service:
    def __init__(self):
        self._logger = AIPerfLogger(__name__)
        self._internal_state = {}

# Type variables: Single capital letter or PascalCase
T = TypeVar("T")
RequestT = TypeVar("RequestT", bound="Request")
```

### Specific Patterns

**Services:**
```python
# Pattern: {Name}Service
class WorkerService:
    pass

class DatasetManagerService:
    pass

class SystemControllerService:
    pass
```

**Metrics:**
```python
# Pattern: {Name}Metric
class TTFTMetric:
    pass

class RequestLatencyMetric:
    pass

class OutputTokenThroughputMetric:
    pass
```

**Configs:**
```python
# Pattern: {Name}Config
class UserConfig:
    pass

class ServiceConfig:
    pass

class EndpointConfig:
    pass
```

**Messages:**
```python
# Pattern: {Name}Message
class RequestMessage:
    pass

class ResponseMessage:
    pass

class ShutdownMessage:
    pass
```

**Handlers:**
```python
# Pattern: {Name}Handler
class MultiProcessLogHandler:
    pass

class RequestHandler:
    pass
```

**Managers:**
```python
# Pattern: {Name}Manager
class WorkerManager:
    pass

class DatasetManager:
    pass

class ExporterManager:
    pass
```

### File Names

```python
# Modules: lowercase_with_underscores
aiperf_logger.py
system_controller.py
multi_process_service_manager.py

# Test files: test_{module}.py
test_aiperf_logger.py
test_system_controller.py
test_worker.py
```

### Acronyms

```python
# Treat acronyms as words in class names
class HttpClient:  # Not HTTPClient
    pass

class AioHttpClientMixin:  # AioHttp is one word
    pass

class OpenAIClient:  # OpenAI is the brand name
    pass

# Uppercase in constants
HTTP_TIMEOUT = 30.0
OPENAI_API_KEY = "secret"
```

## Docstring Standards

AIPerf uses Google-style docstrings.

### Function Docstrings

```python
def compute_ttft(
    record: RequestRecord,
    baseline_ns: int,
) -> float:
    """Compute time to first token in seconds.

    Args:
        record: The request record containing timing information.
        baseline_ns: Baseline timestamp in nanoseconds for relative timing.

    Returns:
        Time to first token in seconds, or 0 if no tokens generated.

    Raises:
        ValueError: If record has no first token timestamp.

    Example:
        >>> record = RequestRecord(first_token_ns=1000000000)
        >>> ttft = compute_ttft(record, baseline_ns=0)
        >>> print(f"TTFT: {ttft:.3f}s")
        TTFT: 1.000s
    """
    if record.first_token_ns is None:
        raise ValueError("Record has no first token timestamp")
    return (record.first_token_ns - baseline_ns) / 1e9
```

### Class Docstrings

```python
class WorkerService(AIPerfLifecycleMixin):
    """Worker service for processing benchmark requests.

    WorkerService handles individual request processing in a multiprocess
    architecture. Each worker maintains its own HTTP client, processes
    requests from the worker manager, and publishes results back.

    Attributes:
        worker_id: Unique identifier for this worker.
        config: Service configuration including endpoints and timeouts.
        client: HTTP client for making requests.
        request_count: Total number of requests processed.

    Example:
        >>> config = ServiceConfig(max_workers=10)
        >>> worker = WorkerService(worker_id="worker_0", config=config)
        >>> await worker.start()
        >>> # Process requests...
        >>> await worker.stop()
    """

    def __init__(
        self,
        worker_id: str,
        config: ServiceConfig,
    ) -> None:
        """Initialize worker service.

        Args:
            worker_id: Unique identifier for this worker.
            config: Service configuration.
        """
        super().__init__()
        self.worker_id = worker_id
        self.config = config
```

### Module Docstrings

```python
"""Worker service implementation for AIPerf benchmarking.

This module provides the WorkerService class which handles individual request
processing in a multiprocess architecture. Workers receive requests from the
worker manager, execute them via HTTP clients, and publish results.

The worker lifecycle is managed through the AIPerfLifecycleMixin, providing
start/stop hooks and background task management.

Example:
    from aiperf.workers.worker import WorkerService
    from aiperf.common.config import ServiceConfig

    config = ServiceConfig(max_workers=10)
    worker = WorkerService(worker_id="worker_0", config=config)
    await worker.start()
"""
```

### Property Docstrings

```python
class Service:
    @property
    def is_running(self) -> bool:
        """Check if service is currently running.

        Returns:
            True if service is running, False otherwise.
        """
        return self._running

    @property
    def request_count(self) -> int:
        """Total number of requests processed.

        Returns:
            Count of processed requests since service start.
        """
        return self._request_count
```

### One-Line Docstrings

```python
def simple_function(x: int) -> int:
    """Double the input value."""
    return x * 2

class SimpleClass:
    """A simple class for demonstration."""
    pass
```

## Comment Guidelines

Use comments judiciously to explain why, not what.

### Good Comments

```python
# Explain complex logic
# Use put_nowait to avoid blocking worker process on queue full.
# Dropping logs is preferable to blocking request processing.
try:
    self.log_queue.put_nowait(log_data)
except queue.Full:
    pass

# Explain non-obvious decisions
# Cannot use LogRecord directly due to pickling issues with custom attributes.
# Extract key fields into serializable dict instead.
log_data = {
    "name": record.name,
    "levelname": record.levelname,
    "msg": record.getMessage(),
}

# Explain workarounds
# TODO: Remove once Python 3.12 is minimum version
# Python 3.10 doesn't support match statements with TypeVar
if isinstance(message, RequestMessage):
    handle_request(message)
elif isinstance(message, ResponseMessage):
    handle_response(message)

# Explain important TODOs
# TODO(username): Implement request cancellation when timeout expires.
# Currently requests are allowed to complete even after client timeout.
```

### Bad Comments

```python
# Bad: States the obvious
# Increment counter
counter += 1

# Bad: Outdated comment
# This function returns a string  # Actually returns int now
def get_count() -> int:
    return 42

# Bad: Redundant with docstring
def compute_ttft(record: RequestRecord) -> float:
    """Compute time to first token."""
    # Compute time to first token
    return (record.first_token_ns - record.start_ns) / 1e9

# Bad: Commented-out code (remove instead)
# result = old_computation(data)
result = new_computation(data)
```

### Comment Types

**Inline comments:**
```python
# Good: Explain non-obvious inline
x = compute()  # Result in nanoseconds, convert later

# Bad: State the obvious
x = compute()  # Call compute function
```

**Block comments:**
```python
# Good: Explain complex sections
# The following section implements adaptive rate limiting based on response
# times. If average latency exceeds threshold, reduce request rate by half.
# This prevents overwhelming the server while maintaining maximum throughput.
if avg_latency > threshold:
    request_rate = request_rate / 2
```

**TODO comments:**
```python
# TODO: Add support for custom headers per request
# TODO(username): Implement exponential backoff retry logic
# FIXME: Race condition when multiple workers access shared queue
# HACK: Workaround for aiohttp issue #1234
```

## Async/Await Conventions

AIPerf is heavily async; follow these conventions.

### Async Function Definitions

```python
# Good: Clear async functions
async def process_request(self, request: Request) -> Response:
    """Process request asynchronously."""
    response = await self.client.post_request(request)
    return response

# Good: Async with error handling
async def safe_process(self, request: Request) -> Response | None:
    """Process request with error handling."""
    try:
        return await self.process_request(request)
    except Exception as e:
        self.logger.exception("Request processing failed")
        return None

# Bad: Sync function calling async (blocking)
def process_request(self, request: Request) -> Response:
    # Don't use asyncio.run() in async codebase
    return asyncio.run(self.async_process(request))
```

### Awaiting Multiple Tasks

```python
# Good: Gather for concurrent execution
results = await asyncio.gather(
    task1(),
    task2(),
    task3(),
    return_exceptions=True,
)

# Good: TaskGroup for structured concurrency (Python 3.11+)
async with asyncio.TaskGroup() as group:
    task1 = group.create_task(process_request(req1))
    task2 = group.create_task(process_request(req2))

# Good: Wait with timeout
try:
    result = await asyncio.wait_for(slow_operation(), timeout=30.0)
except asyncio.TimeoutError:
    logger.warning("Operation timed out")

# Bad: Sequential when could be concurrent
result1 = await task1()  # Waits
result2 = await task2()  # Then waits again
```

### Async Context Managers

```python
# Good: Async context manager
class AsyncResource:
    async def __aenter__(self):
        await self.acquire()
        return self

    async def __aexit__(self, *args):
        await self.release()

# Usage
async with AsyncResource() as resource:
    await resource.use()

# Good: Multiple context managers
async with (
    AsyncResource1() as res1,
    AsyncResource2() as res2,
):
    await process(res1, res2)
```

### Async Generators

```python
# Good: Async generator for streaming
async def stream_responses(self) -> AsyncIterator[Response]:
    """Stream responses from server."""
    while True:
        response = await self.receive()
        if response is None:
            break
        yield response

# Usage
async for response in stream_responses():
    process(response)
```

### Background Tasks

```python
from aiperf.common.hooks import background_task

# Good: Background task decorator
class Service:
    @background_task(immediate=True, interval=1.0)
    async def _monitor_health(self) -> None:
        """Monitor service health every second."""
        health = await self.check_health()
        if not health.is_healthy:
            self.logger.warning("Service unhealthy")

# Good: Manual task creation
class Service:
    async def start(self) -> None:
        """Start service and background tasks."""
        self._task = asyncio.create_task(self._monitor_health())

    async def stop(self) -> None:
        """Stop service and cancel tasks."""
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
```

### Yielding to Event Loop

```python
# Good: Yield in tight loops
async def process_many(items: list[Item]) -> None:
    """Process many items without blocking event loop."""
    for i, item in enumerate(items):
        process_item(item)
        if i % 100 == 0:
            await asyncio.sleep(0)  # Yield to event loop

# Good: Using utility
from aiperf.common.utils import yield_to_event_loop

async def process_many(items: list[Item]) -> None:
    """Process many items without blocking event loop."""
    for item in items:
        process_item(item)
        await yield_to_event_loop()
```

## Error Handling Patterns

Consistent error handling improves reliability and debuggability.

### Exception Types

```python
# Good: Specific exceptions
try:
    result = await self.client.post_request(request)
except aiohttp.ClientConnectionError as e:
    self.logger.error(f"Connection failed: {e}")
    return None
except aiohttp.ClientTimeout as e:
    self.logger.warning(f"Request timeout: {e}")
    return None
except Exception as e:
    self.logger.exception("Unexpected error")
    raise

# Bad: Catching everything
try:
    result = await self.client.post_request(request)
except:  # Too broad, hides bugs
    pass
```

### Logging Exceptions

```python
# Good: Use logger.exception for stack trace
try:
    result = risky_operation()
except Exception as e:
    logger.exception("Operation failed")
    raise

# Good: Include context
try:
    result = process_record(record)
except ValueError as e:
    logger.error(f"Invalid record {record.id}: {e}")
    raise

# Bad: Lose stack trace
try:
    result = risky_operation()
except Exception as e:
    logger.error(f"Error: {e}")  # No stack trace
    raise
```

### Error Recovery

```python
# Good: Retry with exponential backoff
async def retry_request(
    self,
    request: Request,
    max_retries: int = 3,
) -> Response | None:
    """Retry request with exponential backoff."""
    for attempt in range(max_retries):
        try:
            return await self.client.post_request(request)
        except aiohttp.ClientError as e:
            if attempt == max_retries - 1:
                self.logger.error(f"Request failed after {max_retries} attempts")
                return None

            delay = 2 ** attempt
            self.logger.warning(f"Request failed, retrying in {delay}s: {e}")
            await asyncio.sleep(delay)

    return None
```

### Custom Exceptions

```python
# Good: Custom exceptions for domain errors
class AIPerfError(Exception):
    """Base exception for AIPerf errors."""
    pass

class ConfigurationError(AIPerfError):
    """Configuration is invalid or missing."""
    pass

class ServiceError(AIPerfError):
    """Service operation failed."""
    pass

# Usage
def validate_config(config: UserConfig) -> None:
    """Validate user configuration."""
    if not config.endpoint.url:
        raise ConfigurationError("Endpoint URL is required")

    if config.max_workers < 1:
        raise ConfigurationError("At least one worker is required")
```

## Logging Conventions

Consistent logging improves debuggability.

### Logger Initialization

```python
# Good: Module-level logger
from aiperf.common.aiperf_logger import AIPerfLogger

logger = AIPerfLogger(__name__)

# Good: Class-level logger via mixin
from aiperf.common.mixins import AIPerfLoggerMixin

class Service(AIPerfLoggerMixin):
    def __init__(self):
        super().__init__()
        # self.logger is available
        self.logger.info("Service initialized")
```

### Log Levels

```python
# TRACE: Full dumps, protocol details
logger.trace(lambda: f"Full request: {request}")

# DEBUG: Development debugging
logger.debug(f"Processing request {request.id}")

# INFO: Important events
logger.info("Worker started successfully")

# NOTICE: Significant milestones
logger.notice("Configuration loaded successfully")

# WARNING: Recoverable issues
logger.warning("Request retried due to timeout")

# SUCCESS: Positive confirmations
logger.success("Benchmark completed successfully")

# ERROR: Failures
logger.error(f"Failed to process request {request.id}")

# CRITICAL: System-threatening
logger.critical("Out of memory, shutting down")
```

### Lazy Evaluation

```python
# Good: Lazy evaluation for expensive operations
logger.debug(lambda: f"Processing {len(items)} items: {items}")

# Good: Check level first
if logger.is_debug_enabled:
    logger.debug(f"Expensive computation: {expensive_repr(obj)}")

# Bad: Always evaluates
logger.debug(f"Large object: {expensive_repr(obj)}")
```

### Structured Logging

```python
# Good: Structured log format for parsing
logger.info(
    f"request_completed "
    f"conversation_id={conv_id} "
    f"latency_ms={latency_ms:.2f} "
    f"tokens={tokens} "
    f"status={status}"
)

# Parseable output:
# request_completed conversation_id=conv_123 latency_ms=456.78 tokens=100 status=200
```

## File Organization

Consistent file organization improves navigability.

### File Header

```python
# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Module description goes here.

Longer description of what this module does, its purpose, and any important
concepts or patterns used.

Example:
    from aiperf.module import SomeClass

    instance = SomeClass()
    instance.do_something()
"""
```

### Import Section

```python
# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Module docstring."""

# Standard library imports
import asyncio
import logging
from pathlib import Path
from typing import Any

# Third-party imports
import aiohttp
from rich.console import Console

# Local imports
from aiperf.common.aiperf_logger import AIPerfLogger
from aiperf.common.config import ServiceConfig
```

### Constants

```python
# Module-level constants after imports
MAX_WORKERS = 1000
DEFAULT_TIMEOUT = 30.0
LOG_QUEUE_MAXSIZE = 1000

logger = AIPerfLogger(__name__)
```

### Classes and Functions

```python
# Classes first, then module-level functions

class PrimaryClass:
    """Primary class in module."""
    pass


class HelperClass:
    """Helper class."""
    pass


def utility_function() -> None:
    """Utility function."""
    pass


def another_utility() -> None:
    """Another utility function."""
    pass


# Main block at end
if __name__ == "__main__":
    main()
```

## Module Structure

Organize modules into logical packages.

### Package Structure

```
aiperf/
├── __init__.py              # Package exports
├── workers/
│   ├── __init__.py          # Export WorkerService, WorkerManager
│   ├── worker.py            # WorkerService implementation
│   ├── worker_manager.py    # WorkerManager implementation
│   └── worker_utils.py      # Utility functions
├── metrics/
│   ├── __init__.py          # Export all metrics
│   ├── base_metric.py       # Base classes
│   ├── ttft_metric.py       # TTFT metric
│   ├── tpot_metric.py       # TPOT metric
│   └── metric_registry.py   # Registry
└── common/
    ├── __init__.py
    ├── config/              # Configuration subsystem
    ├── messages/            # Message types
    └── mixins/              # Reusable mixins
```

### Package __init__.py

```python
# aiperf/workers/__init__.py
"""Worker services for AIPerf benchmarking."""

from aiperf.workers.worker import WorkerService
from aiperf.workers.worker_manager import WorkerManager

__all__ = [
    "WorkerService",
    "WorkerManager",
]
```

### Avoid Circular Imports

```python
# Bad: Circular dependency
# module_a.py
from module_b import ClassB

class ClassA:
    def use_b(self):
        return ClassB()

# module_b.py
from module_a import ClassA

class ClassB:
    def use_a(self):
        return ClassA()

# Good: Use TYPE_CHECKING
# module_a.py
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from module_b import ClassB

class ClassA:
    def use_b(self) -> "ClassB":
        from module_b import ClassB
        return ClassB()
```

## Code Review Checklist

Use this checklist when reviewing code:

### Functionality
- [ ] Code does what it's supposed to do
- [ ] Edge cases are handled
- [ ] Error handling is appropriate
- [ ] Tests are included and passing

### Style
- [ ] Follows PEP 8 conventions
- [ ] Black/Ruff formatting applied
- [ ] Imports are organized correctly
- [ ] Type hints are complete
- [ ] Docstrings follow Google style
- [ ] Comments explain why, not what

### Design
- [ ] Functions are focused and single-purpose
- [ ] Classes have clear responsibilities
- [ ] No code duplication
- [ ] Appropriate abstraction level
- [ ] Follows existing patterns

### Performance
- [ ] No obvious performance issues
- [ ] Async/await used correctly
- [ ] Lazy evaluation where appropriate
- [ ] No blocking calls in async code

### Security
- [ ] No hardcoded secrets
- [ ] Input validation present
- [ ] No SQL injection risks
- [ ] Sensitive data not logged

### Documentation
- [ ] Public APIs documented
- [ ] Complex logic explained
- [ ] Examples provided where helpful
- [ ] README updated if needed

## Anti-Patterns to Avoid

### Anti-Pattern 1: Mutable Default Arguments

```python
# Bad
def function(items=[]):
    items.append(1)
    return items

# Good
def function(items=None):
    if items is None:
        items = []
    items.append(1)
    return items
```

### Anti-Pattern 2: Catching Too Broad

```python
# Bad
try:
    risky_operation()
except:
    pass

# Good
try:
    risky_operation()
except SpecificError as e:
    logger.exception("Operation failed")
    handle_error(e)
```

### Anti-Pattern 3: String Concatenation in Loops

```python
# Bad
result = ""
for item in items:
    result += str(item)

# Good
result = "".join(str(item) for item in items)
```

### Anti-Pattern 4: Using eval()

```python
# Bad
result = eval(user_input)

# Good
import ast
result = ast.literal_eval(user_input)
```

### Anti-Pattern 5: Bare except

```python
# Bad
try:
    operation()
except:
    pass

# Good
try:
    operation()
except Exception as e:
    logger.exception("Operation failed")
```

## Key Takeaways

1. **Follow PEP 8 with 88-character line length** as the foundational style guide for all Python code.

2. **Black handles formatting automatically**, so don't fight it—let it format your code and focus on logic.

3. **Ruff provides comprehensive linting** covering style (E), bugs (F), modernization (UP), and simplification (SIM).

4. **Organize imports in three groups**: standard library, third-party, and local application imports, alphabetically sorted.

5. **Type hints are required for all public APIs** to improve code clarity and enable static analysis.

6. **Use Google-style docstrings** with Args, Returns, Raises, and Example sections for comprehensive documentation.

7. **Naming conventions follow patterns**: PascalCase for classes, lowercase_with_underscores for functions/variables, UPPERCASE for constants.

8. **Async/await conventions**: use async functions consistently, await multiple tasks with gather, yield in tight loops.

9. **Lazy evaluation with lambdas** improves logging performance when log levels are disabled.

10. **Error handling should be specific**: catch specific exceptions, log with context, and use logger.exception for stack traces.

11. **Comments explain why, not what**: focus on non-obvious decisions, complex logic, and important TODOs.

12. **File organization is consistent**: copyright header, docstring, imports, constants, classes, functions, main block.

13. **Pre-commit hooks enforce style automatically**, running ruff, adding copyright headers, and catching common issues.

14. **Code review checklist covers functionality, style, design, performance, security, and documentation** for thorough reviews.

15. **Avoid common anti-patterns**: mutable defaults, bare except, eval(), catching too broadly, and string concatenation in loops.

---

[Previous: Chapter 38 - Development Environment](chapter-38-development-environment.md) | [Index](INDEX.md) | [Next: Chapter 40 - Testing Strategies](chapter-40-testing-strategies.md)
