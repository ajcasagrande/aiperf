<!--
# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
-->
# AIPerf Development Guide for AI Assistants

This document provides guidance for AI assistants working on the AIPerf codebase. Read this carefully before making changes.

## Core Philosophy

**Every line of code is a liability.** Before adding code, ask:
1. Does this solve a real problem?
2. Can existing code already do this?
3. Is this the simplest solution?
4. Will this be maintainable in 6 months?

If you cannot answer "yes" to all four questions, reconsider your approach.

## Architecture Principles

### 1. Service-Based Architecture

AIPerf is a distributed system where services communicate via ZMQ. Each service is an independent process.

**Critical Rules**:
- Services MUST NOT directly import or instantiate other services
- Communication ONLY through ZMQ message bus
- Each service follows the lifecycle: CREATED → INITIALIZED → RUNNING → STOPPED
- Lifecycle hooks (@on_init, @on_start, @on_stop) are REQUIRED, not optional

**Example of WRONG approach**:
```python
# NEVER DO THIS
from aiperf.workers.worker import Worker
worker = Worker()  # Direct instantiation breaks architecture
```

**Example of CORRECT approach**:
```python
# Use factory and service manager
@ServiceFactory.register(ServiceType.WORKER)
class Worker(BaseService):
    ...
```

### 2. Communication Patterns

Three ZMQ patterns are used. Use the right one:

**Pub/Sub (Broadcasting)**:
- Use for: Status updates, heartbeats, commands to all services
- Pattern: One publisher, many subscribers
- Implementation: `MessageBusClientMixin`

**Push/Pull (Work Distribution)**:
- Use for: Credit drops, result collection
- Pattern: Round-robin work distribution
- Implementation: `PullClientMixin`

**Dealer/Router (Request/Reply)**:
- Use for: Data requests (e.g., conversations)
- Pattern: Async request-response
- Implementation: `ReplyClientMixin`

**Rule**: If you need communication, use one of these patterns. Do NOT invent new patterns.

### 3. Credit System is Sacred

The credit system ensures precise rate control. It MUST be respected:

**Absolute Requirements**:
- Every credit drop MUST result in exactly one credit return
- Credit return MUST be in a `finally` block
- Semaphore MUST be acquired BEFORE `recv_string()` in pull clients
- Never lose or duplicate credits

**Example**:
```python
async def _process_credit_drop_internal(self, message: CreditDropMessage):
    try:
        await self._execute_single_credit_internal(message)
    finally:
        # ALWAYS return credit, even on error
        await self.credit_return_push_client.push(
            CreditReturnMessage(...)
        )
```

Violating credit system rules will break benchmarking accuracy. No exceptions.

## Code Quality Standards

### Follow PEP 8, But With Intent

**Type Hints**: Always use them. They are documentation.
```python
def process_record(record: ParsedResponseRecord) -> MetricRecordDict:
    ...
```

**Docstrings**: Required for public APIs. Keep them concise and accurate.
```python
def process_record(self, record: ParsedResponseRecord) -> MetricRecordDict:
    """Process a single record and compute metrics.

    Args:
        record: The parsed response record

    Returns:
        Dict of computed metrics

    Raises:
        NoMetricValue: If metric cannot be computed
    """
```

**Line Length**: 88 characters (Black default). Don't fight the formatter.

### DRY (Don't Repeat Yourself)

**Good**: Extract repeated logic into functions
```python
def _validate_token_count(count: int | None) -> int:
    if count is None or count < 0:
        raise NoMetricValue("Invalid token count")
    return count

# Use in multiple metrics
input_tokens = _validate_token_count(record.input_token_count)
output_tokens = _validate_token_count(record.output_token_count)
```

**Bad**: Copy-paste logic everywhere
```python
# In metric 1
if record.input_token_count is None or record.input_token_count < 0:
    raise NoMetricValue("Invalid token count")

# In metric 2
if record.output_token_count is None or record.output_token_count < 0:
    raise NoMetricValue("Invalid token count")
```

**But**: Don't over-abstract. Two occurrences is not duplication. Three+ is duplication.

### KISS (Keep It Simple, Stupid)

**Prefer simple over clever**:
```python
# Good: Clear and obvious
if len(record.responses) < 2:
    raise NoMetricValue("Need at least 2 responses")

# Bad: Clever but confusing
if not (responses := record.responses)[1:]:
    raise NoMetricValue("Need at least 2 responses")
```

