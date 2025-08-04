# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
import graphlib
import importlib
from pathlib import Path
from threading import Lock
from typing import TYPE_CHECKING

from aiperf.common.aiperf_logger import AIPerfLogger
from aiperf.common.enums.metric_enums import (
    MetricFlags,
    MetricType,
    MetricUnitT,
)
from aiperf.common.exceptions import MetricTypeError
from aiperf.common.types import MetricTagT

if TYPE_CHECKING:
    from aiperf.metrics.base_metric import BaseMetric


_logger = AIPerfLogger(__name__)


class MetricRegistry:
    """
    A registry for metrics. This is used to store all the metrics that are available to the system.
    It is used to lookup metrics by their tag, and to get all the metrics that are available.
    It also provides methods to get metrics by their type, flag, and to create a dependency order for the metrics.
    """

    # Map of metric tags to their classes
    _metrics_map: dict[MetricTagT, type["BaseMetric"]] = {}

    # Map of metric tags to their instances
    _instances_map: dict[MetricTagT, "BaseMetric"] = {}
    _instance_lock = Lock()

    @classmethod
    def _discover_metrics(cls) -> None:
        """
        This method dynamically imports all metric type modules from the 'types' directory to ensure
        all metric classes are registered via __init_subclass__. It will only discover metrics once.
        """
        # Get the types directory path
        types_dir = Path(__file__).parent / "types"

        # Ensure that the types directory exists
        if not types_dir.exists() or not types_dir.is_dir():
            raise MetricTypeError(
                f"Types directory '{types_dir.resolve()}' does not exist or is not a directory"
            )

        # Import all metric type modules to trigger registration
        _logger.debug(
            f"Importing metric type modules from {types_dir.resolve()} {cls.__module__=}"
        )

        cls._import_metric_type_modules(types_dir, "aiperf.metrics.types")

    @classmethod
    def _import_metric_type_modules(cls, types_dir: Path, module_prefix: str) -> None:
        """Import all metric type modules from the given directory. This will raise an error if the module cannot be imported."""
        for python_file in types_dir.glob("*.py"):
            if python_file.name != "__init__.py":
                module_name = python_file.stem  # Get filename without extension
                # TODO: Can the below be more generic using the __module__ attribute of this file?
                module_path = f"{module_prefix}.{module_name}"
                try:
                    _logger.debug(
                        f"Importing metric type module: {module_path} from {python_file.resolve()}"
                    )
                    importlib.import_module(module_path)
                except ImportError as err:
                    raise MetricTypeError(
                        f"Error importing metric type module '{module_path}' from '{python_file.resolve()}'"
                    ) from err

    @classmethod
    def register_metric(cls, metric: type["BaseMetric"]):
        """Register a metric class with the registry. This will raise a MetricTypeError if the class is already registered."""
        if metric.tag in cls._metrics_map:
            # TODO: Should we consider adding an override_priority parameter to the metric class similar to AIPerfFactory?
            raise MetricTypeError(
                f"Metric class with tag {metric.tag} already registered by {cls._metrics_map[metric.tag].__name__}"
            )

        cls._metrics_map[metric.tag] = metric

    @classmethod
    def has_tag(cls, tag: MetricTagT) -> bool:
        """Check if a metric is registered."""
        return tag in cls._metrics_map

    @classmethod
    def get_class(cls, tag: MetricTagT) -> type["BaseMetric"]:
        """Get a metric class by its tag. This will raise a KeyError if the class is not found."""
        return cls._metrics_map[tag]

    @classmethod
    def get_type(cls, tag: MetricTagT) -> MetricType:
        """Get the type of a metric by its tag. This will raise a KeyError if the class is not found."""
        return cls._metrics_map[tag].type

    @classmethod
    def get_unit(cls, tag: MetricTagT) -> MetricUnitT:
        """Get the unit of a metric by its tag. This will raise a KeyError if the class is not found."""
        return cls._metrics_map[tag].unit

    @classmethod
    def get_instance(cls, tag: MetricTagT) -> "BaseMetric":
        """Get an instance of a metric class by its tag. This will create a new instance if it does not exist."""
        # Check without acquiring the lock for performance
        if tag not in cls._instances_map:
            with cls._instance_lock:
                # Check again after acquiring the lock
                if tag not in cls._instances_map:
                    cls._instances_map[tag] = cls.get_class(tag)()
        return cls._instances_map[tag]

    @classmethod
    def tags_applicable_to(
        cls,
        required_flags: MetricFlags,
        disallowed_flags: MetricFlags,
        *types: MetricType,
    ) -> list[MetricTagT]:
        """Get metrics tags that are applicable to the given arguments.
        Arguments:
            required_flags: The flags that the metric must have.
            disallowed_flags: The flags that the metric must not have.
            types: The types of metrics to include. If not provided, all types will be included.
        """
        return [
            tag
            for tag, metric_class in cls._metrics_map.items()
            if metric_class.has_flags(required_flags)
            and metric_class.missing_flags(disallowed_flags)
            and (not types or metric_class.type in types)
        ]

    @classmethod
    def all_tags(cls) -> list[MetricTagT]:
        """Get all of the tags of the defined metric classes."""
        return list(cls._metrics_map.keys())

    @classmethod
    def all_classes(cls) -> list[type["BaseMetric"]]:
        """Get all of the classes of the defined metric classes."""
        return list(cls._metrics_map.values())

    @classmethod
    def classes_for(cls, tags: list[MetricTagT]) -> list[type["BaseMetric"]]:
        """Get the classes for the given tags."""
        return [cls.get_class(tag) for tag in tags]

    @classmethod
    def validate_dependencies(cls) -> None:
        """Validate that all dependencies are registered."""
        all_tags = cls.all_tags()
        all_classes = cls.all_classes()

        # Validate that all required metrics are registered
        for metric in all_classes:
            for required_tag in metric.required_metrics or set():
                if required_tag not in all_tags:
                    raise ValueError(
                        f"Metric {metric.tag} depends on {required_tag}, which is not registered"
                    )

    @classmethod
    def create_dependency_order(cls) -> list[MetricTagT]:
        """
        Create a dependency order for all available metrics using topological sort.

        This ensures that all dependencies are computed before their dependents.

        Returns:
            List of metric tags in dependency order (dependencies first).

        Raises:
            ValueError: If there are unregistered dependencies or circular dependencies.
        """
        return cls.create_dependency_order_for()

    @classmethod
    def create_dependency_order_for(
        cls, tags: list[MetricTagT] | None = None
    ) -> list[MetricTagT]:
        """
        Create a dependency order for the given metrics using topological sort.

        This ensures that all dependencies are computed before their dependents.
        Note that this will only sort and return the tags that were requested. If a tag
        has a dependency that is not in the list of tags, it will not be included in the order.
        This is useful for cases where we want to sort a subset of metrics that have dependencies
        on other metrics that we know are already computed such as is the case for derived metrics
        that are computed after all the other metrics.

        Returns:
            List of metric tags in dependency order (dependencies first). Will only
            include tags that were in the requested list.

        Raises:
            ValueError: If there are unregistered dependencies or circular dependencies.
        """
        if tags is None:
            tags = cls.all_tags()

        cls.validate_dependencies()

        # Build the dependency graph
        sorter = graphlib.TopologicalSorter()

        for metric in cls.classes_for(tags):
            # Add the metric with its required dependencies
            sorter.add(metric.tag, *(metric.required_metrics or set()))

        try:
            # Get the dependency order
            order = list(sorter.static_order())

            # Make sure we only return the tags that were requested
            tags_set = set(tags)
            return [tag for tag in order if tag in tags_set]
        except graphlib.CycleError as e:
            raise ValueError(f"Circular dependency detected among metrics: {e}") from e


# Ensure that the metrics are discovered when the module is imported.
MetricRegistry._discover_metrics()
