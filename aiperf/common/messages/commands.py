# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

from abc import ABC

from pydantic import BaseModel, Field, SerializeAsAny

from aiperf.common.config.user_config import UserConfig
from aiperf.common.enums import CommandType, ServiceType
from aiperf.common.messages.message import AutoRequestID, RequiresRequestID
from aiperf.common.messages.service_messages import BaseServiceMessage
from aiperf.common.models import ErrorDetails
from aiperf.common.types import MessageTypeT


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

    data: SerializeAsAny[BaseModel] | None = Field(
        default=None,
        description="The data of the command message. This can be overridden in the subclasses.",
    )


class CommandResponseMessage(BaseServiceMessage, RequiresRequestID, ABC):  # type: ignore
    """Base class for all command response messages."""

    message_type: MessageTypeT = Field(
        ...,
        description="The type of the message. Must be set in the subclass.",
    )
    origin_service_id: str = Field(
        ..., description="The ID of the service that sent the request"
    )
    data: SerializeAsAny[BaseModel] | None = Field(
        default=None,
        description="The data of the command message. This can be overridden in the subclasses.",
    )
    error: ErrorDetails | None = Field(
        default=None, description="Error information if the command failed"
    )


class ProcessRecordsCommand(CommandMessage):
    """This message is sent by the system controller to a component service to request
    that it process records.
    """

    message_type: MessageTypeT = CommandType.PROCESS_RECORDS

    cancelled: bool = Field(
        default=False,
        description="Whether the profile run was cancelled",
    )


class ProcessRecordsResponse(CommandResponseMessage):
    message_type: MessageTypeT = CommandType.PROCESS_RECORDS_RESPONSE


class ShutdownCommand(CommandMessage):
    message_type: MessageTypeT = CommandType.SHUTDOWN


class ShutdownResponse(CommandResponseMessage):
    message_type: MessageTypeT = CommandType.SHUTDOWN_RESPONSE


class ProfileConfigureCommand(CommandMessage):
    message_type: MessageTypeT = CommandType.PROFILE_CONFIGURE
    data: UserConfig = Field(  # type: ignore[override]
        ...,
        description="The configuration data for the profile",
    )


class ProfileConfigureResponse(CommandResponseMessage):
    message_type: MessageTypeT = CommandType.PROFILE_CONFIGURE_RESPONSE


class ProfileStartCommand(CommandMessage):
    message_type: MessageTypeT = CommandType.PROFILE_START


class ProfileStartResponse(CommandResponseMessage):
    message_type: MessageTypeT = CommandType.PROFILE_START_RESPONSE


class ProfileStopCommand(CommandMessage):
    message_type: MessageTypeT = CommandType.PROFILE_STOP


class ProfileStopResponse(CommandResponseMessage):
    message_type: MessageTypeT = CommandType.PROFILE_STOP_RESPONSE


class ProfileCancelCommand(CommandMessage):
    message_type: MessageTypeT = CommandType.PROFILE_CANCEL


class ProfileCancelResponse(CommandResponseMessage):
    message_type: MessageTypeT = CommandType.PROFILE_CANCEL_RESPONSE
