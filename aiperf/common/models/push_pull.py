"""Pydantic models for push-pull patterns used in communication."""

import time
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field

from aiperf.common.models.base_models import BasePayload


class PushPullData(BaseModel):
    """Base model for push data."""

    source: str = Field(
        ...,
        description="ID of the source sending the data",
    )
    topic: str = Field(
        ...,
        description="Topic to which the data is being sent",
    )
    timestamp: float = Field(
        default_factory=time.time,
        description="Time when the data was created",
    )
    data: Any = Field(
        ...,
        description="Data payload as a dictionary (for backward compatibility)",
    )
    payload: Optional[BasePayload] = Field(
        default=None,
        description="Structured data payload (Pydantic model)",
    )
