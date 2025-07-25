# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
import uuid
from typing import Any

from pydantic import (
    BaseModel,
    Field,
    SerializeAsAny,
    model_validator,
)
from typing_extensions import Self

from aiperf.common.enums import (
    CommandResponseStatus,
    CommandType,
    MessageType,
)
from aiperf.common.messages.service_messages import BaseServiceMessage
from aiperf.common.models.error_models import ErrorDetails
from aiperf.common.types import MessageTypeT, ServiceTypeT


class TargetedServiceMessage(BaseServiceMessage):
    """Message that can be targeted to a specific service by id or type.
    If both `target_service_type` and `target_service_id` are None, the message is
    sent to all services that are subscribed to the message type.
    """

    @model_validator(mode="after")
    def validate_target_service(self) -> Self:
        if self.target_service_id is not None and self.target_service_type is not None:
            raise ValueError(
                "Either target_service_id or target_service_type can be provided, but not both"
            )
        return self

    target_service_id: str | None = Field(
        default=None,
        description="ID of the target service to send the message to. "
        "If both `target_service_type` and `target_service_id` are None, the message is "
        "sent to all services that are subscribed to the message type.",
    )
    target_service_type: ServiceTypeT | None = Field(
        default=None,
        description="Type of the service to send the message to. "
        "If both `target_service_type` and `target_service_id` are None, the message is "
        "sent to all services that are subscribed to the message type.",
    )


class CommandResponseMessage(TargetedServiceMessage):
    """Message containing a command response."""

    message_type: MessageTypeT = MessageType.COMMAND_RESPONSE

    command: CommandType = Field(
        ...,
        description="Command type that is being responded to",
    )
    command_id: str = Field(
        ..., description="The ID of the command that is being responded to"
    )
    status: CommandResponseStatus = Field(..., description="The status of the command")
    data: SerializeAsAny[BaseModel | list[Any] | None] = Field(
        default=None,
        description="Data to send with the command response if the command succeeded",
    )
    error: ErrorDetails | None = Field(
        default=None,
        description="Error information if the command failed",
    )


class SpawnWorkersCommandData(BaseModel):
    """Data to send with the spawn workers command."""

    num_workers: int = Field(..., description="Number of workers to spawn")


class ShutdownWorkersCommandData(BaseModel):
    """Data to send with the shutdown workers command."""

    @model_validator(mode="after")
    def validate_worker_ids_or_num_workers(self) -> Self:
        if self.worker_ids is None and self.num_workers is None:
            raise ValueError("Either worker_ids or num_workers must be provided")
        if self.worker_ids is not None and self.num_workers is not None:
            raise ValueError(
                "Either worker_ids or num_workers must be provided, not both"
            )
        return self

    worker_ids: list[str] | None = Field(
        default=None,
        description="IDs of the workers to shutdown. If not provided, will shutdown random workers up to the number of workers to shutdown.",
    )
    num_workers: int | None = Field(
        default=None,
        description="Number of workers to shutdown if worker_ids is not provided.",
    )


class ProcessRecordsCommandData(BaseModel):
    """Data to send with the process records command."""

    cancelled: bool = Field(
        default=False,
        description="Whether the profile run was cancelled",
    )


class CommandMessage(TargetedServiceMessage):
    """Message containing command data.
    This message is sent by the system controller to a service to command it to do something.
    """

    message_type: MessageTypeT = MessageType.COMMAND

    command: CommandType = Field(
        ...,
        description="Command to execute",
    )
    command_id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Unique identifier for this command. If not provided, a random UUID will be generated.",
    )
    require_response: bool = Field(
        default=False,
        description="Whether a response is required for this command",
    )
    data: SerializeAsAny[
        SpawnWorkersCommandData
        | ShutdownWorkersCommandData
        | ProcessRecordsCommandData
        | BaseModel
        | None
    ] = Field(
        default=None,
        description="Data to send with the command",
    )
