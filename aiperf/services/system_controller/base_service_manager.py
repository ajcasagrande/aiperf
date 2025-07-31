# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
import asyncio
from abc import ABC, abstractmethod

from aiperf.common.config import ServiceConfig
from aiperf.common.config.user_config import UserConfig
from aiperf.common.hooks import on_start, on_stop
from aiperf.common.types import ServiceTypeT
from aiperf.services.system_controller.service_registry import ServiceRegistryMixin


class BaseServiceManager(ServiceRegistryMixin, ABC):
    """
    Base class for service managers. It provides a common interface for managing services.
    """

    def __init__(
        self,
        required_services: dict[ServiceTypeT, int],
        service_config: ServiceConfig,
        user_config: UserConfig,
        service_id: str,
        **kwargs,
    ):
        super().__init__(
            service_id=service_id,
            service_config=service_config,
            user_config=user_config,
            **kwargs,
        )
        self.set_required_services(required_services)

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
        await self.run_services(self._required_services)

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
