# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

import sys
import time
import uuid
from datetime import datetime
from typing import Any, Generic, Literal, Union

from pydantic import BaseModel, Field

from aiperf.common.constants import NANOS_PER_SECOND
from aiperf.common.enums import (
    CommandType,
    MessageType,
    RequestTimerKind,
    ServiceRegistrationStatus,
    ServiceState,
    ServiceType,
)
from aiperf.common.types import ResponseT

################################################################################
# ZMQ Configuration Models
################################################################################


class ZMQTCPTransportConfig(BaseModel):
    """Configuration for TCP transport."""

    host: str = Field(
        default="0.0.0.0",
        description="Host address for TCP connections",
    )
    controller_pub_sub_port: int = Field(
        default=5555, description="Port for controller pub/sub messages"
    )
    component_pub_sub_port: int = Field(
        default=5556, description="Port for component pub/sub messages"
    )
    inference_push_pull_port: int = Field(
        default=5557, description="Port for inference push/pull messages"
    )
    req_rep_port: int = Field(
        default=5558, description="Port for sending and receiving requests"
    )
    push_pull_port: int = Field(
        default=5559, description="Port for pushing and pulling data"
    )
    records_port: int = Field(default=5560, description="Port for record data")
    conversation_data_port: int = Field(
        default=5561, description="Port for conversation data"
    )
    credit_drop_port: int = Field(
        default=5562, description="Port for credit drop operations"
    )
    credit_return_port: int = Field(
        default=5563, description="Port for credit return operations"
    )


class ZMQCommunicationConfig(BaseModel):
    """Configuration for ZMQ communication."""

    protocol_config: ZMQTCPTransportConfig = Field(
        default_factory=ZMQTCPTransportConfig,
        description="Configuration for the selected transport protocol",
    )
    client_id: str | None = Field(
        default=None, description="Client ID, will be generated if not provided"
    )

    @property
    def controller_pub_sub_address(self) -> str:
        """Get the controller pub/sub address based on protocol configuration."""
        return f"tcp://{self.protocol_config.host}:{self.protocol_config.controller_pub_sub_port}"

    @property
    def component_pub_sub_address(self) -> str:
        """Get the component pub/sub address based on protocol configuration."""
        return f"tcp://{self.protocol_config.host}:{self.protocol_config.component_pub_sub_port}"

    @property
    def inference_push_pull_address(self) -> str:
        """Get the inference push/pull address based on protocol configuration."""
        return f"tcp://{self.protocol_config.host}:{self.protocol_config.inference_push_pull_port}"

    @property
    def records_address(self) -> str:
        """Get the records address based on protocol configuration."""
        return f"tcp://{self.protocol_config.host}:{self.protocol_config.records_port}"

    @property
    def conversation_data_address(self) -> str:
        """Get the conversation data address based on protocol configuration."""
        return f"tcp://{self.protocol_config.host}:{self.protocol_config.conversation_data_port}"

    @property
    def credit_drop_address(self) -> str:
        """Get the credit drop address based on protocol configuration."""
        return (
            f"tcp://{self.protocol_config.host}:{self.protocol_config.credit_drop_port}"
        )

    @property
    def credit_return_address(self) -> str:
        """Get the credit return address based on protocol configuration."""
        return f"tcp://{self.protocol_config.host}:{self.protocol_config.credit_return_port}"


################################################################################
# Payload Models
################################################################################


class BasePayload(BaseModel):
    """Base model for all payload data. Each payload type must inherit
    from this class, and override the `message_type` field.

    This is used with Pydantic's `discriminator` to allow for polymorphic payloads,
    and automatic type coercion when receiving messages.
    """

    message_type: MessageType = Field(
        ...,
        description="Type of message this payload represents",
    )


class ErrorPayload(BasePayload):
    """Exception payload sent by services to report an error."""

    message_type: Literal[MessageType.ERROR] = MessageType.ERROR  # type: ignore

    error: str = Field(..., description="Exception message")


class DataPayload(BasePayload):
    """Base model for data payloads with metadata."""

    message_type: Literal[MessageType.DATA] = MessageType.DATA  # type: ignore


class StatusPayload(BasePayload):
    """Status payload sent by services to report their current state."""

    message_type: Literal[MessageType.STATUS] = MessageType.STATUS  # type: ignore

    state: ServiceState = Field(
        ...,
        description="Current state of the service",
    )
    service_type: ServiceType = Field(
        ...,
        description="Type of service",
    )


