# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Backward compatibility adapter for existing factory usage.

This module provides adapters that allow existing code to work with the new
dependency injection system without requiring immediate migration.
"""

import warnings
from typing import Any, Generic, TypeVar, Union
from enum import Enum

from aiperf.common.di_container import ModernFactory, SingletonFactory, main_container
from aiperf.common.modern_factories import (
    service_factory,
    communication_factory,
    data_exporter_factory,
    ui_factory,
    service_manager_factory,
    record_processor_factory,
    results_processor_factory,
    request_rate_generator_factory,
    zmq_proxy_factory,
)
from aiperf.common.exceptions import FactoryCreationError

EnumT = TypeVar('EnumT', bound=Enum)
ProtocolT = TypeVar('ProtocolT')


class FactoryAdapter(Generic[EnumT, ProtocolT]):
    """Adapter that provides backward compatibility with the old factory interface."""

    def __init__(self, modern_factory: Union[ModernFactory, SingletonFactory]):
        self._modern_factory = modern_factory
        self._deprecation_warned = False

    def _warn_deprecation(self, method_name: str) -> None:
        """Warn about deprecated usage."""
        if not self._deprecation_warned:
            warnings.warn(
                f"Using legacy factory method '{method_name}' is deprecated. "
                f"Consider migrating to the modern dependency injection system.",
                DeprecationWarning,
                stacklevel=3
            )
            self._deprecation_warned = True

    @classmethod
    def register(cls, class_type: EnumT | str, override_priority: int = 0):
        """Legacy register decorator - now logs warning and does nothing."""
        def decorator(service_class):
            warnings.warn(
                f"Legacy @Factory.register() decorator is deprecated. "
                f"Register '{class_type}' in pyproject.toml entry points instead.",
                DeprecationWarning,
                stacklevel=2
            )
            return service_class
        return decorator

    @classmethod
    def register_all(cls, *class_types: EnumT | str, override_priority: int = 0):
        """Legacy register_all decorator - now logs warning and does nothing."""
        def decorator(service_class):
            warnings.warn(
                f"Legacy @Factory.register_all() decorator is deprecated. "
                f"Register {class_types} in pyproject.toml entry points instead.",
                DeprecationWarning,
                stacklevel=2
            )
            return service_class
        return decorator

    def create_instance(self, class_type: EnumT | str, **kwargs: Any) -> ProtocolT:
        """Create instance using modern factory."""
        self._warn_deprecation('create_instance')
        return self._modern_factory.create_instance(class_type, **kwargs)

    def get_class_from_type(self, class_type: EnumT | str):
        """Get class from type - not supported in modern system."""
        self._warn_deprecation('get_class_from_type')
        warnings.warn(
            "get_class_from_type() is not supported in the modern DI system. "
            "Use create_instance() instead.",
            DeprecationWarning,
            stacklevel=2
        )
        raise NotImplementedError(
            "get_class_from_type() is not supported in the modern DI system"
        )

    def get_all_classes(self):
        """Get all classes - not directly supported in modern system."""
        self._warn_deprecation('get_all_classes')
        warnings.warn(
            "get_all_classes() is not directly supported in the modern DI system. "
            "Use get_available_implementations() instead.",
            DeprecationWarning,
            stacklevel=2
        )
        return []

    def get_all_class_types(self):
        """Get all class types."""
        self._warn_deprecation('get_all_class_types')
        return self._modern_factory.get_available_implementations()

    def get_all_classes_and_types(self):
        """Get all classes and types - not directly supported."""
        self._warn_deprecation('get_all_classes_and_types')
        warnings.warn(
            "get_all_classes_and_types() is not directly supported in the modern DI system.",
            DeprecationWarning,
            stacklevel=2
        )
        return []


class SingletonFactoryAdapter(FactoryAdapter[EnumT, ProtocolT]):
    """Adapter for singleton factories with additional singleton-specific methods."""

    def __init__(self, modern_factory: SingletonFactory):
        super().__init__(modern_factory)
        self._singleton_factory = modern_factory

    def set_instance(self, class_type: EnumT | str, instance: ProtocolT) -> None:
        """Set instance - not supported in modern system."""
        self._warn_deprecation('set_instance')
        warnings.warn(
            "set_instance() is not supported in the modern DI system. "
            "Use dependency injection configuration instead.",
            DeprecationWarning,
            stacklevel=2
        )
        raise NotImplementedError("set_instance() is not supported in the modern DI system")

    def get_or_create_instance(self, class_type: EnumT | str, **kwargs: Any) -> ProtocolT:
        """Get or create instance - same as create_instance for singletons."""
        self._warn_deprecation('get_or_create_instance')
        return self._singleton_factory.create_instance(class_type, **kwargs)

    def get_instance(self, class_type: EnumT | str) -> ProtocolT:
        """Get existing instance."""
        self._warn_deprecation('get_instance')
        instance = self._singleton_factory.get_instance(class_type)
        if instance is None:
            raise FactoryCreationError(
                f"No instance found for {class_type}. Call create_instance() first."
            )
        return instance

    def get_all_instances(self):
        """Get all instances - not directly supported."""
        self._warn_deprecation('get_all_instances')
        warnings.warn(
            "get_all_instances() is not directly supported in the modern DI system.",
            DeprecationWarning,
            stacklevel=2
        )
        return {}

    def has_instance(self, class_type: EnumT | str) -> bool:
        """Check if instance exists."""
        self._warn_deprecation('has_instance')
        return self._singleton_factory.get_instance(class_type) is not None


# Create backward compatibility adapters for existing factories
ServiceFactory = FactoryAdapter(service_factory)
CommunicationFactory = SingletonFactoryAdapter(communication_factory)
DataExporterFactory = FactoryAdapter(data_exporter_factory)
AIPerfUIFactory = SingletonFactoryAdapter(ui_factory)
ServiceManagerFactory = FactoryAdapter(service_manager_factory)
RecordProcessorFactory = FactoryAdapter(record_processor_factory)
ResultsProcessorFactory = FactoryAdapter(results_processor_factory)
RequestRateGeneratorFactory = FactoryAdapter(request_rate_generator_factory)
ZMQProxyFactory = FactoryAdapter(zmq_proxy_factory)

# Additional adapters for other factories can be added as needed
CommunicationClientFactory = FactoryAdapter(None)  # Placeholder
ComposerFactory = FactoryAdapter(None)  # Placeholder
ConsoleExporterFactory = FactoryAdapter(None)  # Placeholder
CustomDatasetFactory = FactoryAdapter(None)  # Placeholder
InferenceClientFactory = FactoryAdapter(None)  # Placeholder
OpenAIObjectParserFactory = SingletonFactoryAdapter(None)  # Placeholder
RequestConverterFactory = SingletonFactoryAdapter(None)  # Placeholder
ResponseExtractorFactory = FactoryAdapter(None)  # Placeholder


def migrate_to_modern_di() -> None:
    """Helper function to display migration guidance."""
    print("""
