# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""
Dependency Injection for Plugins (AIP-001)

Provides dependency injection capabilities for plugins.
Allows plugins to declare dependencies that are automatically resolved.

Note: This is a simplified implementation. For full DI framework,
consider integrating with dependency-injector library.
"""

import inspect
from collections.abc import Callable
from typing import Any

from aiperf.common.aiperf_logger import AIPerfLogger

logger = AIPerfLogger(__name__)


class PluginInjector:
    """
    Simple dependency injector for plugins.

    Resolves constructor dependencies for plugin instantiation.

    Example:
        >>> injector = PluginInjector()
        >>> injector.register('tokenizer', tokenizer_instance)
        >>> injector.register('config', config_instance)
        >>>
        >>> # Plugin constructor: def __init__(self, tokenizer=None, config=None)
        >>> instance = injector.instantiate(PluginClass)
        >>> # tokenizer and config automatically injected
    """

    def __init__(self):
        """Initialize injector with empty dependency registry."""
        self._dependencies: dict[str, Any] = {}
        self._factories: dict[str, Callable[[], Any]] = {}

    def register(self, name: str, instance: Any):
        """
        Register a dependency instance.

        Args:
            name: Dependency name (matches parameter name)
            instance: Instance to inject

        Example:
            >>> injector.register('tokenizer', my_tokenizer)
        """
        self._dependencies[name] = instance
        logger.debug(f"Registered dependency: {name}")

    def register_factory(self, name: str, factory: Callable[[], Any]):
        """
        Register a factory function for lazy instantiation.

        Args:
            name: Dependency name
            factory: Callable that returns instance

        Example:
            >>> injector.register_factory('expensive_resource', lambda: create_resource())
        """
        self._factories[name] = factory
        logger.debug(f"Registered factory for: {name}")

    def instantiate(self, plugin_class: type, **extra_kwargs) -> Any:
        """
        Instantiate plugin with dependency injection.

        Args:
            plugin_class: Plugin class to instantiate
            **extra_kwargs: Additional keyword arguments (override dependencies)

        Returns:
            Plugin instance with dependencies injected

        Example:
            >>> plugin = injector.instantiate(MyPlugin, custom_arg='value')
        """
        # Get constructor signature
        try:
            sig = inspect.signature(plugin_class.__init__)
        except (ValueError, TypeError):
            # No __init__ or can't inspect
            return plugin_class()

        # Build kwargs for constructor
        kwargs = {}

        for param_name, param in sig.parameters.items():
            if param_name == "self":
                continue

            # Use extra_kwargs if provided
            if param_name in extra_kwargs:
                kwargs[param_name] = extra_kwargs[param_name]
                continue

            # Try to resolve dependency
            if param_name in self._dependencies:
                kwargs[param_name] = self._dependencies[param_name]
                logger.debug(f"Injecting dependency: {param_name}")
            elif param_name in self._factories:
                # Lazy create from factory
                instance = self._factories[param_name]()
                self._dependencies[param_name] = instance  # Cache it
                kwargs[param_name] = instance
                logger.debug(
                    f"Created and injected dependency from factory: {param_name}"
                )
            elif param.default is not inspect.Parameter.empty:
                # Has default value, don't inject
                pass
            else:
                # Required parameter without available dependency
                logger.warning(
                    f"No dependency available for required parameter: {param_name} "
                    f"in {plugin_class.__name__}"
                )

        try:
            return plugin_class(**kwargs)
        except Exception as e:
            logger.error(f"Failed to instantiate {plugin_class.__name__}: {e}")
            raise

    def get_dependency(self, name: str) -> Any | None:
        """
        Get a registered dependency.

        Args:
            name: Dependency name

        Returns:
            Dependency instance or None
        """
        if name in self._dependencies:
            return self._dependencies[name]

        if name in self._factories:
            instance = self._factories[name]()
            self._dependencies[name] = instance
            return instance

        return None

    def clear(self):
        """Clear all registered dependencies and factories."""
        self._dependencies.clear()
        self._factories.clear()
        logger.debug("Cleared all dependencies")


# Global injector instance
_global_injector: PluginInjector | None = None


def get_plugin_injector() -> PluginInjector:
    """
    Get the global plugin injector instance.

    Returns:
        Singleton PluginInjector instance
    """
    global _global_injector

    if _global_injector is None:
        _global_injector = PluginInjector()

    return _global_injector
