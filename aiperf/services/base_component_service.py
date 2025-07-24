# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

from aiperf.common.config import ServiceConfig, UserConfig
from aiperf.common.enums import (
    CommandType,
    LifecycleState,
)
from aiperf.common.hooks import (
    background_task,
    command_handler,
    on_init,
    on_state_change,
)
from aiperf.common.messages import (
    CommandMessage,
    HeartbeatMessage,
    RegistrationMessage,
    StatusMessage,
)
from aiperf.services.base_service import BaseService


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
        user_config: UserConfig,
        service_id: str | None = None,
        **kwargs,
    ) -> None:
        super().__init__(
            service_config=service_config,
            user_config=user_config,
            service_id=service_id,
            **kwargs,
        )

    @background_task(
        interval=lambda self: self.service_config.heartbeat_interval_seconds,
        immediate=False,
    )
    async def _heartbeat_task(self) -> None:
        """Send a heartbeat notification to the system controller."""
        heartbeat_message = self.create_heartbeat_message()
        self.debug(lambda: f"Sending heartbeat: {heartbeat_message}")
        try:
            await self.pub_client.publish(
                message=heartbeat_message,
            )
        except Exception as e:
            raise self._service_error("Failed to send heartbeat") from e

    @on_init
    async def _register_service(self) -> None:
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

    @command_handler(CommandType.SHUTDOWN)
    async def _on_shutdown_command(self, message: CommandMessage) -> None:
        try:
            await self.stop()
        except Exception as e:
            self.warning(
                f"Failed to stop service {self} ({self.service_id}) after receiving shutdown command: {e}. Killing."
            )
            await self.kill()

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
