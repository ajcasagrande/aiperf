# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

import time

from aiperf.common.enums import CommandType, MessageType
from aiperf.common.hooks import on_command, on_message
from aiperf.common.messages import (
    HeartbeatMessage,
    StatusMessage,
)
from aiperf.common.messages.command_messages import RegisterServiceCommand
from aiperf.common.mixins.command_handler_mixin import CommandHandlerMixin
from aiperf.common.service_registry import ServiceRegistry


class ServiceRegistryMixin(CommandHandlerMixin):
    """Mixin that provides service registry functionality via command handler
    and message bus.

    This mixin manages the ServiceRegistry instance and listens to service
    registration, heartbeat, and status messages to track service states.
    """

    @on_command(CommandType.REGISTER_SERVICE)
    async def _on_register_service_command(
        self, message: RegisterServiceCommand
    ) -> None:
        """Handle service registration messages."""
        self.debug(
            lambda: f"Received registration from {message.service_type} service: {message.service_id}"
        )
        await ServiceRegistry.register(
            service_id=message.service_id,
            service_type=message.service_type,
            first_seen_ns=message.request_ns or time.time_ns(),
            state=message.state,
        )

    @on_message(MessageType.HEARTBEAT)
    async def _on_heartbeat_message(self, message: HeartbeatMessage) -> None:
        """Handle service heartbeat messages."""
        self.debug(
            lambda: f"Received heartbeat from {message.service_type} service: {message.service_id}"
        )
        await ServiceRegistry.update_service(
            service_id=message.service_id,
            service_type=message.service_type,
            last_seen_ns=message.request_ns or time.time_ns(),
            state=message.state,
        )

    @on_message(MessageType.STATUS)
    async def _on_status_message(self, message: StatusMessage) -> None:
        """Handle service status messages."""
        self.debug(
            lambda: f"Received status from {message.service_type} service: {message.service_id}"
        )
        await ServiceRegistry.update_service(
            service_id=message.service_id,
            service_type=message.service_type,
            last_seen_ns=message.request_ns or time.time_ns(),
            state=message.state,
        )
