# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
import asyncio
import multiprocessing
from abc import ABC, abstractmethod

from aiperf.common.config import ServiceConfig
from aiperf.common.config.user_config import UserConfig
from aiperf.common.hooks import on_start, on_stop
from aiperf.common.mixins.aiperf_lifecycle_mixin import AIPerfLifecycleMixin
from aiperf.common.models import ServiceRunInfo
from aiperf.common.types import ServiceTypeT


class BaseServiceManager(AIPerfLifecycleMixin, ABC):
    """
    Base class for service managers. It provides a common interface for managing services.
    """

    def __init__(
        self,
        required_services: dict[ServiceTypeT, int],
        service_config: ServiceConfig,
        user_config: UserConfig,
        log_queue: "multiprocessing.Queue | None" = None,
    ):
        super().__init__(logger_name="service_manager")
        self.required_services = required_services
        self.service_config = service_config
        self.user_config = user_config
        self.log_queue = log_queue
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

    async def run_services(self, service_types: dict[ServiceTypeT, int]) -> None:
        await asyncio.gather(
            *[
                self.run_service(service_type, num_replicas)
                for service_type, num_replicas in service_types.items()
            ],
            return_exceptions=True,
        )

    async def run_required_services(self) -> None:
        await self.run_services(self.required_services)

    @abstractmethod
    async def run_service(
        self, service_type: ServiceTypeT, num_replicas: int = 1
    ) -> None:
        pass

    @abstractmethod
    async def shutdown_all_services(self) -> None:
        pass

    @abstractmethod
    async def kill_all_services(self) -> None:
        pass

    @abstractmethod
    async def wait_for_all_services_registration(
        self, stop_event: asyncio.Event, timeout_seconds: int = 30
    ) -> None:
        pass
