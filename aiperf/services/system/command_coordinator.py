# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""
Command Coordinator for managing command responses and timeouts.

This module provides functionality to coordinate service commands and wait for responses
with timeout handling.
"""

import asyncio
import logging
import time

from pydantic import BaseModel, Field

from aiperf.common.enums import CommandResponseStatus, CommandType
from aiperf.common.messages import CommandResponseMessage


class PendingCommand(BaseModel):
    """Information about a pending command awaiting response."""

    model_config = {"arbitrary_types_allowed": True}

    command_id: str = Field(..., description="Unique command identifier")
    command_type: CommandType = Field(..., description="Type of command")
    target_service_ids: set[str] = Field(
        ..., description="Service IDs that should respond"
    )
    created_at: float = Field(
        default_factory=time.time, description="When command was created"
    )
    timeout_seconds: float = Field(default=10.0, description="Timeout for this command")

    # Track responses
    successful_responses: set[str] = Field(
        default_factory=set, description="Services that responded successfully"
    )
    failed_responses: set[str] = Field(
        default_factory=set, description="Services that responded with failure"
    )

    # Async coordination
    completion_event: asyncio.Event = Field(
        default_factory=asyncio.Event,
        description="Event set when all responses received",
    )

    @property
    def is_complete(self) -> bool:
        """Check if all expected responses have been received."""
        return len(self.successful_responses | self.failed_responses) == len(
            self.target_service_ids
        )

    @property
    def is_successful(self) -> bool:
        """Check if all responses were successful."""
        return len(self.successful_responses) == len(self.target_service_ids)

    @property
    def is_expired(self) -> bool:
        """Check if the command has expired."""
        return time.time() - self.created_at > self.timeout_seconds


class CommandCoordinator:
    """
    Coordinates command responses and manages timeouts.

    This class helps the SystemController track outgoing commands and wait for responses
    from multiple services with timeout handling.
    """

    def __init__(self, default_timeout: float = 10.0):
        self.default_timeout = default_timeout
        self.pending_commands: dict[str, PendingCommand] = {}
        self.logger = logging.getLogger(self.__class__.__name__)

    def register_command(
        self,
        command_id: str,
        command_type: CommandType,
        target_service_ids: set[str],
        timeout_seconds: float | None = None,
    ) -> PendingCommand:
        """
        Register a command that expects responses from specific services.

        Args:
            command_id: Unique identifier for the command
            command_type: Type of command being sent
            target_service_ids: Set of service IDs that should respond
            timeout_seconds: Custom timeout for this command

        Returns:
            PendingCommand object for tracking
        """
        if command_id in self.pending_commands:
            raise ValueError(f"Command {command_id} is already registered")

        timeout = timeout_seconds or self.default_timeout

        pending_command = PendingCommand(
            command_id=command_id,
            command_type=command_type,
            target_service_ids=target_service_ids,
            timeout_seconds=timeout,
        )

        self.pending_commands[command_id] = pending_command

        self.logger.debug(
            "Registered command %s expecting responses from %d services",
            command_id,
            len(target_service_ids),
        )

        return pending_command

    def process_response(self, response: CommandResponseMessage) -> None:
        """Process a command response message."""
        command_id = response.command_id
        service_id = response.service_id

        if command_id not in self.pending_commands:
            self.logger.warning("Received response for unknown command %s", command_id)
            return

        pending_command = self.pending_commands[command_id]

        if service_id not in pending_command.target_service_ids:
            self.logger.debug(
                "Received response from unexpected service %s for command %s",
                service_id,
                command_id,
            )
            return

        # Record the response
        if response.status == CommandResponseStatus.SUCCESS:
            pending_command.successful_responses.add(service_id)
            self.logger.debug(
                "Recorded successful response from %s for command %s",
                service_id,
                command_id,
            )
        else:
            pending_command.failed_responses.add(service_id)
            self.logger.warning(
                "Recorded failed response from %s for command %s",
                service_id,
                command_id,
            )

        # Check if all responses received
        if pending_command.is_complete:
            pending_command.completion_event.set()
            self.logger.debug("All responses received for command %s", command_id)

    async def wait_for_responses(
        self, command_id: str, timeout_seconds: float | None = None
    ) -> bool:
        """Wait for all expected responses to a command.

        Args:
            command_id: The ID of the command to wait for
            timeout_seconds: The timeout in seconds

        Returns:
            True if all responses were successful, False otherwise
        """
        if command_id not in self.pending_commands:
            raise ValueError(f"Command {command_id} not found")

        pending_command = self.pending_commands[command_id]
        timeout = timeout_seconds or pending_command.timeout_seconds

        try:
            await asyncio.wait_for(
                pending_command.completion_event.wait(), timeout=timeout
            )

            successful = pending_command.is_successful

            if successful:
                self.logger.debug("Command %s completed successfully", command_id)
            else:
                self.logger.warning(
                    "Command %s completed with %d failures",
                    command_id,
                    len(pending_command.failed_responses),
                )

            return successful

        except asyncio.TimeoutError:
            self.logger.error(
                "Command %s timed out after %ds. Received %d of %d expected responses",
                command_id,
                timeout,
                len(
                    pending_command.successful_responses
                    | pending_command.failed_responses
                ),
                len(pending_command.target_service_ids),
            )
            raise
        finally:
            self.pending_commands.pop(command_id, None)

    def cleanup_expired_commands(self) -> None:
        """Clean up expired commands that haven't completed."""
        expired_commands = [
            cmd_id
            for cmd_id, cmd in self.pending_commands.items()
            if cmd.is_expired and not cmd.is_complete
        ]

        for cmd_id in expired_commands:
            self.logger.warning("Cleaning up expired command %s", cmd_id)
            self.pending_commands.pop(cmd_id, None)