**Prefer explicit over implicit**:
```python
# Good: Explicit state transitions
self.state = ServiceState.INITIALIZED
await self._start_background_tasks()
self.state = ServiceState.RUNNING

# Bad: Hidden state changes
await self._start()  # What state are we in now?
```

### Pythonic Code

**Use context managers**:
```python
# Good
async with self.processing_lock:
    self.counter += 1

# Bad
await self.processing_lock.acquire()
try:
    self.counter += 1
finally:
    self.processing_lock.release()
```

**Use comprehensions when clear**:
```python
# Good: Clear intent
metric_tags = [m.tag for m in metrics if m.flags.has_flags(MetricFlags.STREAMING_ONLY)]

# Bad: Loop is clearer here
result = []
for m in metrics:
    if m.flags.has_flags(MetricFlags.STREAMING_ONLY):
        result.append(m.tag)
        result.sort()  # Side effects in loop
```

**Use dataclasses/Pydantic, not dicts**:
```python
# Good: Type-safe, validated
@dataclass
class WorkerStats:
    completed: int
    failed: int
    in_progress: int

# Bad: Brittle, no validation
stats = {"completed": 0, "failed": 0, "in_progress": 0}
```

## Common Patterns in AIPerf

### Pattern: Factory Registration

When adding new types of components, use factory pattern:

```python
@MyFactory.register(MyType.NEW_OPTION)
class NewOption(MyProtocol):
    ...
```

**Do NOT** manually add to factory dictionaries. Registration is automatic.

### Pattern: Mixin Composition

Use mixins for orthogonal concerns:

```python
class MyService(MessageBusClientMixin, PullClientMixin, BaseService):
    # Inherits pub/sub + pull functionality
    ...
```

**Rule**: Mixins provide functionality, not state. Base class provides state.

### Pattern: Lifecycle Hooks

Use decorators for lifecycle events:

```python
@on_init
async def _initialize(self):
    # Setup resources
    ...

@on_start
async def _start(self):
    # Start operations
    ...

@on_stop
async def _stop(self):
    # Cleanup
    ...
```

**Critical**: Hooks MUST be async. Hooks MUST NOT block.

### Pattern: Background Tasks

Use the background task decorator:

```python
@background_task(immediate=True, interval=1.0)
async def _periodic_task(self):
    # Runs every 1 second
    ...
```

**Do NOT** manually create tasks with `asyncio.create_task()` unless you have a very good reason.

### Pattern: Error Handling in Pipeline

In data processing pipelines, convert errors to data:

```python
# Good: Error becomes data
try:
    result = compute_metric(record)
except Exception as e:
    return RequestRecord(
        error=ErrorDetails.from_exception(e),
        ...
    )

# Bad: Exception propagates and breaks pipeline
result = compute_metric(record)  # Crashes on error
```

## What NOT To Do

### 1. Do Not Break Timing Precision

**Never** use `time.time()` for latency measurements. Use `time.perf_counter_ns()`:

```python
# WRONG
start = time.time()
await operation()
latency = time.time() - start

# CORRECT
start_ns = time.perf_counter_ns()
await operation()
latency_ns = time.perf_counter_ns() - start_ns
```

**Why**: `time.time()` is affected by clock adjustments. `time.perf_counter_ns()` is monotonic and high-resolution.

### 2. Do Not Modify Semaphore Order

**Never** change the order of semaphore acquisition in pull clients:

```python
# CORRECT - acquire BEFORE recv
await self.semaphore.acquire()
message = await socket.recv_string()

# WRONG - breaks load balancing
message = await socket.recv_string()
await self.semaphore.acquire()
```

**Why**: ZMQ round-robin distribution only works if the socket is blocked when at capacity.

### 3. Do Not Skip Validation

**Never** disable Pydantic validation or skip model validators:

```python
# WRONG
config = UserConfig.model_construct(...)  # Skips validation

# CORRECT
config = UserConfig(...)  # Validates all fields
```

**Why**: Validation catches configuration errors early. Runtime errors are much worse.

### 4. Do Not Forget Credit Returns

**Never** have a code path where a credit is not returned:

```python
# WRONG - credit leaked on error
async def process_credit(message):
    result = await execute(message)
    await return_credit(message)  # Not called if execute() raises

# CORRECT - always returned
async def process_credit(message):
    try:
        result = await execute(message)
    finally:
        await return_credit(message)
```

**Why**: Leaked credits will halt the benchmark. This is a critical bug.

