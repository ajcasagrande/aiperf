# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

import asyncio
from abc import ABC
from collections.abc import Iterable
from typing import Any

from aiperf.common.config import ServiceConfig, UserConfig
from aiperf.common.constants import DEFAULT_COMMAND_RESPONSE_TIMEOUT
from aiperf.common.enums import MessageType
from aiperf.common.hooks import AIPerfHook, on_message, provides_hooks
from aiperf.common.messages import (
    CommandAcknowledgedResponse,
    CommandErrorResponse,
    CommandMessage,
    CommandResponse,
    CommandSuccessResponse,
    CommandUnhandledResponse,
)
from aiperf.common.mixins.message_bus_mixin import MessageBusClientMixin
from aiperf.common.models import ErrorDetails
from aiperf.common.registry.command_tracker import (
    CommandTracker,
)


@provides_hooks(AIPerfHook.ON_COMMAND)
class EnhancedCommandHandlerMixin(MessageBusClientMixin, ABC):
    """Enhanced command handler with thread-safe tracking and atomic operations."""

    def __init__(
        self,
        service_config: ServiceConfig,
        user_config: UserConfig,
        service_id: str,
        **kwargs,
    ) -> None:
        self.service_config = service_config
        self.user_config = user_config
        self.service_id = service_id

        self._command_tracker = CommandTracker()
        self.attach_child_lifecycle(self._command_tracker)

        self._response_lock = asyncio.Lock()

        super().__init__(
            service_config=self.service_config,
            user_config=self.user_config,
            **kwargs,
        )

    @property
    def command_tracker(self) -> CommandTracker:
        """Access to the command tracker instance."""
        return self._command_tracker

    @on_message(
        lambda self: {
            MessageType.COMMAND,
            f"{MessageType.COMMAND}.{self.service_type}",
            f"{MessageType.COMMAND}.{self.service_id}",
        }
    )
    async def _process_command_message(self, message: CommandMessage) -> None:
        """Process command messages with duplicate detection and atomic tracking."""
        self.debug(lambda: f"Received command message: {message}")

        if await self._command_tracker.is_command_processed(message.command_id):
            self.debug(
                lambda: f"Received duplicate command message: {message}. Sending acknowledgment."
            )
            await self._publish_command_acknowledged_response(message)
            return

        await self._command_tracker.mark_command_processed(message.command_id)

        if message.service_id == self.service_id:
            self.debug(
                lambda: f"Received broadcast command message from self: {message}. Ignoring."
            )
            return

        for hook in self.get_hooks(AIPerfHook.ON_COMMAND):
            if isinstance(hook.params, Iterable) and message.command in hook.params:
                await self._execute_command_hook(message, hook)
                return

        await self._publish_command_unhandled_response(message)

    async def _execute_command_hook(self, message: CommandMessage, hook: Any) -> None:
        """Execute command hook with error handling and response tracking."""
        try:
            result = await hook.func(message)
            if result is None:
                await self._publish_command_acknowledged_response(message)
                return
            await self._publish_command_success_response(message, result)
        except Exception as e:
            self.exception(
                "Failed to handle command %s with hook %s: %s",
                message.command,
                hook,
                e,
            )
            await self._publish_command_error_response(
                message, ErrorDetails.from_exception(e)
            )

    async def send_command_and_wait_for_response(
        self,
        message: CommandMessage,
        timeout: float = DEFAULT_COMMAND_RESPONSE_TIMEOUT,
    ) -> CommandResponse | ErrorDetails:
        """Send command with enhanced tracking and atomic response handling."""
        async with self._response_lock:
            await self._command_tracker.start_tracking_command(
                command_id=message.command_id,
                command_type=message.command,
                target_service_ids=None,
                timeout=timeout,
            )

        await self.publish(message)
        await self._command_tracker.mark_command_sent(message.command_id)

        try:
            result = await self._command_tracker.wait_for_command_completion(
                command_id=message.command_id,
                timeout=timeout,
            )

            if result is None:
                return ErrorDetails(
                    error_type="timeout",
                    error_message=f"Command {message.command_id} timed out",
                )

            if result.success and result.responses:
                return result.responses[0]

            return result.error_details or ErrorDetails(
                error_type="unknown",
                error_message="Command execution failed without error details",
            )

        except Exception as e:
            await self._command_tracker.cancel_command(message.command_id)
            return ErrorDetails.from_exception(e)

    async def send_command_and_wait_for_all_responses(
        self,
        command: CommandMessage,
        service_ids: list[str],
        timeout: float = DEFAULT_COMMAND_RESPONSE_TIMEOUT,
    ) -> list[CommandResponse | ErrorDetails]:
        """Send command to multiple services with enhanced tracking."""
        target_service_ids = set(service_ids)

        async with self._response_lock:
            await self._command_tracker.start_tracking_command(
                command_id=command.command_id,
                command_type=command.command,
                target_service_ids=target_service_ids,
                timeout=timeout,
            )

        await self.publish(command)
        await self._command_tracker.mark_command_sent(command.command_id)

        try:
            responses = await self._command_tracker.wait_for_all_responses(
                command_id=command.command_id,
                timeout=timeout,
            )

            if len(responses) == len(service_ids):
                return responses

            timeout_error = ErrorDetails(
                error_type="timeout",
                error_message=f"Command {command.command_id} timed out waiting for all responses",
            )

            return responses + [timeout_error] * (len(service_ids) - len(responses))

        except Exception as e:
            await self._command_tracker.cancel_command(command.command_id)
            error = ErrorDetails.from_exception(e)
            return [error] * len(service_ids)

    @on_message(
        lambda self: {
            f"{MessageType.COMMAND_RESPONSE}.{self.service_id}",
        }
    )
    async def _process_command_response_message(self, message: CommandResponse) -> None:
        """Process command responses with atomic tracking updates."""
        self.trace_or_debug(
            lambda: f"Received command response message: {message}",
            lambda: f"Received command response for command '{message.command}' with id: {message.command_id}",
        )

        command_info = await self._command_tracker.get_command_info(message.command_id)
        if command_info is None:
            self.debug(
                lambda: f"Received command response for untracked command: {message}. Ignoring."
            )
            return

        if command_info.target_service_ids:
            await self._command_tracker.record_response(
                command_id=message.command_id,
                service_id=message.service_id,
                response=message,
            )
        else:
            await self._command_tracker.record_single_response(
                command_id=message.command_id,
                response=message,
            )

    async def get_command_execution_stats(self) -> dict[str, Any]:
        """Get comprehensive command execution statistics."""
        stats = await self._command_tracker.get_tracker_stats()
        return {
            "total_commands": stats.total_commands,
            "active_commands": stats.active_commands,
            "completed_commands": stats.completed_commands,
            "failed_commands": stats.failed_commands,
            "timeout_commands": stats.timeout_commands,
            "commands_by_type": stats.commands_by_type,
            "commands_by_state": stats.commands_by_state,
            "average_response_time": stats.average_response_time,
            "last_updated": stats.last_updated,
        }

    async def get_active_command_info(self, command_id: str) -> dict[str, Any] | None:
        """Get detailed information about an active command."""
        info = await self._command_tracker.get_command_info(command_id)
        if info is None:
            return None

        return {
            "command_id": info.command_id,
            "command_type": info.command_type,
            "state": info.state,
            "target_service_ids": list(info.target_service_ids),
            "pending_service_ids": list(info.pending_service_ids),
            "created_at": info.created_at,
            "sent_at": info.sent_at,
            "timeout_at": info.timeout_at,
            "responses_count": len(info.responses_received),
            "error_details": info.error_details.model_dump()
            if info.error_details
            else None,
        }

    async def cancel_command_execution(self, command_id: str) -> bool:
        """Cancel an active command execution."""
        return await self._command_tracker.cancel_command(command_id)

    async def add_command_completion_callback(
        self,
        callback: Any,
        weak_ref: bool = True,
    ) -> None:
        """Add callback for command completion events."""
        await self._command_tracker.add_completion_callback(callback, weak_ref)

    async def add_command_timeout_callback(
        self,
        callback: Any,
        weak_ref: bool = True,
    ) -> None:
        """Add callback for command timeout events."""
        await self._command_tracker.add_timeout_callback(callback, weak_ref)

    async def _publish_command_acknowledged_response(
        self, message: CommandMessage
    ) -> None:
        """Publish command acknowledged response."""
        await self.publish(
            CommandAcknowledgedResponse.from_command_message(message, self.service_id)
        )

    async def _publish_command_success_response(
        self, message: CommandMessage, result: Any
    ) -> None:
        """Publish command success response."""
        await self.publish(
            CommandSuccessResponse.from_command_message(
                message, self.service_id, result
            )
        )

    async def _publish_command_error_response(
        self, message: CommandMessage, error: ErrorDetails
    ) -> None:
        """Publish command error response."""
        await self.publish(
            CommandErrorResponse.from_command_message(message, self.service_id, error)
        )

    async def _publish_command_unhandled_response(
        self, message: CommandMessage
    ) -> None:
        """Publish command unhandled response."""
        await self.publish(
            CommandUnhandledResponse.from_command_message(message, self.service_id)
        )
