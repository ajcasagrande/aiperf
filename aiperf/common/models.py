# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

import sys
import time
import uuid
from datetime import datetime
from typing import Any, Generic, Literal, Union

from pydantic import BaseModel, Field

from aiperf.common.enums import (
    CommandType,
    MessageType,
    RequestTimerKind,
    ServiceRegistrationStatus,
    ServiceState,
    ServiceType,
)
from aiperf.common.types import ResponseT

__all__ = [
    "ZMQTCPTransportConfig",
    "ZMQCommunicationConfig",
    "BasePayload",
    "ErrorPayload",
    "DataPayload",
    "StatusPayload",
    "HeartbeatPayload",
    "RegistrationPayload",
    "CommandPayload",
    "CreditDropPayload",
    "CreditReturnPayload",
    "Message",
    "ServiceRunInfo",
    "Payload",
    "BaseMessage",
    "DataMessage",
    "HeartbeatMessage",
    "RegistrationMessage",
    "StatusMessage",
    "CommandMessage",
    "CreditDropMessage",
    "CreditReturnMessage",
    "ErrorMessage",
    "Message",
    "InferResult",
    "InferInput",
    "InferRequestOptions",
    "RequestRecord",
    "RequestTimers",
    "GenericHTTPBackendClientConfig",
    "BackendClientResponse",
    "BaseBackendClientConfig",
]

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

    # Note: Literal[MessageType.UNKNOWN] is required due to the way the
    # discriminator is implemented in Pydantic, it requires everything to be a
    # literal.
    message_type: Literal[MessageType.UNKNOWN] = Field(
        ...,
        description="Type of message this payload represents",
    )


class ErrorPayload(BasePayload):
    """Exception payload sent by services to report an error."""

    message_type: Literal[MessageType.ERROR] = MessageType.ERROR

    error_code: str | None = Field(
        default=None,
        description="Exception code",
    )
    error_message: str | None = Field(
        default=None,
        description="Exception message",
    )
    error_details: dict[str, Any] | None = Field(
        default=None,
        description="Additional details about the error",
    )


class DataPayload(BasePayload):
    """Base model for data payloads with metadata."""

    message_type: Literal[MessageType.DATA] = MessageType.DATA


class StatusPayload(BasePayload):
    """Status payload sent by services to report their current state."""

    message_type: Literal[MessageType.STATUS] = MessageType.STATUS

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

    message_type: Literal[MessageType.HEARTBEAT] = MessageType.HEARTBEAT

    state: ServiceState = ServiceState.RUNNING


class RegistrationPayload(StatusPayload):
    """Registration payload sent by services to register themselves."""

    message_type: Literal[MessageType.REGISTRATION] = MessageType.REGISTRATION

    state: ServiceState = ServiceState.READY


class CommandPayload(BasePayload):
    """Command payload sent to services to request an action."""

    message_type: Literal[MessageType.COMMAND] = MessageType.COMMAND

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

    message_type: Literal[MessageType.CREDIT_DROP] = MessageType.CREDIT_DROP

    amount: int = Field(
        ...,
        description="Amount of credits to drop",
    )
    timestamp: int = Field(
        default_factory=time.time_ns, description="Timestamp of the credit drop"
    )


class CreditReturnPayload(BasePayload):
    """Credit return payload sent to services to request a credit return."""

    message_type: Literal[MessageType.CREDIT_RETURN] = MessageType.CREDIT_RETURN

    amount: int = Field(
        ...,
        description="Amount of credits to return",
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
    ErrorPayload,
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

    payload: DataPayload


class HeartbeatMessage(BaseMessage):
    """Message containing heartbeat data."""

    payload: HeartbeatPayload


class RegistrationMessage(BaseMessage):
    """Message containing registration data."""

    payload: RegistrationPayload


class StatusMessage(BaseMessage):
    """Message containing status data."""

    payload: StatusPayload


class CommandMessage(BaseMessage):
    """Message containing command data."""

    payload: CommandPayload


class CreditDropMessage(BaseMessage):
    """Message indicating that a credit has been dropped."""

    payload: CreditDropPayload


class CreditReturnMessage(BaseMessage):
    """Message indicating that a credit has been returned."""

    payload: CreditReturnPayload


class ErrorMessage(BaseMessage):
    """Message containing error data."""

    payload: ErrorPayload


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


class RequestRecord(BaseModel, Generic[ResponseT]):
    """Record of a request."""

    start_time_ns: int = Field(
        default_factory=time.time_ns,
        description="The start time of the request in nanoseconds since the epoch.",
    )
    response_timestamps_ns: list[int] = Field(
        default_factory=list,
        description="The timestamps of each response in nanoseconds since the epoch.",
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
            and len(self.response_timestamps_ns) > 0
            and all(0 < ts < sys.maxsize for ts in self.response_timestamps_ns)
        )

    @property
    def start_time_(self) -> datetime:
        """Get start time as a datetime object."""
        from datetime import datetime, timezone

        return datetime.fromtimestamp(self.start_time_ns / 1e9, tz=timezone.utc)

    @property
    def response_timestamps_(self):
        """Get response timestamps as datetime objects."""
        from datetime import datetime, timezone

        return [
            datetime.fromtimestamp(ts / 1e9, tz=timezone.utc)
            for ts in self.response_timestamps_ns
        ]

    @property
    def time_to_first_response_ns(self) -> int:
        """Get the time to the first response in nanoseconds."""
        if not self.valid:
            return sys.maxsize
        return self.response_timestamps_ns[0] - self.start_time_ns

    @property
    def time_to_last_response_ns(self) -> int:
        """Get the time to the last response in nanoseconds."""
        if not self.valid:
            return sys.maxsize
        return self.response_timestamps_ns[-1] - self.start_time_ns


class RequestTimers:
    """Records timestamps for different stages of request handling."""

    def __init__(self):
        """Initialize timer with zeroed timestamps."""
        self.timestamps: list[int] = [0] * len(RequestTimerKind)
        self.reset()

    def reset(self) -> None:
        """Reset all timestamp values to zero. Must be called before re-using the timer."""
        self.timestamps = [0] * len(RequestTimerKind)

    def timestamp(self, kind: RequestTimerKind) -> int:
        """Get the timestamp, in nanoseconds, for a kind.

        Args:
            kind: The timestamp kind.

        Returns:
            The timestamp in nanoseconds.
        """
        return self.timestamps[kind.value - 1]

    def capture_timestamp(self, kind: RequestTimerKind) -> int:
        """Set a timestamp to the current time, in nanoseconds.

        Args:
            kind: The timestamp kind.

        Returns:
            The timestamp in nanoseconds.
        """
        ts = time.time_ns()
        self.timestamps[kind.value - 1] = ts
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
        stime = self.timestamps[start.value - 1]
        etime = self.timestamps[end.value - 1]

        # If the start or end timestamp is 0 then can't calculate the
        # duration, so return max to indicate error.
        if stime == 0 or etime == 0:
            return sys.maxsize

        return sys.maxsize if stime > etime else etime - stime
