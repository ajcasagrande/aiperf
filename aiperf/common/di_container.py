# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Modern dependency injection container for AIPerf.

This module provides a state-of-the-art dependency injection system using the dependency-injector
library with lazy loading, entry points support, and plugin architecture.
"""

import importlib.metadata
import threading
from enum import Enum
from typing import Any, Dict, Generic, Optional, Protocol, Type, TypeVar, Union, runtime_checkable
from collections.abc import Callable

from dependency_injector import containers, providers
from dependency_injector.wiring import Provide, inject

from aiperf.common.aiperf_logger import AIPerfLogger
from aiperf.common.exceptions import FactoryCreationError, InvalidOperationError

# Type variables for generic factory support
EnumT = TypeVar('EnumT', bound=Enum)
ProtocolT = TypeVar('ProtocolT')

logger = AIPerfLogger(__name__)


@runtime_checkable
class PluginProtocol(Protocol):
    """Base protocol that all plugins should implement for validation."""

    def __init_subclass__(cls, **kwargs: Any) -> None:
        """Called when a class is subclassed."""
        super().__init_subclass__(**kwargs)


class LazyProvider(providers.Provider):
    """Custom provider that supports lazy loading from entry points."""

    def __init__(self, entry_point_name: str, entry_point_group: str, **kwargs: Any):
        super().__init__(**kwargs)
        self._entry_point_name = entry_point_name
        self._entry_point_group = entry_point_group
        self._loaded_class: Optional[Type] = None
        self._load_lock = threading.Lock()

    def _provide(self, *args: Any, **kwargs: Any) -> Any:
        """Provide the service instance with lazy loading."""
        if self._loaded_class is None:
            with self._load_lock:
                if self._loaded_class is None:
                    self._load_class()

        return self._loaded_class(*args, **kwargs)

    def _load_class(self) -> None:
        """Load the class from entry point."""
        try:
            entry_points = importlib.metadata.entry_points().select(
                group=self._entry_point_group, name=self._entry_point_name
            )
            entry_point = next(iter(entry_points), None)

            if entry_point is None:
                raise FactoryCreationError(
                    f"Entry point '{self._entry_point_name}' not found in group '{self._entry_point_group}'"
                )

            self._loaded_class = entry_point.load()
            logger.debug(f"Lazily loaded class {self._loaded_class.__name__} from entry point")

        except Exception as e:
            raise FactoryCreationError(
                f"Failed to load entry point '{self._entry_point_name}': {e}"
            ) from e


class AIPerfContainer(containers.DeclarativeContainer):
    """Main AIPerf dependency injection container with plugin support."""

    # Configuration provider for runtime config
    config = providers.Configuration()

    # Plugin registry
    _plugin_registry: Dict[str, Dict[str, providers.Provider]] = {}
    _registry_lock = threading.Lock()
    _initialized = False

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        if not cls._initialized:
            cls._discover_plugins()
            cls._initialized = True

    @classmethod
    def _discover_plugins(cls) -> None:
        """Discover and register all plugins from entry points."""
        with cls._registry_lock:
            # Define entry point groups for different plugin types
            plugin_groups = {
                'services': 'aiperf.services',
                'exporters': 'aiperf.exporters',
                'clients': 'aiperf.clients',
                'composers': 'aiperf.composers',
                'processors': 'aiperf.processors',
            }

            for plugin_type, group_name in plugin_groups.items():
                cls._plugin_registry[plugin_type] = {}
                cls._discover_plugin_group(plugin_type, group_name)

    @classmethod
    def _discover_plugin_group(cls, plugin_type: str, group_name: str) -> None:
        """Discover plugins for a specific group."""
        try:
            entry_points = importlib.metadata.entry_points().select(group=group_name)

            for entry_point in entry_points:
                # Create lazy provider
                lazy_provider = LazyProvider(
                    entry_point_name=entry_point.name,
                    entry_point_group=group_name
                )

                # Register the provider
                cls._plugin_registry[plugin_type][entry_point.name] = lazy_provider

                # Also set as container attribute for direct access
                setattr(cls, f"{plugin_type}_{entry_point.name}", lazy_provider)

                logger.info(f"Registered {plugin_type} plugin: {entry_point.name}")

        except Exception as e:
            logger.error(f"Failed to discover plugins for group {group_name}: {e}")

    @classmethod
    def get_plugin_provider(cls, plugin_type: str, plugin_name: str) -> providers.Provider:
        """Get a plugin provider by type and name."""
        if plugin_type not in cls._plugin_registry:
            raise ValueError(f"Unknown plugin type: {plugin_type}")

        if plugin_name not in cls._plugin_registry[plugin_type]:
            available = list(cls._plugin_registry[plugin_type].keys())
            raise ValueError(f"Plugin '{plugin_name}' not found in {plugin_type}. Available: {available}")

        return cls._plugin_registry[plugin_type][plugin_name]

    @classmethod
    def list_plugins(cls, plugin_type: Optional[str] = None) -> Dict[str, list[str]]:
        """List all available plugins."""
        if plugin_type:
            if plugin_type not in cls._plugin_registry:
                return {plugin_type: []}
            return {plugin_type: list(cls._plugin_registry[plugin_type].keys())}

        return {
            ptype: list(plugins.keys())
            for ptype, plugins in cls._plugin_registry.items()
        }


class ModernFactory(Generic[EnumT, ProtocolT]):
    """Modern factory implementation using dependency-injector with lazy loading."""

    def __init__(
        self,
        container: AIPerfContainer,
        plugin_type: str,
        protocol: Type[ProtocolT],
        enum_type: Type[EnumT]
    ):
        self.container = container
        self.plugin_type = plugin_type
        self.protocol = protocol
        self.enum_type = enum_type
        self._logger = AIPerfLogger(f"{self.__class__.__name__}[{plugin_type}]")

    def create_instance(
        self,
        service_key: Union[EnumT, str],
        **kwargs: Any
    ) -> ProtocolT:
        """Create an instance with lazy loading and validation."""
        # Convert enum to string if needed
        plugin_name = service_key.value if isinstance(service_key, Enum) else str(service_key)

        try:
            # Get the lazy provider
            provider = self.container.get_plugin_provider(self.plugin_type, plugin_name)

            # Create instance
            instance = provider(**kwargs)

            # Validate protocol compliance
            self._validate_instance(instance, plugin_name)

            return instance

        except Exception as e:
            raise FactoryCreationError(
                f"Failed to create {self.plugin_type} instance '{plugin_name}': {e}"
            ) from e

    def _validate_instance(self, instance: Any, plugin_name: str) -> None:
        """Validate that instance implements the expected protocol."""
        if not isinstance(instance, self.protocol):
            self._logger.warning(
                f"Plugin '{plugin_name}' does not properly implement {self.protocol.__name__}"
            )

    def get_available_implementations(self) -> list[str]:
        """Get list of available implementations."""
        return list(self.container._plugin_registry.get(self.plugin_type, {}).keys())

    def has_implementation(self, service_key: Union[EnumT, str]) -> bool:
        """Check if implementation is available."""
        plugin_name = service_key.value if isinstance(service_key, Enum) else str(service_key)
        return plugin_name in self.container._plugin_registry.get(self.plugin_type, {})


class SingletonFactory(ModernFactory[EnumT, ProtocolT]):
    """Factory that creates singleton instances."""

    def __init__(
        self,
        container: AIPerfContainer,
        plugin_type: str,
        protocol: Type[ProtocolT],
        enum_type: Type[EnumT]
    ):
        super().__init__(container, plugin_type, protocol, enum_type)
        self._instances: Dict[str, ProtocolT] = {}
        self._instances_lock = threading.Lock()

    def create_instance(
        self,
        service_key: Union[EnumT, str],
        **kwargs: Any
    ) -> ProtocolT:
        """Create or return existing singleton instance."""
        plugin_name = service_key.value if isinstance(service_key, Enum) else str(service_key)

        if plugin_name not in self._instances:
            with self._instances_lock:
                if plugin_name not in self._instances:
                    self._instances[plugin_name] = super().create_instance(service_key, **kwargs)

        return self._instances[plugin_name]

    def get_instance(self, service_key: Union[EnumT, str]) -> Optional[ProtocolT]:
        """Get existing instance without creating new one."""
        plugin_name = service_key.value if isinstance(service_key, Enum) else str(service_key)
        return self._instances.get(plugin_name)


# Dependency injection decorators
def service_inject(
    factory: ModernFactory,
    service_key: Union[EnumT, str],
    **factory_kwargs: Any
) -> Callable:
    """Decorator for injecting services."""
    def decorator(func: Callable) -> Callable:
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            service = factory.create_instance(service_key, **factory_kwargs)
            return func(service, *args, **kwargs)
        return wrapper
    return decorator


# Initialize the main container
main_container = AIPerfContainer()


# Convenience function for wiring
def wire_container(modules: list[str]) -> None:
    """Wire the container to specified modules."""
    main_container.wire(modules=modules)


# Auto-discovery function
def discover_and_register_plugins() -> None:
    """Force re-discovery of plugins (useful for testing or runtime registration)."""
    main_container._initialized = False
    main_container._discover_plugins()
    main_container._initialized = True
