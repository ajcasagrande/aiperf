# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
import asyncio
import logging
from abc import ABC, abstractmethod

from aiperf.common.config import ServiceConfig
from aiperf.common.enums import ServiceType
from aiperf.common.service_models import ServiceRunInfo
from aiperf.services.service_registry import ServiceRegistry


class BaseServiceManager(ABC):
    """
    Base class for service managers. It provides a common interface for
    managing services and a way to look up service information by service ID.
    """

    def __init__(
        self,
        required_service_types: list[tuple[ServiceType, int]],
        config: ServiceConfig,
    ):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.required_service_types = required_service_types
        self.config = config

        # Centralized service registry
        self.service_registry = ServiceRegistry()

    @property
    def service_map(self) -> dict[ServiceType, list[ServiceRunInfo]]:
        """Legacy compatibility: get services organized by type as lists."""
        result = {}
        for service_type in self.service_registry.get_all_service_types():
            services = self.service_registry.get_services_by_type(service_type)
            result[service_type] = list(services.values())
        return result

    @property
    def service_id_map(self) -> dict[str, ServiceRunInfo]:
        """Legacy compatibility: get all services by ID."""
        result = {}
        for service_id in self.service_registry.get_all_service_ids():
            service_info = self.service_registry.get_service(service_id)
            if service_info is not None:
                result[service_id] = service_info
        return result

    @abstractmethod
    async def run_all_services(self) -> None:
        """Run all required services."""
        pass

    @abstractmethod
    async def shutdown_all_services(self) -> None:
        """Shutdown all managed services."""
        pass

    @abstractmethod
    async def kill_all_services(self) -> None:
        """Kill all managed services."""
        pass

    @abstractmethod
    async def wait_for_all_services_registration(
        self, cancel_event: asyncio.Event, timeout_seconds: int = 30
    ) -> None:
        """Wait for all required services to be registered."""
        pass