### 5. Do Not Create Blocking Operations

**Never** use blocking operations in async code:

```python
# WRONG
async def fetch_data(self):
    time.sleep(1)  # Blocks entire event loop
    data = requests.get(url)  # Blocking I/O
    return data

# CORRECT
async def fetch_data(self):
    await asyncio.sleep(1)  # Non-blocking
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            return await response.text()
```

**Why**: Blocking operations freeze all coroutines. AIPerf's performance depends on async.

### 6. Do Not Add Print Statements

**Never** use `print()` for logging:

```python
# WRONG
print(f"Processing record {record.id}")

# CORRECT
self.debug(f"Processing record {record.id}")
```

**Why**: Logging is routed to the UI and files. Print statements break the dashboard.

### 7. Do Not Create Circular Dependencies

**Never** create circular imports between modules:

```python
# WRONG
# In module_a.py
from module_b import ClassB  # module_b imports module_a

# CORRECT
# In module_a.py
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from module_b import ClassB  # Only for type checking
```

**Why**: Circular dependencies break imports and make code unmaintainable.

## Adding New Features

### Adding a New Metric

1. Create file: `aiperf/metrics/types/my_metric.py`
2. Choose type: `BaseRecordMetric`, `BaseAggregateMetric`, or `BaseDerivedMetric`
3. Implement `_parse_record()` or `_derive_value()`
4. Set required fields: `tag`, `header`, `unit`, `flags`
5. Write test: `tests/metrics/test_my_metric.py`

**That's it.** Auto-registration handles the rest.

**Example**:
```python
class MyMetric(BaseRecordMetric[int]):
    tag = "my_metric"
    header = "My Metric"
    unit = MetricTimeUnit.NANOSECONDS
    display_unit = MetricTimeUnit.MILLISECONDS
    flags = MetricFlags.STREAMING_ONLY

    def _parse_record(self, record: ParsedResponseRecord,
                     record_metrics: MetricRecordDict) -> int:
        if not record.responses:
            raise NoMetricValue("No responses")
        return record.responses[-1].perf_ns - record.start_perf_ns
```

### Adding a New Dataset Type

1. Create model: `aiperf/dataset/loader/models.py`
2. Create loader: `aiperf/dataset/loader/my_loader.py`
3. Register with factory: `@CustomDatasetFactory.register(CustomDatasetType.MY_TYPE)`
4. Implement `load_dataset()` and `convert_to_conversations()`
5. Write test: `tests/dataset/test_my_loader.py`

**Do NOT** modify existing loaders unless fixing bugs.

### Adding a New Configuration Option

1. Add field to appropriate config class (e.g., `InputConfig`)
2. Add default to defaults class (e.g., `InputDefaults`)
3. Add `CLIParameter` annotation for CLI mapping
4. Add validator if needed (use `@model_validator` or `@field_validator`)
5. Update tests: `tests/config/test_input_config.py`

**Example**:
```python
my_field: Annotated[
    int,
    Field(gt=0, description="My new field"),
    CLIParameter(name=("--my-field",), group=Groups.INPUT),
] = InputDefaults.MY_FIELD
```

## Testing Guidelines

### Write Tests That Test Behavior, Not Implementation

**Good test**:
```python
def test_worker_processes_credit():
    """Worker should return credit even on error."""
    worker = Worker(...)
    credit = CreditDropMessage(...)

    # Simulate error during processing
    with patch.object(worker, '_execute_single_credit_internal', side_effect=Exception):
        await worker._credit_drop_callback(credit)

    # Credit should still be returned
    assert len(worker.returned_credits) == 1
```

**Bad test**:
```python
def test_worker_credit_callback_calls_internal():
    """Worker calls _process_credit_drop_internal."""
    worker = Worker(...)
    credit = CreditDropMessage(...)

    with patch.object(worker, '_process_credit_drop_internal') as mock:
        await worker._credit_drop_callback(credit)

    # This tests implementation detail, not behavior
    mock.assert_called_once()
```

**Why**: Good tests survive refactoring. Bad tests break when you improve code.

### Use Fixtures for Common Setup

**Do**:
```python
@pytest.fixture
def user_config():
    return UserConfig(
        endpoint=EndpointConfig(...),
        loadgen=LoadGeneratorConfig(...),
    )

def test_something(user_config):
    # Use fixture
    ...
```

