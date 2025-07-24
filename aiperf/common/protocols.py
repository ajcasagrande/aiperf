# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

import asyncio
import multiprocessing
from typing import Protocol, runtime_checkable

from aiperf.common.config import ServiceConfig, UserConfig
from aiperf.common.constants import (
    DEFAULT_SERVICE_REGISTRATION_TIMEOUT,
    DEFAULT_SERVICE_START_TIMEOUT,
)
from aiperf.common.types import ServiceRunInfoT, ServiceTypeT


@runtime_checkable
class ServiceManagerProtocol(AIPerfLifecycleProtocol, Protocol):
    """Protocol for a service manager.
    see :class:`aiperf.services.service_manager.base.BaseServiceManager` for more details.
    """

    def __init__(
        self,
        required_services: dict[ServiceTypeT, int],
        service_config: ServiceConfig,
        user_config: UserConfig,
        log_queue: "multiprocessing.Queue | None" = None,
    ): ...

    required_services: dict[ServiceTypeT, int]
    service_map: dict[ServiceTypeT, list[ServiceRunInfoT]]
    service_id_map: dict[str, ServiceRunInfoT]

    async def run_service(
        self, service_type: ServiceTypeT, num_replicas: int = 1
    ) -> None: ...

    async def run_services(self, service_types: dict[ServiceTypeT, int]) -> None: ...
    async def run_required_services(self) -> None: ...
    async def shutdown_all_services(self) -> None: ...
    async def kill_all_services(self) -> None: ...

    async def wait_for_all_services_registration(
        self,
        stop_event: asyncio.Event,
        timeout_seconds: float = DEFAULT_SERVICE_REGISTRATION_TIMEOUT,
    ) -> None: ...

    async def wait_for_all_services_start(
        self,
        stop_event: asyncio.Event,
        timeout_seconds: float = DEFAULT_SERVICE_START_TIMEOUT,
    ) -> None: ...
