# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""
Service Registry for tracking and managing services by type and ID.
"""

import logging
import time

from aiperf.common.enums import ServiceRegistrationStatus, ServiceState, ServiceType
from aiperf.common.service_models import ServiceRegistrationInfo


class ServiceRegistry:
    """
    Centralized registry for tracking services by type and ID.

    This class provides a clean interface for registering, looking up, and managing
    services in the AIPerf system.
    """

    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)

        # services organized by type
        self._services_by_type: dict[
            ServiceType, dict[str, ServiceRegistrationInfo]
        ] = {}
        # direct lookup by service ID
        self._services_by_id: dict[str, ServiceRegistrationInfo] = {}

    def register_service(
        self,
        service_id: str,
        service_type: ServiceType,
        state: ServiceState = ServiceState.READY,
        registration_status: ServiceRegistrationStatus = ServiceRegistrationStatus.REGISTERED,
    ) -> ServiceRegistrationInfo:
        """Register a new service in the registry."""
        if service_id in self._services_by_id:
            raise ValueError(f"Service {service_id} is already registered")

        current_time = time.time_ns()
        service_info = ServiceRegistrationInfo(
            registration_status=registration_status,
            service_type=service_type,
            service_id=service_id,
            first_seen=current_time,
            state=state,
            last_seen=current_time,
        )

        # add to both indexes
        if service_type not in self._services_by_type:
            self._services_by_type[service_type] = {}

        self._services_by_type[service_type][service_id] = service_info
        self._services_by_id[service_id] = service_info

        self.logger.debug("Registered service %s of type %s", service_id, service_type)
        return service_info

    def unregister_service(self, service_id: str) -> bool:
        """Unregister a service from the registry."""
        if service_id not in self._services_by_id:
            self.logger.warning(
                "Attempted to unregister unknown service %s", service_id
            )
            return False

        service_info = self._services_by_id[service_id]
        service_type = service_info.service_type

        # remove from both indexes
        del self._services_by_id[service_id]
        del self._services_by_type[service_type][service_id]

        # clean up empty service type entries
        if not self._services_by_type[service_type]:
            del self._services_by_type[service_type]

        self.logger.debug(
            "Unregistered service %s of type %s", service_id, service_type
        )
        return True

    def service_by_id(self, service_id: str) -> ServiceRegistrationInfo | None:
        """Get service information by service ID."""
        return self._services_by_id.get(service_id)

    def get_service(self, service_id: str) -> ServiceRegistrationInfo | None:
        """Get service information by service ID."""
        return self._services_by_id.get(service_id)

    def services_by_type(
        self, service_type: ServiceType
    ) -> dict[str, ServiceRegistrationInfo]:
        """Get all services of a specific type."""
        return self._services_by_type.get(service_type, {}).copy()

    def service_ids_by_type(self, service_type: ServiceType) -> set[str]:
        """Get all service IDs of a specific type."""
        return set(self._services_by_type.get(service_type, {}).keys())

    def all_service_types(self) -> set[ServiceType]:
        """Get all service types currently registered."""
        return set(self._services_by_type.keys())

    def all_service_ids(self) -> set[str]:
        """Get all service IDs currently registered."""
        return set(self._services_by_id.keys())

    def service_count_by_type(self, service_type: ServiceType) -> int:
        """Get count of services of a specific type."""
        return len(self._services_by_type.get(service_type, {}))

    def total_service_count(self) -> int:
        """Get total count of all registered services."""
        return len(self._services_by_id)

    def update_service_state(self, service_id: str, state: ServiceState) -> bool:
        """Update the state of a registered service."""
        if service_id not in self._services_by_id:
            self.logger.warning(
                "Attempted to update state of unknown service %s", service_id
            )
            return False

        service_info = self._services_by_id[service_id]
        service_info.state = state
        service_info.last_seen = time.time_ns()

        self.logger.debug("Updated service %s state to %s", service_id, state)
        return True

    def update_service_heartbeat(self, service_id: str) -> bool:
        """Update the last seen timestamp for a service (heartbeat)."""
        if service_id not in self._services_by_id:
            self.logger.debug("Received heartbeat from unknown service %s", service_id)
            return False

        service_info = self._services_by_id[service_id]
        service_info.last_seen = time.time_ns()

        return True

    def is_service_registered(self, service_id: str) -> bool:
        """Check if a service is registered."""
        return service_id in self._services_by_id

    def has_service_type(self, service_type: ServiceType) -> bool:
        """Check if any services of a specific type are registered."""
        return (
            service_type in self._services_by_type
            and len(self._services_by_type[service_type]) > 0
        )

    def services_by_registration_status(
        self, registration_status: ServiceRegistrationStatus
    ) -> dict[str, ServiceRegistrationInfo]:
        """Get all services with a specific registration status."""
        return {
            service_id: service_info
            for service_id, service_info in self._services_by_id.items()
            if service_info.registration_status == registration_status
        }

    def services_by_state(
        self, state: ServiceState
    ) -> dict[str, ServiceRegistrationInfo]:
        """Get all services with a specific state."""
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

    def registry_summary(self) -> dict:
        """Get a summary of the current registry state."""
        service_counts_by_type = {
            service_type: len(services)
            for service_type, services in self._services_by_type.items()
        }

        return {
            "total_services": self.total_service_count(),
            "service_types": len(self._services_by_type),
            "services_by_type": service_counts_by_type,
            "registered_services": len(
                self.services_by_registration_status(
                    ServiceRegistrationStatus.REGISTERED
                )
            ),
        }
