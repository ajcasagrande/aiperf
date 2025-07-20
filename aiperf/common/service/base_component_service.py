# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

from aiperf.common.config import ServiceConfig, UserConfig
from aiperf.common.enums import (
    ServiceState,
)
from aiperf.common.enums.message_enums import CommandType
from aiperf.common.exceptions import InitializationError
from aiperf.common.hooks import (
    AIPerfHook,
    aiperf_auto_task,
    on_command_message,
    on_init,
    on_set_state,
)
from aiperf.common.messages import (
    CommandMessage,
    CommandResponseMessage,
    HeartbeatMessage,
    RegistrationMessage,
    StatusMessage,
)
from aiperf.common.models import ErrorDetails
from aiperf.common.service.base_service import BaseService


class BaseComponentService(BaseService):
    """Base class for all Component services.

    This class provides a common interface for all Component services in the AIPerf
    framework such as the Timing Manager, Dataset Manager, etc.

    It extends the BaseService by:
    - Subscribing to the command message_type
    - Processing command messages
    - Sending registration requests to the system controller
    - Sending heartbeat notifications to the system controller
    - Sending status notifications to the system controller
    - Helpers to create heartbeat, registration, and status messages
    """

    def __init__(
        self,
        service_config: ServiceConfig,
        user_config: UserConfig | None = None,
        service_id: str | None = None,
        **kwargs,
    ) -> None:
        super().__init__(
            service_config=service_config,
            user_config=user_config,
            service_id=service_id,
            **kwargs,
        )
        self._heartbeat_interval_seconds = (
            self.service_config.heartbeat_interval_seconds
        )

    # TODO: Should this be a new post-init? Or is that already handled by the base mixins?
    @on_init
    async def register(self) -> None:
        """Publish a registration request to the system controller.

        This method should be called after the service has been initialized and is
        ready to start processing messages.
        """
        self.debug(
            lambda: f"Attempting to register service {self.service_type} ({self.service_id}) with system controller"
        )
        try:
            await self.pub_client.publish(self.create_registration_message())
        except Exception as e:
            raise InitializationError("Failed to register service") from e

    @aiperf_auto_task(
        interval_sec=lambda self: self.service_config.heartbeat_interval_seconds
    )
    async def _heartbeat_task(self) -> None:
        """Starts a background task to send heartbeats at regular intervals. It
        will continue to send heartbeats even if an error occurs until cancelled.
        """
        await self.send_heartbeat()

    async def send_heartbeat(self) -> None:
        """Send a heartbeat notification to the system controller."""
        heartbeat_message = self.create_heartbeat_message()
        self.debug(lambda: f"Sending heartbeat: {heartbeat_message}")
        try:
            await self.pub_client.publish(heartbeat_message)
        except Exception as e:
            raise InitializationError("Failed to send heartbeat") from e

    @on_command_message(
        CommandType.PROFILE_CONFIGURE,
        CommandType.PROFILE_START,
        CommandType.PROFILE_STOP,
        CommandType.PROFILE_CANCEL,
        CommandType.SHUTDOWN,
    )
    async def process_command_message(self, message: CommandMessage) -> None:
        """Process a command message received from the controller.

        This method will process the command message and execute the appropriate action.
        """
        self.debug(lambda: f"{self.service_id}: Processing command message: {message}")
        response_data = None
        try:
            if message.message_type == CommandType.PROFILE_START:
                response_data = await self.start()

            elif message.message_type == CommandType.SHUTDOWN:
                self.debug(lambda: f"{self.service_id}: Received shutdown command")
                await self.stop()

            elif message.message_type == CommandType.PROFILE_CONFIGURE:
                response_data = await self.run_hooks(AIPerfHook.ON_CONFIGURE, message)

            else:
                self.warning(
                    lambda: f"{self.service_id}: Received unknown command: {message.message_type}"
                )
                return

            # Publish the success response
            await self.pub_client.publish(
                CommandResponseMessage(
                    message_type=message.message_type + "_response",
                    request_id=message.request_id,
                    service_id=self.service_id,
                    origin_service_id=message.service_id,
                    data=response_data,
                ),
            )

        except Exception as e:
            # Publish the failure response
            await self.pub_client.publish(
                CommandResponseMessage(
                    message_type=message.message_type + "_response",
                    request_id=message.request_id,
                    service_id=self.service_id,
                    origin_service_id=message.service_id,
                    error=ErrorDetails.from_exception(e),
                ),
            )

    @on_set_state
    async def _on_set_state(self, state: ServiceState) -> None:
        """Action to take when the service state is set.

        This method will also publish the status message to the status message_type if the
        communications are initialized.
        """
        if (
            self.pub_client
            and self.pub_client.is_initialized
            and not self.pub_client.stop_event.is_set()
        ):
            await self.pub_client.publish(
                self.create_status_message(state),
            )

    def create_heartbeat_message(self) -> HeartbeatMessage:
        """Create a heartbeat notification message."""
        return HeartbeatMessage(
            service_id=self.service_id,
            service_type=self.service_type,
            state=self.state,
        )

    def create_registration_message(self) -> RegistrationMessage:
        """Create a registration request message."""
        return RegistrationMessage(
            service_id=self.service_id,
            service_type=self.service_type,
        )

    def create_status_message(self, state: ServiceState) -> StatusMessage:
        """Create a status notification message."""
        return StatusMessage(
            service_id=self.service_id,
            state=state,
            service_type=self.service_type,
        )
