# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
from abc import ABC, abstractmethod

from aiperf.common.config import ServiceConfig, UserConfig
from aiperf.common.constants import (
    DEFAULT_WAIT_FOR_START_SECONDS,
    DEFAULT_WAIT_FOR_STOP_SECONDS,
)
from aiperf.common.enums import MessageType
from aiperf.common.enums.service_enums import ServiceRunType
from aiperf.common.factories import FactoryMixin
from aiperf.common.messages import RegistrationMessage
from aiperf.common.messages.commands import StartWorkersCommand
from aiperf.common.messages.error_messages import BaseServiceErrorMessage
from aiperf.common.messages.service_messages import HeartbeatMessage, StatusMessage
from aiperf.common.models import ServiceRegistrationInfo
from aiperf.common.types import ServiceTypeT
from aiperf.core import command_handler, message_handler
from aiperf.core.communication_mixins import MessageBusMixin
from aiperf.services.service_manager.service_registry import ServiceRegistry


class BaseServiceManager(MessageBusMixin, ABC):
    """
    Base class for service managers. It provides a common interface for
    managing services and a way to look up service information by service ID.
    """

    def __init__(
        self,
        required_services: dict[ServiceTypeT, int],
        service_config: ServiceConfig,
        user_config: UserConfig,
        **kwargs,
    ):
        self.required_services = required_services
        self.service_config = service_config
        self.user_config = user_config
        self.registry = ServiceRegistry()

        # Maps to track service information
        self.service_map: dict[ServiceTypeT, list[ServiceRegistrationInfo]] = {}

        # Create service ID map for component lookups
        self.service_id_map: dict[str, ServiceRegistrationInfo] = {}

        super().__init__(
            required_services=required_services,
            service_config=service_config,
            user_config=user_config,
            **kwargs,
        )

    @abstractmethod
    async def run_all_required_services(self) -> None:
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
    async def wait_for_all_required_services_registration(
        self, timeout_seconds: float = DEFAULT_WAIT_FOR_START_SECONDS
    ) -> None:
        """Wait for all required services to be registered."""
        pass

    @abstractmethod
    async def wait_for_all_required_services_to_start(
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

    @command_handler(MessageType.StartWorkers)
    async def _on_start_workers_command(self, message: StartWorkersCommand) -> None:
        """Handle a command message from a service."""
        self.debug(lambda: f"Received start workers command: {message}")

    @message_handler(MessageType.Registration)
    async def _on_registration_message(self, message: RegistrationMessage) -> None:
        self.registry.register_service(
            message.service_id,
            message.service_type,
            message.state,
        )

    @message_handler(MessageType.Heartbeat)
    async def _on_heartbeat_message(self, message: HeartbeatMessage) -> None:
        self.registry.update_service_heartbeat(message.service_id)

    @message_handler(MessageType.Status)
    async def _on_status_message(self, message: StatusMessage) -> None:
        self.registry.update_service_state(message.service_id, message.state)

    @message_handler(MessageType.ServiceError)
    async def _on_service_error_message(self, message: BaseServiceErrorMessage) -> None:
        self.registry[message.service_id].errors.append(message.error)


class ServiceManagerFactory(FactoryMixin[ServiceRunType, BaseServiceManager]):
    """Factory for creating service managers for different service run types.
    see :class:`aiperf.common.factories.FactoryMixin` for more details.
    """
