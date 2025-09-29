# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

import graphlib
import importlib
from collections.abc import Iterable
from pathlib import Path
from threading import Lock
from typing import TYPE_CHECKING, Any

from dependency_injector import containers, providers
from dependency_injector.wiring import Provide, inject

from aiperf.cli_utils import exit_on_error
from aiperf.common.aiperf_logger import AIPerfLogger
from aiperf.common.enums import MetricFlags, MetricType
from aiperf.common.exceptions import MetricTypeError
from aiperf.common.singleton import Singleton
from aiperf.common.types import MetricTagT

if TYPE_CHECKING:
    from aiperf.metrics.base_metric import BaseMetric

_logger = AIPerfLogger(__name__)


class MetricContainer(containers.DeclarativeContainer):
    """Dependency injection container for metrics using dependency-injector."""

    # Configuration
    config = providers.Configuration()

    # Core services can be added here as singletons
    # logger = providers.Singleton(AIPerfLogger, __name__)


class MetricFactory:
    """Factory for creating metric instances with dependency injection."""

    def __init__(self, metric_class: type["BaseMetric"], container: MetricContainer):
        self.metric_class = metric_class
        self.container = container

    def create(self) -> "BaseMetric":
        """Create a metric instance with dependencies injected."""
        instance = self.metric_class()

        # Inject dependencies if the metric has any
        if self.metric_class.required_metrics:
            for dep_tag in self.metric_class.required_metrics:
                if hasattr(self.container, dep_tag):
                    dep_provider = getattr(self.container, dep_tag)
                    dep_instance = dep_provider()
                    setattr(instance, f"_{dep_tag}_dependency", dep_instance)

        return instance


