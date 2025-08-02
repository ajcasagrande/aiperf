# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
import graphlib
from threading import Lock
from typing import TYPE_CHECKING

from aiperf.common.enums.metric_enums import MetricFlags, MetricType
from aiperf.common.types import MetricTagT

if TYPE_CHECKING:
    from aiperf.metrics.base_metrics import BaseMetric


class MetricRegistry:
    """
    A registry for metrics. This is used to store all the metrics that are available to the system.
    It is used to lookup metrics by their tag, and to get all the metrics that are available.
    """

    _metric_interfaces: dict[MetricTagT, type["BaseMetric"]] = {}
    _instances: dict[MetricTagT, "BaseMetric"] = {}
    _instance_lock = Lock()

    @classmethod
    def register_metric(cls, metric: type["BaseMetric"]):
        """
        Register a metric class with the registry.
        """
        cls._metric_interfaces[metric.tag] = metric

    @classmethod
    def get_class(cls, tag: MetricTagT) -> type["BaseMetric"]:
        """
        Get a metric class by its tag.
        """
        if tag not in cls._metric_interfaces:
            raise ValueError(f"Metric class with tag {tag} not found")
        return cls._metric_interfaces[tag]

    @classmethod
    def get_instance(cls, tag: MetricTagT) -> "BaseMetric":
        """
        Get an instance of a metric class by its tag.
        """
        if tag not in cls._instances:
            with cls._instance_lock:
                if tag not in cls._instances:
                    cls._instances[tag] = cls.get_class(tag)()
        return cls._instances[tag]

    @classmethod
    def classes_by_type(cls, *types: MetricType) -> list[type["BaseMetric"]]:
        """
        Get a metric by its type.
        """
        return [metric for metric in cls.all_classes() if metric.type in types]

    @classmethod
    def instances_by_type(cls, *types: MetricType) -> list["BaseMetric"]:
        """
        Get instances of metrics by their type.
        """
        return [cls.get_instance(metric.tag) for metric in cls.classes_by_type(*types)]

    @classmethod
    def classes_with_flags(cls, flags: MetricFlags) -> list[type["BaseMetric"]]:
        """
        Get metrics classes that have the given flag(s).
        """
        return [metric for metric in cls.all_classes() if metric.has_flag(flags)]

    @classmethod
    def instances_with_flags(cls, flags: MetricFlags) -> list["BaseMetric"]:
        """
        Get instances of metrics classes that have the given flag(s).
        """
        return [
            cls.get_instance(metric.tag) for metric in cls.classes_with_flags(flags)
        ]

    @classmethod
    def classes_without_flags(cls, flags: MetricFlags) -> list[type["BaseMetric"]]:
        """
        Get metrics classes that do not have the given flag(s).
        """
        return [metric for metric in cls.all_classes() if not metric.has_flag(flags)]

    @classmethod
    def instances_without_flags(cls, flags: MetricFlags) -> list["BaseMetric"]:
        """
        Get instances of metrics classes that do not have the given flag(s).
        """
        return [
            cls.get_instance(metric.tag) for metric in cls.classes_without_flags(flags)
        ]

    @classmethod
    def all_classes(cls) -> list[type["BaseMetric"]]:
        """
        Get all of the defined metric classes.
        """
        return list(cls._metric_interfaces.values())

    @classmethod
    def all_instances(cls) -> list["BaseMetric"]:
        """
        Get an instance of for each of the metric classes.
        """
        return [cls.get_instance(metric.tag) for metric in cls.all_classes()]

    @classmethod
    def all_tags(cls) -> list[MetricTagT]:
        """
        Get all of the tags of the defined metric classes.
        """
        return list(cls._metric_interfaces.keys())

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
        return cls.create_dependency_order_of(cls.all_classes())

    @classmethod
    def create_dependency_order_of(
        cls, classes: list[type["BaseMetric"]]
    ) -> list[MetricTagT]:
        """
        Create a dependency order for the given metrics using topological sort.
        This ensures that all dependencies are computed before their dependents.

        Returns:
            List of metric tags in dependency order (dependencies first).

        Raises:
            ValueError: If there are unregistered dependencies or circular dependencies.
        """
        all_tags = cls.all_tags()

        # Validate that all required metrics are registered and that they are registered
        for metric in classes:
            for required_tag in metric.required_metrics:
                if required_tag not in all_tags:
                    raise ValueError(
                        f"Metric {metric.tag} depends on {required_tag}, which is not registered"
                    )

        # Build the dependency graph using TopologicalSorter
        sorter = graphlib.TopologicalSorter()

        for metric in classes:
            # Add the metric with its dependencies (predecessors)
            sorter.add(metric.tag, *metric.required_metrics)

        try:
            # Get the topological order
            return list(sorter.static_order())
        except graphlib.CycleError as e:
            raise ValueError(f"Circular dependency detected among metrics: {e}") from e
