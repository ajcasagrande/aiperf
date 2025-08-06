# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

import asyncio
import time

from aiperf.common.enums import ServiceRegistrationStatus
from aiperf.common.enums.service_enums import LifecycleState
from aiperf.common.messages import HeartbeatMessage, StatusMessage
from aiperf.common.messages.command_messages import RegisterServiceCommand
from aiperf.common.mixins.aiperf_lifecycle_mixin import AIPerfLifecycleMixin
from aiperf.common.models import ServiceRunInfo
from aiperf.common.registry.service_registry import ServiceRegistry
from aiperf.common.types import ServiceTypeT


class EnhancedServiceRegistryMixin(AIPerfLifecycleMixin):
    """Mixin providing enhanced service registry capabilities with thread safety."""

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._service_registry = ServiceRegistry()
        self.attach_child_lifecycle(self._service_registry)

        self._heartbeat_lock = asyncio.Lock()
        self._registration_lock = asyncio.Lock()

    @property
    def service_registry(self) -> ServiceRegistry:
        """Access to the service registry instance."""
        return self._service_registry

    async def handle_service_registration(
        self,
        message: RegisterServiceCommand,
    ) -> bool:
        """Handle service registration with atomic operations."""
        async with self._registration_lock:
            service_info = ServiceRunInfo(
                registration_status=ServiceRegistrationStatus.REGISTERED,
                service_type=message.service_type,
                service_id=message.service_id,
                first_seen=time.time_ns(),
                state=message.state,
                last_seen=time.time_ns(),
            )

            return await self._service_registry.register_service(
                service_id=message.service_id,
                service_type=message.service_type,
                service_info=service_info,
            )

    async def handle_service_heartbeat(
        self,
        message: HeartbeatMessage,
    ) -> bool:
        """Handle service heartbeat with state synchronization."""
        async with self._heartbeat_lock:
            return await self._service_registry.update_service_heartbeat(
                service_id=message.service_id,
                timestamp=message.request_ns,
                state=message.state,
            )

    async def handle_service_status_update(
        self,
        message: StatusMessage,
    ) -> bool:
        """Handle service status updates with atomic state changes."""
        return await self._service_registry.update_service_state(
            service_id=message.service_id,
            new_state=message.state,
            update_timestamp=True,
        )

    async def wait_for_required_services(
        self,
        required_services: dict[ServiceTypeT, int],
        timeout: float | None = None,
    ) -> bool:
        """Wait for required services to be registered."""
        service_types = set(required_services.keys())
        return await self._service_registry.wait_for_service_types(
            service_types=service_types,
            status=ServiceRegistrationStatus.REGISTERED,
            timeout=timeout,
        )

    async def get_registered_services_by_type(
        self,
        service_type: ServiceTypeT,
        state: LifecycleState | None = None,
    ) -> list[ServiceRunInfo]:
        """Get all registered services of a specific type."""
        result = await self._service_registry.get_services_by_type(
            service_type=service_type,
            status=ServiceRegistrationStatus.REGISTERED,
            state=state,
        )
        return result.services

    async def get_all_service_ids(self) -> set[str]:
        """Get all registered service IDs."""
        result = await self._service_registry.get_services_by_status(
            ServiceRegistrationStatus.REGISTERED
        )
        return {service.service_id for service in result.services}

    async def is_service_registered(self, service_id: str) -> bool:
        """Check if a service is registered."""
        service_info = await self._service_registry.get_service(service_id)
        return (
            service_info is not None
            and service_info.registration_status == ServiceRegistrationStatus.REGISTERED
        )

    async def unregister_service(self, service_id: str) -> bool:
        """Unregister a service."""
        result = await self._service_registry.unregister_service(service_id)
        return result is not None