class DependencyInjectionMetricRegistry(Singleton):
    """
    A dependency injection-based metric registry using the dependency-injector package.

    This provides a clean, maintainable approach to managing metric dependencies with
    proper lifecycle management and validation.
    """

    def __init__(self):
        if hasattr(self, '_initialized'):
            return

        self._container = MetricContainer()
        self._metrics_map: dict[MetricTagT, type["BaseMetric"]] = {}
        self._factories: dict[MetricTagT, MetricFactory] = {}
        self._discovery_lock = Lock()
        self._initialized = True

        # Auto-discover metrics on initialization
        self._discover_metrics()
        self._setup_container()

    @property
    def container(self) -> MetricContainer:
        """Get the underlying DI container."""
        return self._container

    def register_metric(self, metric_class: type["BaseMetric"]) -> None:
        """Register a metric class with dependency injection support."""
        if metric_class.tag in self._metrics_map:
            raise MetricTypeError(
                f"Metric class with tag {metric_class.tag} already registered by {self._metrics_map[metric_class.tag].__name__}"
            )

        self._metrics_map[metric_class.tag] = metric_class
        self._factories[metric_class.tag] = MetricFactory(metric_class, self._container)

        # Dynamically add the metric as a singleton provider to the container
        provider = providers.Singleton(self._factories[metric_class.tag].create)
        setattr(self._container, metric_class.tag, provider)

    def register_custom_provider(self, key: str, provider: providers.Provider) -> None:
        """Register a custom provider that can be injected into metrics."""
        setattr(self._container, key, provider)

    def register_singleton(self, key: str, factory: type | Any, *args, **kwargs) -> None:
        """Register a singleton dependency."""
        provider = providers.Singleton(factory, *args, **kwargs)
        setattr(self._container, key, provider)

    def register_factory(self, key: str, factory: type | Any, *args, **kwargs) -> None:
        """Register a factory dependency (new instance each time)."""
        provider = providers.Factory(factory, *args, **kwargs)
        setattr(self._container, key, provider)

    def register_instance(self, key: str, instance: Any) -> None:
        """Register a pre-created instance."""
        provider = providers.Object(instance)
        setattr(self._container, key, provider)

    def get_class(self, tag: MetricTagT) -> type["BaseMetric"]:
        """Get a metric class by its tag."""
        if tag not in self._metrics_map:
            raise MetricTypeError(f"Metric class with tag '{tag}' not found")
        return self._metrics_map[tag]

    def get_instance(self, tag: MetricTagT) -> "BaseMetric":
        """Get an instance of a metric with dependencies injected."""
        if tag not in self._metrics_map:
            raise MetricTypeError(f"Metric with tag '{tag}' not found")

        provider = getattr(self._container, tag)
        return provider()

    def get_instances(self, tags: Iterable[MetricTagT]) -> dict[MetricTagT, "BaseMetric"]:
        """Get multiple metric instances with dependencies injected."""
        return {tag: self.get_instance(tag) for tag in tags}

    def tags_applicable_to(
        self,
        required_flags: MetricFlags,
        disallowed_flags: MetricFlags,
        *types: MetricType,
    ) -> list[MetricTagT]:
        """Get metrics tags that are applicable to the given arguments."""
        return [
            tag
            for tag, metric_class in self._metrics_map.items()
            if metric_class.has_flags(required_flags)
            and metric_class.missing_flags(disallowed_flags)
            and (not types or metric_class.type in types)
        ]

    def all_tags(self) -> list[MetricTagT]:
        """Get all of the tags of the defined metric classes."""
        return list(self._metrics_map.keys())

    def all_classes(self) -> list[type["BaseMetric"]]:
        """Get all of the classes of the defined metric classes."""
        return list(self._metrics_map.values())

    def classes_for(self, tags: Iterable[MetricTagT]) -> list[type["BaseMetric"]]:
        """Get the classes for the given tags."""
        return [self.get_class(tag) for tag in tags]

    def create_dependency_order(self) -> list[MetricTagT]:
        """Create a dependency order for all available metrics."""
        return self.create_dependency_order_for()

    def create_dependency_order_for(
        self,
        tags: Iterable[MetricTagT] | None = None,
    ) -> list[MetricTagT]:
        """Create a dependency order for the given metrics using topological sort."""
        if tags is None:
            tags = self._metrics_map.keys()

        # Build the dependency graph
        sorter = graphlib.TopologicalSorter()

        for tag in tags:
            metric_class = self._metrics_map[tag]
            dependencies = metric_class.required_metrics or set()
            sorter.add(tag, *dependencies)

        try:
            # Get the dependency order
            order = list(sorter.static_order())
            # Filter to only requested tags
            tags_set = set(tags)
            return [tag for tag in order if tag in tags_set]
        except graphlib.CycleError as e:
            raise MetricTypeError(f"Circular dependency detected among metrics: {e}") from e

    def validate_dependencies(self) -> None:
        """Validate that all dependencies are resolvable."""
        all_tags = set(self._metrics_map.keys())

        # Check for missing dependencies
        for metric_class in self._metrics_map.values():
            for required_tag in metric_class.required_metrics or set():
                if required_tag not in all_tags:
                    raise MetricTypeError(
                        f"Metric '{metric_class.tag}' depends on '{required_tag}', which is not registered"
                    )

        # Validate metric type dependencies
        _allowed_dependencies_by_type = {
            MetricType.RECORD: {MetricType.RECORD},
            MetricType.AGGREGATE: {MetricType.RECORD, MetricType.AGGREGATE},
            MetricType.DERIVED: {MetricType.RECORD, MetricType.AGGREGATE, MetricType.DERIVED},
        }

        for metric_class in self._metrics_map.values():
            for required_tag in metric_class.required_metrics or set():
                required_metric_type = self._metrics_map[required_tag].type
                if required_metric_type not in _allowed_dependencies_by_type[metric_class.type]:
                    raise MetricTypeError(
                        f"Metric '{metric_class.tag}' is a {metric_class.type} metric, "
                        f"but depends on '{required_tag}', which is a {required_metric_type} metric"
                    )

        # Check for circular dependencies
        try:
            self.create_dependency_order()
        except MetricTypeError:
            raise  # Re-raise the circular dependency error

    def get_dependency_graph(self) -> dict[str, set[str]]:
        """Get the dependency graph."""
        return {
            tag: metric_class.required_metrics or set()
            for tag, metric_class in self._metrics_map.items()
        }

    def _setup_container(self) -> None:
        """Setup the container with all registered metrics."""
        # Wire the container for dependency injection
        self._container.wire(modules=[__name__])

    def _discover_metrics(self) -> None:
        """Discover and register all metric types from the types directory."""
        with self._discovery_lock:
            types_dir = Path(__file__).parent / "types"

            if not types_dir.exists() or not types_dir.is_dir():
                raise MetricTypeError(
                    f"Types directory '{types_dir.resolve()}' does not exist or is not a directory"
                )

            module_prefix = ".".join([*self.__module__.split(".")[:-1], "types"])
            _logger.debug(
                f"Importing metric type modules from '{types_dir.resolve()}' with module prefix '{module_prefix}'"
            )

            self._import_metric_type_modules(types_dir, module_prefix)

    def _import_metric_type_modules(self, types_dir: Path, module_prefix: str) -> None:
        """Import all metric type modules from the given directory."""
        for python_file in types_dir.glob("*.py"):
            if python_file.name != "__init__.py":
                module_name = python_file.stem
                module_path = f"{module_prefix}.{module_name}"
                try:
                    _logger.debug(
                        f"Importing metric type module: '{module_path}' from '{python_file.resolve()}'"
                    )
                    importlib.import_module(module_path)
                except ImportError as err:
                    raise MetricTypeError(
                        f"Error importing metric type module '{module_path}' from '{python_file.resolve()}'"
                    ) from err


# Convenience functions for dependency injection
def inject_metric(tag: MetricTagT):
    """Decorator to inject a metric dependency."""
    return inject(Provide[f"container.{tag}"])


def inject_all_metrics():
    """Decorator to inject all available metrics."""
    def decorator(func):
        def wrapper(*args, **kwargs):
            registry = DIMetricRegistry()
            metrics = registry.get_instances(registry.all_tags())
            return func(*args, metrics=metrics, **kwargs)
        return wrapper
    return decorator


# Create the global instance
DIMetricRegistry = DependencyInjectionMetricRegistry()

# Auto-validate dependencies on module import
with exit_on_error(
    MetricTypeError,
    title="Error Validating DI Metric Dependencies",
):
    DIMetricRegistry.validate_dependencies()
