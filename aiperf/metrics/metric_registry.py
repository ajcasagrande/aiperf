# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
import graphlib
import importlib
from collections.abc import Iterable
from pathlib import Path
from threading import Lock
from typing import TYPE_CHECKING

from aiperf.cli_utils import exit_on_error
from aiperf.common.aiperf_logger import AIPerfLogger
from aiperf.common.enums import (
    MetricFlags,
    MetricType,
)
from aiperf.common.exceptions import MetricTypeError
from aiperf.common.types import MetricTagT

# Plugin system imports (AIP-001)
from aiperf.plugins.discovery import PluginDiscovery, PluginLoader
from aiperf.plugins.validator import PluginValidator

if TYPE_CHECKING:
    # This is used to avoid circular imports
    from aiperf.metrics.base_metric import BaseMetric


_logger = AIPerfLogger(__name__)


class MetricRegistry:
    """
    A registry for metrics.

    This is used to store all the metrics that are available to the system.
    It is used to lookup metrics by their tag, and to get all the metrics that are available.
    It also provides methods to get metrics by their type, flag, and to create a dependency order for the metrics.
    It is also used to create instances of metrics.

    This class is not meant to be instantiated directly. It is meant to be used as a singleton via classmethods.
    """

    # Map of metric tags to their classes
    _metrics_map: dict[MetricTagT, type["BaseMetric"]] = {}

    # Map of metric tags to their instances
    _instances_map: dict[MetricTagT, "BaseMetric"] = {}
    _instance_lock = Lock()

    # Plugin system state (AIP-001)
    _plugin_loader: PluginLoader | None = None
    _plugin_validator: PluginValidator | None = None
    _plugin_load_errors: dict[str, Exception] = {}

    def __init__(self) -> None:
        raise TypeError(
            "MetricRegistry is a singleton and cannot be instantiated directly"
        )

    @classmethod
    def _discover_metrics(cls) -> None:
        """
        This method dynamically imports all metric type modules from the 'types' directory to ensure
        all metric classes are registered via __init_subclass__. This will be called once when the
        module is imported.

        This method also discovers and loads metric plugins via the AIP-001 plugin system.
        """
        # Get the types directory path
        types_dir = Path(__file__).parent / "types"

        # Ensure that the types directory exists
        if not types_dir.exists() or not types_dir.is_dir():
            raise MetricTypeError(
                f"Types directory '{types_dir.resolve()}' does not exist or is not a directory"
            )

        # Get the module prefix for the types directory, which is the parent of
        # this module, plus the types directory name.
        # For example, `aiperf.metrics.metric_registry` will become `aiperf.metrics.types`
        module_prefix = ".".join([*cls.__module__.split(".")[:-1], "types"])
        _logger.debug(
            f"Importing metric type modules from '{types_dir.resolve()}' with module prefix '{module_prefix}'"
        )
        # Import all metric type modules to trigger registration
        cls._import_metric_type_modules(types_dir, module_prefix)

        # Discover and load metric plugins (AIP-001)
        cls._discover_metric_plugins()

    @classmethod
    def _import_metric_type_modules(cls, types_dir: Path, module_prefix: str) -> None:
        """Import all metric type modules from the given directory. This will raise an error if the module cannot be imported."""
        for python_file in types_dir.glob("*.py"):
            if python_file.name != "__init__.py":
                module_name = python_file.stem  # Get filename without extension
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

    @classmethod
    def _discover_metric_plugins(cls) -> None:
        """
        Discover and load metric plugins via the AIP-001 plugin system.

        This method:
        1. Discovers metric plugins via entry points
        2. Loads and validates each plugin
        3. Registers valid plugins with the MetricRegistry
        4. Logs plugin discovery and any errors
        5. Handles errors gracefully without failing the entire discovery process

        Plugin loading is performed lazily and errors are logged but do not prevent
        built-in metrics from working. This ensures backward compatibility.
        """
        # Initialize plugin system components (lazy initialization)
        if cls._plugin_loader is None:
            cls._plugin_loader = PluginLoader()
        if cls._plugin_validator is None:
            cls._plugin_validator = PluginValidator()

        # Discover metric plugins via entry points
        _logger.info("Discovering metric plugins (AIP-001)...")
        plugin_group = "aiperf.metric"

        try:
            plugin_metadata_list = PluginDiscovery.discover_plugins_by_group(plugin_group)

            if not plugin_metadata_list:
                _logger.debug("No metric plugins discovered via entry points")
                return

            _logger.info(f"Discovered {len(plugin_metadata_list)} metric plugin(s)")

            # Track statistics for summary logging
            loaded_count = 0
            failed_count = 0
            registered_count = 0

            # Load and register each plugin
            for plugin_metadata in plugin_metadata_list:
                try:
                    _logger.debug(
                        f"Loading metric plugin '{plugin_metadata.name}' from {plugin_metadata.entry_point.value}"
                    )

                    # Load the plugin (lazy loading)
                    plugin_class = cls._plugin_loader.load_plugin(plugin_metadata)

                    if plugin_class is None:
                        _logger.warning(f"Failed to load metric plugin '{plugin_metadata.name}'")
                        failed_count += 1
                        continue

                    loaded_count += 1

                    # Validate the plugin conforms to MetricPluginProtocol
                    if not cls._plugin_validator.validate_plugin(plugin_class, plugin_group):
                        _logger.error(
                            f"Metric plugin '{plugin_metadata.name}' failed validation and will not be registered"
                        )
                        failed_count += 1
                        continue

                    # Register the plugin with the MetricRegistry
                    # The plugin class should automatically register via __init_subclass__ if it inherits from BaseMetric
                    # However, we need to ensure it's actually registered
                    if hasattr(plugin_class, 'tag'):
                        tag = plugin_class.tag

                        # Check if already registered (could happen if plugin inherits from BaseMetric)
                        if tag in cls._metrics_map:
                            # Check if it's the same class or a different one
                            if cls._metrics_map[tag] is plugin_class:
                                _logger.debug(
                                    f"Metric plugin '{plugin_metadata.name}' with tag '{tag}' already registered via __init_subclass__"
                                )
                                registered_count += 1
                            else:
                                _logger.warning(
                                    f"Metric plugin '{plugin_metadata.name}' with tag '{tag}' conflicts with existing metric '{cls._metrics_map[tag].__name__}'"
                                )
                                failed_count += 1
                        else:
                            # Manually register if not already registered
                            try:
                                cls.register_metric(plugin_class)
                                registered_count += 1
                                _logger.info(
                                    f"Registered metric plugin '{plugin_metadata.name}' with tag '{tag}'"
                                )
                            except MetricTypeError as e:
                                _logger.error(
                                    f"Failed to register metric plugin '{plugin_metadata.name}': {e}"
                                )
                                failed_count += 1
                    else:
                        _logger.error(
                            f"Metric plugin '{plugin_metadata.name}' does not have a 'tag' attribute"
                        )
                        failed_count += 1

                except Exception as e:
                    # Catch all exceptions to prevent plugin loading from breaking the entire discovery process
                    _logger.error(
                        f"Error loading metric plugin '{plugin_metadata.name}': {e}",
                        exc_info=True
                    )
                    cls._plugin_load_errors[plugin_metadata.name] = e
                    failed_count += 1

            # Log summary
            _logger.info(
                f"Metric plugin discovery complete: {registered_count} registered, "
                f"{loaded_count} loaded, {failed_count} failed"
            )

            # Store load errors for diagnostics
            if cls._plugin_loader:
                cls._plugin_load_errors.update(cls._plugin_loader.get_load_errors())

        except Exception as e:
            # Catch all exceptions during discovery to ensure built-in metrics still work
            _logger.error(
                f"Error during metric plugin discovery: {e}",
                exc_info=True
            )
            _logger.warning(
                "Metric plugin discovery failed, but built-in metrics will continue to work normally"
            )

    @classmethod
    def register_metric(cls, metric: type["BaseMetric"]):
        """Register a metric class with the registry. This will raise a MetricTypeError if the class is already registered.

        This method is called automatically via the __init_subclass__ method of the BaseMetric class, so there is no need
        to call it manually. It is also called when registering metric plugins discovered via the AIP-001 plugin system.
        """
        if metric.tag in cls._metrics_map:
            # TODO: Should we consider adding an override_priority parameter to the metric class similar to AIPerfFactory?
            #       This would allow the user to override built-in metrics with custom implementations, without requiring
            #       them to modify the built-in metric classes.
            raise MetricTypeError(
                f"Metric class with tag {metric.tag} already registered by {cls._metrics_map[metric.tag].__name__}"
            )

        cls._metrics_map[metric.tag] = metric

    @classmethod
    def get_class(cls, tag: MetricTagT) -> type["BaseMetric"]:
        """Get a metric class by its tag.

        Raises:
            MetricTypeError: If the metric class is not found.
        """
        try:
            return cls._metrics_map[tag]
        except KeyError as e:
            raise MetricTypeError(f"Metric class with tag '{tag}' not found") from e

    @classmethod
    def get_instance(cls, tag: MetricTagT) -> "BaseMetric":
        """Get an instance of a metric class by its tag. This will create a new instance if it does not exist.

        Raises:
            MetricTypeError: If the metric class is not found.
        """
        # Check first without acquiring the lock for performance reasons. Since this is a hot path, we want to avoid
        # acquiring the lock if we can. We can do this because we have added a secondary check after acquiring the lock.
        if tag not in cls._instances_map:
            with cls._instance_lock:
                # Check again after acquiring the lock
                if tag not in cls._instances_map:
                    metric_class = cls.get_class(tag)
                    cls._instances_map[tag] = metric_class()
        return cls._instances_map[tag]

    @classmethod
    def tags_applicable_to(
        cls,
        required_flags: MetricFlags,
        disallowed_flags: MetricFlags,
        *types: MetricType,
    ) -> list[MetricTagT]:
        """Get metrics tags that are applicable to the given arguments.

        This method is used to filter the metrics that are applicable to a given set of flags and types.
        For instance, this can be used to only get all DERIVED metrics, or only get metrics that are
        applicable to non-streaming endpoints, etc.

        Arguments:
            required_flags: The flags that the metric must have.
            disallowed_flags: The flags that the metric must not have.
            types: The types of metrics to include. If not provided, all types will be included.

        Returns:
            A list of metric tags that are applicable to the given arguments.
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
    def classes_for(cls, tags: Iterable[MetricTagT]) -> list[type["BaseMetric"]]:
        """Get the classes for the given tags.

        Raises:
            MetricTypeError: If a tag is not found.
        """
        return [cls.get_class(tag) for tag in tags]

    @classmethod
    def get_plugin_load_errors(cls) -> dict[str, Exception]:
        """Get all plugin loading errors for diagnostics.

        Returns:
            Dictionary mapping plugin names to their loading exceptions.
        """
        return cls._plugin_load_errors.copy()

    @classmethod
    def _validate_dependencies(cls) -> None:
        """Validate that all dependencies are registered.

        Raises:
            MetricTypeError: If a dependency is not registered.
        """
        all_tags = cls._metrics_map.keys()
        all_classes = cls._metrics_map.values()

        # Map of metric types to the types of metrics they can have dependencies on
        _allowed_dependencies_by_type = {
            # Record metrics can only depend on other record metrics
            MetricType.RECORD: {MetricType.RECORD},
            # Aggregate metrics can depend on other record or aggregate metrics
            MetricType.AGGREGATE: {MetricType.RECORD, MetricType.AGGREGATE},
            # Derived metrics can depend on any other metric type
            MetricType.DERIVED: {
                MetricType.RECORD,
                MetricType.AGGREGATE,
                MetricType.DERIVED,
            },
        }

        # Validate that all required metrics are registered, and that the dependencies are allowed
        for metric in all_classes:
            for required_tag in metric.required_metrics or set():
                # Validate that the dependency is registered
                if required_tag not in all_tags:
                    raise MetricTypeError(
                        f"Metric '{metric.tag}' depends on '{required_tag}', which is not registered"
                    )

                # Validate that the dependency is allowed
                required_metric_type = cls._metrics_map[required_tag].type
                if (
                    required_metric_type
                    not in _allowed_dependencies_by_type[metric.type]
                ):
                    raise MetricTypeError(
                        f"Metric '{metric.tag}' is a {metric.type} metric, but depends on '{required_tag}', which is a {required_metric_type} metric"
                    )

    @classmethod
    def _get_all_required_tags(cls, tags: Iterable[MetricTagT]) -> set[MetricTagT]:
        """Get all of the required tags, recursively, for a given list of metric tags."""
        required_tags = set(tags)
        for metric_class in cls.classes_for(tags):
            for required_tag in metric_class.required_metrics or set():
                if required_tag not in required_tags:
                    required_tags.add(required_tag)
                    required_tags.update(cls._get_all_required_tags([required_tag]))
        return required_tags

    @classmethod
    def create_dependency_order(cls) -> list[MetricTagT]:
        """
        Create a dependency order for all available metrics using topological sort.

        See :meth:`create_dependency_order_for` for more details.
        """
        return cls.create_dependency_order_for()

    @classmethod
    def create_dependency_order_for(
        cls,
        tags: Iterable[MetricTagT] | None = None,
    ) -> list[MetricTagT]:
        """
        Create a dependency order for the given metrics using topological sort.

        This ensures that all dependencies are computed before their dependents.
        If `tags` is provided, only the tags present in `tags` will be included in the order.

        Arguments:
            tags: The tags of the metrics to compute the dependency order for. If not provided, all metrics will be included.

        Returns:
            List of metric tags in dependency order (dependencies first).

        Raises:
            MetricTypeError: If there are unregistered dependencies or circular dependencies.
        """
        if tags is None:
            tags = cls._metrics_map.keys()

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
            raise MetricTypeError(
                f"Circular dependency detected among metrics: {e}"
            ) from e


# Ensure that the metrics are discovered when the module is imported.
with exit_on_error(
    MetricTypeError,
    title="Error Discovering Metrics",
):
    MetricRegistry._discover_metrics()

# Ensure that the dependencies are validated, and no circular dependencies are detected
with exit_on_error(
    MetricTypeError,
    title="Error Validating Metric Dependencies",
):
    MetricRegistry._validate_dependencies()
    MetricRegistry.create_dependency_order()


# Import plugin integration at module level (after MetricRegistry is defined)
try:
    from aiperf.metrics.plugin_integration import discover_and_register_metric_plugins
    # Call during module initialization
    discover_and_register_metric_plugins(MetricRegistry)
except Exception as e:
    _logger.debug(f"Plugin system not initialized: {e}")
