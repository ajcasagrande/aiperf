<!--
# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
-->
# AIPerf Plugin System Tests (AIP-001)

This directory contains comprehensive tests for the AIPerf plugin architecture (AIP-001).

## Test Files

### `conftest.py`
Shared fixtures and mock plugins for testing:
- Mock plugin classes for all plugin types (metric, endpoint, exporter, transport, processor, collector)
- Mock entry points for simulating installed plugins
- Invalid/malformed plugin examples for testing error handling
- Utility fixtures for cache clearing and environment isolation

**Key Fixtures:**
- `mock_metric_entry_point` - Mock metric plugin entry point
- `mock_plugin_classes` - Dictionary of all mock plugin classes
- `clear_discovery_cache` - Clears discovery cache between tests
- `clear_registry_singleton` - Resets registry singleton
- `isolated_plugin_environment` - Complete test isolation

### `test_plugin_discovery.py` (532 lines, 18 tests)
Tests for plugin discovery system:
- Discovery of plugins via entry points
- Python 3.9 vs 3.10+ compatibility
- LRU cache behavior
- Error handling for malformed entry points
- Multiple plugins per group

**Why These Tests Matter:**
Discovery is the foundation of the plugin system. These tests ensure we can reliably find plugins across different Python versions and handle errors gracefully.

### `test_plugin_loader.py` (699 lines, 25 tests)
Tests for lazy loading system:
- Lazy loading behavior (load only when needed)
- Plugin caching (avoid redundant loads)
- Error tracking for failed loads
- Thread safety of loading operations
- All plugin types (metric, endpoint, exporter, transport, processor, collector)

**Why These Tests Matter:**
Lazy loading is critical for performance. These tests ensure plugins are loaded efficiently and safely in concurrent scenarios.

### `test_plugin_registry.py` (644 lines, 23 tests)
Tests for plugin registry:
- Singleton pattern implementation
- Enable/disable functionality
- Integration with discovery and loading
- Thread safety of registry operations
- Error reporting

**Why These Tests Matter:**
The registry is the central hub for plugin management. These tests ensure it orchestrates discovery, loading, and validation correctly while maintaining thread safety.

### `test_plugin_validator.py` (692 lines, 28 tests)
Tests for plugin validation:
- Protocol conformance checking
- Metadata structure validation
- AIP version compatibility
- Error reporting for validation failures
- All plugin types

**Why These Tests Matter:**
Validation prevents runtime errors from malformed plugins. These tests ensure only conforming plugins are accepted and clear error messages are provided.

### `test_plugin_integration.py` (694 lines, 20 tests)
Integration tests for complete workflows:
- End-to-end plugin lifecycle (discover → load → validate → execute)
- Multiple plugins coexisting
- Plugin execution in AIPerf context
- Performance characteristics
- Real-world usage scenarios

**Why These Tests Matter:**
Integration tests verify the entire plugin system works together as users would experience it. They catch issues that unit tests might miss.

## Test Coverage

**Total Tests:** 114 tests across 6 test files

**Coverage by Component:**
- Discovery: 18 tests
- Loader: 25 tests
- Registry: 23 tests
- Validator: 28 tests
- Integration: 20 tests

**Coverage by Concern:**
- Core functionality: ~60 tests
- Error handling: ~25 tests
- Thread safety: ~10 tests
- Performance: ~5 tests
- Python version compatibility: ~5 tests
- Integration/workflows: ~20 tests

## Running Tests

### Run all plugin tests:
```bash
pytest tests/plugins/
```

### Run specific test file:
```bash
pytest tests/plugins/test_plugin_discovery.py
```

### Run specific test class:
```bash
pytest tests/plugins/test_plugin_discovery.py::TestPluginDiscoveryBasics
```

### Run specific test:
```bash
pytest tests/plugins/test_plugin_discovery.py::TestPluginDiscoveryBasics::test_discover_all_plugins_returns_dict
```

