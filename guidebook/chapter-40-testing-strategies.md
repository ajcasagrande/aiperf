<!--
# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
-->
# Chapter 40: Testing Strategies

## Overview

Testing is the foundation of reliable software. AIPerf employs comprehensive testing strategies spanning unit tests, integration tests, async testing, mocking, fixtures, and parametrization. This chapter explores the complete testing infrastructure, from test organization and pytest configuration to async testing patterns and coverage analysis.

Understanding AIPerf's testing strategies enables you to write effective tests for new features, debug failing tests, and maintain high code quality.

## Table of Contents

1. [Testing Philosophy](#testing-philosophy)
2. [Test Structure and Organization](#test-structure-and-organization)
3. [Pytest Configuration](#pytest-configuration)
4. [Unit Testing Patterns](#unit-testing-patterns)
5. [Integration Testing](#integration-testing)
6. [Async Testing](#async-testing)
7. [Mocking Strategies](#mocking-strategies)
8. [Fixture Patterns](#fixture-patterns)
9. [Parametrized Testing](#parametrized-testing)
10. [Testing Services](#testing-services)
11. [Testing ZMQ Communication](#testing-zmq-communication)
12. [Testing Metrics](#testing-metrics)
13. [Testing Configuration](#testing-configuration)
14. [Test Coverage](#test-coverage)
15. [Performance Testing](#performance-testing)
16. [Continuous Integration](#continuous-integration)
17. [Test Debugging](#test-debugging)
18. [Best Practices](#best-practices)
19. [Key Takeaways](#key-takeaways)

## Testing Philosophy

AIPerf's testing philosophy emphasizes comprehensive coverage, fast execution, and reliability.

### Core Principles

1. **Test Behavior, Not Implementation**: Tests should verify what code does, not how it does it.
2. **Fast Tests Enable Rapid Development**: Tests must run quickly to enable frequent execution.
3. **Isolated Tests Are Reliable Tests**: Each test should be independent and repeatable.
4. **Clear Tests Are Living Documentation**: Test code should be readable and self-explanatory.
5. **Comprehensive Coverage Prevents Regressions**: High coverage catches bugs early.

### Test Pyramid

```
           /\
          /  \         E2E Tests (Few)
         /____\        - Full system integration
        /      \       - Slow but comprehensive
       /________\
      /          \     Integration Tests (Some)
     /            \    - Multiple components
    /______________\   - Medium speed
   /                \
  /                  \ Unit Tests (Many)
 /____________________\- Single component
                       - Fast and focused
```

AIPerf focuses on:
- **Many unit tests**: Fast, focused, comprehensive
- **Some integration tests**: Verify component interactions
- **Few E2E tests**: Full system validation (optional)

### Test Categories

From `/home/anthony/nvidia/projects/aiperf/tests/conftest.py`:

```python
def pytest_addoption(parser):
    """Add custom command line options for pytest."""
    parser.addoption(
        "--performance",
        action="store_true",
        default=False,
        help="Run performance tests (disabled by default)",
    )
    parser.addoption(
        "--integration",
        action="store_true",
        default=False,
        help="Run integration tests (disabled by default)",
    )
```

**Standard Tests (default):**
- Unit tests
- Component tests
- Fast mocked integration tests

**Performance Tests (`--performance`):**
- Benchmark tests
- Load tests
- Profiling tests

**Integration Tests (`--integration`):**
- Multi-component tests
- External dependency tests
- Slower but realistic tests

## Test Structure and Organization

AIPerf tests mirror the source code structure.

### Directory Structure

```
tests/
├── conftest.py                       # Shared fixtures
├── __init__.py
├── logging/
│   ├── __init__.py
│   ├── test_aiperf_logger.py        # Logger unit tests
│   └── test_logging_mixins.py       # Mixin tests
├── metrics/
│   ├── conftest.py                  # Metric fixtures
│   ├── __init__.py
│   ├── test_ttft_metric.py          # TTFT metric tests
│   ├── test_request_latency_metric.py
│   └── test_metrics_registry.py     # Registry tests
├── workers/
│   ├── conftest.py
│   ├── __init__.py
│   ├── test_worker.py               # Worker unit tests
│   └── test_worker_manager.py       # Manager tests
├── clients/
│   ├── http/
│   │   ├── conftest.py              # HTTP client fixtures
│   │   ├── test_aiohttp_client.py   # Client tests
│   │   └── test_sse_utils.py        # SSE tests
│   └── openai/
│       └── test_openai_aiohttp.py
├── config/
│   ├── test_user_config.py
│   ├── test_service_config.py
│   └── test_config_validators.py
└── comms/
    ├── mock_zmq.py                  # Mock ZMQ for testing
    └── __init__.py
```

### Test File Naming

```
# Pattern: test_{module_name}.py
test_aiperf_logger.py     # Tests aiperf_logger.py
test_worker.py            # Tests worker.py
test_ttft_metric.py       # Tests ttft_metric.py

# Pattern: test_{feature}.py (for integration tests)
test_end_to_end.py
test_multiprocess_workflow.py
```

### Test Class Naming

```python
# Pattern: Test{ClassName}
class TestAIPerfLogger:
    """Tests for AIPerfLogger class."""
    pass

class TestWorkerService:
    """Tests for WorkerService class."""
    pass

# Pattern: Test{Feature} (for feature tests)
class TestRequestCancellation:
    """Tests for request cancellation feature."""
    pass
```

### Test Function Naming

```python
# Pattern: test_{behavior}__{condition}
def test_logger_initialization():
    """Test that logger initializes correctly."""
    pass

def test_exception_logging__includes_exc_info():
    """Test exception logging includes exc_info."""
    pass

def test_compute_ttft__with_valid_record():
    """Test TTFT computation with valid record."""
    pass

def test_compute_ttft__with_missing_first_token__raises_error():
    """Test TTFT raises error when first token is missing."""
    pass
```

## Pytest Configuration

AIPerf's pytest configuration from `/home/anthony/nvidia/projects/aiperf/pyproject.toml`:

```toml
[tool.pytest.ini_options]
# Basic pytest configuration
testpaths = ["tests"]
asyncio_mode = "auto"
asyncio_default_fixture_loop_scope = "function"
```

### Configuration Options

**testpaths = ["tests"]:**
- Pytest searches `tests/` directory for tests
- Enables running `pytest` without arguments

**asyncio_mode = "auto":**
- Automatically detects async test functions
- No need for `@pytest.mark.asyncio` decorator
- Requires pytest-asyncio

**asyncio_default_fixture_loop_scope = "function":**
- Each test gets its own event loop
- Ensures test isolation
- Prevents event loop reuse issues

### Custom Markers

From `/home/anthony/nvidia/projects/aiperf/tests/conftest.py`:

```python
def pytest_configure(config):
    """Configure custom markers."""
    config.addinivalue_line(
        "markers",
        "performance: marks tests as performance tests (disabled by default, use --performance to enable)",
    )
    config.addinivalue_line(
        "markers",
        "integration: marks tests as integration tests (disabled by default, use --integration to enable)",
    )
```

Usage:

```python
@pytest.mark.performance
def test_logger_performance():
    """Performance test for logger."""
    pass

@pytest.mark.integration
def test_end_to_end_workflow():
    """Integration test for full workflow."""
    pass
```

Run specific markers:

```bash
# Run performance tests
pytest tests/ --performance

# Run integration tests
pytest tests/ --integration

# Run both
pytest tests/ --performance --integration
```

### Marker Collection

From `/home/anthony/nvidia/projects/aiperf/tests/conftest.py`:

```python
def pytest_collection_modifyitems(config, items):
    """Skip performance and integration tests unless their respective options are given."""
    performance_enabled = config.getoption("--performance")
    integration_enabled = config.getoption("--integration")

    skip_performance = pytest.mark.skip(
        reason="performance tests disabled (use --performance to enable)"
    )
    skip_integration = pytest.mark.skip(
        reason="integration tests disabled (use --integration to enable)"
    )

    for item in items:
        if "performance" in item.keywords and not performance_enabled:
            item.add_marker(skip_performance)
        if "integration" in item.keywords and not integration_enabled:
            item.add_marker(skip_integration)
```

This automatically skips performance and integration tests unless explicitly enabled.

## Unit Testing Patterns

Unit tests verify individual functions and methods in isolation.

### Basic Unit Test

```python
def test_logger_initialization():
    """Test that logger initializes correctly."""
    logger = AIPerfLogger("test")
    assert logger._logger.name == "test"
```

### Testing Return Values

```python
def test_compute_ttft__returns_correct_value():
    """Test TTFT computation returns correct value."""
    record = create_record(
        start_ns=100,
        responses=[150],  # First response at 150ns
    )

    ttft = compute_ttft(record)

    assert ttft == 50  # 150 - 100 = 50ns
```

### Testing Exceptions

```python
def test_compute_ttft__with_missing_first_token__raises_value_error():
    """Test TTFT raises ValueError when first token missing."""
    record = create_record(
        start_ns=100,
        responses=[],  # No responses
    )

    with pytest.raises(ValueError, match="No first token"):
        compute_ttft(record)
```

### Testing State Changes

```python
def test_worker_increments_request_count():
    """Test that worker increments request count."""
    worker = WorkerService("worker_0", config)

    initial_count = worker.request_count
    worker.process_request(request)

    assert worker.request_count == initial_count + 1
```

### Testing Side Effects

```python
def test_logger_emits_log_to_handler(mock_handler):
    """Test logger emits log to registered handler."""
    logger = AIPerfLogger("test")
    logger.addHandler(mock_handler)

    logger.info("Test message")

    mock_handler.emit.assert_called_once()
    record = mock_handler.emit.call_args[0][0]
    assert record.getMessage() == "Test message"
```

## Integration Testing

Integration tests verify multiple components work together.

### Multi-Component Test

```python
@pytest.mark.integration
async def test_worker_manager_creates_workers():
    """Test worker manager creates and manages workers."""
    config = ServiceConfig(max_workers=3)
    manager = WorkerManager(config)

    await manager.start()

    assert len(manager.workers) == 3
    assert all(worker.is_running for worker in manager.workers)

    await manager.stop()

    assert all(not worker.is_running for worker in manager.workers)
```

### Testing Communication

```python
@pytest.mark.integration
async def test_worker_receives_request_from_manager(mock_zmq_communication):
    """Test worker receives and processes request from manager."""
    manager = WorkerManager(config)
    worker = WorkerService("worker_0", config)

    await manager.start()
    await worker.start()

    # Manager sends request
    request = Request(id="req_1", data="test")
    await manager.send_request(request)

    # Worker receives and processes
    await asyncio.sleep(0.1)  # Give time to process

    # Verify worker processed request
    assert worker.request_count == 1

    await manager.stop()
    await worker.stop()
```

### Testing End-to-End Workflows

```python
@pytest.mark.integration
async def test_full_benchmark_workflow():
    """Test complete benchmark workflow from start to finish."""
    # Setup configuration
    user_config = UserConfig(
        endpoint=EndpointConfig(url="http://localhost:8000"),
        sessions=SessionsConfig(max_workers=2, max_requests=10),
    )
    service_config = ServiceConfig()

    # Run benchmark
    controller = SystemController(user_config, service_config)
    await controller.start()
    results = await controller.run_benchmark()
    await controller.stop()

    # Verify results
    assert results.request_count == 10
    assert results.metrics["ttft"].avg > 0
    assert results.metrics["request_latency"].avg > 0
```

## Async Testing

AIPerf is heavily async; pytest-asyncio enables testing async code.

### Basic Async Test

```python
async def test_async_function():
    """Test async function."""
    result = await async_operation()
    assert result == expected_value
```

No `@pytest.mark.asyncio` needed with `asyncio_mode = "auto"`.

### Testing Async Context Managers

```python
async def test_async_context_manager():
    """Test async context manager."""
    async with AsyncResource() as resource:
        assert resource.is_acquired
        await resource.use()

    assert not resource.is_acquired  # Released on exit
```

### Testing Async Generators

```python
async def test_async_generator():
    """Test async generator."""
    results = []

    async for item in stream_responses():
        results.append(item)
        if len(results) >= 5:
            break

    assert len(results) == 5
    assert all(isinstance(item, Response) for item in results)
```

### Testing Timeouts

```python
async def test_operation_respects_timeout():
    """Test operation respects timeout."""
    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(slow_operation(), timeout=0.1)
```

### Testing Concurrent Operations

```python
async def test_concurrent_requests():
    """Test concurrent request handling."""
    requests = [create_request(i) for i in range(10)]

    results = await asyncio.gather(
        *[process_request(req) for req in requests]
    )

    assert len(results) == 10
    assert all(result.success for result in results)
```

### Testing Background Tasks

```python
async def test_background_task_runs_periodically():
    """Test background task executes periodically."""
    service = Service()
    await service.start()

    # Wait for task to execute multiple times
    await asyncio.sleep(0.3)  # Task runs every 0.1s

    assert service.task_execution_count >= 3

    await service.stop()
```

## Mocking Strategies

Mocking isolates code under test from external dependencies.

### Mock with unittest.mock

```python
from unittest.mock import Mock, patch

def test_worker_logs_error_on_failure():
    """Test worker logs error when request fails."""
    worker = WorkerService("worker_0", config)
    worker.logger = Mock()

    # Simulate failure
    worker.client.post_request = Mock(side_effect=Exception("Connection failed"))

    worker.process_request(request)

    # Verify error logged
    worker.logger.exception.assert_called_once()
```

### AsyncMock for Async Functions

```python
from unittest.mock import AsyncMock

async def test_worker_processes_request():
    """Test worker processes request."""
    worker = WorkerService("worker_0", config)
    worker.client.post_request = AsyncMock(return_value=response)

    result = await worker.process_request(request)

    assert result == response
    worker.client.post_request.assert_called_once_with(request)
```

### Patching Functions

```python
@patch("aiperf.workers.worker.time.perf_counter_ns")
def test_timing_measurement(mock_time):
    """Test timing measurement."""
    mock_time.side_effect = [100, 200]  # Start, end

    duration = measure_operation()

    assert duration == 100  # 200 - 100
```

### Patching Classes

```python
@patch("aiperf.workers.worker.AioHttpClient")
def test_worker_creates_client(MockClient):
    """Test worker creates HTTP client."""
    mock_client = Mock()
    MockClient.return_value = mock_client

    worker = WorkerService("worker_0", config)

    MockClient.assert_called_once()
    assert worker.client == mock_client
```

### Mock Configuration

```python
def test_service_uses_config_timeout():
    """Test service uses configured timeout."""
    config = Mock()
    config.timeout = 30.0

    service = Service(config)

    assert service.timeout == 30.0
```

### Verifying Calls

```python
def test_logger_called_with_correct_message():
    """Test logger called with correct message."""
    logger = Mock()

    log_message(logger, "Test message")

    logger.info.assert_called_once_with("Test message")
```

### Call Count Assertions

```python
def test_retry_attempts_three_times():
    """Test retry logic attempts three times."""
    operation = Mock(side_effect=Exception("Fail"))

    with pytest.raises(Exception):
        retry_operation(operation, max_retries=3)

    assert operation.call_count == 3
```

## Fixture Patterns

Fixtures provide reusable test setup.

### Basic Fixture

From `/home/anthony/nvidia/projects/aiperf/tests/conftest.py`:

```python
@pytest.fixture
def user_config() -> UserConfig:
    """Create test user configuration."""
    config = UserConfig(endpoint=EndpointConfig(model_names=["test-model"]))
    return config
```

Usage:

```python
def test_uses_user_config(user_config):
    """Test that uses user config fixture."""
    assert user_config.endpoint.model_names == ["test-model"]
```

### Fixture with Setup and Teardown

```python
@pytest.fixture
async def running_service():
    """Create and start service, then stop after test."""
    service = Service(config)
    await service.start()

    yield service

    await service.stop()
```

Usage:

```python
async def test_service_processes_request(running_service):
    """Test service processes request while running."""
    result = await running_service.process(request)
    assert result.success
```

### Parametrized Fixtures

```python
@pytest.fixture(params=[1, 2, 5, 10])
def worker_count(request):
    """Parametrized fixture for worker count."""
    return request.param
```

Usage:

```python
def test_creates_correct_worker_count(worker_count):
    """Test creates correct number of workers."""
    # This test runs 4 times with worker_count = 1, 2, 5, 10
    manager = WorkerManager(max_workers=worker_count)
    assert len(manager.workers) == worker_count
```

### Fixture Scope

```python
# Function scope (default): New instance per test
@pytest.fixture(scope="function")
def function_scoped():
    return create_object()

# Class scope: New instance per test class
@pytest.fixture(scope="class")
def class_scoped():
    return create_object()

# Module scope: New instance per module
@pytest.fixture(scope="module")
def module_scoped():
    return create_object()

# Session scope: One instance for entire test session
@pytest.fixture(scope="session")
def session_scoped():
    return create_object()
```

### Autouse Fixtures

From `/home/anthony/nvidia/projects/aiperf/tests/conftest.py`:

```python
@pytest.fixture(autouse=True)
def no_sleep(monkeypatch) -> None:
    """
    Patch asyncio.sleep with a no-op to prevent test delays.

    This ensures tests don't need to wait for real sleep calls.
    """

    async def fast_sleep(*args, **kwargs):
        await real_sleep(0)  # Relinquish time slice

    monkeypatch.setattr(asyncio, "sleep", fast_sleep)
```

This fixture runs automatically for every test, speeding up tests that use `asyncio.sleep()`.

### Factory Fixtures

```python
@pytest.fixture
def create_request():
    """Factory fixture to create requests."""
    def _create(request_id: str, **kwargs):
        return Request(id=request_id, **kwargs)
    return _create
```

Usage:

```python
def test_multiple_requests(create_request):
    """Test with multiple requests."""
    req1 = create_request("req_1", data="data1")
    req2 = create_request("req_2", data="data2")
    assert req1.id != req2.id
```

### Shared Fixtures (conftest.py)

Place fixtures in `conftest.py` to share across tests:

```python
# tests/conftest.py
@pytest.fixture
def user_config():
    """Shared user config fixture."""
    return UserConfig(...)

# tests/metrics/conftest.py
@pytest.fixture
def metric_records():
    """Metric-specific fixture."""
    return [create_record(...) for _ in range(10)]
```

## Parametrized Testing

Parametrization runs the same test with different inputs.

### Basic Parametrization

```python
@pytest.mark.parametrize("level,expected", [
    ("DEBUG", True),
    ("INFO", True),
    ("WARNING", True),
    ("INVALID", False),
])
def test_is_valid_level(level, expected):
    """Test level validation."""
    assert AIPerfLogger.is_valid_level(level) == expected
```

This runs 4 separate tests with different parameters.

### Multiple Parameters

```python
@pytest.mark.parametrize("status_code,reason,error_text", [
    (400, "Bad Request", "Invalid request format"),
    (401, "Unauthorized", "Authentication failed"),
    (404, "Not Found", "Resource not found"),
    (500, "Internal Server Error", "Server error occurred"),
])
async def test_http_error_handling(status_code, reason, error_text):
    """Test HTTP error response handling."""
    # Test implementation
    pass
```

### Parametrizing Fixtures

```python
@pytest.fixture(params=[1, 10, 100])
def record_count(request):
    """Parametrized record count."""
    return request.param

def test_processes_all_records(record_count):
    """Test processes all records."""
    records = [create_record() for _ in range(record_count)]
    results = process_records(records)
    assert len(results) == record_count
```

### Named Parameters

```python
@pytest.mark.parametrize("timeout_ms,expected_seconds", [
    pytest.param(1000, 1.0, id="1_second"),
    pytest.param(5000, 5.0, id="5_seconds"),
    pytest.param(30000, 30.0, id="30_seconds"),
])
def test_timeout_conversion(timeout_ms, expected_seconds):
    """Test timeout conversion."""
    assert convert_ms_to_s(timeout_ms) == expected_seconds
```

### Combining Parametrization

```python
@pytest.mark.parametrize("worker_count", [1, 5, 10])
@pytest.mark.parametrize("request_count", [10, 100, 1000])
def test_worker_scaling(worker_count, request_count):
    """Test worker scaling with different loads."""
    # This runs 9 tests (3 × 3 combinations)
    manager = create_manager(worker_count)
    results = manager.process_requests(request_count)
    assert len(results) == request_count
```

## Testing Services

Testing AIPerf services requires handling lifecycle and async operations.

### Testing Service Initialization

```python
def test_worker_service_initialization():
    """Test worker service initializes correctly."""
    worker = WorkerService("worker_0", config)

    assert worker.worker_id == "worker_0"
    assert worker.config == config
    assert not worker.is_running
```

### Testing Service Lifecycle

```python
async def test_service_lifecycle():
    """Test service start and stop."""
    service = Service(config)

    assert not service.is_running

    await service.start()
    assert service.is_running

    await service.stop()
    assert not service.is_running
```

### Testing Lifecycle Hooks

```python
async def test_service_runs_startup_hook():
    """Test service runs startup hook."""
    service = Service(config)
    service._startup_called = False

    async def startup_hook():
        service._startup_called = True

    service.on_startup(startup_hook)
    await service.start()

    assert service._startup_called

    await service.stop()
```

### Testing Background Tasks

```python
async def test_background_task_executes():
    """Test background task executes."""
    service = Service(config)
    execution_count = 0

    @background_task(immediate=True, interval=0.1)
    async def task():
        nonlocal execution_count
        execution_count += 1

    service._background_task = task
    await service.start()
    await asyncio.sleep(0.3)
    await service.stop()

    assert execution_count >= 3
```

## Testing ZMQ Communication

Testing ZMQ communication uses mocks to avoid real sockets.

### Mock ZMQ Fixture

From `/home/anthony/nvidia/projects/aiperf/tests/comms/mock_zmq.py`:

```python
@pytest.fixture
def mock_zmq_communication():
    """Mock ZMQ communication for testing."""
    mock = MagicMock()
    mock.publish_calls = []
    mock.subscribe_calls = []

    async def mock_publish(message):
        mock.publish_calls.append(message)

    async def mock_subscribe(message_type, callback):
        mock.subscribe_calls.append((message_type, callback))

    mock.publish = mock_publish
    mock.subscribe = mock_subscribe

    return mock
```

### Testing Message Publishing

```python
async def test_service_publishes_message(mock_zmq_communication):
    """Test service publishes message."""
    service = Service(communication=mock_zmq_communication)

    message = RequestMessage(id="req_1")
    await service.publish(message)

    assert len(mock_zmq_communication.publish_calls) == 1
    assert mock_zmq_communication.publish_calls[0] == message
```

### Testing Message Subscription

```python
async def test_service_subscribes_to_messages(mock_zmq_communication):
    """Test service subscribes to messages."""
    service = Service(communication=mock_zmq_communication)

    async def callback(message):
        pass

    await service.subscribe(RequestMessage, callback)

    assert len(mock_zmq_communication.subscribe_calls) == 1
    msg_type, cb = mock_zmq_communication.subscribe_calls[0]
    assert msg_type == RequestMessage
```

## Testing Metrics

Testing metrics uses helper functions from conftest.

### Helper Functions

From `/home/anthony/nvidia/projects/aiperf/tests/metrics/conftest.py`:

```python
def create_record(
    start_ns: int = 100,
    responses: list[int] | None = None,
    input_tokens: int | None = None,
    output_tokens_per_response: int = 1,
    error: ErrorDetails | None = None,
) -> ParsedResponseRecord:
    """Simple helper to create test records with sensible defaults."""
    responses = responses or [start_ns + 50]

    request = RequestRecord(
        start_perf_ns=start_ns,
        timestamp_ns=start_ns,
        end_perf_ns=responses[-1] if responses else start_ns,
        error=error,
    )

    response_data = [
        ParsedResponse(perf_ns=perf_ns, data=TextResponseData(text="test"))
        for perf_ns in responses
    ]

    return ParsedResponseRecord(
        request=request,
        responses=response_data,
        input_token_count=input_tokens,
        output_token_count=len(responses) * output_tokens_per_response,
    )
```

### Testing Metric Computation

```python
def test_ttft_metric_computes_correctly():
    """Test TTFT metric computes correctly."""
    record = create_record(
        start_ns=100,
        responses=[150, 200, 250],  # First response at 150ns
    )

    metric = TTFTMetric()
    result = metric.parse_record(record, {})

    assert result == 50  # 150 - 100 = 50ns
```

### Testing Aggregate Metrics

```python
def test_request_count_aggregates_correctly():
    """Test request count aggregates correctly."""
    records = [create_record() for _ in range(10)]

    metric = RequestCountMetric()
    for record in records:
        value = metric.parse_record(record, {})
        metric.aggregate_value(value)

    assert metric.current_value == 10
```

### Testing Derived Metrics

```python
def test_throughput_derives_from_count_and_duration():
    """Test throughput derives from count and duration."""
    metric_results = {
        "request_count": 100,
        "benchmark_duration": 10.0,  # 10 seconds
    }

    metric = RequestThroughputMetric()
    throughput = metric.derive_value(metric_results)

    assert throughput == 10.0  # 100 requests / 10 seconds
```

### Testing Metrics Pipeline

From `/home/anthony/nvidia/projects/aiperf/tests/metrics/conftest.py`:

```python
def run_simple_metrics_pipeline(
    records: list[ParsedResponseRecord], *metrics_to_test: MetricTagT
) -> MetricResultsDict:
    """Run a simple metrics triple stage pipeline."""
    metrics = [
        MetricRegistry.get_class(tag)()
        for tag in MetricRegistry.create_dependency_order_for(metrics_to_test)
    ]

    metric_results = MetricResultsDict()
    for record in records:
        metric_dict = MetricRecordDict()
        for metric in metrics:
            if metric.type in [MetricType.RECORD, MetricType.AGGREGATE]:
                metric_dict[metric.tag] = metric.parse_record(record, metric_dict)

        for metric in metrics:
            if metric.type == MetricType.AGGREGATE:
                metric.aggregate_value(metric_dict[metric.tag])
                metric_results[metric.tag] = metric.current_value

    for metric in metrics:
        if metric.type == MetricType.DERIVED:
            metric_results[metric.tag] = metric.derive_value(metric_results)

    return metric_results
```

Usage:

```python
def test_metrics_pipeline():
    """Test complete metrics pipeline."""
    records = [create_record() for _ in range(10)]

    results = run_simple_metrics_pipeline(
        records,
        "ttft",
        "request_latency",
        "request_count",
    )

    assert "ttft" in results
    assert "request_latency" in results
    assert results["request_count"] == 10
```

## Testing Configuration

Testing configuration validation and loading.

### Testing Config Validation

```python
def test_user_config_validates_endpoint():
    """Test user config validates endpoint URL."""
    with pytest.raises(ValidationError):
        UserConfig(endpoint=EndpointConfig(url=""))
```

### Testing Config Defaults

```python
def test_service_config_uses_defaults():
    """Test service config uses default values."""
    config = ServiceConfig()

    assert config.log_level == "INFO"
    assert config.max_workers == 10
    assert config.timeout == 30.0
```

### Testing Config Overrides

```python
def test_user_config_overrides_defaults():
    """Test user config overrides default values."""
    config = UserConfig(
        sessions=SessionsConfig(max_workers=20),
    )

    assert config.sessions.max_workers == 20
```

### Testing Config Loading

```python
def test_load_config_from_yaml(tmp_path):
    """Test loading config from YAML file."""
    config_file = tmp_path / "config.yaml"
    config_file.write_text("""
    endpoint:
      url: http://localhost:8000
    sessions:
      max_workers: 5
    """)

    config = UserConfig.from_yaml(config_file)

    assert config.endpoint.url == "http://localhost:8000"
    assert config.sessions.max_workers == 5
```

## Test Coverage

Measuring and improving test coverage.

### Running Coverage

```bash
# Run tests with coverage
pytest tests/ --cov=aiperf

# Generate HTML report
pytest tests/ --cov=aiperf --cov-report=html

# Open report
open htmlcov/index.html

# Show missing lines
pytest tests/ --cov=aiperf --cov-report=term-missing
```

### Coverage Output

```
Name                                Stmts   Miss  Cover   Missing
-----------------------------------------------------------------
aiperf/__init__.py                      5      0   100%
aiperf/workers/worker.py              150     10    93%   45-52, 78-80
aiperf/metrics/ttft_metric.py          45      2    96%   23, 67
aiperf/common/logging.py               80      5    94%   102-106
-----------------------------------------------------------------
TOTAL                                1500     75    95%
```

### Coverage Goals

AIPerf aims for:
- **Overall coverage: 90%+**
- **Critical paths: 95%+**
- **New code: 100%**

### Improving Coverage

```python
# Bad: Untested error path
def function(value):
    if value < 0:
        raise ValueError("Negative value")  # Untested!
    return value * 2

# Good: Test both paths
def test_function_with_positive_value():
    assert function(5) == 10

def test_function_with_negative_value():
    with pytest.raises(ValueError):
        function(-5)
```

### Coverage Exclusions

```python
# Exclude from coverage with pragma comment
def debug_only_function():  # pragma: no cover
    """Function only used for debugging."""
    print("Debug info")

# Exclude entire block
if TYPE_CHECKING:  # pragma: no cover
    from typing import SomeType
```

## Performance Testing

Performance tests validate speed and efficiency.

### Marking Performance Tests

```python
@pytest.mark.performance
def test_logger_lazy_evaluation_performance():
    """Test lazy evaluation performance."""
    logger = AIPerfLogger("test")
    logger.set_level(_INFO)  # DEBUG disabled

    # Measure time for 10000 calls
    start = time.perf_counter()
    for _ in range(10000):
        logger.debug(lambda: f"Expensive: {expensive_computation()}")
    duration = time.perf_counter() - start

    # Should be fast (lazy evaluation skips computation)
    assert duration < 0.1  # Less than 100ms
```

### Comparative Performance Tests

From `/home/anthony/nvidia/projects/aiperf/tests/logging/test_aiperf_logger.py`:

```python
def compare_logger_performance(
    aiperf_logger_func,
    standard_logger_func,
    number=10_000,
    tries=5,
    min_speed_up=None,
    max_slow_down=None,
):
    """Compare AIPerf logger vs standard logger performance."""
    aiperf_times = [
        timeit.timeit(aiperf_logger_func, number=number) for _ in range(tries)
    ]
    standard_times = [
        timeit.timeit(standard_logger_func, number=number) for _ in range(tries)
    ]

    aiperf_avg_time = sum(aiperf_times) / tries
    standard_avg_time = sum(standard_times) / tries
    speed_up = standard_avg_time / aiperf_avg_time

    if min_speed_up is not None:
        assert speed_up >= min_speed_up
```

### Benchmark Tests

```python
@pytest.mark.performance
def test_metric_computation_throughput():
    """Test metric computation throughput."""
    records = [create_record() for _ in range(1000)]
    metric = TTFTMetric()

    start = time.perf_counter()
    for record in records:
        metric.parse_record(record, {})
    duration = time.perf_counter() - start

    throughput = len(records) / duration

    # Should process at least 10000 records/second
    assert throughput > 10000
```

## Continuous Integration

Running tests in CI pipelines.

### GitHub Actions Example

```yaml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ["3.10", "3.11"]

    steps:
    - uses: actions/checkout@v3

    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: ${{ matrix.python-version }}

    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install -e ".[dev]"

    - name: Run tests
      run: |
        pytest tests/ -n auto --cov=aiperf --cov-report=xml

    - name: Upload coverage
      uses: codecov/codecov-action@v3
      with:
        file: ./coverage.xml
```

### Running Tests Locally

```bash
# Run all tests (fast)
pytest tests/ -n auto

# Run with coverage
pytest tests/ -n auto --cov=aiperf --cov-report=html

# Run specific category
pytest tests/logging/ -v

# Run with markers
pytest tests/ --performance --integration
```

## Test Debugging

Debugging failing tests effectively.

### Running Single Test

```bash
# Run specific test
pytest tests/logging/test_aiperf_logger.py::TestAIPerfLogger::test_logger_initialization -v

# With output
pytest tests/logging/test_aiperf_logger.py::TestAIPerfLogger::test_logger_initialization -v -s

# Drop into debugger on failure
pytest tests/logging/test_aiperf_logger.py::TestAIPerfLogger::test_logger_initialization --pdb
```

### Print Debugging

```python
def test_something():
    """Test something."""
    value = compute_value()
    print(f"DEBUG: value = {value}")  # Use -s flag to see output
    assert value == expected
```

### Debugger

```python
def test_something():
    """Test something."""
    value = compute_value()

    # Drop into debugger
    import pdb; pdb.set_trace()

    assert value == expected
```

### Verbose Output

```bash
# Show test names
pytest tests/ -v

# Show print statements
pytest tests/ -s

# Show local variables on failure
pytest tests/ -l

# Very verbose
pytest tests/ -vv
```

### Capturing Logs

```python
def test_something(caplog):
    """Test with log capture."""
    with caplog.at_level(logging.DEBUG):
        function_that_logs()

    assert "Expected message" in caplog.text
```

## Best Practices

### 1. Write Tests First (TDD)

```python
# Write test first
def test_compute_ttft():
    """Test TTFT computation."""
    record = create_record(start_ns=100, responses=[150])
    assert compute_ttft(record) == 50

# Then implement
def compute_ttft(record):
    return record.responses[0].perf_ns - record.start_perf_ns
```

### 2. Test One Thing Per Test

```python
# Bad: Tests multiple things
def test_worker():
    worker = WorkerService("worker_0", config)
    assert worker.worker_id == "worker_0"
    assert not worker.is_running
    worker.start()
    assert worker.is_running
    worker.process_request(request)
    assert worker.request_count == 1

# Good: Separate tests
def test_worker_initialization():
    worker = WorkerService("worker_0", config)
    assert worker.worker_id == "worker_0"

def test_worker_starts():
    worker = WorkerService("worker_0", config)
    worker.start()
    assert worker.is_running

def test_worker_processes_request():
    worker = WorkerService("worker_0", config)
    worker.process_request(request)
    assert worker.request_count == 1
```

### 3. Use Descriptive Test Names

```python
# Bad
def test_1():
    pass

# Good
def test_compute_ttft__with_valid_record__returns_correct_value():
    pass
```

### 4. Arrange-Act-Assert Pattern

```python
def test_something():
    # Arrange: Set up test data
    record = create_record(start_ns=100, responses=[150])
    metric = TTFTMetric()

    # Act: Perform the operation
    result = metric.parse_record(record, {})

    # Assert: Verify the result
    assert result == 50
```

### 5. Use Fixtures for Common Setup

```python
# Bad: Duplicate setup
def test_1():
    config = UserConfig(...)
    # test code

def test_2():
    config = UserConfig(...)
    # test code

# Good: Fixture
@pytest.fixture
def user_config():
    return UserConfig(...)

def test_1(user_config):
    # test code

def test_2(user_config):
    # test code
```

### 6. Don't Test Implementation Details

```python
# Bad: Tests internal implementation
def test_worker_internal_state():
    worker = WorkerService("worker_0", config)
    assert worker._internal_counter == 0  # Private attribute!

# Good: Tests behavior
def test_worker_processes_request():
    worker = WorkerService("worker_0", config)
    result = worker.process_request(request)
    assert result.success
```

### 7. Keep Tests Fast

```python
# Bad: Slow test
def test_something():
    time.sleep(5)  # Slow!
    assert True

# Good: Fast test with mock
@pytest.fixture(autouse=True)
def fast_sleep(monkeypatch):
    async def instant_sleep(*args):
        pass
    monkeypatch.setattr(asyncio, "sleep", instant_sleep)

async def test_something():
    await asyncio.sleep(5)  # Instant!
    assert True
```

### 8. Test Edge Cases

```python
def test_compute_ttft():
    # Normal case
    record = create_record(start_ns=100, responses=[150])
    assert compute_ttft(record) == 50

    # Edge case: No responses
    record = create_record(start_ns=100, responses=[])
    with pytest.raises(ValueError):
        compute_ttft(record)

    # Edge case: Zero duration
    record = create_record(start_ns=100, responses=[100])
    assert compute_ttft(record) == 0
```

### 9. Use Parametrization for Similar Tests

```python
# Bad: Duplicate tests
def test_level_debug():
    assert is_valid_level("DEBUG")

def test_level_info():
    assert is_valid_level("INFO")

def test_level_warning():
    assert is_valid_level("WARNING")

# Good: Parametrized
@pytest.mark.parametrize("level", ["DEBUG", "INFO", "WARNING"])
def test_valid_levels(level):
    assert is_valid_level(level)
```

### 10. Clean Up Resources

```python
# Bad: Leaves resources open
def test_something():
    file = open("test.txt", "w")
    file.write("test")
    assert file.tell() > 0

# Good: Cleans up
def test_something():
    with open("test.txt", "w") as file:
        file.write("test")
        assert file.tell() > 0
```

## Key Takeaways

1. **AIPerf uses pytest with pytest-asyncio** for comprehensive test coverage of both sync and async code.

2. **Test organization mirrors source structure**, with `test_{module}.py` files testing `{module}.py` implementations.

3. **Pytest configuration enables auto async detection** with `asyncio_mode = "auto"` and function-scoped event loops.

4. **Custom markers (performance, integration)** allow selective test execution with `--performance` and `--integration` flags.

5. **Fixtures provide reusable test setup** in `conftest.py` files, with scope control and autouse options.

6. **Parametrized tests reduce duplication** by running the same test with different inputs via `@pytest.mark.parametrize`.

7. **Mocking with unittest.mock and AsyncMock** isolates code under test from external dependencies.

8. **Testing async code requires AsyncMock** for async functions, async context managers, and async generators.

9. **ZMQ communication testing uses mocks** to avoid real socket creation and enable fast, isolated tests.

10. **Metric testing uses helper functions** like `create_record()` and `run_simple_metrics_pipeline()` from conftest.py.

11. **Test coverage should exceed 90%** overall, with 95%+ for critical paths and 100% for new code.

12. **Performance tests use @pytest.mark.performance** and are disabled by default to keep regular test runs fast.

13. **The Arrange-Act-Assert pattern** structures tests clearly: set up data, perform operation, verify result.

14. **Test one thing per test** to make failures easy to diagnose and tests easy to understand.

15. **Keep tests fast** by mocking slow operations, using fixtures efficiently, and patching time-consuming calls like `asyncio.sleep`.

---

[Previous: Chapter 39 - Code Style Guide](chapter-39-code-style-guide.md) | [Index](INDEX.md) | [Next: Chapter 41 - Debugging Techniques](chapter-41-debugging-techniques.md)
