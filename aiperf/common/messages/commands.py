# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

from abc import ABC
from typing import Literal

from pydantic import Field, SerializeAsAny

from aiperf.common.enums import MessageType, ServiceType
from aiperf.common.messages.message import AutoRequestID, RequiresRequestID
from aiperf.common.messages.service_messages import BaseServiceMessage
from aiperf.common.models import AIPerfBaseModel, ErrorDetails

# class CommandMessage(BaseServiceMessage):
#     """Message containing command data.
#     This message is sent by the system controller to a service to command it to do something.
#     """

#     message_type: Literal[MessageType.COMMAND] = MessageType.COMMAND

#     command: CommandType = Field(
#         ...,
#         description="Command to execute",
#     )
#     command_id: str = Field(
#         default_factory=lambda: str(uuid.uuid4()),
#         description="Unique identifier for this command. If not provided, a random UUID will be generated.",
#     )
#     require_response: bool = Field(
#         default=False,
#         description="Whether a response is required for this command",
#     )
#     target_service_type: ServiceType | None = Field(
#         default=None,
#         description="Type of the service to send the command to. "
#         "If both `target_service_type` and `target_service_id` are None, the command is "
#         "sent to all services.",
#     )
#     target_service_id: str | None = Field(
#         default=None,
#         description="ID of the target service to send the command to. "
#         "If both `target_service_type` and `target_service_id` are None, the command is "
#         "sent to all services.",
#     )
#     # TODO: I'm not sure if SerializeAsAny actually works as expected
#     data: SerializeAsAny[
#         UserConfig | ProcessRecordsCommandData | AIPerfBaseModel | Any
#     ] = Field(
#         default=None,
#         description="Data to send with the command",
#     )


# class CommandResponseMessage(BaseServiceMessage):
#     """Message containing a command response.
#     This message is sent by a component service to the system controller to respond to a command.
#     """

#     message_type: Literal[MessageType.COMMAND_RESPONSE] = MessageType.COMMAND_RESPONSE

#     command: CommandType = Field(
#         ..., description="Command type that is being responded to"
#     )
#     command_id: str = Field(
#         ..., description="The ID of the command that is being responded to"
#     )
#     status: CommandResponseStatus = Field(..., description="The status of the command")
#     data: SerializeAsAny[AIPerfBaseModel | None] = Field(
#         default=None,
#         description="Data to send with the command response if the command succeeded",
#     )
#     error: ErrorDetails | None = Field(
#         default=None, description="Error information if the command failed"
#     )


class CommandMessage(BaseServiceMessage, AutoRequestID, ABC):  # type: ignore
    """Base class for all command messages."""

    require_response: bool = Field(
        default=False,
        description="Whether a response is required for this command",
    )
    target_service_type: ServiceType | None = Field(
        default=None,
        description="Type of the service to send the command to. "
        "If both `target_service_type` and `target_service_id` are None, the command is "
        "sent to all services.",
    )
    target_service_id: str | None = Field(
        default=None,
        description="ID of the target service to send the command to. "
        "If both `target_service_type` and `target_service_id` are None, the command is "
        "sent to all services.",
    )


class CommandResponseMessage(BaseServiceMessage, RequiresRequestID, ABC):  # type: ignore
    """Base class for all command response messages."""

    origin_service_id: str = Field(
        ..., description="The ID of the service that sent the request"
    )
    error: ErrorDetails | None = Field(
        default=None, description="Error information if the command failed"
    )


class ProcessRecordsCommand(CommandMessage):
    """This message is sent by the system controller to a component service to request
    that it process records.
    """

    message_type: Literal[MessageType.PROCESS_RECORDS_COMMAND] = (
        MessageType.PROCESS_RECORDS_COMMAND
    )

    cancelled: bool = Field(
        default=False,
        description="Whether the profile run was cancelled",
    )


class ProcessRecordsResponse(CommandResponseMessage):
    """This message is sent by a component service to the system controller to respond
    to a process records request.
    """

    message_type: Literal[MessageType.PROCESS_RECORDS_RESPONSE] = (
        MessageType.PROCESS_RECORDS_RESPONSE
    )

    # TODO: Better way to handle results data
    results: SerializeAsAny[AIPerfBaseModel | None] = Field(
        default=None,
        description="Data returned from the process records request",
    )