### Run with coverage:
```bash
pytest tests/plugins/ --cov=aiperf.plugins --cov-report=html
```

### Run integration tests only:
```bash
pytest tests/plugins/test_plugin_integration.py
```

### Run performance tests (disabled by default):
```bash
pytest tests/plugins/ --performance
```

## Testing Philosophy

These tests follow AIPerf's testing philosophy:

1. **Test Outcomes, Not Implementation**
   - We verify plugins can be discovered, loaded, and used
   - We don't test internal data structures or private methods

2. **Clear "WHY TEST THIS" Documentation**
   - Every test has a docstring explaining its purpose
   - Focus on what behavior matters and why

3. **Maintainable Tests**
   - Tests use fixtures to avoid repetition
   - Mock only what's necessary (entry points, not entire system)
   - Tests are independent and can run in any order

4. **Critical Behaviors Only**
   - Tests focus on essential functionality
   - Edge cases that matter (not exhaustive)
   - Real usage scenarios

## Test Organization

Tests are organized by component and concern:

```
conftest.py                    # Shared fixtures
test_plugin_discovery.py       # Entry point discovery
test_plugin_loader.py          # Lazy loading
test_plugin_registry.py        # Registry management
test_plugin_validator.py       # Protocol validation
test_plugin_integration.py     # End-to-end workflows
```

Each test file follows this structure:
1. Module docstring explaining what and why
2. Test classes grouped by functionality
3. Individual tests with clear docstrings
4. Fixtures specific to that file (if any)

## Mock Plugins

The test suite includes mock plugins for all plugin types:

- **MockMetricPlugin** - Example metric plugin
- **MockEndpointPlugin** - Example endpoint plugin
- **MockDataExporterPlugin** - Example exporter plugin
- **MockTransportPlugin** - Example transport plugin
- **MockProcessorPlugin** - Example processor plugin
- **MockCollectorPlugin** - Example collector plugin
- **InvalidMetricPlugin** - Malformed plugin for error testing
- **NoMetadataPlugin** - Plugin without metadata
- **OldAIPVersionPlugin** - Plugin with unsupported AIP version

## Thread Safety Testing

Several tests verify thread safety:
- Concurrent plugin discovery
- Concurrent plugin loading
- Concurrent registry access
- Concurrent enable/disable operations

These tests use Python's `threading` module to spawn multiple threads that access the plugin system simultaneously.

## Performance Testing

Performance tests (marked with `@pytest.mark.performance`) verify:
- Discovery completes quickly (< 100ms for 50 plugins)
- Cached discovery is nearly instant
- Minimal startup overhead (AIP-001 requirement)

Run performance tests with: `pytest tests/plugins/ --performance`

## Python Version Compatibility

Tests verify compatibility with both:
- Python 3.9 (uses `entry_points().select()`)
- Python 3.10+ (uses `entry_points(group=...)`)

Version-specific tests use `@pytest.mark.skipif` to run only on appropriate versions.

## Contributing

When adding new plugin system features:

1. Add tests to appropriate file:
   - Discovery changes → `test_plugin_discovery.py`
   - Loading changes → `test_plugin_loader.py`
   - Registry changes → `test_plugin_registry.py`
   - Validation changes → `test_plugin_validator.py`
   - New workflows → `test_plugin_integration.py`

2. Add necessary fixtures to `conftest.py`

3. Follow existing patterns:
   - Clear docstrings with "WHY TEST THIS"
   - Use fixtures for setup
   - Test behaviors, not implementation
   - Keep tests independent

4. Verify tests pass:
   ```bash
   pytest tests/plugins/ -v
   ```

## Related Documentation

- **AIP-001 Specification**: Plugin system architecture and requirements
- **Developer's Guide**: Chapter on extending AIPerf with plugins
- **Plugin Protocols**: `aiperf/plugins/protocols.py`
- **Plugin Discovery**: `aiperf/plugins/discovery.py`
