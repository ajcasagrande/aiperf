<!--
# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
-->
# Worker Service Test Suite

This directory contains comprehensive tests for the AIPerf worker service module, ensuring system robustness and correctness.

## Test Structure

### Files

- `conftest.py` - Shared pytest fixtures for all worker tests
- `test_worker.py` - Comprehensive tests for the Worker class
- `test_worker_protocols.py` - Tests for protocol compliance and interfaces
- `test_runner.py` - Convenient test runner script
- `__init__.py` - Package initialization file

### Test Categories

#### 1. Worker Initialization Tests (`TestWorkerInitialization`)
- Service initialization and configuration
- Dependency injection and setup
- Communication client setup
- Shutdown procedures

#### 2. Credit Drop Processing Tests (`TestCreditDropProcessing`)
- Successful credit drop handling
- Warmup vs. regular task processing
- Error handling during processing
- Communication with various clients
- Metrics tracking

#### 3. Inference API Tests (`TestInferenceApiCalls`)
- Successful API calls
- Error handling and recovery
- Delayed execution scenarios
- Request formatting and conversion
- Response processing

#### 4. Health Check Tests (`TestHealthCheck`)
- Health message creation
- Periodic health reporting
- Error handling in health checks
- Process monitoring

#### 5. Metrics Tests (`TestWorkerMetrics`)
- Metrics initialization
- Counter updates for different scenarios
- Warmup vs. regular task metrics
- Failure tracking

#### 6. Error Handling Tests (`TestErrorHandling`)
- Exception handling in various scenarios
- Graceful degradation
- Error recovery mechanisms
- Logging and error reporting

#### 7. Protocol Compliance Tests (`TestWorkerProtocol`)
- Interface compliance verification
- Method availability
- Service type validation
- Health message generation

#### 8. Edge Cases Tests (`TestWorkerEdgeCases`)
- Boundary conditions
- Null/None value handling
- Concurrent operations
- Resource constraints
- Performance under load

#### 9. Protocol Interface Tests (`TestWorkerCommunicationsProtocol`)
- Protocol definition validation
- Mock implementation testing
- Type hint verification
- Runtime behavior validation

## Fixtures

### Configuration Fixtures
- `worker_service_config` - Service configuration for testing
- `worker_user_config` - User configuration for testing

### Mock Fixtures
- `mock_inference_client` - Mock inference client
- `mock_request_converter` - Mock request converter
- `mock_model_endpoint` - Mock model endpoint information
- `mock_communication_clients` - Mock communication clients
- `mock_communication` - Mock communication layer

### Data Fixtures
- `sample_credit_drop_message` - Sample credit drop message
- `sample_warmup_credit_drop_message` - Sample warmup credit drop
- `sample_conversation_response` - Sample conversation response
- `sample_turn` - Sample conversation turn
- `sample_request_record` - Sample successful request record
- `sample_failed_request_record` - Sample failed request record

### Service Fixtures
- `worker_instance` - Worker instance with mocked dependencies
- `initialized_worker` - Fully initialized worker ready for testing

### Utility Fixtures
- `mock_time_functions` - Mock time functions for consistent testing
- `mock_asyncio_sleep` - Mock asyncio.sleep for testing
- `command_message` - Sample command message

## Running Tests

### Using pytest directly
```bash
# Run all worker tests
pytest aiperf/tests/worker/

# Run with verbose output
pytest -v aiperf/tests/worker/

# Run specific test class
pytest aiperf/tests/worker/test_worker.py::TestWorkerInitialization

# Run specific test method
pytest aiperf/tests/worker/test_worker.py::TestWorkerInitialization::test_worker_initialization

# Run with coverage
pytest --cov=aiperf.services.worker --cov-report=html aiperf/tests/worker/
```

### Using the test runner script
```bash
# Run all tests
python aiperf/tests/worker/test_runner.py

# Run with verbose output
python aiperf/tests/worker/test_runner.py --verbose

# Run with coverage report
python aiperf/tests/worker/test_runner.py --coverage

# Run specific test pattern
python aiperf/tests/worker/test_runner.py -k "test_worker_init"

# Run only async tests
python aiperf/tests/worker/test_runner.py -m "asyncio"

# Run tests in parallel
python aiperf/tests/worker/test_runner.py --parallel 4

# Stop on first failure
python aiperf/tests/worker/test_runner.py --fail-fast
```

## Test Philosophy

### Comprehensive Coverage
- Tests cover all major code paths and edge cases
- Both success and failure scenarios are tested
- Error handling is thoroughly validated
- Performance and concurrency aspects are considered

### Isolated Testing
- Each test is independent and can run in isolation
- Extensive use of mocks to avoid external dependencies
- Consistent test environment through fixtures
- Clean setup and teardown for each test

### Realistic Scenarios
- Tests simulate real-world usage patterns
- Edge cases and boundary conditions are covered
- Error conditions are tested realistically
- Performance characteristics are validated

### Maintainability
- Clear test naming and documentation
- Modular test structure with reusable fixtures
- Comprehensive assertions with meaningful error messages
- Easy to extend and modify as code evolves

## Best Practices

### Test Organization
- Group related tests into classes
- Use descriptive test names that explain the scenario
- Include docstrings for complex test scenarios
- Use parameterized tests for multiple similar scenarios

### Fixtures
- Use fixtures for complex setup that's shared across tests
- Prefer scoped fixtures to reduce test execution time
- Mock external dependencies to ensure test isolation
- Use async fixtures for async test scenarios

### Assertions
- Use specific assertions that provide meaningful error messages
- Test both positive and negative cases
- Verify not just return values but also side effects
- Check metrics and state changes where applicable

### Error Testing
- Test exception handling explicitly
- Verify graceful degradation under error conditions
- Test recovery mechanisms
- Ensure proper cleanup in error scenarios

## Dependencies

### Required Packages
- `pytest` - Testing framework
- `pytest-asyncio` - Async testing support
- `pytest-mock` - Advanced mocking capabilities
- `pytest-cov` - Coverage reporting (optional)
- `pytest-xdist` - Parallel test execution (optional)

### Optional Packages
- `pytest-html` - HTML test reports
- `pytest-benchmark` - Performance benchmarking
- `pytest-timeout` - Test timeout handling

## Contributing

When adding new tests:

1. Follow the existing test structure and naming conventions
2. Add appropriate fixtures to `conftest.py` if they're reusable
3. Include both positive and negative test cases
4. Document complex test scenarios with docstrings
5. Ensure tests are isolated and don't depend on external state
6. Run the full test suite to ensure no regressions
7. Consider adding performance and edge case tests for new features

## Troubleshooting

### Common Issues

1. **Import Errors**: Ensure the virtual environment is activated and all dependencies are installed
2. **Async Test Failures**: Make sure to use `@pytest.mark.asyncio` for async tests
3. **Mock Issues**: Verify that mocks are properly configured and reset between tests
4. **Fixture Scope Issues**: Check fixture scopes and ensure proper cleanup

### Debug Tips

1. Use `pytest -v -s` for verbose output with print statements
2. Add `import pdb; pdb.set_trace()` for debugging
3. Use `pytest --tb=long` for detailed traceback information
4. Check fixture dependencies and ensure proper initialization order
