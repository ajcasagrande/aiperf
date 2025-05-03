# AIPerf Testing Guide

This document provides comprehensive information on how to run and write tests for the AIPerf project.

## Table of Contents

- [Prerequisites](#prerequisites)
- [Running Tests](#running-tests)
- [Test Categories](#test-categories)
- [Writing Tests](#writing-tests)
- [Test Fixtures](#test-fixtures)
- [Mocking](#mocking)
- [Test Coverage](#test-coverage)
- [CI Integration](#ci-integration)
- [Troubleshooting](#troubleshooting)

## Prerequisites

Ensure you have the following dependencies installed:

```bash
pip install pytest pytest-asyncio pytest-cov pytest-xdist pytest-mock pyyaml
```

For testing Kubernetes functionality, additional dependencies are required:

```bash
pip install kubernetes
```

## Running Tests

### Run all tests

```bash
pytest aiperf/tests/
```

### Run tests with coverage report

```bash
pytest --cov=aiperf aiperf/tests/
```

Detailed HTML coverage report:

```bash
pytest --cov=aiperf --cov-report=html aiperf/tests/
```

### Run specific test modules

```bash
# Run all Kubernetes tests
pytest aiperf/tests/system/test_kubernetes*.py

# Run all API client tests
pytest aiperf/tests/api/
```

### Run tests with specific markers

```bash
# Run only asyncio tests
pytest -m asyncio aiperf/tests/

# Run only Kubernetes tests
pytest -m kubernetes aiperf/tests/
```

### Run tests in parallel

```bash
pytest -xvs -n auto aiperf/tests/
```

## Test Categories

The tests are organized by component:

- **CLI Tests**: `aiperf/tests/cli/`
  - Tests for CLI commands, argument parsing and execution
  - Tests for worker CLI functionality

- **System Tests**: `aiperf/tests/system/`
  - Tests for system controller
  - Tests for Kubernetes integration
  - Tests for other system-level components

- **Config Tests**: `aiperf/tests/config/`
  - Tests for configuration loading and validation

- **API Tests**: `aiperf/tests/api/`
  - Tests for API clients
  - Tests for client factory

- **Common Tests**: `aiperf/tests/common/`
  - Tests for communication classes
  - Tests for shared utilities

- **Worker Tests**: `aiperf/tests/workers/`
  - Tests for worker implementation

- **Other Component Tests**: 
  - Tests for dataset, timing, metrics, and processors

## Writing Tests

### Best Practices

1. **Use pytest fixtures** for test setup and teardown
2. **Parameterize tests** to reduce duplication
3. **Mock external dependencies** like API endpoints, file systems, etc.
4. **Use descriptive test names** that explain what is being tested
5. **Follow the arrange-act-assert pattern**:
   - Arrange: Set up test data and conditions
   - Act: Perform the action being tested
   - Assert: Check the results

### Test Structure Example

```python
# Imports
import pytest
from unittest.mock import patch, MagicMock, AsyncMock

# Components being tested
from aiperf.some_module import SomeClass

class TestSomeClass:
    """Tests for SomeClass."""
    
    @pytest.fixture
    def sample_config(self):
        """Create a sample configuration."""
        return {
            "key1": "value1",
            "key2": "value2"
        }
    
    @pytest.mark.parametrize("input_value,expected_result", [
        (1, 2),
        (2, 4),
        (3, 6)
    ])
    def test_some_method(self, input_value, expected_result, sample_config):
        """Test some_method with various inputs."""
        # Arrange
        instance = SomeClass(sample_config)
        
        # Act
        result = instance.some_method(input_value)
        
        # Assert
        assert result == expected_result
    
    @pytest.mark.asyncio
    async def test_async_method(self, sample_config):
        """Test an async method."""
        # Arrange
        instance = SomeClass(sample_config)
        
        # Act
        result = await instance.async_method()
        
        # Assert
        assert result is True
```

## Test Fixtures

Common test fixtures are defined in `aiperf/tests/conftest.py`. Here are the key fixtures available:

- `sample_aiperf_config`: A sample AIPerf configuration
- `mock_kubernetes_client`: A mocked Kubernetes client for testing
- `mock_kubernetes_config`: A sample Kubernetes configuration
- `mock_zmq_context`: A mocked ZMQ context for testing

### Creating Custom Fixtures

```python
@pytest.fixture
def custom_fixture():
    """Description of the fixture."""
    # Setup
    resource = setup_resource()
    
    yield resource
    
    # Teardown
    cleanup_resource(resource)
```

## Mocking

### Mocking Asynchronous Functions

Use `AsyncMock` from `unittest.mock` to mock async functions:

```python
from unittest.mock import AsyncMock

async def test_async_function():
    with patch("module.async_function", new_callable=AsyncMock) as mock_func:
        mock_func.return_value = "mocked_result"
        result = await some_function_that_calls_async_function()
        assert result == "expected_result"
```

### Mocking Kubernetes

When testing Kubernetes functionality:

```python
@pytest.mark.asyncio
async def test_kubernetes_function(mock_kubernetes_client):
    # The mock_kubernetes_client fixture provides a mocked kubernetes client
    apps_api = mock_kubernetes_client.AppsV1Api.return_value
    apps_api.create_namespaced_deployment.return_value = {"metadata": {"name": "test-deployment"}}
    
    # Test code that uses kubernetes client
    ...
```

### Mocking Communication Classes

When testing communication:

```python
@pytest.mark.asyncio
async def test_communication(mock_zmq_context):
    # The mock_zmq_context fixture provides mocked ZMQ sockets
    mock_context, mock_pub_socket, mock_sub_socket, mock_req_socket, mock_rep_socket = mock_zmq_context
    
    # Test code that uses ZMQ communication
    ...
```

## Test Coverage

Aim for high test coverage, especially for critical components. Use pytest-cov to measure coverage:

```bash
pytest --cov=aiperf --cov-report=term aiperf/tests/
```

## CI Integration

The tests are integrated with CI systems to run automatically on pull requests and commits to main branches.

The CI pipeline runs:
1. Linting checks
2. Unit tests
3. Coverage reporting
4. Integration tests (when applicable)

## Troubleshooting

### Common Issues

1. **Missing Fixtures**: Ensure that required fixtures are imported or defined in your test module or conftest.py.

2. **Asyncio Errors**: Make sure to use `@pytest.mark.asyncio` for async tests and `pytest-asyncio` is installed.

3. **Import Errors**: Check that the module paths are correct and the required modules are installed.

4. **Timeouts in Tests**: Some tests may time out due to slow execution or hanging async operations. Check for infinite loops or missing awaits.

5. **ZMQ Context Errors**: ZMQ can sometimes leave hanging contexts between tests. Use the `mock_zmq_context` fixture to avoid these issues.

### Debugging Tips

1. Use `pytest -xvs` for verbose output and to stop on first failure.

2. Add print statements with `pytest -xvs` to inspect variables.

3. Use `pytest --trace` for even more detailed debugging.

4. For complex async tests, add delays or logging to troubleshoot timing issues. 