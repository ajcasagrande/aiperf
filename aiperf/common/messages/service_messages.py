# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0


from pydantic import Field

from aiperf.common.enums import ServiceState, ServiceType
from aiperf.common.enums.message_enums import MessageType
from aiperf.common.messages.message import Message
from aiperf.common.types import MessageTypeT


class BaseServiceMessage(Message):
    """Base message that is sent from a service. Requires a service_id field to specify
    the service that sent the message."""

    service_id: str = Field(
        ...,
        description="ID of the service sending the message",
    )


class BaseStatusMessage(BaseServiceMessage):
    """Base message containing status data.
    This message is sent by a service to the system controller to report its status.
    """

    state: ServiceState = Field(
        ...,
        description="Current state of the service",
    )


class StatusMessage(BaseStatusMessage):
    """Message containing status data.
    This message is sent by a service to the system controller to report its status.
    """

    message_type: MessageTypeT = MessageType.STATUS


class RegistrationMessage(BaseStatusMessage):
    """Message containing registration data.
    This message is sent by a service to the system controller to register itself.
    """

    message_type: MessageTypeT = MessageType.REGISTRATION

    service_type: ServiceType | str = Field(
        ...,
        description="Type of service",
    )


class HeartbeatMessage(BaseStatusMessage):
    """Message containing heartbeat data.
    This message is sent by a service to the system controller to indicate that it is
    still running.
    """

    message_type: MessageTypeT = MessageType.HEARTBEAT
