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
"""Pydantic models for request-response patterns used in communication."""

import time
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field

from aiperf.common.enums import PayloadType
from aiperf.common.models.base_models import RequestResponseBasePayload


class BaseRequestPayload(RequestResponseBasePayload):
    """Base model for all request payload data."""

    # Request-specific fields can be added here


class BaseResponsePayload(RequestResponseBasePayload):
    """Base model for all response payload data."""

    status: str = Field(
        default="ok",
        description="Status of the response (ok, error, etc.)",
    )
    message: Optional[str] = Field(
        default=None,
        description="Optional message providing more details about the response",
    )


class RequestData(BaseModel):
    """Base model for request data."""

    request_id: str = Field(
        ...,
        description="Unique identifier for this request",
    )
    client_id: str = Field(
        ...,
        description="ID of the client making the request",
    )
    timestamp: float = Field(
        default_factory=time.time,
        description="Time when the request was created",
    )
    data: Dict[str, Any] = Field(
        default_factory=dict,
        description="Request payload as a dictionary (for backward compatibility)",
    )
    target: Optional[str] = Field(
        default=None,
        description="Target component to send request to",
    )
    payload: Optional[BaseRequestPayload] = Field(
        default=None,
        description="Structured request payload (Pydantic model)",
    )


class ResponseData(BaseModel):
    """Base model for response data."""

    request_id: str = Field(
        ...,
        description="ID of the request this is responding to",
    )
    client_id: str = Field(
        ...,
        description="ID of the client sending the response",
    )
    timestamp: float = Field(
        default_factory=time.time,
        description="Time when the response was created",
    )
    data: Dict[str, Any] = Field(
        default_factory=dict,
        description="Response payload as a dictionary (for backward compatibility)",
    )
    target: Optional[str] = Field(
        default=None,
        description="Target client to send response to",
    )
    status: str = Field(
        default="ok",
        description="Status of the response (ok or error)",
    )
    message: Optional[str] = Field(
        default=None,
        description="Error message if status is error",
    )
    payload: Optional[BaseResponsePayload] = Field(
        default=None,
        description="Structured response payload (Pydantic model)",
    )


class RequestStateInfo(BaseModel):
    """Model for request state information."""

    pending_requests: list[str] = Field(
        default_factory=list,
        description="List of pending request IDs",
    )
    pending_request_count: int = Field(
        default=0,
        description="Number of pending requests",
    )
    client_count: int = Field(
        default=0,
        description="Number of clients",
    )
    subscription_count: int = Field(
        default=0,
        description="Number of active subscriptions",
    )
    response_topics: list[str] = Field(
        default_factory=list,
        description="List of response topics",
    )
    response_subscribers: Dict[str, list[str]] = Field(
        default_factory=dict,
        description="Dict of subscribers by response topic",
    )
    client_ids: list[str] = Field(
        default_factory=list,
        description="List of client IDs",
    )
    error: Optional[str] = Field(
        default=None,
        description="Error message if there was an error getting state info",
    )


class WorkerRequestPayload(BaseRequestPayload):
    """Specific request payload for worker requests."""

    payload_type: PayloadType = PayloadType.WORKER_REQUEST
    operation: str = Field(
        ...,
        description="The operation to perform",
    )
    parameters: Dict[str, Any] = Field(
        default_factory=dict,
        description="Operation parameters",
    )
