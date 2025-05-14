#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#  http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
"""Pydantic models for message structures used in inter-service communication."""

import time
import uuid
from typing import Optional

from pydantic import BaseModel, Field

from aiperf.common.models.payloads import PayloadType, RequestPayload, ResponsePayload


class BaseMessage(BaseModel):
    """Base message model with common fields for all messages.
    The payload can be any of the payload types defined by .
    """

    service_id: Optional[str] = Field(
        default=None,
        description="ID of the service sending the message",
    )
    timestamp: int = Field(
        default_factory=time.time_ns,
        description="Time when the message was created",
    )
    request_id: Optional[str] = Field(
        default=None,
        description="ID of the request",
    )
    payload: PayloadType = Field(
        default=None,
        discriminator="message_type",
        description="Payload of the message",
    )


class BaseRequestMessage(BaseMessage):
    """Base request message model with common fields for all request messages.
    The payload must override the RequestPayload type.
    """

    message_type: RequestPayload = Field(
        default=None,
        description="Type of the message",
    )
    request_id: str = Field(
        default_factory=lambda: uuid.uuid4().hex[:8],
        description="ID of the request",
    )
    payload: RequestPayload = Field(
        default=None,
        discriminator="message_type",
        description="Payload of the message",
    )


class BaseResponseMessage(BaseMessage):
    """Base response message model with common fields for all response messages.
    The payload must override the ResponsePayload type.
    """

    message_type: ResponsePayload = Field(
        default=None,
        description="Type of the message",
    )

    request_id: str = Field(
        description="ID of the request",
    )
    payload: ResponsePayload = Field(
        default=None,
        discriminator="message_type",
        description="Payload of the message",
    )
