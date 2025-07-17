# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
from abc import ABC, abstractmethod

from aiperf.common.config import ServiceConfig
from aiperf.common.constants import (
    DEFAULT_WAIT_FOR_START_SECONDS,
    DEFAULT_WAIT_FOR_STOP_SECONDS,
)
from aiperf.common.enums import ServiceType
from aiperf.common.messages import BaseServiceMessage
from aiperf.common.mixins import AIPerfLoggerMixin
from aiperf.common.models import ServiceRegistrationInfo


class BaseServiceManager(AIPerfLoggerMixin, ABC):
    """
    Base class for service managers. It provides a common interface for
    managing services and a way to look up service information by service ID.
    """

    def __init__(
        self,
        required_services: dict[ServiceType, int],
        config: ServiceConfig,
    ):
        super().__init__(logger_name="service_manager")
        self.required_services = required_services
        self.config = config

        # Maps to track service information
        self.service_map: dict[ServiceType, list[ServiceRegistrationInfo]] = {}

        # Create service ID map for component lookups
        self.service_id_map: dict[str, ServiceRegistrationInfo] = {}

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
        self, timeout_seconds: float = DEFAULT_WAIT_FOR_START_SECONDS
    ) -> None:
        """Wait for all required services to be registered."""
        pass

    @abstractmethod
    async def wait_for_all_services_to_start(
        self,
        timeout_seconds: float = DEFAULT_WAIT_FOR_START_SECONDS,
    ) -> None:
        """Wait for all services to start."""
        pass

    @abstractmethod
    async def wait_for_all_services_to_stop(
        self,
        timeout_seconds: float = DEFAULT_WAIT_FOR_STOP_SECONDS,
    ) -> None:
        """Wait for all services to stop."""
        pass

    @abstractmethod
    async def on_message(self, message: BaseServiceMessage) -> None:
        """Handle a message from a service."""
        pass
