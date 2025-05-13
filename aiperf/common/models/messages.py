"""Pydantic models for message structures used in inter-service communication."""

import time
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Union, TypeVar, Generic

from pydantic import BaseModel, Field

from aiperf.common.enums import CommandType, MessageType, ServiceState, PayloadType
from aiperf.common.models.base_models import BasePayload, PayloadT, DataPayload


class BaseMessage(BaseModel, Generic[PayloadT]):
    """Base message model with common fields for all messages."""

    service_id: Optional[str] = Field(
        default=None,
        description="ID of the service sending the message",
    )
    service_type: Optional[str] = Field(
        default=None,
        description="Type of service sending the message",
    )
    timestamp: int = Field(
        default_factory=time.time_ns,
        description="Time when the message was created",
    )
    payload: Optional[PayloadT] = Field(
        default=None,
        description="Overloaded Payload of the message",
    )


MessageT = TypeVar("MessageT", bound=BaseMessage)


class StatusMessage(BaseMessage):
    """Status message sent by services to report their state."""

    state: ServiceState = Field(
        ...,
        description="Current state of the service",
    )


class HeartbeatMessage(StatusMessage):
    """Heartbeat message sent periodically by services."""

    state: ServiceState = ServiceState.RUNNING
    timestamp: datetime = Field(
        default_factory=datetime.now,
        description="Time when the heartbeat was sent",
    )


class RegistrationMessage(StatusMessage):
    """Payload for registration messages."""

    state: ServiceState = Field(
        default=ServiceState.READY,
        description="Current state of the service",
    )


class CommandMessage(BaseMessage):
    """Command message sent to services to request an action."""

    command: CommandType = Field(
        ...,
        description="Command to execute",
    )
    command_id: str = Field(
        default_factory=lambda: uuid.uuid4().hex[:8],
        description="Unique identifier for this command",
    )
    require_response: bool = Field(
        default=False,
        description="Whether a response is required for this command",
    )
    target_service_id: Optional[str] = Field(
        default=None,
        description="ID of the target service for this command",
    )


class ResponsePayload(BasePayload):
    """Structured payload for response messages."""

    payload_type: PayloadType = PayloadType.RESPONSE
    status: str = Field(
        default="ok",
        description="Status of the response (ok, error, etc.)",
    )
    message: Optional[str] = Field(
        default=None,
        description="Optional message providing more details about the response",
    )
    data: Dict[str, Any] = Field(
        default_factory=dict,
        description="Any additional data accompanying the response",
    )


ResponseT = TypeVar("ResponseT", bound=ResponsePayload)


class ResponseMessage(BaseMessage):
    """Response message sent in reply to a command."""

    response: ResponseT = Field(
        default_factory=ResponsePayload,
        description="Response payload data",
    )


class DataMessage(BaseMessage):
    """Data message for sharing information between services."""

    message_type: MessageType = MessageType.DATA
    payload: DataPayload = Field(
        ...,
        description="Structured data payload",
    )


class RegistrationResponseMessage(BaseModel):
    """Response to a registration request."""

    status: str = Field(
        ...,
        description="Status of the registration (ok or error)",
    )
    error: Optional[str] = Field(
        default=None,
        description="Error message if registration failed",
    )


class CreditData(BasePayload):
    """Structured model for credit information."""

    payload_type: PayloadType = PayloadType.CREDIT
    credit_id: str = Field(
        ...,
        description="Unique identifier for this credit",
    )
    request_count: int = Field(
        default=1,
        description="Number of requests authorized by this credit",
    )
    expiry_time: Optional[float] = Field(
        default=None,
        description="Time when this credit expires (in seconds since epoch)",
    )
    parameters: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional parameters for this credit",
    )


class CreditMessage(BaseMessage):
    """Credit message sent by the timing manager to authorize a request."""

    message_type: MessageType = MessageType.CREDIT
    credit: CreditData = Field(
        ...,
        description="Credit data",
    )


class ConversationTurn(BaseModel):
    """Model representing a single turn in a conversation."""

    role: str = Field(
        ...,
        description="Role of the speaker (user, assistant, system, etc.)",
    )
    content: str = Field(
        ...,
        description="Content of the message",
    )
    timestamp: float = Field(
        default_factory=time.time,
        description="Time when the message was created",
    )


class ConversationData(DataPayload):
    """Model for conversation data."""

    payload_type: PayloadType = PayloadType.CONVERSATION
    conversation_id: str = Field(
        ...,
        description="Unique identifier for this conversation",
    )
    turns: List[ConversationTurn] = Field(
        default_factory=list,
        description="List of conversation turns",
    )


class ResultData(DataPayload):
    """Structured model for result information."""

    payload_type: PayloadType = PayloadType.RESULT
    result_id: str = Field(
        ...,
        description="Unique identifier for this result",
    )
    metrics: Dict[str, Union[float, int, str]] = Field(
        default_factory=dict,
        description="Performance metrics for this result",
    )
    tags: List[str] = Field(
        default_factory=list,
        description="Tags associated with this result",
    )


class ResultMessage(BaseMessage):
    """Result message sent by workers to report results."""

    message_type: MessageType = MessageType.DATA  # Using DATA type for results
    result: ResultData = Field(
        ...,
        description="Result data",
    )
