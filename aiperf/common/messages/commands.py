# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

from abc import ABC

from pydantic import BaseModel, Field, SerializeAsAny
from pydantic.fields import FieldInfo

from aiperf.common.config.user_config import UserConfig
from aiperf.common.enums import CommandType, ServiceType
from aiperf.common.messages.message import AutoRequestID, RequiresRequestID
from aiperf.common.messages.service_messages import BaseServiceMessage
from aiperf.common.models import AIPerfBaseModel, ErrorDetails


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

    data: SerializeAsAny[BaseModel] | None = Field(
        default=None,
        description="The data of the command message. This can be overridden in the subclasses.",
    )

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

    message_type = CommandType.PROCESS_RECORDS

    cancelled: bool = Field(
        default=False,
        description="Whether the profile run was cancelled",
    )


def _command_message_type(
    message_type: CommandType,
    data_type: type[BaseModel] | None = None,
    data_field: FieldInfo | None = None,
) -> type[CommandMessage]:
    """Create a generic command message class for a given message type."""

    # Need to save the message type here for use below in the class definition
    _message_type = message_type
    _data_type = data_type
    _data_field = data_field

    class GenericCommandMessage(CommandMessage):
        message_type = _message_type
        if _data_type is not None:
            data: _data_type = _data_field

    # Set the class name and docstring
    GenericCommandMessage.__doc__ = f"Message for the {message_type.name} command."
    GenericCommandMessage.__name__ = f"{message_type.name.title()}Command"
    GenericCommandMessage.__qualname__ = GenericCommandMessage.__name__
    return GenericCommandMessage


def _command_response_type(
    message_type: CommandType,
    data_type: type[BaseModel] | None = None,
    data_field: FieldInfo | None = None,
) -> type[CommandResponseMessage]:
    """Create a generic command response class for a given message type."""

    # Need to save the message type here for use below in the class definition
    _message_type = message_type
    _data_type = data_type
    _data_field = data_field

    class GenericCommandResponseMessage(CommandResponseMessage):
        message_type = _message_type
        if _data_type is not None:
            data: _data_type = _data_field

    # Set the class name and docstring
    GenericCommandResponseMessage.__doc__ = (
        f"Response to the {message_type.name} command."
    )
    GenericCommandResponseMessage.__name__ = f"{message_type.name.title()}Message"
    GenericCommandResponseMessage.__qualname__ = GenericCommandResponseMessage.__name__
    return GenericCommandResponseMessage


# On the fly generated command message types
ProfileConfigureCommand = _command_message_type(
    CommandType.PROFILE_CONFIGURE,
    data_type=UserConfig,
    data_field=Field(
        default=None,
        description="The data of the command message. This can be overridden in the subclasses.",
    ),
)
ProfileStartCommand = _command_message_type(CommandType.PROFILE_START)
ProfileStopCommand = _command_message_type(CommandType.PROFILE_STOP)
ProfileCancelCommand = _command_message_type(CommandType.PROFILE_CANCEL)
ShutdownCommand = _command_message_type(CommandType.SHUTDOWN)

# On the fly generated command response types
ProfileStartResponse = _command_response_type(CommandType.PROFILE_START_RESPONSE)
ProfileStopResponse = _command_response_type(CommandType.PROFILE_STOP_RESPONSE)
ProfileCancelResponse = _command_response_type(CommandType.PROFILE_CANCEL_RESPONSE)
ShutdownResponse = _command_response_type(CommandType.SHUTDOWN_RESPONSE)
ProcessRecordsResponse = _command_response_type(
    CommandType.PROCESS_RECORDS_RESPONSE,
    data_type=AIPerfBaseModel,
    data_field=Field(
        default=None,
        description="The data of the command message. This can be overridden in the subclasses.",
    ),
)