class HeartbeatPayload(StatusPayload):
    """Heartbeat payload sent periodically by services."""

    message_type: Literal[MessageType.HEARTBEAT] = MessageType.HEARTBEAT  # type: ignore

    state: ServiceState = ServiceState.RUNNING


class RegistrationPayload(StatusPayload):
    """Registration payload sent by services to register themselves."""

    message_type: Literal[MessageType.REGISTRATION] = MessageType.REGISTRATION  # type: ignore

    state: ServiceState = ServiceState.READY


class CommandPayload(BasePayload):
    """Command payload sent to services to request an action."""

    message_type: Literal[MessageType.COMMAND] = MessageType.COMMAND  # type: ignore

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
    target_service_id: str | None = Field(
        default=None,
        description="ID of the target service for this command",
    )
    data: BaseModel | None = Field(
        default=None,
        description="Data to send with the command",
    )


class CreditDropPayload(BasePayload):
    """Credit drop payload sent to services to request a credit drop."""

    message_type: Literal[MessageType.CREDIT_DROP] = MessageType.CREDIT_DROP  # type: ignore

    amount: int = Field(
        ...,
        description="Amount of credits to drop",
    )
    timestamp: int = Field(
        default_factory=time.time_ns, description="Timestamp of the credit drop"
    )


class CreditReturnPayload(BasePayload):
    """Credit return payload sent to services to request a credit return."""

    message_type: Literal[MessageType.CREDIT_RETURN] = MessageType.CREDIT_RETURN  # type: ignore

    amount: int = Field(
        ...,
        description="Amount of credits to return",
    )


class CreditsCompletePayload(BasePayload):
    """Credits complete payload sent to System controller to signify all requests have completed."""

    message_type: Literal[MessageType.CREDITS_COMPLETE] = MessageType.CREDITS_COMPLETE  # type: ignore


class ConversationRequestPayload(BasePayload):
    """Request payload sent to services to request a conversation."""

    message_type: Literal[MessageType.CONVERSATION_REQUEST] = (  # type: ignore
        MessageType.CONVERSATION_REQUEST
    )
    conversation_id: str = Field(..., description="The ID of the conversation")


class ConversationResponsePayload(BasePayload):
    """Response payload sent to services to respond to a conversation request."""

    message_type: Literal[MessageType.CONVERSATION_RESPONSE] = (  # type: ignore
        MessageType.CONVERSATION_RESPONSE
    )
    conversation_id: str = Field(..., description="The ID of the conversation")
    conversation_data: list[dict[str, Any]] = Field(
        ..., description="The data of the conversation"
    )


class InferenceResultsPayload(BasePayload):
    """Payload for a inference results."""

    message_type: Literal[MessageType.INFERENCE_RESULTS] = MessageType.INFERENCE_RESULTS  # type: ignore
    record: "RequestErrorRecord | RequestRecord" = Field(
        ..., description="The inference results record"
    )


# Only put concrete payload types here, with unique message_type values,
# otherwise the discriminator will complain.
Payload = Union[  # noqa: UP007
    DataPayload,
    HeartbeatPayload,
    RegistrationPayload,
    StatusPayload,
    CommandPayload,
    CreditDropPayload,
    CreditReturnPayload,
    CreditsCompletePayload,
    ErrorPayload,
    ConversationRequestPayload,
    ConversationResponsePayload,
    InferenceResultsPayload,
]
"""This is a union of all the payload types that can be sent and received.

This is used with Pydantic's `discriminator` to allow for polymorphic payloads,
and automatic type coercion when receiving messages.
"""


################################################################################
# Message Models
################################################################################


class BaseMessage(BaseModel):
    """Base message model with common fields for all messages.
    The payload can be any of the payload types defined by the payloads.py module.

    The message type is determined by the discriminator field `message_type`. This is
    used by the Pydantic `discriminator` argument to determine the type of the
    payload automatically when the message is deserialized from a JSON string.

    To serialize a message to a JSON string, use the `model_dump_json` method.
    To deserialize a message from a JSON string, use the `model_validate_json`
    method.

    Example:
    ```python
    >>> message = BaseMessage(
    ...     service_id="service_1",
    ...     request_id="request_1",
    ...     payload=DataPayload(data="Hello, world!"),
    ... )
    >>> json_string = message.model_dump_json()
    >>> print(json_string)
    {"payload": {"data": "Hello, world!"}, "service_id": "service_1", "request_id": "request_1"}
    >>> deserialized_message = BaseMessage.model_validate_json(json_string)
    >>> print(deserialized_message)
    BaseMessage(
        payload=DataPayload(data="Hello, world!"),
        service_id="service_1",
        request_id="request_1",
        timestamp=1716278400000000000,
    )
    >>> print(deserialized_message.payload.data)
    Hello, world!
    ```
    """

    service_id: str | None = Field(
        default=None,
        description="ID of the service sending the response",
    )
    timestamp: int = Field(
        default_factory=time.time_ns,
        description="Time when the response was created",
    )
    request_id: str | None = Field(
        default=None,
        description="ID of the request",
    )
    payload: Payload = Field(
        ...,
        discriminator="message_type",
        description="Payload of the response",
    )


