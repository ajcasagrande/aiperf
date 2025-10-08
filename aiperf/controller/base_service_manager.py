# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
import asyncio
from abc import ABC, abstractmethod

from aiperf.common.config import ServiceConfig, UserConfig
from aiperf.common.constants import (
    DEFAULT_SERVICE_REGISTRATION_TIMEOUT,
    DEFAULT_SERVICE_START_TIMEOUT,
)
from aiperf.common.decorators import implements_protocol
from aiperf.common.hooks import on_start, on_stop
from aiperf.common.mixins import AIPerfLifecycleMixin
from aiperf.common.models import ServiceRunInfo
from aiperf.common.protocols import ServiceManagerProtocol
from aiperf.common.types import ServiceTypeT


@implements_protocol(ServiceManagerProtocol)
class BaseServiceManager(AIPerfLifecycleMixin, ABC):
    """
    Base class for service managers. It provides a common interface for managing services.
    """

    def __init__(
        self,
        required_services: dict[ServiceTypeT, int],
        service_config: ServiceConfig,
        user_config: UserConfig,
        **kwargs,
    ):
        super().__init__(
            service_config=service_config,
            user_config=user_config,
            **kwargs,
        )
        self.required_services = required_services
        self.service_config = service_config
        self.user_config = user_config
        self.kwargs = kwargs
        # Maps to track service information
        self.service_map: dict[ServiceTypeT, list[ServiceRunInfo]] = {}

        # Create service ID map for component lookups
        self.service_id_map: dict[str, ServiceRunInfo] = {}

    @on_start
    async def _start_service_manager(self) -> None:
        await self.run_required_services()

    @on_stop
    async def _stop_service_manager(self) -> None:
        await self.shutdown_all_services()

    async def run_services(
        self, service_types: dict[ServiceTypeT, int]
    ) -> list[BaseException | None]:
        return await asyncio.gather(
            *[
                self.run_service(service_type, num_replicas)
                for service_type, num_replicas in service_types.items()
            ],
            return_exceptions=True,
        )

    @abstractmethod
    async def stop_service(
        self, service_type: ServiceTypeT, service_id: str | None = None
    ) -> list[BaseException | None]: ...

    # TODO: This stuff needs some major cleanup

    async def stop_services_by_type(
        self, service_types: list[ServiceTypeT]
    ) -> list[BaseException | None]:
        """Stop a set of services."""
        results = await asyncio.gather(
            *[self.stop_service(service_type) for service_type in service_types],
            return_exceptions=True,
        )
        output: list[BaseException | None] = []
        for result in results:
            if isinstance(result, list):
                output.extend(result)
            else:
                output.append(result)
        return output

    async def run_required_services(self) -> None:
        await self.run_services(self.required_services)

    @abstractmethod
    async def run_service(
        self, service_type: ServiceTypeT, num_replicas: int = 1
    ) -> None:
        pass

    @abstractmethod
    async def shutdown_all_services(self) -> list[BaseException | None]:
        pass

    @abstractmethod
    async def kill_all_services(self) -> list[BaseException | None]:
        pass

    @abstractmethod
    async def wait_for_all_services_registration(
        self,
        stop_event: asyncio.Event,
        timeout_seconds: float = DEFAULT_SERVICE_REGISTRATION_TIMEOUT,
    ) -> None:
        pass

    @abstractmethod
    async def wait_for_all_services_start(
        self,
        stop_event: asyncio.Event,
        timeout_seconds: float = DEFAULT_SERVICE_START_TIMEOUT,
    ) -> None:
        pass

    def is_required_service(self, service_id: str) -> bool:
        """Check if a service is required based on its service_id.

        Args:
            service_id: The ID of the service to check

        Returns:
            True if the service is required, False otherwise
        """
        service_info = self.service_id_map.get(service_id)
        if not service_info:
            return False
        return service_info.service_type in self.required_services

    def remove_service_from_maps(self, service_id: str) -> None:
        """Remove a service from service_id_map and service_map.

        Args:
            service_id: The ID of the service to remove
        """
        service_info = self.service_id_map.pop(service_id, None)
        if service_info and service_info.service_type in self.service_map:
            # Remove from the service_map list
            service_list = self.service_map[service_info.service_type]
            self.service_map[service_info.service_type] = [
                s for s in service_list if s.service_id != service_id
            ]
            # Clean up empty lists
            if not self.service_map[service_info.service_type]:
                del self.service_map[service_info.service_type]
