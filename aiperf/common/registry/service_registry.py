# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

import asyncio
import time
import weakref
from collections import defaultdict
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

from pydantic import BaseModel, Field

from aiperf.common.aiperf_logger import AIPerfLogger
from aiperf.common.enums import ServiceRegistrationStatus
from aiperf.common.enums.service_enums import LifecycleState
from aiperf.common.mixins.aiperf_lifecycle_mixin import AIPerfLifecycleMixin
from aiperf.common.models import ServiceRunInfo
from aiperf.common.types import ServiceTypeT


class ServiceRegistryStats(BaseModel):
    """Statistics about the service registry state."""

    total_services: int = Field(
        default=0, description="Total number of registered services"
    )
    services_by_type: dict[ServiceTypeT, int] = Field(
        default_factory=dict, description="Count of services by type"
    )
    services_by_status: dict[ServiceRegistrationStatus, int] = Field(
        default_factory=dict, description="Count of services by registration status"
    )
    services_by_state: dict[LifecycleState, int] = Field(
        default_factory=dict, description="Count of services by lifecycle state"
    )
    last_updated: float = Field(
        default_factory=time.time, description="Timestamp of last stats update"
    )


class ServiceLookupResult(BaseModel):
    """Result of a service lookup operation."""

    services: list[ServiceRunInfo] = Field(
        default_factory=list, description="List of matching services"
    )
    total_count: int = Field(description="Total number of matching services")
    lookup_timestamp: float = Field(
        default_factory=time.time, description="Timestamp when lookup was performed"
    )


