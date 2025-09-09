# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
import asyncio
from collections import defaultdict
from collections.abc import Iterable

from aiperf.common.constants import DEFAULT_SERVICE_REGISTRATION_TIMEOUT
from aiperf.common.enums import LifecycleState, ServiceRegistrationStatus
from aiperf.common.mixins import AIPerfLoggerMixin
from aiperf.common.models import ServiceRunInfo
from aiperf.common.types import ServiceTypeT


class _ServiceRegistry(AIPerfLoggerMixin):
    """Service registry for tracking service registration and state."""

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)

        # Expected services
        self.expected_by_type: dict[ServiceTypeT, int] = defaultdict(int)
        self.expected_ids: set[str] = set()

        # Registered services
        self.services: dict[str, ServiceRunInfo] = {}
        self.by_type: dict[ServiceTypeT, set[str]] = defaultdict(set)

        # Events for waiting
        self._all_event: asyncio.Event | None = None
        self._type_events: dict[ServiceTypeT, asyncio.Event] = {}
        self._id_events: dict[frozenset[str], asyncio.Event] = {}

        # NOTE: All public methods need to acquire the lock, and all private methods
        #       should expect that the lock is already acquired. This is because there
        #       is no re-entrant lock in asyncio.
        self._lock = asyncio.Lock()

    async def expect_services(self, services: dict[ServiceTypeT, int]) -> None:
        """Set expected services by type and count."""
        async with self._lock:
            self.expected_by_type.update(services)
            self.debug(lambda: f"Expecting services: {services}")

    async def expect_service(self, service_id: str, service_type: ServiceTypeT) -> None:
        """Set an expected service by ID and type. This is used to track services that are expected to be registered."""
        async with self._lock:
            self.expected_ids.add(service_id)
            self.expected_by_type[service_type] += 1
            self.debug(lambda: f"Expecting service: {service_id} ({service_type})")

    async def expect_ids(self, service_ids: dict[str, ServiceTypeT]) -> None:
        """Set expected specific service IDs."""
        async with self._lock:
            self.expected_ids.update(service_ids)
            for service_id, service_type in service_ids.items():
                self.services[service_id] = ServiceRunInfo(
                    service_id=service_id,
                    service_type=service_type,
                    first_seen_ns=None,
                    last_seen_ns=None,
                    registration_status=ServiceRegistrationStatus.UNREGISTERED,
                    state=LifecycleState.CREATED,
                )
            self.debug(lambda: f"Expecting service IDs: {service_ids}")

    async def register(
        self,
        service_id: str,
        service_type: ServiceTypeT,
        first_seen_ns: int,
        state: LifecycleState,
    ) -> None:
        """Register a service and trigger any waiting events."""
        async with self._lock:
            if service_id in self.services:
                self.warning(
                    f"Attempting to register a service that is already registered: {service_id}"
                )
                return

            service_info = ServiceRunInfo(
                service_id=service_id,
                service_type=service_type,
                first_seen_ns=first_seen_ns,
                last_seen_ns=first_seen_ns,
                registration_status=ServiceRegistrationStatus.REGISTERED,
                state=state,
            )
            self.services[service_id] = service_info
            self.by_type[service_type].add(service_id)

            self.info(f"Registered: {service_type.title()} ('{service_id}')")
            await self._check_events()

    async def update_service(
        self,
        service_id: str,
        service_type: ServiceTypeT,
        last_seen_ns: int,
        state: LifecycleState,
    ) -> None:
        """Update a service's registration status and state."""
        should_register = False
        async with self._lock:
            if service_id not in self.services:
                should_register = True
            else:
                service_info = self.services[service_id]
                if (
                    service_info.last_seen_ns is not None
                    and service_info.last_seen_ns >= last_seen_ns
                ):
                    # Ignore this update if it is older than the last update
                    return
                service_info.last_seen_ns = last_seen_ns
                service_info.state = state

        # Note that this needs to be outside the lock, as it is not a re-entrant lock
        if should_register:
            await self.register(service_id, service_type, last_seen_ns, state)

    async def unregister(self, service_id: str) -> None:
        """Unregister a service."""
        async with self._lock:
            if service_id not in self.services:
                self.warning(
                    f"Attempting to unregister a service that is not registered: {service_id}"
                )
                return

            self.services[
                service_id
            ].registration_status = ServiceRegistrationStatus.UNREGISTERED
            self.services[service_id].state = LifecycleState.STOPPED
            self.debug(
                lambda: f"Unregistered: {self.services[service_id].service_type.title()} ('{service_id}')"
            )

    async def forget(self, service_id: str) -> None:
        """Forget a service. Remove it from the registry altogether, and do not expect it to be registered again."""
        async with self._lock:
            if service_id not in self.services:
                self.warning(
                    f"Attempted to forget a service that is not registered: {service_id}"
                )
                return
            service_type = self.services[service_id].service_type
            self.by_type[service_type].remove(service_id)
            self.expected_ids.discard(service_id)
            del self.services[service_id]
            self.debug(lambda: f"Forgot service: '{service_id}'")

    async def wait_for_all(
        self, timeout: float | None = DEFAULT_SERVICE_REGISTRATION_TIMEOUT
    ) -> None:
        """Wait until all expected services are registered."""
        async with self._lock:
            if await self._all_registered():
                return

            if self._all_event is None:
                self._all_event = asyncio.Event()
            event = self._all_event

        self.info(
            f"Waiting for all services to be registered (timeout: {timeout} seconds)..."
        )
        await asyncio.wait_for(event.wait(), timeout)

    async def wait_for_type(
        self, service_type: ServiceTypeT, timeout: float | None = None
    ) -> None:
        """Wait until all services of a specific type are registered."""
        async with self._lock:
            if await self._all_types_registered(service_type):
                return

            if service_type not in self._type_events:
                self._type_events[service_type] = asyncio.Event()
            event = self._type_events[service_type]

        self.info(
            f"Waiting for {len(self.by_type[service_type])} services of type {service_type.title()} to be registered..."
        )
        await asyncio.wait_for(event.wait(), timeout)

    async def wait_for_ids(
        self, service_ids: list[str], timeout: float | None = None
    ) -> None:
        """Wait until all specified service IDs are registered."""
        ids = frozenset(service_ids)

        async with self._lock:
            if await self._all_ids_registered(service_ids):
                return

            if ids not in self._id_events:
                self._id_events[ids] = asyncio.Event()
            event = self._id_events[ids]

        self.info(f"Waiting for {len(service_ids)} services to be registered...")
        await asyncio.wait_for(event.wait(), timeout)

    async def get_services(
        self, service_type: ServiceTypeT | None = None
    ) -> list[ServiceRunInfo]:
        """Get registered services by type or all services."""
        async with self._lock:
            if service_type:
                # Look up full ServiceRunInfo objects from service IDs
                service_ids = self.by_type.get(service_type, set())
                return [
                    self.services[service_id]
                    for service_id in service_ids
                    if service_id in self.services
                ]
            return list(self.services.values())

    async def get_service(self, service_id: str) -> ServiceRunInfo | None:
        """Get a specific registered service."""
        async with self._lock:
            return self.services.get(service_id)

    async def get_all_registered_ids(self) -> list[str]:
        """Get all registered service IDs."""
        async with self._lock:
            return list(
                service_id
                for service_id, service_info in self.services.items()
                if service_info.registration_status
                == ServiceRegistrationStatus.REGISTERED
            )

    async def is_registered(self, service_id: str) -> bool:
        """Check if a service is registered."""
        async with self._lock:
            return (
                service_id in self.services
                and self.services[service_id].registration_status
                == ServiceRegistrationStatus.REGISTERED
            )

    async def all_types_registered(self, service_type: ServiceTypeT) -> bool:
        """Check if all services of a type are registered."""
        async with self._lock:
            return await self._all_types_registered(service_type)

    async def all_ids_registered(self, service_ids: Iterable[str]) -> bool:
        """Check if all specified service IDs are registered."""
        async with self._lock:
            return await self._all_ids_registered(service_ids)

    async def all_registered(self) -> bool:
        """Check if all expected services are registered."""
        async with self._lock:
            return await self._all_registered()

    async def _all_registered(self) -> bool:
        """Check if all expected services are registered."""
        for service_type in self.expected_by_type:
            if not await self._all_types_registered(service_type):
                return False
        return await self._all_ids_registered(self.expected_ids)

    async def _all_types_registered(self, service_type: ServiceTypeT) -> bool:
        """Check if all services of a type are registered."""
        expected = self.expected_by_type.get(service_type, 0)
        return expected == 0 or self._num_registered_of_type(service_type) >= expected

    async def _all_ids_registered(self, service_ids: Iterable[str]) -> bool:
        """Check if all specified service IDs are registered."""
        registered_ids = await self.get_all_registered_ids()
        return all(service_id in registered_ids for service_id in service_ids)

    def _num_registered_of_type(self, service_type: ServiceTypeT) -> int:
        """Count the number of registered services of a specific type."""
        return sum(
            1
            for service_id in self.by_type[service_type]
            if service_id in self.services
            and self.services[service_id].registration_status
            == ServiceRegistrationStatus.REGISTERED
        )

    async def _check_events(self) -> None:
        """Check and trigger any events that are satisfied."""
        if self._all_event and await self._all_registered():
            self._all_event.set()
            self._all_event = None

        # Check type events
        types_to_remove = []
        for service_type, event in self._type_events.items():
            if await self._all_types_registered(service_type):
                event.set()
                types_to_remove.append(service_type)

        for service_type in types_to_remove:
            del self._type_events[service_type]

        # Check id events
        ids_to_remove = []
        for ids, event in self._id_events.items():
            if await self._all_ids_registered(ids):
                event.set()
                ids_to_remove.append(ids)

        for ids in ids_to_remove:
            del self._id_events[ids]


# global instance of the service registry
ServiceRegistry = _ServiceRegistry()
