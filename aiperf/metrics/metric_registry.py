# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
import graphlib
import importlib
from pathlib import Path
from threading import Lock
from typing import TYPE_CHECKING

from aiperf.common.enums.metric_enums import MetricFlags, MetricType
from aiperf.common.exceptions import MetricTypeError
from aiperf.common.types import MetricTagT

if TYPE_CHECKING:
    from aiperf.metrics.base_metrics import BaseMetric


class MetricRegistry:
    """
    A registry for metrics. This is used to store all the metrics that are available to the system.
    It is used to lookup metrics by their tag, and to get all the metrics that are available.
    It also provides methods to get metrics by their type, flag, and to create a dependency order for the metrics.
    """

    _classes_by_tag: dict[MetricTagT, type["BaseMetric"]] = {}
    _instances_by_tag: dict[MetricTagT, "BaseMetric"] = {}
    _instance_lock = Lock()
    _discovered_metrics = False
    _discover_lock = Lock()

    @classmethod
    def discover_metrics(cls) -> None:
        """
        This method dynamically imports all metric type modules from the 'types' directory to ensure
        all metric classes are registered via __init_subclass__. It will only discover metrics once.
        """
        if cls._discovered_metrics:
            return  # Already discovered

        with cls._discover_lock:
            # Check again after acquiring the lock
            if cls._discovered_metrics:
                return  # Already discovered

            # Get the types directory path
            types_dir = Path(__file__).parent / "types"

            # Ensure that the types directory exists
            if not types_dir.exists() or not types_dir.is_dir():
                raise MetricTypeError(
                    f"Types directory '{types_dir.resolve()}' does not exist or is not a directory"
                )

            # Import all metric type modules to trigger registration
            cls._import_metric_type_modules(types_dir, "aiperf.metrics.types")

    @classmethod
    def _import_metric_type_modules(cls, types_dir: Path, module_prefix: str) -> None:
        """Import all metric type modules from the given directory."""
        for python_file in types_dir.glob("*.py"):
            if python_file.name != "__init__.py":
                module_name = python_file.stem  # Get filename without extension
                # TODO: Can the below be more generic using the __module__ attribute of this file?
                module_path = f"{module_prefix}.{module_name}"
                try:
                    importlib.import_module(module_path)
                except ImportError as err:
                    raise MetricTypeError(
                        f"Error importing metric type module '{module_path}' from '{python_file.resolve()}'"
                    ) from err

    @classmethod
    def register_metric(cls, metric: type["BaseMetric"]):
        """Register a metric class with the registry. This will raise an error if the class is already registered."""
        if metric.tag in cls._classes_by_tag:
            # TODO: Should we consider adding an override_priority parameter to the metric class similar to AIPerfFactory?
            raise ValueError(
                f"Metric class with tag {metric.tag} already registered by {cls._classes_by_tag[metric.tag].__name__}"
            )
        cls._classes_by_tag[metric.tag] = metric

    @classmethod
    def get_class(cls, tag: MetricTagT) -> type["BaseMetric"]:
        """Get a metric class by its tag. This will raise an error if the class is not found."""
        if tag not in cls._classes_by_tag:
            raise ValueError(f"Metric class with tag {tag} not found")
        return cls._classes_by_tag[tag]

    @classmethod
    def get_instance(cls, tag: MetricTagT) -> "BaseMetric":
        """Get an instance of a metric class by its tag. This will create a new instance if it does not exist."""
        # Check without acquiring the lock for performance
        if tag not in cls._instances_by_tag:
            with cls._instance_lock:
                # Check again after acquiring the lock
                if tag not in cls._instances_by_tag:
                    cls._instances_by_tag[tag] = cls.get_class(tag)()
        return cls._instances_by_tag[tag]

    @classmethod
    def tags_by_type(cls, *types: MetricType) -> list[MetricTagT]:
        """Get metrics tags with the given type(s)."""
        return [tag for tag in cls.all_tags() if cls.get_class(tag).type in types]

    @classmethod
    def tags_with_flags(cls, flags: MetricFlags) -> list[MetricTagT]:
        """Get metrics tags that have the given flag(s)."""
        return [tag for tag in cls.all_tags() if cls.get_class(tag).has_flags(flags)]

    @classmethod
    def tags_without_flags(cls, flags: MetricFlags) -> list[MetricTagT]:
        """Get metrics tags that do not have the given flag(s)."""
        return [
            tag for tag in cls.all_tags() if not cls.get_class(tag).has_flags(flags)
        ]

    @classmethod
    def tags_applicable_to(
        cls, required_flags: MetricFlags, disallowed_flags: MetricFlags
    ) -> list[MetricTagT]:
        """Get metrics tags that are applicable to the given endpoint type."""
        return [
            metric_cls.tag
            for metric_cls in cls.classes_for(cls.all_tags())
            if metric_cls.has_flags(required_flags)
            and metric_cls.missing_flags(disallowed_flags)
        ]

    @classmethod
    def all_tags(cls) -> list[MetricTagT]:
        """Get all of the tags of the defined metric classes."""
        return list(cls._classes_by_tag.keys())

    @classmethod
    def classes_for(cls, tags: list[MetricTagT]) -> list[type["BaseMetric"]]:
        """Get the classes for the given tags."""
        return [cls.get_class(tag) for tag in tags]

    @classmethod
    def instances_for(cls, tags: list[MetricTagT]) -> list["BaseMetric"]:
        """Get instances of the given metric classes."""
        return [cls.get_instance(tag) for tag in tags]

    @classmethod
    def validate_dependencies(cls) -> None:
        """Validate that all dependencies are registered."""
        cls.discover_metrics()
        all_tags = cls.all_tags()
        all_classes = cls.classes_for(all_tags)

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
        Create a dependency order for all the metrics using topological sort.
        This ensures that all dependencies are computed before their dependents.

        Returns:
            List of metric tags in dependency order (dependencies first).

        Raises:
            ValueError: If there are unregistered dependencies or circular dependencies.
        """
        return cls.create_dependency_order_for(cls.all_tags())

    @classmethod
    def create_dependency_order_for(cls, tags: list[MetricTagT]) -> list[MetricTagT]:
        """
        Create a dependency order for the given metrics using topological sort.
        This ensures that all dependencies are computed before their dependents.

        Returns:
            List of metric tags in dependency order (dependencies first).

        Raises:
            ValueError: If there are unregistered dependencies or circular dependencies.
        """
        cls.validate_dependencies()

        # Build the dependency graph using TopologicalSorter
        sorter = graphlib.TopologicalSorter()

        for metric in cls.classes_for(tags):
            # Add the metric with its dependencies (predecessors)
            sorter.add(metric.tag, *(metric.required_metrics or set()))

        try:
            # Get the topological order
            return list(sorter.static_order())
        except graphlib.CycleError as e:
            raise ValueError(f"Circular dependency detected among metrics: {e}") from e
