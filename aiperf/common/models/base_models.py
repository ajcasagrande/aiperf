"""Base Pydantic models used across the application."""

from typing import Any, Dict, Optional, TypeVar

from pydantic import BaseModel, Field


class BasePayload(BaseModel):
    """Base model for all payload data."""


PayloadT = TypeVar("PayloadT", bound=BasePayload)


class RequestResponseBasePayload(BasePayload):
    """Base payload for request-response patterns."""

    transaction_id: Optional[str] = Field(
        default=None,
        description="Optional transaction ID for tracking request-response flows",
    )


class DataPayload(BasePayload):
    """Base model for data payloads with metadata."""

    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Optional metadata for the payload",
    )