class ServiceRegistry(AIPerfLifecycleMixin):
    """Thread-safe service registry with atomic operations and event notifications."""

    def __init__(self, stats_update_interval: float = 30.0, **kwargs) -> None:
        super().__init__(**kwargs)
        self._logger = AIPerfLogger(self.__class__.__name__)

        self._service_id_map: dict[str, ServiceRunInfo] = {}
        self._service_type_map: dict[ServiceTypeT, set[str]] = defaultdict(set)
        self._service_status_map: dict[ServiceRegistrationStatus, set[str]] = (
            defaultdict(set)
        )
        self._service_state_map: dict[LifecycleState, set[str]] = defaultdict(set)

        self._global_lock = asyncio.Lock()
        self._service_locks: dict[str, asyncio.Lock] = {}
        self._lock_cleanup_refs: weakref.WeakValueDictionary[str, asyncio.Lock] = (
            weakref.WeakValueDictionary()
        )
        self._lock_creation_lock = asyncio.Lock()

        self._registration_events: dict[ServiceTypeT, asyncio.Event] = {}
        self._state_change_callbacks: list[tuple[weakref.ReferenceType, Any]] = []

        self._stats = ServiceRegistryStats()
        self._stats_update_interval = stats_update_interval
        self._stats_dirty = True

    @asynccontextmanager
    async def _service_lock(self, service_id: str) -> AsyncGenerator[None, None]:
        """Get or create a per-service lock with automatic cleanup."""
        # First, ensure the lock exists (separate from global lock to avoid deadlock)
        async with self._lock_creation_lock:
            if service_id not in self._service_locks:
                lock = asyncio.Lock()
                self._service_locks[service_id] = lock
                self._lock_cleanup_refs[service_id] = lock

        # Now acquire the service-specific lock
        lock = self._service_locks[service_id]
        async with lock:
            yield

        # Cleanup check - must check service existence under global lock for consistency
        async with self._global_lock:
            service_exists = service_id in self._service_id_map

        if not service_exists:
            async with self._lock_creation_lock:
                # Double-check pattern to avoid race with lock creation
                if service_id in self._service_locks:
                    async with self._global_lock:
                        if service_id not in self._service_id_map:
                            del self._service_locks[service_id]

    async def register_service(
        self,
        service_id: str,
        service_type: ServiceTypeT,
        service_info: ServiceRunInfo,
    ) -> bool:
        """Register a service with atomic updates to all indices."""
        async with self._service_lock(service_id), self._global_lock:
            existing_service = self._service_id_map.get(service_id)

            if existing_service is not None:
                if existing_service.service_type != service_type:
                    self._logger.warning(
                        "Service %s already registered with different type: %s vs %s",
                        service_id,
                        existing_service.service_type,
                        service_type,
                    )
                    return False

                self._remove_from_indices(service_id, existing_service)

            self._service_id_map[service_id] = service_info
            self._add_to_indices(service_id, service_info)
            self._stats_dirty = True

            if service_type not in self._registration_events:
                self._registration_events[service_type] = asyncio.Event()
            self._registration_events[service_type].set()

            await self._notify_state_change(service_id, service_info, existing_service)

            return True

    async def update_service_state(
        self,
        service_id: str,
        new_state: LifecycleState,
        update_timestamp: bool = True,
    ) -> bool:
        """Update service state with atomic index updates."""
        async with self._service_lock(service_id), self._global_lock:
            service_info = self._service_id_map.get(service_id)
            if service_info is None:
                return False

            old_state = service_info.state
            if old_state == new_state:
                return True

            self._service_state_map[old_state].discard(service_id)
            if not self._service_state_map[old_state]:
                del self._service_state_map[old_state]

            service_info.state = new_state
            if update_timestamp:
                service_info.last_seen = time.time_ns()

            self._service_state_map[new_state].add(service_id)
            self._stats_dirty = True

            await self._notify_state_change(service_id, service_info, None)

            return True

    async def update_service_status(
        self,
        service_id: str,
        new_status: ServiceRegistrationStatus,
    ) -> bool:
        """Update service registration status with atomic index updates."""
        async with self._service_lock(service_id), self._global_lock:
            service_info = self._service_id_map.get(service_id)
            if service_info is None:
                return False

            old_status = service_info.registration_status
            if old_status == new_status:
                return True

            self._service_status_map[old_status].discard(service_id)
            if not self._service_status_map[old_status]:
                del self._service_status_map[old_status]

            service_info.registration_status = new_status
            service_info.last_seen = time.time_ns()

            self._service_status_map[new_status].add(service_id)
            self._stats_dirty = True

            await self._notify_state_change(service_id, service_info, None)

            return True

    async def update_service_heartbeat(
        self,
        service_id: str,
        timestamp: int | None = None,
        state: LifecycleState | None = None,
    ) -> bool:
        """Update service heartbeat timestamp and optionally state."""
        async with self._service_lock(service_id), self._global_lock:
            service_info = self._service_id_map.get(service_id)
            if service_info is None:
                return False

            service_info.last_seen = timestamp or time.time_ns()

            if state is not None and state != service_info.state:
                old_state = service_info.state
                self._service_state_map[old_state].discard(service_id)
                if not self._service_state_map[old_state]:
                    del self._service_state_map[old_state]

                service_info.state = state
                self._service_state_map[state].add(service_id)
                self._stats_dirty = True

                await self._notify_state_change(service_id, service_info, None)

            return True

    async def unregister_service(self, service_id: str) -> ServiceRunInfo | None:
        """Unregister a service and clean up all indices."""
        async with self._service_lock(service_id), self._global_lock:
            service_info = self._service_id_map.pop(service_id, None)
            if service_info is None:
                return None

            self._remove_from_indices(service_id, service_info)
            self._stats_dirty = True

            await self._notify_state_change(service_id, None, service_info)

            return service_info

    async def get_service(self, service_id: str) -> ServiceRunInfo | None:
        """Get service information by ID."""
        async with self._global_lock:
            return self._service_id_map.get(service_id)

    async def get_services_by_type(
        self,
        service_type: ServiceTypeT,
        status: ServiceRegistrationStatus | None = None,
        state: LifecycleState | None = None,
    ) -> ServiceLookupResult:
        """Get all services of a specific type with optional filtering."""
        async with self._global_lock:
            service_ids = self._service_type_map.get(service_type, set()).copy()

            if status is not None:
                status_ids = self._service_status_map.get(status, set())
                service_ids &= status_ids

            if state is not None:
                state_ids = self._service_state_map.get(state, set())
                service_ids &= state_ids

            services = [
                self._service_id_map[service_id]
                for service_id in service_ids
                if service_id in self._service_id_map
            ]

            return ServiceLookupResult(
                services=services,
                total_count=len(services),
            )

    async def get_services_by_status(
        self,
        status: ServiceRegistrationStatus,
    ) -> ServiceLookupResult:
        """Get all services with a specific registration status."""
        async with self._global_lock:
            service_ids = self._service_status_map.get(status, set()).copy()
            services = [
                self._service_id_map[service_id]
                for service_id in service_ids
                if service_id in self._service_id_map
            ]

            return ServiceLookupResult(
                services=services,
                total_count=len(services),
            )

    async def get_services_by_state(
        self,
        state: LifecycleState,
    ) -> ServiceLookupResult:
        """Get all services with a specific lifecycle state."""
        async with self._global_lock:
            service_ids = self._service_state_map.get(state, set()).copy()
            services = [
                self._service_id_map[service_id]
                for service_id in service_ids
                if service_id in self._service_id_map
            ]

            return ServiceLookupResult(
                services=services,
                total_count=len(services),
            )

    async def wait_for_service_types(
        self,
        service_types: set[ServiceTypeT],
        status: ServiceRegistrationStatus = ServiceRegistrationStatus.REGISTERED,
        timeout: float | None = None,
    ) -> bool:
        """Wait for specific service types to be registered."""

        async def check_requirements() -> bool:
            for service_type in service_types:
                result = await self.get_services_by_type(service_type, status=status)
                if not result.services:
                    return False
            return True

        if await check_requirements():
            return True

        wait_events = []
        for service_type in service_types:
            if service_type not in self._registration_events:
                self._registration_events[service_type] = asyncio.Event()
            wait_events.append(self._registration_events[service_type].wait())

        try:
            while True:
                done, pending = await asyncio.wait(
                    wait_events,
                    timeout=timeout,
                    return_when=asyncio.FIRST_COMPLETED,
                )

                if not done:
                    for task in pending:
                        task.cancel()
                    return False

                if await check_requirements():
                    for task in pending:
                        task.cancel()
                    return True

                for event in self._registration_events.values():
                    if event.is_set():
                        event.clear()

        except asyncio.TimeoutError:
            return False

    async def get_registry_stats(
        self, force_update: bool = False
    ) -> ServiceRegistryStats:
        """Get current registry statistics with optional forced update."""
        if force_update or self._stats_dirty:
            await self._update_stats()

        return self._stats.model_copy()

    async def add_state_change_callback(
        self,
        callback: Any,
        weak_ref: bool = True,
    ) -> None:
        """Add a callback for service state changes."""
        async with self._global_lock:
            if weak_ref:
                ref = weakref.ref(callback)
                self._state_change_callbacks.append((ref, None))
            else:
                self._state_change_callbacks.append((None, callback))

    def _add_to_indices(self, service_id: str, service_info: ServiceRunInfo) -> None:
        """Add service to all relevant indices."""
        self._service_type_map[service_info.service_type].add(service_id)
        self._service_status_map[service_info.registration_status].add(service_id)
        self._service_state_map[service_info.state].add(service_id)

    def _remove_from_indices(
        self, service_id: str, service_info: ServiceRunInfo
    ) -> None:
        """Remove service from all indices with cleanup."""
        self._service_type_map[service_info.service_type].discard(service_id)
        if not self._service_type_map[service_info.service_type]:
            del self._service_type_map[service_info.service_type]

        self._service_status_map[service_info.registration_status].discard(service_id)
        if not self._service_status_map[service_info.registration_status]:
            del self._service_status_map[service_info.registration_status]

        self._service_state_map[service_info.state].discard(service_id)
        if not self._service_state_map[service_info.state]:
            del self._service_state_map[service_info.state]

    async def _update_stats(self) -> None:
        """Update registry statistics."""
        async with self._global_lock:
            services_by_type = defaultdict(int)
            services_by_status = defaultdict(int)
            services_by_state = defaultdict(int)

            for service_info in self._service_id_map.values():
                services_by_type[service_info.service_type] += 1
                services_by_status[service_info.registration_status] += 1
                services_by_state[service_info.state] += 1

            self._stats = ServiceRegistryStats(
                total_services=len(self._service_id_map),
                services_by_type=dict(services_by_type),
                services_by_status=dict(services_by_status),
                services_by_state=dict(services_by_state),
                last_updated=time.time(),
            )
            self._stats_dirty = False

    async def _notify_state_change(
        self,
        service_id: str,
        new_service: ServiceRunInfo | None,
        old_service: ServiceRunInfo | None,
    ) -> None:
        """Notify registered callbacks of service state changes."""
        cleanup_refs = []

        for weak_ref, strong_ref in self._state_change_callbacks:
            callback = None
            if weak_ref is not None:
                callback = weak_ref()
                if callback is None:
                    cleanup_refs.append((weak_ref, strong_ref))
                    continue
            else:
                callback = strong_ref

            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(service_id, new_service, old_service)
                else:
                    callback(service_id, new_service, old_service)
            except Exception as e:
                self._logger.exception(
                    "State change callback failed for service %s: %s",
                    service_id,
                    e,
                )

        for ref_tuple in cleanup_refs:
            self._state_change_callbacks.remove(ref_tuple)
