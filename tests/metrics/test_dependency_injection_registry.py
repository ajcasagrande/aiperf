# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

import pytest
from unittest.mock import Mock, patch

from dependency_injector import providers

from aiperf.common.enums import MetricFlags, MetricType
from aiperf.common.exceptions import MetricTypeError
from aiperf.common.models import ParsedResponseRecord
from aiperf.metrics import BaseRecordMetric, BaseDerivedMetric
from aiperf.metrics.dependency_injection_registry import (
    DependencyInjectionMetricRegistry,
    MetricContainer,
    MetricFactory,
    inject_metric,
)
from aiperf.metrics.metric_dicts import MetricRecordDict, MetricResultsDict


class MockMetric(BaseRecordMetric[int]):
    """Mock metric for testing."""

    tag = "mock_metric"
    header = "Mock Metric"
    unit = "count"
    type = MetricType.RECORD
    flags = MetricFlags.NONE
    required_metrics = None

    def _parse_record(self, record: ParsedResponseRecord, record_metrics: MetricRecordDict) -> int:
        return 42


class MockDependentMetric(BaseDerivedMetric[float]):
    """Mock metric that depends on another metric."""

    tag = "mock_dependent_metric"
    header = "Mock Dependent Metric"
    unit = "ratio"
    type = MetricType.DERIVED
    flags = MetricFlags.NONE
    required_metrics = {"mock_metric"}

    def _derive_value(self, metric_results: MetricResultsDict) -> float:
        mock_value = metric_results.get("mock_metric", 0)
        return float(mock_value) * 2.0


class MockService:
    """Mock service for dependency injection testing."""

    def __init__(self, value: str = "default"):
        self.value = value

    def get_value(self) -> str:
        return self.value


class TestMetricContainer:
    """Test the MetricContainer class."""

    def test_container_creation(self):
        """Test creating a metric container."""
        container = MetricContainer()
        assert container is not None
        assert hasattr(container, 'config')

    def test_container_provider_addition(self):
        """Test adding providers to the container."""
        container = MetricContainer()

        # Add a singleton provider
        provider = providers.Singleton(MockService, value="test")
        setattr(container, "mock_service", provider)

        # Test the provider works
        service = container.mock_service()
        assert isinstance(service, MockService)
        assert service.get_value() == "test"

        # Test singleton behavior
        service2 = container.mock_service()
        assert service is service2


class TestMetricFactory:
    """Test the MetricFactory class."""

    def test_factory_creation(self):
        """Test creating a metric factory."""
        container = MetricContainer()
        factory = MetricFactory(MockMetric, container)

        assert factory.metric_class == MockMetric
        assert factory.container == container

    def test_factory_create_simple_metric(self):
        """Test creating a metric without dependencies."""
        container = MetricContainer()
        factory = MetricFactory(MockMetric, container)

        metric = factory.create()
        assert isinstance(metric, MockMetric)
        assert metric.tag == "mock_metric"

    def test_factory_create_dependent_metric(self):
        """Test creating a metric with dependencies."""
        container = MetricContainer()

        # Add the dependency to the container
        mock_provider = providers.Singleton(MetricFactory(MockMetric, container).create)
        setattr(container, "mock_metric", mock_provider)

        # Create the dependent metric
        factory = MetricFactory(MockDependentMetric, container)
        metric = factory.create()

        assert isinstance(metric, MockDependentMetric)
        assert metric.tag == "mock_dependent_metric"
        # Check that dependency was injected
        assert hasattr(metric, "_mock_metric_dependency")


