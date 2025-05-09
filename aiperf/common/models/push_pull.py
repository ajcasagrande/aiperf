"""Pydantic models for push-pull patterns used in communication."""

import time
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


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
        description="Data payload",
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
        description="Data payload",
    )
