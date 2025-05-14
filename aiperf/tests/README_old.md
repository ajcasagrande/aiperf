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
# AIPerf Testing Framework

This directory contains a comprehensive testing framework for the AIPerf services, built using pytest. The framework provides utilities and base classes for testing all aspects of service functionality, with a focus on asynchronous messaging and service interactions.

## Features

- **Mock Communication**: Built-in utilities for mocking and tracking message publishing and subscription.
- **Service Base Testing**: Common tests for all services based on the `ServiceBase` class.
- **Parameterized Tests**: Support for parameterized testing of message handlers.
- **Async Testing Utilities**: Helper methods for testing asynchronous code and handling timeouts.
- **Message Flow Simulation**: Utilities for simulating message flow between services.

## Directory Structure

```
tests/
├── conftest.py               # Shared pytest fixtures
├── base_test_service.py      # Base test class for services
├── utils/
│   ├── async_test_utils.py   # Utilities for testing async code
│   └── message_mocks.py      # Utilities for mocking messages
├── comms/                    # Communication layer tests
│   └── test_zmq_communication.py # Tests for ZMQ communication
└── services/                 # Service-specific tests
    ├── test_system_controller.py
    ├── test_dataset_manager.py
    ├── test_worker.py
    ├── test_worker_manager.py
    ├── test_timing_manager.py
    ├── test_post_processor_manager.py
    ├── test_records_manager.py
    └── ... (other service tests)
```

## Using the Framework

### Basic Service Test

To create a test for a specific service:

1. Create a new test file in the `services` directory
2. Inherit from `BaseServiceTest`
3. Implement the `service_class` fixture
4. Add service-specific tests

Example:

```python
from aiperf.tests.base_test_service import BaseServiceTest, async_fixture
import pytest

class TestMyService(BaseServiceTest):
    @pytest.fixture
    def service_class(self):
        return MyService

    async def test_my_service_specific_functionality(self, service_under_test):
        # The service_under_test fixture provides an initialized service
        service = await async_fixture(service_under_test)
        # Test service-specific functionality
        pass
```

### Working with Async Fixtures

The framework includes an `async_fixture` helper function that safely handles both async generators and regular objects:

```python
async def async_fixture(fixture):
    """Manually await an async fixture if it's an async generator, otherwise return it."""
    # Check if the fixture is an async generator or a regular object
    if hasattr(fixture, "__aiter__"):
        # It's an async generator, so we need to await it
        async for value in fixture:
            return value
    else:
        # It's a regular object, just return it
        return fixture
```

Always use this helper when working with fixtures that might be async generators:

```python
service = await async_fixture(service_under_test)
```

### Testing Message Handling

The framework provides utilities for testing message handling:

```python
from aiperf.tests.utils.message_mocks import MessageTestUtils

async def test_handle_message(self, service_under_test, mock_communication):
    service = await async_fixture(service_under_test)

    # Create a mock response
    message = MessageTestUtils.create_mock_message(
        MessageClass,
        param1="value1",
        param2="value2"
    )

    # Simulate receiving the response
    await MessageTestUtils.simulate_message_receive(
        service, Topic.MY_TOPIC, message
    )

    # Verify the service handled the response correctly
    # ...
```

### Parameterized Testing

Use `pytest.mark.parametrize` to test different message variations:

```python
@pytest.mark.parametrize("command", ["start", "stop", "restart"])
async def test_command_handling(self, service_under_test, command):
    service = await async_fixture(service_under_test)
    # Test handling of different commands
    # ...
```

Or use the provided `MessageParamBuilder`:

```python
from aiperf.tests.utils.message_mocks import MessageParamBuilder

param_sets = MessageParamBuilder.build_message_params(
    message_class=CommandMessage,
    field_variations={
        "command": ["start", "stop", "restart"],
        "priority": ["high", "low"]
    },
    required_fields={"target_service_id": "test_id"}
)

@pytest.mark.parametrize("params", param_sets)
async def test_command_variations(self, service_under_test, params):
    service = await async_fixture(service_under_test)
    # Test with different parameter combinations
    # ...
```



For more complex async testing scenarios, consider implementing additional utilities as needed for your specific test cases.

### Service State Expectations

When testing service initialization, be aware that services may transition between states during test execution. The framework's tests are designed to handle multiple valid states:

```python
async def test_service_initialization(self, service_under_test):
    service = await async_fixture(service_under_test)
    assert service.service_id is not None
    assert service.service_type is not None

    # Service may be in one of several valid states after initialization
    assert service.state in [
        ServiceState.INITIALIZING,
        ServiceState.READY,
        ServiceState.UNKNOWN,
    ]
```

## Mocking Dependencies

Use the `mock_dependent_services` fixture to mock dependencies:

```python
async def test_service_with_dependencies(self, service_under_test, mock_dependent_services):
    service = await async_fixture(service_under_test)

    # Access mock services
    mock_system_controller = mock_dependent_services["system_controller"]
    mock_worker = mock_dependent_services["worker"]

    # Configure mock behaviors
    mock_system_controller.get_configuration.return_value = {"key": "value"}

    # Test interactions with other services
    # ...
```

## Testing Full Workflows

Test complete service workflows using message flow simulation:

```python
async def test_workflow(self, service_under_test, mock_communication, simulate_message_flow):
    service = await async_fixture(service_under_test)

    # Start the service
    await service._start()

    # Simulate a response flow
    await simulate_message_flow(
        service,
        Topic.COMMAND,
        {"command": "start_benchmark", "benchmark_id": "123"}
    )

    # Verify the results
    # ...
```

## Testing Communication Layer

The `comms` directory contains tests for the communication layer implementations:

```python
@pytest.mark.asyncio
class TestZMQCommunication:
    """Tests for the ZMQ communication class."""

    @pytest.fixture
    def zmq_communication(self, mock_config):
        """Return a ZMQCommunication instance for testing."""
        with patch("zmq.asyncio.Context", MagicMock()) as mock_context:
            mock_context.return_value = MagicMock()
            comm = ZMQCommunication(config=mock_config)
            return comm

    async def test_publish_message(self, zmq_communication, test_message):
        """Test publishing messages."""
        # Test ZMQ-specific functionality
        pass
```
```

## Troubleshooting

If you encounter issues with async tests:

1. Ensure the `pytest-asyncio` plugin is installed and configured properly
2. Use the `async_fixture` helper function when working with fixtures that might be async generators
3. Add `@pytest.mark.asyncio` decorator to all async test functions
4. Check that the `asyncio_mode = auto` is set in pytest.ini
5. Verify that there are no conflicting event loop policies set elsewhere in the code
