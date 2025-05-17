#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#  http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
import asyncio
import contextlib
from abc import ABC, abstractmethod

from aiperf.common.config.service_config import ServiceConfig
from aiperf.common.enums import (
    ClientType,
    CommandType,
    PubClientType,
    ServiceState,
    SubClientType,
    Topic,
)
from aiperf.common.exceptions.comm_exceptions import CommunicationSubscribeException
from aiperf.common.exceptions.service_exceptions import (
    ServiceHeartbeatException,
    ServiceInitializationException,
    ServiceRegistrationException,
)
from aiperf.common.models.message_models import BaseMessage
from aiperf.common.models.payload_models import (
    HeartbeatPayload,
    PayloadType,
    RegistrationPayload,
    StatusPayload,
)
from aiperf.common.service.base_service import BaseService


class BaseComponentService(BaseService, ABC):
    """Base class for all component services.

    This class provides a common interface for all component services in the AIPerf
    framework such as the Timing Manager, Dataset Manager, etc.

    It inherits from the BaseService class and implements the required methods for
    component services.
    """

    def __init__(self, service_config: ServiceConfig, service_id: str = None) -> None:
        super().__init__(service_config=service_config, service_id=service_id)

    @property
    def required_clients(self) -> list[ClientType]:
        """The communication clients required by the service.

        The component services subscribe to controller messages and publish
        component messages.
        """
        return [PubClientType.COMPONENT, SubClientType.CONTROLLER]

    @abstractmethod
    async def _configure(self, payload: PayloadType) -> None:
        """Configure the service with the given configuration payload.

        This method is called when a configure command is received from the controller.
        It should be implemented by the derived class to configure the service.

        The service should validate the payload and configure itself accordingly.
        If successful, the service should publish a success message to the controller.
        On failure, the service should publish an error message to the controller.

        Args:
            payload: The configuration payload. This is a union type of all the possible
            configuration payloads.

        """
        pass

    async def _run(self) -> None:
        """Internal method to run the service. This method will start the service and
        initialize its components. It will also subscribe to the command topic and
        process commands as they are received.

        This method will be called by the base service class to run the service.
        """
        # Initialize the service
        try:
            await self.initialize()
        except Exception as e:
            self.logger.error("Exception initializing service: %s", e)
            raise ServiceInitializationException("Failed to initialize service") from e

        # Subscribe to the command topic
        try:
            await self.comms.subscribe(
                Topic.COMMAND,
                self.process_command_message,
            )
        except Exception as e:
            self.logger.error("Exception subscribing to command topic: %s", e)
            raise CommunicationSubscribeException(
                "Failed to subscribe to command topic"
            ) from e

        # TODO: Find a way to wait for the communication to be fully initialized
        # FIXME: This is a hack to ensure the communication is fully initialized
        await asyncio.sleep(1)

        # Register the service
        try:
            await self.register()
        except Exception as e:
            raise ServiceRegistrationException() from e

        # ignore errors with setting the state for now
        _ = await self.set_state(ServiceState.READY)

        # Note: Do not start the service here, let the system controller start it
        # This is because the service needs to be configured first and may need
        # to wait for other services to register before it can start

        # Start the heartbeat task
        await self.start_heartbeat_task()

    async def send_heartbeat(self) -> None:
        """Send a heartbeat notification to the system controller."""
        heartbeat_message = self.create_heartbeat_message()
        self.logger.debug("Sending heartbeat: %s", heartbeat_message)
        try:
            await self.comms.publish(
                topic=Topic.HEARTBEAT,
                message=heartbeat_message,
            )
        except Exception as e:
            raise ServiceHeartbeatException from e

    async def register(self) -> None:
        """Publish a registration request to the system controller.

        This method should be called after the service has been initialized and is
        ready to start processing messages.
        """
        self.logger.debug(
            "Attempting to register service %s (%s) with system controller",
            self.service_type,
            self.service_id,
        )
        try:
            await self.comms.publish(
                topic=Topic.REGISTRATION,
                message=self.create_registration_message(),
            )
        except Exception as e:
            raise ServiceRegistrationException() from e

    async def process_command_message(self, message: BaseMessage) -> None:
        """Process a command message received from the controller.

        This method will process the command message and execute the appropriate action.
        """
        if message.payload.target_service_id not in [None, self.service_id]:
            return  # Ignore commands meant for other services

        cmd = message.payload.command
        if cmd == CommandType.START:
            await self.start()

        elif cmd == CommandType.STOP:
            await self.stop()

        elif cmd == CommandType.CONFIGURE:
            await self._configure(message.payload)

        else:
            self.logger.warning(f"{self.service_type} received unknown command: {cmd}")

    async def set_state(self, state: ServiceState) -> None:
        """Set the state of the service.

        This method will also publish the status message to the status topic if the
        communications are initialized.
        """
        self._state = state
        if self.comms and self.comms.is_initialized:
            await self.comms.publish(
                topic=Topic.STATUS,
                message=self.create_status_message(state),
            )

    async def stop(self) -> None:
        """Stop the service."""
        await super().stop()
        await self.stop_heartbeat_task()

    async def stop_heartbeat_task(self) -> None:
        """Stop the heartbeat task if it is running."""
        if self._heartbeat_task and not self._heartbeat_task.done():
            self._heartbeat_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._heartbeat_task

    def create_heartbeat_message(self) -> BaseMessage:
        """Create a heartbeat notification message."""
        return self.create_message(
            HeartbeatPayload(
                service_type=self.service_type,
            )
        )

    def create_registration_message(self) -> BaseMessage:
        """Create a registration request message."""
        return self.create_message(
            RegistrationPayload(
                service_type=self.service_type,
            )
        )

    def create_status_message(self, state: ServiceState) -> BaseMessage:
        """Create a status notification message."""
        return self.create_message(
            StatusPayload(
                state=state,
                service_type=self.service_type,
            )
        )

    async def _heartbeat_loop(self) -> None:
        while not self.stop_event.is_set():
            # Sleep first to avoid sending a heartbeat before the registration
            # message has been published
            await asyncio.sleep(self._heartbeat_interval)

            try:
                await self.send_heartbeat()
            except Exception as e:
                self.logger.warning("Exception sending heartbeat: %s", e)
                # continue to keep sending heartbeats regardless of the error

    async def start_heartbeat_task(self) -> None:
        """Start a background task to send heartbeats at regular intervals."""

        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
        self.logger.debug(
            "%s: Started heartbeat task with interval %fs",
            self.service_type,
            self._heartbeat_interval,
        )
