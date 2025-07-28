# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
import uuid
from typing import cast

from aiperf.common.config import ServiceConfig, UserConfig
from aiperf.common.enums import (
    CommandResponseStatus,
    MessageType,
)
from aiperf.common.hooks import on_message
from aiperf.common.messages import (
    CommandMessage,
    CommandResponse,
)
from aiperf.common.messages.command_messages import (
    ErrorCommandResponse,
    TrackedCommand,
)
from aiperf.common.mixins.message_bus_mixin import MessageBusClientMixin


class Commander(MessageBusClientMixin):
    """System Controller service.

    This service is responsible for managing the lifecycle of all other services.
    It will start, stop, and configure all other services.
    """

    def __init__(
        self,
        user_config: UserConfig,
        service_config: ServiceConfig,
        service_id: str | None = None,
    ) -> None:
        super().__init__(
            service_config=service_config,
            user_config=user_config,
            service_id=service_id,
        )
        self._tracked_commands: dict[str, TrackedCommand] = {}

    async def send_command_with_tracking(self, command: CommandMessage) -> str:
        """Send a command and track the response."""
        command_id = str(uuid.uuid4())
        tracked_command = TrackedCommand(
            command=command.command,
            command_id=command_id,
            responses={},
        )
        self._tracked_commands[command_id] = tracked_command
        await self.publish(command)
        return command_id

    @on_message(
        lambda self: {
            f"{MessageType.COMMAND_RESPONSE}.{self.service_id}",
        }
    )
    async def _process_command_response_message(self, message: CommandResponse) -> None:
        """Process a command response message."""
        self.debug(lambda: f"Received command response message: {message}")
        if message.status == CommandResponseStatus.SUCCESS:
            self.debug(f"Command {message.command} succeeded from {message.service_id}")
        elif message.status == CommandResponseStatus.ACKNOWLEDGED:
            self.debug(
                f"Command {message.command} acknowledged from {message.service_id}"
            )
        elif message.status == CommandResponseStatus.UNHANDLED:
            self.debug(f"Command {message.command} unhandled from {message.service_id}")
        elif message.status == CommandResponseStatus.FAILURE:
            message = cast(ErrorCommandResponse, message)
            self.error(
                f"Command {message.command} failed from {message.service_id}: {message.error}"
            )
