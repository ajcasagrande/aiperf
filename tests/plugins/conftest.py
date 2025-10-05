# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""
Shared fixtures for testing AIPerf plugin system.

Provides mock plugins, entry points, and testing utilities for AIP-001 plugin testing.
"""

from typing import Any
from unittest.mock import MagicMock

import pytest

from aiperf.common.models import ParsedResponseRecord
from aiperf.metrics.metric_dicts import MetricRecordDict

# ============================================================================
# Mock Plugin Classes
# ============================================================================


class MockMetricPlugin:
    """
    Mock metric plugin for testing.

    WHY THIS MATTERS: Metric plugins are the most common plugin type.
    This mock provides a realistic test double that conforms to MetricPluginProtocol.
    """

    tag = "mock_metric"
    header = "Mock Metric"
    unit = "ms"
    flags = 0
    short_header = "Mock"
    display_unit = "ms"
    display_order = 100
    required_metrics = set()

    def _parse_record(
        self, record: ParsedResponseRecord, record_metrics: MetricRecordDict
    ) -> float:
        """Compute mock metric value."""
        return 42.0

    @staticmethod
    def plugin_metadata() -> dict[str, Any]:
        """Return plugin metadata."""
        return {
            "name": "mock_metric",
            "display_name": "Mock Metric Plugin",
            "version": "1.0.0",
            "plugin_type": "metric",
            "aip_version": "001",
            "author": "NVIDIA",
            "license": "Apache-2.0",
        }


class MockEndpointPlugin:
    """Mock endpoint plugin for testing."""

    @staticmethod
    def endpoint_metadata() -> dict[str, Any]:
        """Return endpoint metadata."""
        return {
            "api_version": "v1",
            "supports_streaming": True,
            "supported_content_types": ["application/json"],
        }

    async def send_request(
        self, endpoint_info: Any, payload: dict[str, Any]
    ) -> dict[str, Any]:
        """Mock send request."""
        return {"status": "success", "data": "mock_response"}

    @staticmethod
    def plugin_metadata() -> dict[str, Any]:
        """Return plugin metadata."""
        return {
            "name": "mock_endpoint",
            "display_name": "Mock Endpoint Plugin",
            "version": "1.0.0",
            "plugin_type": "endpoint",
            "aip_version": "001",
        }


class MockDataExporterPlugin:
    """Mock data exporter plugin for testing."""

    def __init__(self, output_dir, config):
        """Initialize exporter."""
        self.output_dir = output_dir
        self.config = config

    async def export(self, results) -> str:
        """Mock export."""
        return "/mock/export/path.json"

    @staticmethod
    def get_export_info() -> dict[str, Any]:
        """Return export format info."""
        return {
            "format": "mock_format",
            "display_name": "Mock Format",
            "file_extension": ".mock",
            "description": "Mock export format",
        }

    @staticmethod
    def plugin_metadata() -> dict[str, Any]:
        """Return plugin metadata."""
        return {
            "name": "mock_exporter",
            "display_name": "Mock Exporter Plugin",
            "version": "1.0.0",
            "plugin_type": "data_exporter",
            "aip_version": "001",
        }


class MockTransportPlugin:
    """Mock transport plugin for testing."""

    async def connect(self, endpoint: str, **kwargs) -> None:
        """Mock connect."""
        pass

    async def send(self, request: Any) -> Any:
        """Mock send."""
        return {"response": "mock_data"}

    async def close(self) -> None:
        """Mock close."""
        pass

    @staticmethod
    def plugin_metadata() -> dict[str, Any]:
        """Return plugin metadata."""
        return {
            "name": "mock_transport",
            "display_name": "Mock Transport Plugin",
            "version": "1.0.0",
            "plugin_type": "transport",
            "aip_version": "001",
        }


class MockProcessorPlugin:
    """Mock processor plugin for testing."""

    def process(self, data: Any) -> Any:
        """Mock process."""
        return {"processed": data}

    @staticmethod
    def plugin_metadata() -> dict[str, Any]:
        """Return plugin metadata."""
        return {
            "name": "mock_processor",
            "display_name": "Mock Processor Plugin",
            "version": "1.0.0",
            "plugin_type": "processor",
            "aip_version": "001",
        }


class MockCollectorPlugin:
    """Mock collector plugin for testing."""

    def collect(self, metrics: dict[str, Any]) -> None:
        """Mock collect."""
        pass

    async def flush(self) -> None:
        """Mock flush."""
        pass

    @staticmethod
    def plugin_metadata() -> dict[str, Any]:
        """Return plugin metadata."""
        return {
            "name": "mock_collector",
            "display_name": "Mock Collector Plugin",
            "version": "1.0.0",
            "plugin_type": "collector",
            "aip_version": "001",
        }


class InvalidMetricPlugin:
    """
    Invalid plugin that doesn't implement required protocol.

    WHY THIS MATTERS: We need to test that validation catches plugins
    that don't conform to their protocols.
    """

    # Missing required attributes and methods
    tag = "invalid_metric"

    @staticmethod
    def plugin_metadata() -> dict[str, Any]:
        """Return plugin metadata."""
        return {
            "name": "invalid_metric",
            "aip_version": "001",
        }


class NoMetadataPlugin:
    """
    Plugin without metadata method.

    WHY THIS MATTERS: Tests that plugins must provide metadata.
    """

    tag = "no_metadata"
    header = "No Metadata"
    unit = "ms"
    flags = 0


class OldAIPVersionPlugin:
    """
    Plugin with unsupported AIP version.

    WHY THIS MATTERS: Tests version compatibility checking.
    """

    tag = "old_aip"
    header = "Old AIP"
    unit = "ms"
    flags = 0

    def _parse_record(self, record, record_metrics):
        return 1.0

    @staticmethod
    def plugin_metadata() -> dict[str, Any]:
        """Return plugin metadata with old AIP version."""
        return {
            "name": "old_aip",
            "aip_version": "000",  # Unsupported version
        }


# ============================================================================
# Mock Entry Points
# ============================================================================


class MockEntryPoint:
    """
    Mock EntryPoint for testing.

    WHY THIS EXISTS: Real EntryPoint objects are immutable, making them
    difficult to mock for testing. This class provides the same interface
    but allows customization of the load() method.
    """

    def __init__(self, name: str, value: str, group: str, load_result: Any = None):
        """
        Initialize mock entry point.

        Args:
            name: Plugin name
            value: Entry point value (module:attribute)
            group: Entry point group (e.g., 'aiperf.metric')
            load_result: What to return when .load() is called
        """
        self.name = name
        self.value = value
        self.group = group
        self._load_result = load_result

        # Create a MagicMock for load so tests can assert on it
        self.load = MagicMock(return_value=load_result, side_effect=self._load_impl)

    def _load_impl(self):
        """Internal load implementation."""
        if self._load_result is not None:
            return self._load_result
        raise ImportError(f"Cannot load {self.name}")

    def __repr__(self):
        """String representation."""
        return f"MockEntryPoint(name={self.name!r}, value={self.value!r}, group={self.group!r})"


def create_mock_entry_point(
    name: str, value: str, group: str, load_result: Any = None
) -> MockEntryPoint:
    """
    Create a mock EntryPoint for testing.

    WHY THIS HELPER EXISTS: EntryPoint objects are typically created by
    importlib.metadata from installed packages. This helper lets us create
    mock entry points without needing to install actual plugin packages.

    Args:
        name: Plugin name
        value: Entry point value (module:attribute)
        group: Entry point group (e.g., 'aiperf.metric')
        load_result: What to return when .load() is called

    Returns:
        Mock EntryPoint that behaves like a real one
    """
    return MockEntryPoint(name=name, value=value, group=group, load_result=load_result)


@pytest.fixture
def mock_metric_entry_point():
    """
    Fixture for a mock metric plugin entry point.

    WHY TEST THIS: Most common plugin type, needs thorough testing.
    """
    return create_mock_entry_point(
        name="mock_metric",
        value="mock_plugin.metric:MockMetricPlugin",
        group="aiperf.metric",
        load_result=MockMetricPlugin,
    )


@pytest.fixture
def mock_endpoint_entry_point():
    """Fixture for a mock endpoint plugin entry point."""
    return create_mock_entry_point(
        name="mock_endpoint",
        value="mock_plugin.endpoint:MockEndpointPlugin",
        group="aiperf.endpoint",
        load_result=MockEndpointPlugin,
    )


@pytest.fixture
def mock_exporter_entry_point():
    """Fixture for a mock data exporter plugin entry point."""
    return create_mock_entry_point(
        name="mock_exporter",
        value="mock_plugin.exporter:MockDataExporterPlugin",
        group="aiperf.data_exporter",
        load_result=MockDataExporterPlugin,
    )


@pytest.fixture
def mock_transport_entry_point():
    """Fixture for a mock transport plugin entry point."""
    return create_mock_entry_point(
        name="mock_transport",
        value="mock_plugin.transport:MockTransportPlugin",
        group="aiperf.transport",
        load_result=MockTransportPlugin,
    )


@pytest.fixture
def mock_processor_entry_point():
    """Fixture for a mock processor plugin entry point."""
    return create_mock_entry_point(
        name="mock_processor",
        value="mock_plugin.processor:MockProcessorPlugin",
        group="aiperf.processor",
        load_result=MockProcessorPlugin,
    )


@pytest.fixture
def mock_collector_entry_point():
    """Fixture for a mock collector plugin entry point."""
    return create_mock_entry_point(
        name="mock_collector",
        value="mock_plugin.collector:MockCollectorPlugin",
        group="aiperf.collector",
        load_result=MockCollectorPlugin,
    )


@pytest.fixture
def invalid_plugin_entry_point():
    """
    Fixture for an invalid plugin that doesn't conform to protocol.

    WHY TEST THIS: Ensures validation catches malformed plugins.
    """
    return create_mock_entry_point(
        name="invalid_metric",
        value="mock_plugin.invalid:InvalidMetricPlugin",
        group="aiperf.metric",
        load_result=InvalidMetricPlugin,
    )


@pytest.fixture
def no_metadata_plugin_entry_point():
    """Fixture for a plugin without metadata."""
    return create_mock_entry_point(
        name="no_metadata",
        value="mock_plugin.nometadata:NoMetadataPlugin",
        group="aiperf.metric",
        load_result=NoMetadataPlugin,
    )


@pytest.fixture
def old_aip_plugin_entry_point():
    """Fixture for a plugin with old AIP version."""
    return create_mock_entry_point(
        name="old_aip",
        value="mock_plugin.oldaip:OldAIPVersionPlugin",
        group="aiperf.metric",
        load_result=OldAIPVersionPlugin,
    )


@pytest.fixture
def failing_entry_point():
    """
    Fixture for an entry point that fails to load.

    WHY TEST THIS: Plugins can fail to load due to import errors,
    missing dependencies, etc. The system must handle this gracefully.
    """
    # Create a custom mock entry point that raises on load
    ep = MockEntryPoint(
        name="failing_plugin",
        value="nonexistent.module:NonexistentClass",
        group="aiperf.metric",
        load_result=None,  # Will raise ImportError in load()
    )
    # Override load to raise specific error
    ep.load = MagicMock(side_effect=ImportError("Module not found"))
    return ep


# ============================================================================
# Collection Fixtures
# ============================================================================


@pytest.fixture
def all_mock_entry_points(
    mock_metric_entry_point,
    mock_endpoint_entry_point,
    mock_exporter_entry_point,
    mock_transport_entry_point,
    mock_processor_entry_point,
    mock_collector_entry_point,
):
    """
    Fixture providing all valid mock entry points organized by group.

    WHY THIS MATTERS: Many tests need to simulate a full plugin ecosystem
    with multiple plugin types. This fixture provides a complete set.
    """
    return {
        "aiperf.metric": [mock_metric_entry_point],
        "aiperf.endpoint": [mock_endpoint_entry_point],
        "aiperf.data_exporter": [mock_exporter_entry_point],
        "aiperf.transport": [mock_transport_entry_point],
        "aiperf.processor": [mock_processor_entry_point],
        "aiperf.collector": [mock_collector_entry_point],
    }


@pytest.fixture
def multiple_plugins_same_group(mock_metric_entry_point):
    """
    Fixture for multiple plugins in the same group.

    WHY TEST THIS: Real deployments will have multiple plugins of the
    same type (e.g., multiple custom metrics). Discovery and loading
    must handle this correctly.
    """
    # Create additional mock metric plugins
    mock_metric_2 = create_mock_entry_point(
        name="mock_metric_2",
        value="mock_plugin.metric2:MockMetricPlugin2",
        group="aiperf.metric",
        load_result=type(
            "MockMetricPlugin2",
            (MockMetricPlugin,),
            {
                "tag": "mock_metric_2",
                "plugin_metadata": lambda: {
                    "name": "mock_metric_2",
                    "aip_version": "001",
                },
            },
        ),
    )

    mock_metric_3 = create_mock_entry_point(
        name="mock_metric_3",
        value="mock_plugin.metric3:MockMetricPlugin3",
        group="aiperf.metric",
        load_result=type(
            "MockMetricPlugin3",
            (MockMetricPlugin,),
            {
                "tag": "mock_metric_3",
                "plugin_metadata": lambda: {
                    "name": "mock_metric_3",
                    "aip_version": "001",
                },
            },
        ),
    )

    return [mock_metric_entry_point, mock_metric_2, mock_metric_3]


@pytest.fixture
def mock_plugin_classes():
    """
    Fixture providing all mock plugin classes.

    WHY THIS MATTERS: Validation and protocol checking tests need
    direct access to plugin classes without going through entry points.
    """
    return {
        "MockMetricPlugin": MockMetricPlugin,
        "MockEndpointPlugin": MockEndpointPlugin,
        "MockDataExporterPlugin": MockDataExporterPlugin,
        "MockTransportPlugin": MockTransportPlugin,
        "MockProcessorPlugin": MockProcessorPlugin,
        "MockCollectorPlugin": MockCollectorPlugin,
        "InvalidMetricPlugin": InvalidMetricPlugin,
        "NoMetadataPlugin": NoMetadataPlugin,
        "OldAIPVersionPlugin": OldAIPVersionPlugin,
    }


# ============================================================================
# Utility Fixtures
# ============================================================================


@pytest.fixture
def clear_discovery_cache():
    """
    Fixture to clear the discovery cache between tests.

    WHY THIS MATTERS: PluginDiscovery uses @lru_cache for performance.
    Tests that modify the plugin environment need to clear this cache
    to see their changes.
    """
    from aiperf.plugins.discovery import PluginDiscovery, discover_plugins

    # Clear caches before test
    PluginDiscovery.discover_all_plugins.cache_clear()
    discover_plugins.cache_clear()

    yield

    # Clear caches after test
    PluginDiscovery.discover_all_plugins.cache_clear()
    discover_plugins.cache_clear()


@pytest.fixture
def clear_registry_singleton():
    """
    Fixture to clear the registry singleton between tests.

    WHY THIS MATTERS: PluginRegistry is a singleton. Tests need to
    reset its state to avoid interference between tests.
    """
    from aiperf.plugins.registry import PluginRegistry

    # Reset singleton
    PluginRegistry._instance = None

    yield

    # Clean up singleton after test
    PluginRegistry._instance = None


@pytest.fixture
def isolated_plugin_environment(clear_discovery_cache, clear_registry_singleton):
    """
    Fixture that provides a completely isolated plugin environment.

    WHY THIS MATTERS: Integration tests need a clean slate without
    interference from previously discovered or loaded plugins.
    """
    yield
    # Cleanup is handled by the dependent fixtures
