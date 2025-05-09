"""Pydantic models for push-pull patterns used in communication."""

import time
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field

from aiperf.common.models.base_models import BasePayload


class PushData(BaseModel):
    """Base model for push data."""

    source: str = Field(
        ...,
        description="ID of the source sending the data",
    )
    timestamp: float = Field(
        default_factory=time.time,
        description="Time when the data was created",
    )
    data: Dict[str, Any] = Field(
        default_factory=dict,
        description="Data payload as a dictionary (for backward compatibility)",
    )
    payload: Optional[BasePayload] = Field(
        default=None,
        description="Structured data payload (Pydantic model)",
    )


class PullData(BaseModel):
    """Base model for pull data."""

    source: str = Field(
        ...,
        description="ID of the source of the data",
    )
    timestamp: float = Field(
        default_factory=time.time,
        description="Time when the data was received",
    )
    data: Dict[str, Any] = Field(
        default_factory=dict,
        description="Data payload as a dictionary (for backward compatibility)",
    )
    payload: Optional[BasePayload] = Field(
        default=None,
        description="Structured data payload (Pydantic model)",
    )
