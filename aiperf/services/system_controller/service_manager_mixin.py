# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

from aiperf.common.config import ServiceConfig
from aiperf.common.config.user_config import UserConfig
from aiperf.common.enums.service import ServiceRunType, ServiceType
from aiperf.common.logging import get_global_log_queue
from aiperf.services.service_manager import BaseServiceManager
from aiperf.services.service_manager.kubernetes import KubernetesServiceManager
from aiperf.services.service_manager.multiprocess import MultiProcessServiceManager


class ServiceManagerMixin:
    """Mixin for the System Controller to manage services."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.service_manager: BaseServiceManager
        self._service_config: ServiceConfig
        self._user_config: UserConfig
        self.required_services: dict[ServiceType, int]

    def create_service_manager(
        self, service_config: ServiceConfig, user_config: UserConfig
    ) -> None:
        """Create the service manager."""
        self._service_config = service_config
        self._user_config = user_config

        # List of required service types, in no particular order
        # These are services that must be running before the system controller can start profiling
        self.required_services = {
            ServiceType.DATASET_MANAGER: 1,
            ServiceType.TIMING_MANAGER: 1,
            ServiceType.WORKER_MANAGER: 1,
            ServiceType.RECORDS_MANAGER: 1,
            ServiceType.INFERENCE_RESULT_PARSER: self._service_config.result_parser_service_count,
        }

        if service_config.service_run_type == ServiceRunType.MULTIPROCESSING:
            self.service_manager = MultiProcessServiceManager(
                required_services=self.required_services,
                config=service_config,
                user_config=user_config,
                log_queue=get_global_log_queue(),
            )

        elif service_config.service_run_type == ServiceRunType.KUBERNETES:
            self.service_manager = KubernetesServiceManager(
                required_services=self.required_services,
                config=service_config,
            )

        else:
            raise ValueError(
                f"Unsupported service run type: {service_config.service_run_type}"
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
