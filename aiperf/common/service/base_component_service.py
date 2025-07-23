# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
from collections.abc import Awaitable, Callable
from typing import Any

from aiperf.common.config import ServiceConfig, UserConfig
from aiperf.common.enums import (
    CommandResponseStatus,
    CommandType,
    LifecycleState,
    MessageType,
)
from aiperf.common.hooks import background_task, on_init, on_state_change
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
    - Sending status notifications to the system controller
    - Helpers to create status messages
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

        self._command_callbacks: dict[
            CommandType, Callable[[CommandMessage], Awaitable[Any]]
        ] = {}

    @on_init
    async def _on_init(self) -> None:
        """Automatically subscribe to the command message_type and register the service
        with the system controller when the run hook is called.

        This method will:
        - Subscribe to the command message_type
        - Wait for the communication to be fully initialized
        - Register the service with the system controller
        """
        # Subscribe to the command message_type
        try:
            await self.sub_client.subscribe(
                MessageType.COMMAND,
                self.process_command_message,
            )
        except Exception as e:
            raise self._service_error("Failed to subscribe to command topic") from e

        # Register the service
        try:
            await self.register()
        except Exception as e:
            raise self._service_error("Failed to register service") from e

    @background_task(
        interval=lambda self: self.service_config.heartbeat_interval_seconds,
        immediate=False,
    )
    async def _heartbeat_task(self) -> None:
        """Starts a background task to send heartbeats at regular intervals. It
        will continue to send heartbeats even if an error occurs until the stop
        event is set.
        """
        await self.send_heartbeat()

    async def send_heartbeat(self) -> None:
        """Send a heartbeat notification to the system controller."""
        heartbeat_message = self.create_heartbeat_message()
        self.debug(lambda: f"Sending heartbeat: {heartbeat_message}")
        try:
            await self.pub_client.publish(
                message=heartbeat_message,
            )
        except Exception as e:
            raise self._service_error("Failed to send heartbeat") from e

    async def register(self) -> None:
        """Publish a registration request to the system controller.

        This method should be called after the service has been initialized and is
        ready to start processing messages.
        """
        self.debug(
            lambda: f"Attempting to register service {self} ({self.service_id}) with system controller"
        )
        try:
            await self.pub_client.publish(
                message=self.create_registration_message(),
            )
        except Exception as e:
            raise self._service_error("Failed to register service") from e

    async def process_command_message(self, message: CommandMessage) -> None:
        """Process a command message received from the controller.

        This method will process the command message and execute the appropriate action.
        """
        if message.target_service_id and message.target_service_id != self.service_id:
            return  # Ignore commands meant for other services
        if (
            message.target_service_type
            and message.target_service_type != self.service_type
        ):
            return  # Ignore commands meant for other services

        self.debug(lambda: f"Processing command message: {message}")
        cmd = message.command
        response_data = None
        try:
            stop_requested = False

            if cmd == CommandType.SHUTDOWN:
                self.debug("Received shutdown command")
                stop_requested = True
                response_status = CommandResponseStatus.ACKNOWLEDGED

            elif cmd in self._command_callbacks:
                response_data = await self._command_callbacks[cmd](message)
                response_status = CommandResponseStatus.SUCCESS

            else:
                raise self._service_error(
                    f"Received unknown command: {cmd}",
                )

            # Publish the success response
            await self.pub_client.publish(
                CommandResponseMessage(
                    service_id=self.service_id,
                    command=cmd,
                    command_id=message.command_id,
                    status=response_status,
                    data=response_data,
                ),
            )

            if stop_requested:
                try:
                    await self.stop()
                except Exception as e:
                    self.warning(
                        f"Failed to stop service {self} ({self.service_id}) after receiving shutdown command: {e}. Killing."
                    )
                    await self.kill()

        except Exception as e:
            # Publish the failure response
            await self.pub_client.publish(
                CommandResponseMessage(
                    service_id=self.service_id,
                    command=cmd,
                    command_id=message.command_id,
                    status=CommandResponseStatus.FAILURE,
                    error=ErrorDetails.from_exception(e),
                ),
            )

    def register_command_callback(
        self,
        cmd: CommandType,
        callback: Callable[[CommandMessage], Awaitable[Any]],
    ) -> None:
        """Register a single callback for a command."""
        self._command_callbacks[cmd] = callback

    @on_state_change
    async def _on_state_change(
        self, old_state: LifecycleState, new_state: LifecycleState
    ) -> None:
        """Action to take when the service state is set.

        This method will also publish the status message to the status message_type if the
        communications are initialized.
        """
        if self.pub_client.is_running:
            self.execute_async(
                self.pub_client.publish(self.create_status_message(new_state))
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
            state=self.state,
        )

    def create_status_message(self, state: LifecycleState) -> StatusMessage:
        """Create a status notification message."""
        return StatusMessage(
            service_id=self.service_id,
            state=state,
            service_type=self.service_type,
        )
