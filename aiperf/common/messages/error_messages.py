# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

from pydantic import Field

from aiperf.common.enums import MessageType
from aiperf.common.messages.message import Message
from aiperf.common.messages.service_messages import BaseServiceMessage
from aiperf.common.models import ErrorDetails
from aiperf.common.types import MessageTypeT


class ErrorMessage(Message):
    """Message containing error data."""

    message_type: MessageTypeT = MessageType.ERROR

    error: ErrorDetails = Field(..., description="Error information")


class BaseServiceErrorMessage(BaseServiceMessage):
    """Base message containing error data."""

    message_type: MessageTypeT = MessageType.SERVICE_ERROR

    error: ErrorDetails = Field(..., description="Error information")
