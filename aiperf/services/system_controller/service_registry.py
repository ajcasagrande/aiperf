# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""
Service Registry for tracking and managing services by type and ID.
"""

import asyncio
import time
from collections.abc import AsyncIterator, Iterator

from aiperf.common.constants import DEFAULT_SERVICE_REGISTRATION_TIMEOUT
from aiperf.common.enums import MessageType
from aiperf.common.enums.command_enums import CommandType
from aiperf.common.enums.service_enums import (
    LifecycleState,
    ServiceRegistrationStatus,
    ServiceType,
)
from aiperf.common.exceptions import InvalidStateError
from aiperf.common.hooks import on_command, on_message
from aiperf.common.messages.command_messages import RegisterServiceCommand
from aiperf.common.messages.service_messages import HeartbeatMessage, StatusMessage
from aiperf.common.mixins import CommandHandlerMixin
from aiperf.common.models import ProcessHealth, ServiceRegistrationInfo
from aiperf.common.types import ServiceTypeT


class ServiceRegistryMixin(CommandHandlerMixin):
    """
    Centralized registry for tracking services by type and ID.

    This class provides a clean interface for registering, looking up, and managing
    services in the AIPerf system.
    """

    def __init__(self, service_id: str, **kwargs):
        super().__init__(service_id=service_id, id=service_id, **kwargs)
        self.service_type = ServiceType.SYSTEM_CONTROLLER
        self.service_id = service_id

        self._registry_lock = asyncio.Lock()
        # Services required by the service manager ServiceType -> number of replicas
        self._required_services: dict[ServiceTypeT, int] = {}
        # Services organized by type -> set of service IDs
        self._services_by_type: dict[ServiceTypeT, set[str]] = {}
        # Direct lookup by service ID -> service info
        self._services_by_id: dict[str, ServiceRegistrationInfo] = {}
        # Service ID -> ProcessHealth
        self._service_health: dict[str, ProcessHealth] = {}

        # Event that is set when all required services are registered
        self._all_services_registered_event = asyncio.Event()

    def set_required_services(self, required_services: dict[ServiceTypeT, int]) -> None:
        """Set the required services for the service manager."""
        self._required_services = required_services
        self._all_services_registered_event.clear()

    def add_required_service(
        self, service_type: ServiceTypeT, num_replicas: int
    ) -> None:
        """Add a required service to the service manager."""
        if service_type in self._required_services:
            self._required_services[service_type] += num_replicas
        else:
            self._required_services[service_type] = num_replicas

        self._all_services_registered_event.clear()

    def remove_required_service(
        self, service_type: ServiceTypeT, num_replicas: int
    ) -> None:
        """Remove a required service from the service manager."""
        if service_type in self._required_services:
            self._required_services[service_type] -= num_replicas
            if self._required_services[service_type] <= 0:
                del self._required_services[service_type]

    @on_command(CommandType.REGISTER_SERVICE)
    async def _handle_register_service_command(
        self, message: RegisterServiceCommand
    ) -> None:
        """Register a new service in the registry and return the service info."""
        async with self._registry_lock:
            # if the service is already registered, raise an error
            if message.service_id in self._services_by_id:
                raise InvalidStateError(
                    f"Service {message.service_id} is already registered"
                )

            # otherwise, create a new registration info
            current_time = time.time_ns()
            registration_info = ServiceRegistrationInfo(
                service_id=message.service_id,
                service_type=message.service_type,
                first_seen=current_time,
                last_seen=current_time,
                state=message.state,
                registration_status=ServiceRegistrationStatus.REGISTERED,
            )

            # add to both indexes
            if registration_info.service_type not in self._services_by_type:
                self._services_by_type[registration_info.service_type] = set()

            self._services_by_type[registration_info.service_type].add(
                registration_info.service_id
            )
            self._services_by_id[registration_info.service_id] = registration_info

        self.info(
            f"Registered service {message.service_id} of type {message.service_type}"
        )
        self._check_all_services_registered()

    def _check_all_services_registered(self) -> bool:
        """Check if all required services are registered."""
        for service_type, num_replicas in self._required_services.items():
            if self.num_replicas(service_type) < num_replicas:
                return False

        self._all_services_registered_event.set()
        self.info("All required services are registered")
        return True

    async def wait_for_all_services_registered(
        self, timeout: float = DEFAULT_SERVICE_REGISTRATION_TIMEOUT
    ) -> bool:
        """Wait for all required services to be registered."""
        try:
            await asyncio.wait_for(self._all_services_registered_event.wait(), timeout)
            return True
        except asyncio.TimeoutError:
            self.warning("Timed out waiting for all required services to be registered")
            return False

    def unregister_service(self, service_id: str) -> None:
        """Unregister a service from the registry."""
        if service_id not in self._services_by_id:
            self.warning(f"Attempted to unregister unknown service {service_id}")
            return

        registration_info = self._services_by_id[service_id]
        service_type = registration_info.service_type

        # remove from both indexes
        del self._services_by_id[service_id]
        self._services_by_type[service_type].discard(service_id)

        # clean up empty service type entries
        if not self._services_by_type[service_type]:
            del self._services_by_type[service_type]

        self.info(f"Unregistered service {service_id} of type {service_type}")

    def num_replicas(self, service_type: ServiceTypeT) -> int:
        """Get the number of replicas of a specific service type."""
        return len(self._services_by_type.get(service_type, set()))

    def services_with_state(self, *states: LifecycleState) -> set[str]:
        """Get all service IDs with a specific state."""
        return set(
            service_id
            for service_id, service_info in self._services_by_id.items()
            if service_info.state in states
        )

    @on_message(MessageType.STATUS)
    def _update_service_state(self, message: StatusMessage) -> None:
        """Update the state of a registered service."""
        service_id = message.service_id
        state = message.state

        if service_id not in self._services_by_id:
            self.warning(f"Attempted to update state of unknown service {service_id}")
            return

        info = self._services_by_id[service_id]
        info.state = state
        info.last_seen = time.time_ns()

        self.debug(lambda: f"Updated service {service_id} state to {state}")

    @on_message(MessageType.HEARTBEAT)
    def _update_service_heartbeat(self, message: HeartbeatMessage) -> None:
        """Update the last seen timestamp for a service (heartbeat)."""
        service_id = message.service_id

        if service_id not in self._services_by_id:
            self.debug(lambda: f"Received heartbeat from unknown service {service_id}")
            # TODO: Should this automatically register the service?
            return

        info = self._services_by_id[service_id]
        info.last_seen = time.time_ns()

    def clear(self) -> None:
        """Clear all registered services from the registry."""
        self._services_by_type.clear()
        self._services_by_id.clear()
        self.debug("Cleared all services from registry")

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

    def service_ids_by_type(self, service_type: ServiceTypeT) -> set[str]:
        return self._services_by_type.get(service_type, set())

    def all_service_types(self) -> set[ServiceTypeT]:
        return set(self._services_by_type.keys())

    def all_service_ids(self) -> set[str]:
        return set(self._services_by_id.keys())
