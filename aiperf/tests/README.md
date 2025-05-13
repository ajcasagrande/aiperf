<!--
#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#  http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
-->
# AI Perf Testing Framework

This document provides a comprehensive guide to the AIPerf testing framework, explaining its architecture, how to use it, and how to troubleshoot common issues.

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Core Components](#core-components)
- [Writing Tests](#writing-tests)
- [Running Tests](#running-tests)
- [Advanced Features](#advanced-features)
- [Troubleshooting](#troubleshooting)

## Overview

The AIPerf testing framework is built on pytest and provides a robust structure for testing service-based components. It's designed to make testing asynchronous services easier by abstracting common test patterns and providing utilities for mocking dependencies.

The framework focuses on:
- **Service lifecycle testing**: Initialize, start, run, and stop services
- **Message handling**: Simulate and verify message passing between services
- **State transitions**: Test service state management
- **Async behavior**: Safely test asynchronous code with proper mocking

## Architecture

The testing framework is built around a base test class (`BaseServiceTest`) that provides a foundation for service-specific test implementations.

### Key Files and Directories

```
aiperf/tests/
├── base_test_service.py  # Core testing class for services
├── conftest.py           # Shared pytest fixtures
├── utils/                # Testing utilities
│   ├── async_test_utils.py   # Async testing helpers
│   └── message_mocks.py      # Message mocking utilities
└── services/             # Service-specific test implementations
```

## Core Components

### BaseServiceTest Class

The `BaseServiceTest` class (in `base_test_service.py`) provides:

- Standard fixtures for service testing
- Common test methods for service lifecycle
- Utilities for service status testing
- Tools for message handling verification

Key fixtures provided:

- `no_sleep`: Replaces `asyncio.sleep` with a no-op function
- `service_class`: Abstract fixture that subclasses must override to provide the class of service to initialize
- `service_under_test`: Creates an initialized service instance with properly set up communication

Standard test methods:

- `test_service_initialization`: Verifies correct service setup
- `test_service_start_stop`: Tests service start and stop lifecycle
- `test_service_heartbeat`: Confirms heartbeat functionality
- `test_service_registration`: Tests service registration
- `test_service_status_update`: Checks status updates
- `test_service_all_states`: Tests all service state transitions

### Common Fixtures

Common fixtures defined in `conftest.py`:

- `service_id`: Generates unique service IDs
- `service_config`: Creates a standard test configuration
- `mock_communication`: Mock communication object for testing

### Utilities

The testing framework includes utilities for:

- **Async testing** (`async_test_utils.py`): Tools for testing asynchronous code
- **Message handling** (`message_mocks.py`): Utilities for message creation and handling

## Writing Tests

### Creating a New Service Test

To create tests for a new service:

1. Create a new test file in the `services` directory
2. Create a test class that uses the `BaseServiceTest` class
3. Override the required fixtures
4. Implement service-specific tests

Example:

```python
@pytest.mark.asyncio
class TestMyService:
    """Tests for my custom service."""

    @pytest.fixture
    def service_class(self):
        """Return the service class for testing."""
        return MyService

    @pytest.fixture
    def service_config(self):
        """Return a service configuration for testing."""
        return ServiceConfig(
            # Service-specific configuration
        )

    # Additional service-specific fixtures if needed

    # Service-specific tests
    async def test_my_service_functionality(self, service_under_test):
        """Test specific functionality of my service."""
        service = await async_fixture(service_under_test)
        # Test code here
```

### Testing Message Handling

The framework provides utilities for testing message handling:

```python
from aiperf.tests.utils.message_mocks import MessageTestUtils, message_handler_test
from aiperf.common.enums import Topic
from aiperf.common.models.messages import CommandMessage

# Using the simulate_message_receive utility
async def test_command_handling(self, service_under_test):
    service = await async_fixture(service_under_test)

    command_msg = CommandMessage(command=CommandType.START)
    await MessageTestUtils.simulate_message_receive(
        service, Topic.COMMAND, command_msg
    )
    # Verify expected behavior

# Using the message_handler_test decorator
@message_handler_test(CommandMessage, Topic.COMMAND, command=CommandType.START)
async def test_start_command(self, service, mock_communication, message):
    # Test code here, message is already sent to the service
```

### Testing Async Code

The framework includes a simple utility for testing asynchronous code. The `async_test_utils.py` module provides an `async_noop` function that can be used as a replacement for functions like `asyncio.sleep` or `asyncio.to_thread` in tests:

```python
from aiperf.tests.utils.async_test_utils import async_noop

async def test_with_no_sleep(self):
    # Use the no_sleep fixture to replace asyncio.sleep
    with patch("asyncio.sleep", return_value=async_noop()):
        # Your test code that calls functions using asyncio.sleep
        pass
```

The `BaseServiceTest` class already includes a `no_sleep` fixture that replaces `asyncio.sleep` with the `async_noop` function:

```python
@pytest.fixture
def no_sleep(self):
    """Fixture to replace asyncio.sleep with a no-op."""
    with patch("asyncio.sleep", return_value=async_noop()):
        yield
```

Use this fixture when testing code that would normally sleep or wait:

```python
async def test_service_operation(self, service_under_test, no_sleep):
    service = await async_fixture(service_under_test)

    # The no_sleep fixture will prevent actual sleeping
    # so this test will run quickly
    await service.operation_with_delays()

    # Test assertions
    assert service.some_property == expected_value
```

## Running Tests

### Basic Usage

Run all tests:

```bash
pytest aiperf/tests
```

Run specific test file:

```bash
pytest aiperf/tests/services/test_worker.py
```

Run specific test:

```bash
pytest aiperf/tests/services/test_worker.py::TestWorker::test_worker_initialization
```

### Useful Pytest Options

- `-v`: Verbose output
- `-xvs`: Exit on first failure, verbose, no capture
- `--cov=aiperf`: Run with coverage reporting
- `--cov-report=html`: Generate HTML coverage report

## Advanced Features

### Parameterized Tests

The framework supports pytest's parameterization:

```python
@pytest.mark.parametrize(
    "state",
    [
        ServiceState.INITIALIZING,
        ServiceState.READY,
        ServiceState.RUNNING,
        # ...more states
    ],
)
async def test_service_states(self, service_under_test, state):
    # Test with each state
```

### Async Fixtures

The framework provides support for async fixtures:

```python
async def async_fixture(fixture: T) -> T:
    """Manually await an async fixture if it's an async generator, otherwise return it."""
    if hasattr(fixture, "__aiter__"):
        async for value in fixture:
            return value
    return fixture

# Usage
service = await async_fixture(service_under_test)
```

## Troubleshooting

### Common Issues

1. **"coroutine was never awaited" warnings**:
   - Ensure all async functions are properly awaited
   - Use `create_safe_mock()` to create mocks for async code
   - Check that all async test functions are decorated with `@pytest.mark.asyncio`

2. **Mock communication not capturing messages**:
   - Verify the mock_communication fixture is properly injected
   - Ensure your service is using the mocked communication and not creating a new one
   - Check that the topic is correctly specified

3. **Service stuck in unexpected state**:
   - Use the `no_sleep` fixture to avoid actual sleep delays
   - Check `service.state` before and after operations
   - Verify that all event callbacks are correctly mocked

### Debugging Tips

1. **Trace message flow**:
   - Use `mock_communication.published_messages` to examine messages
   - Check `mock_communication.subscriptions` to verify subscription callbacks

2. **Inspect service state**:
   - Add breakpoints to examine service state during testing
   - Use `print` statements with `pytest -s` to see output during test execution

3. **Check mock behavior**:
   - Verify mock return values and side effects
   - Use `AsyncMockWithTracking` to record call history
