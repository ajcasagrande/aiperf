# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""
Service Registry for tracking and managing services by type and ID.
"""

import logging
import time
from collections.abc import AsyncIterator, Iterator

from aiperf.common.enums import ServiceState, ServiceType
from aiperf.common.models import ServiceRegistrationInfo


class ServiceRegistry:
    """
    Centralized registry for tracking services by type and ID.

    This class provides a clean interface for registering, looking up, and managing
    services in the AIPerf system.
    """

    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)

        # Services organized by type -> set of service IDs
        self._services_by_type: dict[ServiceType, set[str]] = {}
        # Direct lookup by service ID -> service info
        self._services_by_id: dict[str, ServiceRegistrationInfo] = {}

    def register_service(
        self,
        service_id: str,
        service_type: ServiceType,
        state: ServiceState = ServiceState.READY,
    ) -> ServiceRegistrationInfo:
        """Register a new service in the registry and return the service info."""

        if service_id in self._services_by_id:
            raise ValueError(f"Service {service_id} is already registered")

        current_time = time.time_ns()
        service_info = ServiceRegistrationInfo(
            service_id=service_id,
            service_type=service_type,
            first_seen=current_time,
            last_seen=current_time,
            state=state,
        )

        # add to both indexes
        if service_type not in self._services_by_type:
            self._services_by_type[service_type] = set()

        self._services_by_type[service_type].add(service_id)
        self._services_by_id[service_id] = service_info

        self.logger.debug("Registered service %s of type %s", service_id, service_type)
        return service_info

    def unregister_service(self, service_id: str) -> bool:
        """Unregister a service from the registry and return True if successful."""
        if service_id not in self._services_by_id:
            self.logger.warning(
                "Attempted to unregister unknown service %s", service_id
            )
            return False

        service_info = self._services_by_id[service_id]
        service_type = service_info.service_type

        # remove from both indexes
        del self._services_by_id[service_id]
        self._services_by_type[service_type].discard(service_id)

        # clean up empty service type entries
        if not self._services_by_type[service_type]:
            del self._services_by_type[service_type]

        self.logger.debug(
            "Unregistered service %s of type %s", service_id, service_type
        )
        return True

    def __contains__(self, service_id: str) -> bool:
        return service_id in self._services_by_id

    def __getitem__(self, service_id: str) -> ServiceRegistrationInfo:
        return self._services_by_id[service_id]

    def __len__(self) -> int:
        return len(self._services_by_id)

    def __iter__(self) -> Iterator[ServiceRegistrationInfo]:
        return iter(self._services_by_id.values())

    async def __aiter__(self) -> AsyncIterator[ServiceRegistrationInfo]:
        for service_info in list(self._services_by_id.values()):
            yield service_info

    def service_ids_by_type(self, service_type: ServiceType) -> set[str]:
        return self._services_by_type.get(service_type, set())

    def all_service_types(self) -> set[ServiceType]:
        return set(self._services_by_type.keys())

    def all_service_ids(self) -> set[str]:
        return set(self._services_by_id.keys())

    def num_replicas(self, service_type: ServiceType) -> int:
        """Get the number of replicas of a specific service type."""
        return len(self._services_by_type.get(service_type, set()))

    def services_with_state(self, *states: ServiceState) -> set[str]:
        """Get all service IDs with a specific state."""
        return set(
            service_id
            for service_id, service_info in self._services_by_id.items()
            if service_info.state in states
        )

    def update_service_state(self, service_id: str, state: ServiceState) -> bool:
        """Update the state of a registered service and return True if successful."""
        if service_id not in self._services_by_id:
            # TODO: Should this automatically register the service?
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
        """Update the last seen timestamp for a service (heartbeat) and return True if successful."""
        if service_id not in self._services_by_id:
            # TODO: Should this automatically register the service?
            self.logger.debug("Received heartbeat from unknown service %s", service_id)
            return False

        service_info = self._services_by_id[service_id]
        service_info.last_seen = time.time_ns()

        return True

    def clear(self) -> None:
        """Clear all registered services from the registry."""
        self._services_by_type.clear()
        self._services_by_id.clear()
        self.logger.debug("Cleared all services from registry")


# Create a global instance
GlobalServiceRegistry = ServiceRegistry()
