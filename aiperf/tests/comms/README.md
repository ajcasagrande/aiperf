<!--
#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
-->
# ZMQ Proxy Testing Suite

This directory contains comprehensive tests for the ZMQ proxy implementations in AIPerf. The test suite is designed to ensure reliability, performance, and correctness of the proxy components that facilitate communication between services.

## Test Philosophy

The test suite follows pytest best practices and focuses on testing **meaningful functionality** rather than trivial implementations. The tests are organized to:

- **Test behavior, not implementation details**: Focus on what the proxies do, not how they do it
- **Ensure reliability under real conditions**: Include integration tests with actual ZMQ sockets
- **Validate performance characteristics**: Test throughput, latency, and resource usage
- **Handle edge cases and errors**: Verify graceful error handling and recovery
- **Provide comprehensive coverage**: Cover all proxy types and configurations

## Test Structure

### Core Test Files

#### `test_zmq_proxies.py`
The main test file containing comprehensive tests for all ZMQ proxy functionality:

- **Configuration Tests**: Validate proxy configurations (TCP/IPC) and address generation
- **Factory Tests**: Test proxy registration and creation through the factory pattern
- **Lifecycle Tests**: Test proxy initialization, running, and shutdown sequences
- **Socket Type Tests**: Verify correct socket types are created for each proxy pattern
- **Integration Tests**: End-to-end message forwarding tests with real ZMQ sockets
- **Error Handling Tests**: Test graceful handling of failures and edge cases

#### `test_zmq_proxy_performance.py`
Performance and load testing focused on:

- **Performance Tests**: Startup time, shutdown time, memory usage
- **Load Tests**: High-volume message forwarding, concurrent clients, fan-out performance
- **Stress Tests**: Rapid start/stop cycles, resource constraints, client disconnections

#### `conftest.py`
Test fixtures and utilities:

- **Context Management**: Real and mock ZMQ contexts
- **Configuration Fixtures**: TCP and IPC proxy configurations
- **Proxy Lifecycle Management**: Context managers for clean proxy setup/teardown
- **Parametrized Fixtures**: Test all proxy types and configurations
- **Error Simulation**: Mock objects for testing failure scenarios

#### `test_runner.py`
Convenient test runner with categorized test execution:

```bash
# Run different test categories
python test_runner.py --unit          # Fast unit tests with mocks
python test_runner.py --integration   # Integration tests with real sockets
python test_runner.py --performance   # Performance benchmarks
python test_runner.py --load          # Load testing
python test_runner.py --stress        # Stress testing
python test_runner.py --all           # All tests

# Additional options
python test_runner.py --unit --verbose --coverage
```

## Test Categories

### Unit Tests (Fast)
- Configuration validation
- Factory registration and creation
- Mocked lifecycle management
- Socket type verification
- Error handling scenarios

**Run with**: `python test_runner.py --unit`

### Integration Tests (Slower)
- Real ZMQ socket communication
- End-to-end message forwarding
- Proxy patterns: PUSH/PULL, PUB/SUB, ROUTER/DEALER
- Multi-client scenarios

**Run with**: `python test_runner.py --integration`

### Performance Tests
- Startup/shutdown timing
- Memory usage validation
- Resource cleanup verification
- Multiple proxy creation

**Run with**: `python test_runner.py --performance`

### Load Tests
- High-volume message forwarding (100+ messages)
- Concurrent clients (5+ simultaneous connections)
- Fan-out performance (multiple subscribers)
- Throughput measurement and validation

**Run with**: `python test_runner.py --load`

### Stress Tests
- Rapid start/stop cycles
- Resource exhaustion simulation
- Client disconnection handling
- Error recovery validation

**Run with**: `python test_runner.py --stress`

## Proxy Types Tested

### PUSH/PULL Proxy (`ZMQPushPullProxy`)
- **Pattern**: Load balancing work distribution
- **Frontend**: PULL socket (receives from PUSH clients)
- **Backend**: PUSH socket (forwards to PULL services)
- **Use Case**: Distributing tasks across worker services

### PUB/SUB Proxy (`ZMQXPubXSubProxy`)
- **Pattern**: Message broadcasting with filtering
- **Frontend**: XSUB socket (receives from PUB clients)
- **Backend**: XPUB socket (forwards to SUB services)
- **Use Case**: Event broadcasting and subscription management

### ROUTER/DEALER Proxy (`ZMQDealerRouterProxy`)
- **Pattern**: Request/reply with load balancing
- **Frontend**: ROUTER socket (receives from DEALER clients)
- **Backend**: DEALER socket (forwards to ROUTER services)
- **Use Case**: Load balancing requests across service instances

