# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

from aiperf.common.enums import ServiceType
from aiperf.common.logging import get_global_log_queue
from aiperf.common.types import ServiceTypeT
from aiperf.core.communication_mixins import MessageBusMixin
from aiperf.services.service_manager import BaseServiceManager, ServiceManagerFactory


class ServiceManagerMixin(MessageBusMixin):
    """Mixin for the System Controller to manage services."""

    def __init__(self, **kwargs):
        self.service_manager: BaseServiceManager
        self._required_services: dict[ServiceTypeT, int]

        # List of required service types, in no particular order
        # These are services that must be running before the system controller can start profiling
        self._required_services = {
            ServiceType.DATASET_MANAGER: 1,
            ServiceType.TIMING_MANAGER: 1,
            ServiceType.WORKER_MANAGER: 1,
            ServiceType.RECORDS_MANAGER: 1,
            ServiceType.INFERENCE_RESULT_PARSER: self.service_config.result_parser_service_count,
        }

        super().__init__(**kwargs)
        self.service_manager = ServiceManagerFactory.get_class_from_type(
            self.service_config.service_run_type
        )(
            required_services=self._required_services,
            service_config=self.service_config,
            user_config=self.user_config,
            log_queue=get_global_log_queue(),
        )

    async def _start(self) -> None:
        await super()._start()
        await self.service_manager.start()

    async def run_all_services(self) -> None:
        """Run all services."""
        if self.service_manager is None:
            raise ValueError("Service manager not created")
        await self.service_manager.run_all_required_services()
        await self.service_manager.wait_for_all_required_services_registration()
        await self.service_manager.wait_for_all_required_services_to_start()

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
