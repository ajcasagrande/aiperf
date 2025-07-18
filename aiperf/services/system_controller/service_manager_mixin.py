# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

from typing import Protocol, runtime_checkable

from aiperf.common.config import ServiceConfig
from aiperf.common.config.user_config import UserConfig
from aiperf.common.enums import ServiceRunType, ServiceType
from aiperf.common.logging import get_global_log_queue
from aiperf.services.service_manager import BaseServiceManager
from aiperf.services.service_manager.kubernetes import KubernetesServiceManager
from aiperf.services.service_manager.multiprocess import MultiProcessServiceManager


@runtime_checkable
class ServiceManagerMixinRequirements(Protocol):
    """Requirements for a class that wishes to subclass the Service Manager Mixin."""

    service_config: ServiceConfig | None = None
    user_config: UserConfig | None = None


class ServiceManagerMixin(ServiceManagerMixinRequirements):
    """Mixin for the System Controller to manage services."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if not isinstance(self, ServiceManagerMixinRequirements):
            raise TypeError(
                "ServiceManagerMixin can only be used with a class that provides the ServiceManagerMixinRequirements protocol"
            )

        self.service_manager: BaseServiceManager | None = None
        self._required_services: dict[ServiceType, int]

        # List of required service types, in no particular order
        # These are services that must be running before the system controller can start profiling
        self._required_services = {
            ServiceType.DATASET_MANAGER: 1,
            ServiceType.TIMING_MANAGER: 1,
            ServiceType.WORKER_MANAGER: 1,
            ServiceType.RECORDS_MANAGER: 1,
            ServiceType.INFERENCE_RESULT_PARSER: self.service_config.result_parser_service_count,
        }

        if self.service_config.service_run_type == ServiceRunType.MULTIPROCESSING:
            self.service_manager = MultiProcessServiceManager(
                required_services=self._required_services,
                service_config=self.service_config,
                user_config=self.user_config,
                log_queue=get_global_log_queue(),
            )

        elif self.service_config.service_run_type == ServiceRunType.KUBERNETES:
            self.service_manager = KubernetesServiceManager(
                required_services=self._required_services,
                service_config=self.service_config,
                user_config=self.user_config,
            )

        else:
            raise ValueError(
                f"Unsupported service run type: {self.service_config.service_run_type}"
            )

    async def run_all_services(self) -> None:
        """Run all services."""
        if self.service_manager is None:
            raise ValueError("Service manager not created")
        await self.service_manager.run_all_services()
        await self.service_manager.wait_for_all_services_registration()
        await self.service_manager.wait_for_all_services_to_start()

    async def stop_all_services(self) -> None:
        """Stop all services."""
        if self.service_manager is None:
            raise ValueError("Service manager not created")
        await self.service_manager.shutdown_all_services()
        await self.service_manager.wait_for_all_services_to_stop()

    async def kill_all_services(self) -> None:
        """Kill all services."""
        if self.service_manager is None:
            raise ValueError("Service manager not created")
        await self.service_manager.kill_all_services()