**Don't**:
```python
def test_something():
    # Duplicate setup in every test
    user_config = UserConfig(
        endpoint=EndpointConfig(...),
        loadgen=LoadGeneratorConfig(...),
    )
    ...
```

### Mock External Dependencies, Not Internal Logic

**Mock**: HTTP requests, file I/O, external services
**Don't Mock**: Internal functions you control

## Performance Considerations

### 1. Use Lazy Logging

```python
# Good: Only formats if debug enabled
self.debug(lambda: f"Processing {len(large_list)} items: {large_list}")

# Bad: Always formats, even if debug disabled
self.debug(f"Processing {len(large_list)} items: {large_list}")
```

### 2. Use NumPy for Large Arrays

```python
# Good: NumPy for metrics storage
self.metrics = MetricArray()  # NumPy-backed

# Bad: Python list for thousands of values
self.metrics = []  # Slow percentile computation
```

### 3. Batch Operations

```python
# Good: Batch UI updates
async with self.widget.batch():
    for item in items:
        self.widget.update(item)

# Bad: Update on every item
for item in items:
    self.widget.update(item)
```

### 4. Profile Before Optimizing

**Do NOT** optimize without profiling. Use `yappi`:

```bash
export AIPERF_DEV_MODE=1
aiperf profile --enable-yappi-profiling ...
```

**Then** optimize the hot paths profiling identified.

## Documentation Standards

### Code Comments: Explain Why, Not What

```python
# Good: Explains WHY
# Acquire semaphore before recv to enable ZMQ load balancing
await self.semaphore.acquire()
message = await socket.recv_string()

# Bad: Explains WHAT (obvious from code)
# Acquire the semaphore
await self.semaphore.acquire()
# Receive the message
message = await socket.recv_string()
```

### Module Docstrings: Explain Purpose

Every module should have a docstring:

```python
"""
Worker Process Implementation

This module implements the Worker service, which:
- Receives credit drops from TimingManager
- Requests conversation data from DatasetManager
- Sends HTTP requests to inference endpoints
- Returns credits and results

Key Classes:
    Worker: Main worker process service

See Also:
    aiperf.workers.worker_manager: Worker orchestration
"""
```

### README Files: Explain How

Each major subsystem should have a README explaining how to use it.

## Pre-Commit Checklist

Before submitting changes, verify:

1. **Tests pass**: `pytest tests/`
2. **Type checks pass**: `mypy aiperf/` (if configured)
3. **Linting passes**: `ruff check aiperf/`
4. **Formatting passes**: `black --check aiperf/`
5. **No print statements**: `git diff | grep -n "print("` returns nothing
6. **No debug code**: `git diff | grep -n "breakpoint()"` returns nothing
7. **Docstrings added**: For any new public functions
8. **Tests added**: For any new functionality
9. **No TODOs**: `git diff | grep -n "TODO"` - either fix or file issue

## When in Doubt

1. **Read existing code**: How is similar functionality implemented?
2. **Check the guidebook**: `/home/anthony/nvidia/projects/aiperf/guidebook/`
3. **Look at tests**: `tests/` shows expected usage patterns
4. **Ask**: Open a discussion on GitHub

## Critical Files Reference

**Core Architecture**:
- `aiperf/controller/system_controller.py` - Central orchestrator
- `aiperf/workers/worker.py` - Request execution
- `aiperf/common/base_service.py` - Service base class

**Communication**:
- `aiperf/zmq/` - ZMQ communication layer
- `aiperf/common/messages/` - Message types

**Data Processing**:
- `aiperf/records/records_manager.py` - Results aggregation
- `aiperf/metrics/` - Metrics system
- `aiperf/parsers/` - Response parsing

**Configuration**:
- `aiperf/common/config/user_config.py` - User-facing config
- `aiperf/common/config/service_config.py` - Runtime config

**Dataset**:
- `aiperf/dataset/dataset_manager.py` - Dataset service
- `aiperf/dataset/loader/` - Dataset loaders

## Final Advice

**Simplicity is the ultimate sophistication.**

AIPerf is already complex because distributed systems are inherently complex. Your job is to manage that complexity, not add to it.

Before adding code, ask yourself:
- Is this necessary?
- Is this the simplest solution?
- Will I understand this in 6 months?
- Will someone else understand this?

If the answer to any question is "no", reconsider.

**The best code is no code. The second best code is simple code.**

---

Read the guidebook at `/home/anthony/nvidia/projects/aiperf/guidebook/` for comprehensive technical details. This file is your quick reference for making good decisions.
