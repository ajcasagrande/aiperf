import asyncio
from abc import ABC, abstractmethod

from aiperf.common.comms.communication_factory import CommunicationFactory
from aiperf.common.config.service_config import ServiceConfig
from aiperf.common.enums import (
    CommandType,
    ServiceType,
    ServiceState,
    ClientType,
    Topic,
)
from aiperf.common.models.base_models import BasePayload
from aiperf.common.models.messages import CommandMessage, StatusMessage
from aiperf.common.service.base import ServiceBase


class ComponentServiceBase(ServiceBase, ABC):
    """Base class for all component services.
    This class provides a common interface for all component services in the AIPerf framework.
    It inherits from the ServiceBase class and implements the required methods for component
    services.
    """

    def __init__(self, service_type: ServiceType, config: ServiceConfig) -> None:
        super().__init__(service_type=service_type, config=config)

    async def run(self) -> None:
        """Start the service and initialize its components."""
        try:
            await self._base_init()

            await self.communication.create_clients(
                ClientType.CONTROLLER_SUB,
                ClientType.COMPONENT_PUB,
            )

            await self._initialize()

            # Set up communication subscriptions if communication is available
            # Subscribe to common topics
            await self.communication.subscribe(
                ClientType.CONTROLLER_SUB,
                Topic.COMMAND,
                self._process_command_message,
            )

            # TODO: Find a way to wait for the communication to be fully initialized
            # Wait for 1 second to ensure the communication is fully initialized
            await asyncio.sleep(1)

            # Additional service-specific subscriptions can be added in derived classes

            await self._register()
            # Start heartbeat task
            await self._start_heartbeat_task()
            await self._set_service_status(ServiceState.READY)

            # Wait forever for the stop event to be set
            await self.stop_event.wait()
        except asyncio.exceptions.CancelledError:
            self.logger.debug("Service execution cancelled")
        except BaseException:
            self.logger.exception("Service execution failed:")
            await self._set_service_status(ServiceState.ERROR)
        finally:
            # Make sure to clean up properly even if there was an error
            if self.state == ServiceState.RUNNING:
                await self.stop()

    async def _process_command_message(self, message: CommandMessage) -> None:
        """Process a command message."""
        if message.target_service_id != self.service_id:
            return  # Ignore commands for other services

        if message.command == CommandType.START:
            await self._on_start()
        elif message.command == CommandType.STOP:
            await self.stop()
        elif message.command == CommandType.CONFIGURE:
            await self._configure(message.payload)
        else:
            self.logger.warning(f"Received unknown command: {message.command}")

    @abstractmethod
    async def _configure(self, payload: BasePayload) -> None:
        """Configure the service."""
        pass

    async def _set_service_status(self, status: ServiceState) -> None:
        """Send a service state message to the system controller."""
        self.state = status
        status_message = StatusMessage(
            service_id=self.service_id,
            service_type=self.service_type,
            state=self.state,
        )
        await self._publish_message(
            ClientType.COMPONENT_PUB, Topic.STATUS, status_message
        )
