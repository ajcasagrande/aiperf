"""Pydantic models for request-response patterns used in communication."""

import time
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


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
        description="Request payload",
    )
    target: Optional[str] = Field(
        default=None,
        description="Target component to send request to",
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
        description="Response payload",
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