class DataMessage(BaseMessage):
    """Message containing data."""

    payload: DataPayload  # type: ignore


class HeartbeatMessage(BaseMessage):
    """Message containing heartbeat data."""

    payload: HeartbeatPayload  # type: ignore


class RegistrationMessage(BaseMessage):
    """Message containing registration data."""

    payload: RegistrationPayload  # type: ignore


class StatusMessage(BaseMessage):
    """Message containing status data."""

    payload: StatusPayload  # type: ignore


class CommandMessage(BaseMessage):
    """Message containing command data."""

    payload: CommandPayload  # type: ignore


class CreditDropMessage(BaseMessage):
    """Message indicating that a credit has been dropped."""

    payload: CreditDropPayload  # type: ignore


class CreditReturnMessage(BaseMessage):
    """Message indicating that a credit has been returned."""

    payload: CreditReturnPayload  # type: ignore


class ErrorMessage(BaseMessage):
    """Message containing error data."""

    payload: ErrorPayload  # type: ignore


class ConversationRequestMessage(BaseMessage):
    """Message containing conversation request data."""

    payload: ConversationRequestPayload  # type: ignore


class ConversationResponseMessage(BaseMessage):
    """Message containing conversation response data."""

    payload: ConversationResponsePayload  # type: ignore


class CreditsCompleteMessage(BaseMessage):
    """Message containing credits complete data."""

    payload: CreditsCompletePayload  # type: ignore


Message = Union[  # noqa: UP007
    BaseMessage,
    DataMessage,
    HeartbeatMessage,
    RegistrationMessage,
    StatusMessage,
    CommandMessage,
    CreditDropMessage,
    CreditReturnMessage,
    ErrorMessage,
    ConversationRequestMessage,
    ConversationResponseMessage,
    CreditsCompleteMessage,
]
"""Union of all message types. This is used as a type hint when a function
accepts a message as an argument.

Example:
```python
>>> def process_message(message: Message) -> None:
...     if isinstance(message, DataMessage):
...         print(message.payload.data)
...     elif isinstance(message, HeartbeatMessage):
...         print(message.payload.state)
```
"""


################################################################################
# Service Models
################################################################################


class ServiceRunInfo(BaseModel):
    """Base model for tracking service run information."""

    service_type: ServiceType = Field(
        ...,
        description="The type of service",
    )
    registration_status: ServiceRegistrationStatus = Field(
        ...,
        description="The registration status of the service",
    )
    service_id: str = Field(
        ...,
        description="The ID of the service",
    )
    first_seen: int | None = Field(
        default_factory=time.time_ns,
        description="The first time the service was seen",
    )
    last_seen: int | None = Field(
        default_factory=time.time_ns,
        description="The last time the service was seen",
    )
    state: ServiceState = Field(
        default=ServiceState.UNKNOWN,
        description="The current state of the service",
    )


################################################################################
# Backend Client Models
################################################################################


class BaseBackendClientConfig(BaseModel):
    """Base configuration options for all backend clients."""

    ...


class GenericHTTPBackendClientConfig(BaseBackendClientConfig):
    """Configuration options for a generic HTTP backend client."""

    url: str = Field(
        default="localhost:8000", description="The URL of the backend client."
    )
    protocol: str = Field(
        default="http", description="The protocol to use for the backend client."
    )
    ssl_options: dict[str, Any] | None = Field(
        default=None,
        description="The SSL options to use for the backend client.",
    )
    timeout_ms: int = Field(
        default=5000,
        description="The timeout in milliseconds for the backend client.",
    )
    headers: dict[str, str] = Field(
        default_factory=dict,
        description="The headers to use for the backend client.",
    )
    api_key: str | None = Field(
        default=None,
        description="The API key to use for the backend client.",
    )


class BackendClientResponse(BaseModel, Generic[ResponseT]):
    """Response from a backend client."""

    timestamp_ns: int = Field(
        ...,
        description="The timestamp of the response in nanoseconds since the epoch.",
    )
    response: ResponseT
    error: str | None = None


################################################################################
# Inference Data Models
################################################################################


