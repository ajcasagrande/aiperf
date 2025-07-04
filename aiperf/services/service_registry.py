# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""
Service Registry for tracking and managing services by type and ID.

This module provides a centralized registry for tracking services, making it easier
to look up services by type or ID, and manage service lifecycle.
"""

import logging
import time

from aiperf.common.enums import ServiceRegistrationStatus, ServiceState, ServiceType
from aiperf.common.service_models import ServiceRunInfo


class ServiceRegistry:
    """
    Centralized registry for tracking services by type and ID.

    This class provides a clean interface for registering, looking up, and managing
    services in the AIPerf system.
    """

    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)

        # Primary storage: services organized by type
        self._services_by_type: dict[ServiceType, dict[str, ServiceRunInfo]] = {}

        # Secondary index: direct lookup by service ID
        self._services_by_id: dict[str, ServiceRunInfo] = {}

    def register_service(
        self,
        service_id: str,
        service_type: ServiceType,
        state: ServiceState = ServiceState.READY,
        registration_status: ServiceRegistrationStatus = ServiceRegistrationStatus.REGISTERED,
    ) -> ServiceRunInfo:
        """
        Register a new service in the registry.

        Args:
            service_id: Unique identifier for the service
            service_type: Type of the service
            state: Initial state of the service
            registration_status: Registration status of the service

        Returns:
            ServiceRunInfo object for the registered service

        Raises:
            ValueError: If service_id is already registered
        """
        if service_id in self._services_by_id:
            raise ValueError(f"Service {service_id} is already registered")

        current_time = time.time_ns()
        service_info = ServiceRunInfo(
            registration_status=registration_status,
            service_type=service_type,
            service_id=service_id,
            first_seen=current_time,
            state=state,
            last_seen=current_time,
        )

        # Add to both indexes
        if service_type not in self._services_by_type:
            self._services_by_type[service_type] = {}

        self._services_by_type[service_type][service_id] = service_info
        self._services_by_id[service_id] = service_info

        self.logger.debug(f"Registered service {service_id} of type {service_type}")
        return service_info

    def unregister_service(self, service_id: str) -> bool:
        """
        Unregister a service from the registry.

        Args:
            service_id: ID of the service to unregister

        Returns:
            True if service was found and removed, False otherwise
        """
        if service_id not in self._services_by_id:
            self.logger.warning(f"Attempted to unregister unknown service {service_id}")
            return False

        service_info = self._services_by_id[service_id]
        service_type = service_info.service_type

        # Remove from both indexes
        del self._services_by_id[service_id]
        del self._services_by_type[service_type][service_id]

        # Clean up empty service type entries
        if not self._services_by_type[service_type]:
            del self._services_by_type[service_type]

        self.logger.debug(f"Unregistered service {service_id} of type {service_type}")
        return True

    def get_service(self, service_id: str) -> ServiceRunInfo | None:
        """
        Get service information by service ID.

        Args:
            service_id: ID of the service to look up

        Returns:
            ServiceRunInfo if found, None otherwise
        """
        return self._services_by_id.get(service_id)

    def get_services_by_type(
        self, service_type: ServiceType
    ) -> dict[str, ServiceRunInfo]:
        """
        Get all services of a specific type.

        Args:
            service_type: Type of services to retrieve

        Returns:
            Dictionary mapping service_id -> ServiceRunInfo for all services of the type
        """
        return self._services_by_type.get(service_type, {}).copy()

    def get_service_ids_by_type(self, service_type: ServiceType) -> set[str]:
        """
        Get all service IDs of a specific type.

        Args:
            service_type: Type of services to retrieve IDs for

        Returns:
            Set of service IDs for the specified type
        """
        return set(self._services_by_type.get(service_type, {}).keys())

    def get_all_service_types(self) -> set[ServiceType]:
        """
        Get all service types currently registered.

        Returns:
            Set of all service types in the registry
        """
        return set(self._services_by_type.keys())

    def get_all_service_ids(self) -> set[str]:
        """
        Get all service IDs currently registered.

        Returns:
            Set of all service IDs in the registry
        """
        return set(self._services_by_id.keys())

    def get_service_count_by_type(self, service_type: ServiceType) -> int:
        """
        Get count of services of a specific type.

        Args:
            service_type: Type of services to count

        Returns:
            Number of services of the specified type
        """
        return len(self._services_by_type.get(service_type, {}))

    def get_total_service_count(self) -> int:
        """
        Get total count of all registered services.

        Returns:
            Total number of registered services
        """
        return len(self._services_by_id)

    def update_service_state(self, service_id: str, state: ServiceState) -> bool:
        """
        Update the state of a registered service.

        Args:
            service_id: ID of the service to update
            state: New state for the service

        Returns:
            True if service was found and updated, False otherwise
        """
        if service_id not in self._services_by_id:
            self.logger.warning(
                f"Attempted to update state of unknown service {service_id}"
            )
            return False

        service_info = self._services_by_id[service_id]
        service_info.state = state
        service_info.last_seen = time.time_ns()

        self.logger.debug(f"Updated service {service_id} state to {state}")
        return True

    def update_service_heartbeat(self, service_id: str) -> bool:
        """
        Update the last seen timestamp for a service (heartbeat).

        Args:
            service_id: ID of the service that sent a heartbeat

        Returns:
            True if service was found and updated, False otherwise
        """
        if service_id not in self._services_by_id:
            self.logger.debug(f"Received heartbeat from unknown service {service_id}")
            return False

        service_info = self._services_by_id[service_id]
        service_info.last_seen = time.time_ns()

        return True

    def is_service_registered(self, service_id: str) -> bool:
        """
        Check if a service is registered.

        Args:
            service_id: ID of the service to check

        Returns:
            True if service is registered, False otherwise
        """
        return service_id in self._services_by_id

    def has_service_type(self, service_type: ServiceType) -> bool:
        """
        Check if any services of a specific type are registered.

        Args:
            service_type: Type to check for

        Returns:
            True if at least one service of the type is registered
        """
        return (
            service_type in self._services_by_type
            and len(self._services_by_type[service_type]) > 0
        )

    def get_services_by_registration_status(
        self, registration_status: ServiceRegistrationStatus
    ) -> dict[str, ServiceRunInfo]:
        """
        Get all services with a specific registration status.

        Args:
            registration_status: Registration status to filter by

        Returns:
            Dictionary mapping service_id -> ServiceRunInfo for matching services
        """
        return {
            service_id: service_info
            for service_id, service_info in self._services_by_id.items()
            if service_info.registration_status == registration_status
        }

    def get_services_by_state(self, state: ServiceState) -> dict[str, ServiceRunInfo]:
        """
        Get all services with a specific state.

        Args:
            state: State to filter by

        Returns:
            Dictionary mapping service_id -> ServiceRunInfo for matching services
        """
        return {
            service_id: service_info
            for service_id, service_info in self._services_by_id.items()
            if service_info.state == state
        }

    def clear(self) -> None:
        """Clear all registered services from the registry."""
        self._services_by_type.clear()
        self._services_by_id.clear()
        self.logger.debug("Cleared all services from registry")

    def get_registry_summary(self) -> dict:
        """
        Get a summary of the current registry state.

        Returns:
            Dictionary with registry statistics and service counts by type
        """
        service_counts_by_type = {
            service_type: len(services)
            for service_type, services in self._services_by_type.items()
        }

        return {
            "total_services": self.get_total_service_count(),
            "service_types": len(self._services_by_type),
            "services_by_type": service_counts_by_type,
            "registered_services": len(
                self.get_services_by_registration_status(
                    ServiceRegistrationStatus.REGISTERED
                )
            ),
        }
