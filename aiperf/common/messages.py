# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
import uuid
from typing import Any, Literal

from pydantic import (
    Field,
    SerializeAsAny,
)

# from aiperf.common.config import UserConfig
from aiperf.common.dataset_models import Conversation
from aiperf.common.enums import (
    CommandResponseStatus,
    CommandType,
    CreditPhase,
    MessageType,
    NotificationType,
    ServiceState,
    ServiceType,
)
from aiperf.common.pydantic_utils import (
    AIPerfBaseModel,
)
from aiperf.common.record_models import (
    ErrorDetails,
    ParsedResponseRecord,
    RequestRecord,
)
from aiperf.messages.base_messages import Message, RequiresRequestNSMixin

################################################################################
# Abstract Base Message Models
################################################################################


class BaseServiceMessage(Message):
    """Base message that is sent from a service. Requires a service_id field to specify
    the service that sent the message."""

    service_id: str = Field(
        ...,
        description="ID of the service sending the message",
    )


class BaseStatusMessage(BaseServiceMessage, RequiresRequestNSMixin):
    """Base message containing status data.
    This message is sent by a service to the system controller to report its status.
    """

    state: ServiceState = Field(
        ...,
        description="Current state of the service",
    )
    service_type: ServiceType = Field(
        ...,
        description="Type of service",
    )


################################################################################
# Concrete Message Models
################################################################################


class StatusMessage(BaseStatusMessage):
    """Message containing status data.
    This message is sent by a service to the system controller to report its status.
    """

    message_type: Literal[MessageType.STATUS] = MessageType.STATUS


class RegistrationMessage(BaseStatusMessage):
    """Message containing registration data.
    This message is sent by a service to the system controller to register itself.
    """

    message_type: Literal[MessageType.REGISTRATION] = MessageType.REGISTRATION

    state: ServiceState = ServiceState.READY


class HeartbeatMessage(BaseStatusMessage):
    """Message containing heartbeat data.
    This message is sent by a service to the system controller to indicate that it is
    still running.
    """

    message_type: Literal[MessageType.HEARTBEAT] = MessageType.HEARTBEAT


class ProcessRecordsCommandData(AIPerfBaseModel):
    """Data to send with the process records command."""

    cancelled: bool = Field(
        default=False,
        description="Whether the profile run was cancelled",
    )


class CommandMessage(BaseServiceMessage):
    """Message containing command data.
    This message is sent by the system controller to a service to command it to do something.
    """

    message_type: Literal[MessageType.COMMAND] = MessageType.COMMAND

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
    # TODO: I'm not sure if SerializeAsAny actually works as expected
    data: SerializeAsAny[Any] = Field(
        default=None,
        description="Data to send with the command",
    )


class CommandResponseMessage(BaseServiceMessage):
    """Message containing a command response.
    This message is sent by a component service to the system controller to respond to a command.
    """

    message_type: Literal[MessageType.COMMAND_RESPONSE] = MessageType.COMMAND_RESPONSE

    command: CommandType = Field(
        ..., description="Command type that is being responded to"
    )
    command_id: str = Field(
        ..., description="The ID of the command that is being responded to"
    )
    status: CommandResponseStatus = Field(..., description="The status of the command")
    data: SerializeAsAny[AIPerfBaseModel | None] = Field(
        default=None,
        description="Data to send with the command response if the command succeeded",
    )
    error: ErrorDetails | None = Field(
        default=None, description="Error information if the command failed"
    )


class ErrorMessage(Message):
    """Message containing error data."""

    message_type: Literal[MessageType.ERROR] = MessageType.ERROR

    error: ErrorDetails = Field(..., description="Error information")


class NotificationMessage(BaseServiceMessage):
    """Message containing a notification from a service. This is used to notify other services of events."""

    message_type: Literal[MessageType.NOTIFICATION] = MessageType.NOTIFICATION

    notification_type: NotificationType = Field(
        ..., description="The type of notification"
    )

    data: SerializeAsAny[AIPerfBaseModel | None] = Field(
        default=None,
        description="Data to send with the notification",
    )


class BaseServiceErrorMessage(BaseServiceMessage):
    """Base message containing error data."""

    message_type: Literal[MessageType.SERVICE_ERROR] = MessageType.SERVICE_ERROR

    error: ErrorDetails = Field(..., description="Error information")


class ConversationRequestMessage(BaseServiceMessage):
    """Message for a conversation request."""

    message_type: Literal[MessageType.CONVERSATION_REQUEST] = (
        MessageType.CONVERSATION_REQUEST
    )

    conversation_id: str | None = Field(
        default=None, description="The session ID of the conversation"
    )
    credit_phase: CreditPhase | None = Field(
        default=None,
        description="The type of credit phase (either warmup or profiling). If not provided, the timing manager will use the default credit phase.",
    )


class ConversationResponseMessage(BaseServiceMessage):
    """Message for a conversation response."""

    message_type: Literal[MessageType.CONVERSATION_RESPONSE] = (
        MessageType.CONVERSATION_RESPONSE
    )
    conversation: Conversation = Field(..., description="The conversation data")


class InferenceResultsMessage(BaseServiceMessage):
    """Message for a inference results."""

    message_type: Literal[MessageType.INFERENCE_RESULTS] = MessageType.INFERENCE_RESULTS

    record: SerializeAsAny[RequestRecord] = Field(
        ..., description="The inference results record"
    )


class ParsedInferenceResultsMessage(BaseServiceMessage):
    """Message for a parsed inference results."""

    message_type: Literal[MessageType.PARSED_INFERENCE_RESULTS] = (
        MessageType.PARSED_INFERENCE_RESULTS
    )

    record: SerializeAsAny[ParsedResponseRecord] = Field(
        ..., description="The post process results record"
    )


class DatasetTimingRequest(BaseServiceMessage):
    """Message for a dataset timing request."""

    message_type: Literal[MessageType.DATASET_TIMING_REQUEST] = (
        MessageType.DATASET_TIMING_REQUEST
    )


class DatasetTimingResponse(BaseServiceMessage):
    """Message for a dataset timing response."""

    message_type: Literal[MessageType.DATASET_TIMING_RESPONSE] = (
        MessageType.DATASET_TIMING_RESPONSE
    )

    timing_data: list[tuple[int, str]] = Field(
        ...,
        description="The timing data of the dataset. Tuple of (timestamp, conversation_id)",
    )
