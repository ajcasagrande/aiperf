from typing import Optional, Dict, Any, Union

from pydantic import BaseModel, Field

from aiperf.common.enums import MessageType, ServiceState


DISCRIMINATOR = "message_type"
"""Discriminator field for polymorphic models."""


class BaseMessageData(BaseModel):
    """Base class for message data payloads."""

    message_type: MessageType = Field(
        ...,
        description="Type of the message",
    )


class StatusData(BaseMessageData):
    """Status message sent by services to report their state."""

    message_type: MessageType = MessageType.STATUS
    state: ServiceState = Field(
        ...,
        description="Current state of the service",
    )


class HeartbeatData(StatusData):
    """Heartbeat message sent periodically by services."""

    message_type: MessageType = MessageType.HEARTBEAT
    state: ServiceState = ServiceState.RUNNING


class CommandData(BaseMessageData):
    """Command message sent to services to request an action."""

    message_type: MessageType = MessageType.COMMAND
    command_id: str = Field(
        ...,
        description="Unique identifier for this command",
    )
    command: str = Field(
        ...,
        description="Command to execute",
    )
    require_response: bool = Field(
        default=False,
        description="Whether a response is required for this command",
    )
    target_service_id: Optional[str] = Field(
        default=None,
        description="ID of the target service for this command",
    )


class ResponseData(BaseMessageData):
    """Response message sent in reply to a command."""

    message_type: MessageType = MessageType.RESPONSE
    request_id: str = Field(
        ...,
        description="ID of the command this is responding to",
    )
    data: Dict[str, Any] = Field(
        default_factory=dict,
        description="Response data",
    )


class MessageData(BaseMessageData):
    """Data message for sharing information between services."""

    message_type: MessageType = MessageType.DATA
    data: Dict[str, Any] = Field(
        default_factory=dict,
        description="Data payload",
    )


class RegistrationData(BaseMessageData):
    """Registration message sent by services to register with the controller."""

    message_type: MessageType = MessageType.REGISTRATION
    state: str = Field(
        default=ServiceState.READY.value,
        description="Current state of the service",
    )


class CreditData(BaseMessageData):
    """Credit message sent by the timing manager to authorize a request."""

    message_type: MessageType = MessageType.CREDIT.value
    credit: Dict[str, Any] = Field(
        ...,
        description="Credit data",
    )


class ResultData(BaseMessageData):
    """Result message sent by workers to report results."""

    message_type: MessageType = MessageType.DATA.value  # Using DATA type for results
    result: Dict[str, Any] = Field(
        ...,
        description="Result data",
    )

MessageDataUnion = Union[CommandData, HeartbeatData, StatusData, MessageData, CreditData, ResultData]