=== AIPerf Factory Migration Guide ===

Your code is using the legacy factory system. To migrate to the modern
dependency injection system:

1. Replace factory imports:
   OLD: from aiperf.di import create_service
# Service registered via entry points in pyproject.toml
   NEW: from aiperf.common.modern_factories import service_factory

2. Replace factory usage:
   OLD: create_service(ServiceType.WORKER, **kwargs)
   NEW: service_factory.create_instance(ServiceType.WORKER, **kwargs)

3. Remove @Factory.register decorators - use entry points in pyproject.toml instead

4. For custom plugins, add entry points to your pyproject.toml:
   [project.entry-points."aiperf.services"]
   my_service = "my_package.my_service:MyService"

5. Use dependency injection for cleaner code:
   from aiperf.common.di_container import service_inject

   @service_inject(service_factory, ServiceType.WORKER)
   def my_function(worker_service, other_args):
       # worker_service is automatically injected
       pass

For more information, see the migration documentation.
""")


# Provide migration helper
__all__ = [
    'ServiceFactory',
    'CommunicationFactory',
    'DataExporterFactory',
    'AIPerfUIFactory',
    'ServiceManagerFactory',
    'RecordProcessorFactory',
    'ResultsProcessorFactory',
    'RequestRateGeneratorFactory',
    'ZMQProxyFactory',
    'migrate_to_modern_di',
]
