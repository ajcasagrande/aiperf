<!--
# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
-->
# Base Test Service Classes

This directory contains base test service classes that provide common testing functionality for AIPerf services. These classes help reduce boilerplate code and ensure consistent testing patterns across the project.

## Available Base Classes

### `BaseTestService`

The basic test class for testing services that inherit from `BaseService`. Provides:
- Pre-configured fixtures for service components
- Mocked communication dependencies
- Helper assertion methods
- Standardized test patterns

### `BaseTestServiceWithMixins`

Extended test class for services that use specific mixins like `PullClientMixin`, `ReplyClientMixin`, `ProcessHealthMixin`, etc. Provides:
- All functionality from `BaseTestService`
- Fixtures for common mixin combinations
- Mixin-specific assertion helpers

## Usage Examples

### Basic Service Testing

```python
from tests.common.conftest import BaseTestService

class TestMyService(BaseTestService):
    def test_service_initialization(self, base_test_service):
        service = base_test_service

        # Use helper assertions
        self.assert_service_initialized(service)
        self.assert_communication_setup(service)

        # Test your service functionality
        assert service.service_type is not None
```

### Service with Mixins

```python
from tests.common.conftest import BaseTestServiceWithMixins

class TestMyServiceWithMixins(BaseTestServiceWithMixins):
    def test_pull_client_service(self, test_service_with_pull_client):
        service = test_service_with_pull_client

        self.assert_service_initialized(service)
        self.assert_pull_client_setup(service)

        # Test pull client functionality
```

### Custom Service Testing

```python
from tests.common.conftest import BaseTestServiceWithMixins
import pytest

class TestCustomService(BaseTestServiceWithMixins):
    @pytest.fixture
    def my_custom_service(
        self,
        mock_service_config,
        mock_user_config,
        mock_service_id,
        mock_communication_factory,
    ):
        from aiperf.my_module.my_service import MyService

        return MyService(
            service_config=mock_service_config,
            user_config=mock_user_config,
            service_id=mock_service_id,
        )

    def test_my_service_functionality(self, my_custom_service):
        service = my_custom_service

        # Test service-specific behavior
        result = service.my_custom_method()
        assert result == expected_value
```

## Available Fixtures

### Base Fixtures
- `mock_service_config`: Pre-configured ServiceConfig
- `mock_user_config`: Pre-configured UserConfig
- `mock_service_id`: Test service ID
- `mock_comm_address`: Test communication address
- `mock_communication_factory`: Mocked communication factory

### Service Fixtures
- `base_test_service`: Basic testable service
- `test_service_with_pull_client`: Service with PullClientMixin
- `test_service_with_reply_client`: Service with ReplyClientMixin
- `test_service_with_process_health`: Service with ProcessHealthMixin

### Mixin Fixtures
- Individual mixin fixtures for isolated testing
- Pre-configured with mocked dependencies

## Helper Assertion Methods

### `BaseTestService` Methods
- `assert_service_initialized(service)`: Verifies basic service setup
- `assert_communication_setup(service)`: Verifies communication setup

### `BaseTestServiceWithMixins` Methods
- `assert_pull_client_setup(service)`: Verifies pull client configuration
- `assert_reply_client_setup(service)`: Verifies reply client configuration
- `assert_process_health_setup(service)`: Verifies process health setup

## Benefits

1. **Reduced Boilerplate**: No need to set up mocks manually in each test
2. **Consistency**: Standardized testing patterns across services
3. **Maintainability**: Central location for test configuration changes
4. **Reusability**: Easy to extend for new service types
5. **Best Practices**: Follows pytest fixture patterns and DRY principles

## Migration from Old Tests

If you have existing tests that manually set up service mocks:

1. Change your test class to inherit from `BaseTestService` or `BaseTestServiceWithMixins`
2. Replace manual mock setup with the provided fixtures
3. Use the helper assertion methods instead of manual assertions
4. Remove redundant fixture definitions from local conftest.py files

Example migration:

```python
# Old way
class TestMyService:
    @pytest.fixture
    def service(self, monkeypatch):
        # 20+ lines of manual mock setup
        mock_comms = Mock()
        # ... lots of repetitive mock code

    def test_something(self, service):
        assert service.config is not None
        # ... manual assertions

# New way
class TestMyService(BaseTestService):
    def test_something(self, base_test_service):
        service = base_test_service
        self.assert_service_initialized(service)
        # ... test actual functionality
```