class InferResult(BaseModel):
    """Result of an inference request."""

    id: str
    model_name: str
    model_version: str | None = None
    outputs: dict[str, Any] = Field(default_factory=dict)
    client_id: int | None = None
    request_id: int | None = None
    raw_response: Any | None = None


class InferInput(BaseModel):
    """Input for an inference request."""

    name: str
    shape: list[int] | None = None
    datatype: str | None = None
    data: Any | None = None


class InferRequestOptions(BaseModel):
    """Options for an inference request."""

    sequence_id: int | None = None
    sequence_start: bool = False
    sequence_end: bool = False
    priority: int | None = None
    timeout_ms: int | None = None
    headers: dict[str, str] = Field(default_factory=dict)


################################################################################
# Worker Internal Models
################################################################################


class BaseRequestRecord(BaseModel):
    """Base record of a request."""

    pass


class RequestErrorRecord(BaseRequestRecord):
    """Record of a request error."""

    error: str = Field(
        ...,
        description="The error message.",
    )


class RequestRecord(BaseRequestRecord, Generic[ResponseT]):
    """Record of a request."""

    start_time_ns: int = Field(
        default_factory=time.time_ns,
        description="The start time of the request in nanoseconds since the epoch.",
    )
    responses: list[BackendClientResponse[ResponseT]] = Field(
        default_factory=list,
        description="The responses received from the request.",
    )
    has_null_last_response: bool = Field(
        default=False, description="Whether the last response received was null."
    )
    sequence_end: bool = Field(
        default=False, description="Whether the sequence has ended."
    )
    delayed: bool = Field(default=False, description="Whether the request was delayed.")

    @property
    def valid(self) -> bool:
        """Check if the request record is valid by ensuring that the start time
        and response timestamps are within valid ranges.

        Returns:
            bool: True if the record is valid, False otherwise.
        """
        return (
            0 < self.start_time_ns < sys.maxsize
            and len(self.responses) > 0
            and all(
                0 < response.timestamp_ns < sys.maxsize for response in self.responses
            )
        )

    @property
    def start_time_(self) -> datetime:
        """Get start time as a datetime object."""
        from datetime import datetime, timezone

        return datetime.fromtimestamp(
            self.start_time_ns / NANOS_PER_SECOND, tz=timezone.utc
        )

    @property
    def response_timestamps_(self):
        """Get response timestamps as datetime objects."""
        from datetime import datetime, timezone

        return [
            datetime.fromtimestamp(
                response.timestamp_ns / NANOS_PER_SECOND, tz=timezone.utc
            )
            for response in self.responses
        ]

    @property
    def time_to_first_response_ns(self) -> int:
        """Get the time to the first response in nanoseconds."""
        if not self.valid:
            return sys.maxsize
        return self.responses[0].timestamp_ns - self.start_time_ns

    @property
    def time_to_last_response_ns(self) -> int:
        """Get the time to the last response in nanoseconds."""
        if not self.valid:
            return sys.maxsize
        return self.responses[-1].timestamp_ns - self.start_time_ns


class RequestTimers:
    """Records timestamps for different stages of request handling."""

    def __init__(self):
        """Initialize timer with zeroed timestamps."""
        self.timestamps: dict[RequestTimerKind, int] = {}
        self.reset()

    def reset(self) -> None:
        """Reset all timestamp values to zero. Must be called before re-using the timer."""
        self.timestamps = {}

    def timestamp(self, kind: RequestTimerKind) -> int:
        """Get the timestamp, in nanoseconds, for a kind.

        Args:
            kind: The timestamp kind.

        Returns:
            The timestamp in nanoseconds.
        """
        return self.timestamps[kind]

    def capture_timestamp(self, kind: RequestTimerKind) -> int:
        """Set a timestamp to the current time, in nanoseconds.

        Args:
            kind: The timestamp kind.

        Returns:
            The timestamp in nanoseconds.
        """
        ts = time.perf_counter_ns()
        self.timestamps[kind] = ts
        return ts

    def duration(self, start: RequestTimerKind, end: RequestTimerKind) -> int:
        """Return the duration between start time point and end timepoint in nanoseconds.

        Args:
            start: The start time point.
            end: The end time point.

        Returns:
            Duration in nanoseconds, or sys.maxsize to indicate that duration
            could not be calculated.
        """
        start_time = self.timestamps[start]
        end_time = self.timestamps[end]

        # If the start or end timestamp is 0 then can't calculate the
        # duration, so return max to indicate error.
        if start_time == 0 or end_time == 0:
            return sys.maxsize

        return sys.maxsize if start_time > end_time else end_time - start_time
