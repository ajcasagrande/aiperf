# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Pure dependency injection service system - replaces all factories."""

from typing import Any, Dict, Type, Union
from enum import Enum

from aiperf.common.aiperf_logger import AIPerfLogger
from aiperf.common.enums import ServiceType
from aiperf.common.exceptions import FactoryCreationError
from aiperf.di.containers import get_app_container

logger = AIPerfLogger(__name__)


class ServiceRegistry:
    """Pure DI service registry - no factories, no decorators."""

    def __init__(self):
        self.logger = AIPerfLogger(self.__class__.__name__)

    def create_service(
        self,
        service_type: Union[ServiceType, str],
        **kwargs: Any
    ) -> Any:
        """Create service instance using pure dependency injection."""
        service_name = service_type.value if isinstance(service_type, Enum) else str(service_type)

        try:
            return get_app_container().get_service(service_name, **kwargs)
        except Exception as e:
            raise FactoryCreationError(
                f"Failed to create service '{service_name}': {e}"
            ) from e

    def create_client(self, client_name: str, **kwargs: Any) -> Any:
        """Create client instance using pure dependency injection."""
        try:
            return get_app_container().get_client(client_name, **kwargs)
        except Exception as e:
            raise FactoryCreationError(
                f"Failed to create client '{client_name}': {e}"
            ) from e

    def create_exporter(self, exporter_name: str, **kwargs: Any) -> Any:
        """Create exporter instance using pure dependency injection."""
        try:
            return get_app_container().get_exporter(exporter_name, **kwargs)
        except Exception as e:
            raise FactoryCreationError(
                f"Failed to create exporter '{exporter_name}': {e}"
            ) from e

    def get_service_class(self, service_type: Union[ServiceType, str]) -> Type:
        """Get service class - for compatibility only."""
        service_name = service_type.value if isinstance(service_type, Enum) else str(service_type)

        # This is a compatibility method - in pure DI we don't expose classes
        # Instead, we create instances through the container
        try:
            # Try to get provider info from container
            if hasattr(app_container.services.provided, service_name):
                provider = getattr(app_container.services.provided, service_name)
                # This is a bit hacky but needed for compatibility
                # In practice, code should be migrated to use create_service instead
                instance = provider()
                return type(instance)
            else:
                available = app_container.list_available_services().get('services', [])
                raise FactoryCreationError(
                    f"Service '{service_name}' not found. Available: {available}"
                )
        except Exception as e:
            raise FactoryCreationError(
                f"Failed to get service class for '{service_name}': {e}"
            ) from e

    def list_available_services(self) -> Dict[str, list[str]]:
        """List all available services."""
        return app_container.list_available_services()


# Global service registry instance
service_registry = ServiceRegistry()

# Convenience functions that replace factory usage
def create_service(service_type: Union[ServiceType, str], **kwargs: Any) -> Any:
    """Create service instance - replaces ServiceFactory.create_instance()."""
    return service_registry.create_service(service_type, **kwargs)

def get_service_class(service_type: Union[ServiceType, str]) -> Type:
    """Get service class - replaces ServiceFactory.get_class_from_type()."""
    return service_registry.get_service_class(service_type)

def create_client(client_name: str, **kwargs: Any) -> Any:
    """Create client instance."""
    return service_registry.create_client(client_name, **kwargs)

def create_exporter(exporter_name: str, **kwargs: Any) -> Any:
    """Create exporter instance."""
    return service_registry.create_exporter(exporter_name, **kwargs)

def list_services() -> Dict[str, list[str]]:
    """List all available services."""
    return service_registry.list_available_services()


# Service creation helpers for specific types
def create_system_controller(**kwargs: Any) -> Any:
    """Create system controller service."""
    return create_service(ServiceType.SYSTEM_CONTROLLER, **kwargs)

def create_worker_manager(**kwargs: Any) -> Any:
    """Create worker manager service."""
    return create_service(ServiceType.WORKER_MANAGER, **kwargs)

def create_dataset_manager(**kwargs: Any) -> Any:
    """Create dataset manager service."""
    return create_service(ServiceType.DATASET_MANAGER, **kwargs)

def create_timing_manager(**kwargs: Any) -> Any:
    """Create timing manager service."""
    return create_service(ServiceType.TIMING_MANAGER, **kwargs)

def create_records_manager(**kwargs: Any) -> Any:
    """Create records manager service."""
    return create_service(ServiceType.RECORDS_MANAGER, **kwargs)

def create_record_processor(**kwargs: Any) -> Any:
    """Create record processor service."""
    return create_service(ServiceType.RECORD_PROCESSOR, **kwargs)