## Running Tests

### Quick Start

```bash
# Activate virtual environment
source .venv/bin/activate

# Run all unit tests (fastest)
python test_runner.py --unit --verbose

# Run integration tests
python test_runner.py --integration

# Run with coverage
python test_runner.py --unit --coverage
```

### Advanced Usage

```bash
# Run specific test classes
pytest test_zmq_proxies.py::TestZMQProxyFactory -v

# Run tests with markers
pytest -m "not integration" -v  # Skip integration tests
pytest -m "performance" -v      # Only performance tests

# Run with profiling
pytest test_zmq_proxies.py --profile

# Parallel execution
pytest -n 4 test_zmq_proxies.py
```

### CI/CD Integration

The test suite is designed for CI/CD environments:

```bash
# Fast feedback (unit tests only)
pytest test_zmq_proxies.py -m "not integration and not performance and not load and not stress"

# Full validation (all tests)
pytest test_zmq_proxies.py test_zmq_proxy_performance.py --maxfail=5
```

## Test Design Principles

### 1. Fixture-Based Resource Management
- Use fixtures for ZMQ contexts, configurations, and proxy instances
- Automatic cleanup prevents resource leaks
- Parametrized fixtures enable comprehensive coverage

### 2. Realistic Integration Testing
- Use real ZMQ sockets for integration tests
- Test actual message forwarding, not just mocked behavior
- Validate end-to-end communication patterns

### 3. Performance Validation
- Measure and validate throughput, latency, and resource usage
- Set reasonable performance thresholds
- Test scalability with multiple clients and high message volumes

### 4. Error Resilience
- Test graceful handling of initialization failures
- Validate recovery from client disconnections
- Ensure proper cleanup under error conditions

### 5. Maintainable Test Code
- Clear test naming and documentation
- Reusable fixtures and utilities
- Minimal test interdependencies

## Extending the Tests

### Adding New Test Cases

1. **Identify the test category**: Unit, integration, performance, load, or stress
2. **Choose the appropriate test file**: `test_zmq_proxies.py` or `test_zmq_proxy_performance.py`
3. **Use existing fixtures**: Leverage `conftest.py` fixtures for setup
4. **Follow naming conventions**: `test_<functionality>_<scenario>`
5. **Add appropriate markers**: `@pytest.mark.integration`, `@pytest.mark.performance`, etc.

### Example: Adding a New Integration Test

```python
@pytest.mark.integration
@pytest.mark.asyncio
async def test_custom_proxy_scenario(self, managed_proxy_fixture, temp_ipc_config, zmq_context):
    """Test custom proxy behavior scenario."""
    async with managed_proxy_fixture(
        ZMQProxyType.PUSH_PULL,
        temp_ipc_config,
        start_proxy=True
    ) as (proxy, config):
        # Test implementation here
        pass
```

### Adding New Fixtures

Add specialized fixtures to `conftest.py`:

```python
@pytest.fixture
def custom_test_fixture():
    """Provide custom test setup."""
    # Setup code
    yield test_object
    # Cleanup code
```

## Performance Benchmarks

The test suite includes performance benchmarks with configurable thresholds:

- **Startup Time**: < 1.0 seconds (configurable in `test_proxy_startup_time`)
- **Message Throughput**: > 10 messages/second (configurable in load tests)
- **Fan-out Performance**: > 50 deliveries/second (configurable in pub/sub tests)
- **Memory Usage**: No significant leaks (validated in `test_proxy_memory_cleanup`)

Adjust these thresholds based on your performance requirements and testing environment.

## Troubleshooting

### Common Issues

1. **Port conflicts**: Use IPC sockets for tests to avoid TCP port conflicts
2. **Resource cleanup**: Ensure proper fixture cleanup to prevent ZMQ context issues
3. **Async timing**: Add appropriate sleep delays for socket connection establishment
4. **Test isolation**: Use temporary directories and separate configurations per test

### Debug Tips

```bash
# Run with maximum verbosity
pytest test_zmq_proxies.py -vvv --tb=long

# Run single test with debugging
pytest test_zmq_proxies.py::TestClass::test_method -v --pdb

# Check test coverage
pytest --cov=aiperf.common.comms.zmq --cov-report=html
```

## Dependencies

The test suite requires:

- `pytest` - Test framework
- `pytest-asyncio` - Async test support
- `pytest-cov` - Coverage reporting
- `pyzmq` - ZMQ Python bindings
- Standard library: `asyncio`, `tempfile`, `unittest.mock`

These are included in the project's `dev` dependencies in `pyproject.toml`.