class TestDependencyInjectionMetricRegistry:
    """Test the main DI metric registry."""

    @pytest.fixture
    def registry(self):
        """Create a fresh registry for testing."""
        # Create a new registry instance for testing
        # We can't use the global singleton for tests
        with patch('aiperf.metrics.dependency_injection_registry.DIMetricRegistry') as mock_registry:
            registry = DependencyInjectionMetricRegistry.__new__(DependencyInjectionMetricRegistry)
            registry._container = MetricContainer()
            registry._metrics_map = {}
            registry._factories = {}
            registry._discovery_lock = Mock()
            registry._initialized = True
            yield registry

    def test_registry_initialization(self, registry):
        """Test registry initialization."""
        assert registry._container is not None
        assert isinstance(registry._metrics_map, dict)
        assert isinstance(registry._factories, dict)

    def test_register_metric(self, registry):
        """Test registering a metric."""
        registry.register_metric(MockMetric)

        assert "mock_metric" in registry._metrics_map
        assert registry._metrics_map["mock_metric"] == MockMetric
        assert "mock_metric" in registry._factories
        assert hasattr(registry._container, "mock_metric")

    def test_register_duplicate_metric(self, registry):
        """Test registering a duplicate metric raises error."""
        registry.register_metric(MockMetric)

        with pytest.raises(MetricTypeError, match="already registered"):
            registry.register_metric(MockMetric)

    def test_get_class(self, registry):
        """Test getting a metric class."""
        registry.register_metric(MockMetric)

        metric_class = registry.get_class("mock_metric")
        assert metric_class == MockMetric

    def test_get_class_not_found(self, registry):
        """Test getting a non-existent metric class."""
        with pytest.raises(MetricTypeError, match="not found"):
            registry.get_class("non_existent")

    def test_get_instance(self, registry):
        """Test getting a metric instance."""
        registry.register_metric(MockMetric)

        instance = registry.get_instance("mock_metric")
        assert isinstance(instance, MockMetric)
        assert instance.tag == "mock_metric"

    def test_get_instance_not_found(self, registry):
        """Test getting a non-existent metric instance."""
        with pytest.raises(MetricTypeError, match="not found"):
            registry.get_instance("non_existent")

    def test_get_instances(self, registry):
        """Test getting multiple metric instances."""
        registry.register_metric(MockMetric)

        instances = registry.get_instances(["mock_metric"])
        assert "mock_metric" in instances
        assert isinstance(instances["mock_metric"], MockMetric)

    def test_register_custom_provider(self, registry):
        """Test registering a custom provider."""
        provider = providers.Singleton(MockService, value="custom")
        registry.register_custom_provider("custom_service", provider)

        assert hasattr(registry._container, "custom_service")
        service = registry._container.custom_service()
        assert isinstance(service, MockService)
        assert service.get_value() == "custom"

    def test_register_singleton(self, registry):
        """Test registering a singleton dependency."""
        registry.register_singleton("test_service", MockService, value="singleton")

        service1 = registry._container.test_service()
        service2 = registry._container.test_service()

        assert service1 is service2
        assert service1.get_value() == "singleton"

    def test_register_factory(self, registry):
        """Test registering a factory dependency."""
        registry.register_factory("test_service", MockService, value="factory")

        service1 = registry._container.test_service()
        service2 = registry._container.test_service()

        assert service1 is not service2
        assert service1.get_value() == "factory"
        assert service2.get_value() == "factory"

    def test_register_instance(self, registry):
        """Test registering a pre-created instance."""
        service_instance = MockService("instance")
        registry.register_instance("test_service", service_instance)

        retrieved_service = registry._container.test_service()
        assert retrieved_service is service_instance
        assert retrieved_service.get_value() == "instance"

    def test_tags_applicable_to(self, registry):
        """Test filtering metrics by flags and types."""
        registry.register_metric(MockMetric)

        # Test with no filters
        tags = registry.tags_applicable_to(MetricFlags.NONE, MetricFlags.NONE)
        assert "mock_metric" in tags

        # Test with type filter
        tags = registry.tags_applicable_to(MetricFlags.NONE, MetricFlags.NONE, MetricType.RECORD)
        assert "mock_metric" in tags

        # Test with wrong type filter
        tags = registry.tags_applicable_to(MetricFlags.NONE, MetricFlags.NONE, MetricType.AGGREGATE)
        assert "mock_metric" not in tags

    def test_all_tags(self, registry):
        """Test getting all metric tags."""
        registry.register_metric(MockMetric)

        tags = registry.all_tags()
        assert "mock_metric" in tags
        assert len(tags) == 1

    def test_all_classes(self, registry):
        """Test getting all metric classes."""
        registry.register_metric(MockMetric)

        classes = registry.all_classes()
        assert MockMetric in classes
        assert len(classes) == 1

    def test_classes_for(self, registry):
        """Test getting classes for specific tags."""
        registry.register_metric(MockMetric)

        classes = registry.classes_for(["mock_metric"])
        assert len(classes) == 1
        assert classes[0] == MockMetric

    def test_create_dependency_order(self, registry):
        """Test creating dependency order."""
        registry.register_metric(MockMetric)
        registry.register_metric(MockDependentMetric)

        order = registry.create_dependency_order()

        # mock_metric should come before mock_dependent_metric
        mock_index = order.index("mock_metric")
        dependent_index = order.index("mock_dependent_metric")
        assert mock_index < dependent_index

    def test_create_dependency_order_for_specific_tags(self, registry):
        """Test creating dependency order for specific tags."""
        registry.register_metric(MockMetric)
        registry.register_metric(MockDependentMetric)

        order = registry.create_dependency_order_for(["mock_dependent_metric"])

        # Should only include the requested tag, but dependencies should be resolved
        assert "mock_dependent_metric" in order

    def test_validate_dependencies_success(self, registry):
        """Test successful dependency validation."""
        registry.register_metric(MockMetric)
        registry.register_metric(MockDependentMetric)

        # Should not raise an exception
        registry.validate_dependencies()

    def test_validate_dependencies_missing_dependency(self, registry):
        """Test validation with missing dependency."""
        registry.register_metric(MockDependentMetric)  # Depends on mock_metric which is not registered

        with pytest.raises(MetricTypeError, match="depends on.*which is not registered"):
            registry.validate_dependencies()

    def test_get_dependency_graph(self, registry):
        """Test getting the dependency graph."""
        registry.register_metric(MockMetric)
        registry.register_metric(MockDependentMetric)

        graph = registry.get_dependency_graph()

        assert "mock_metric" in graph
        assert "mock_dependent_metric" in graph
        assert graph["mock_metric"] == set()
        assert graph["mock_dependent_metric"] == {"mock_metric"}


class TestDecorators:
    """Test the dependency injection decorators."""

    def test_inject_metric_decorator(self):
        """Test the inject_metric decorator."""
        decorator = inject_metric("test_metric")

        # The decorator should be a function
        assert callable(decorator)

        # This is a basic test - full integration would require a running container


if __name__ == "__main__":
    pytest.main([__file__])
