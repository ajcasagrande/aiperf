"""Pydantic models for message structures used in inter-service communication."""

import uuid
from typing import Optional
from typing import TypeVar

from pydantic import BaseModel, Field

from aiperf.common.enums import ServiceType
from aiperf.common.models.message_data import MessageDataUnion, DISCRIMINATOR

# # Generic type for data payloads
# DataT = TypeVar("DataT")


class BaseMessage(BaseModel):#, Generic[DataT]):
    """Base message model with common fields for all messages."""

    id: str = Field(
        default_factory=lambda: uuid.uuid4().hex,
        description="Unique identifier for this message",
    )
    service_id: str = Field(
        ...,
        description="ID of the service sending the message",
    )
    service_type: ServiceType = Field(
        ...,
        description="Type of service sending the message",
    )
    # data: DataT = Field(
    #     ...,
    #     description="Data payload of the message",
    # )
    data: Optional[MessageDataUnion] = Field(discriminator=DISCRIMINATOR)
    error: Optional[str] = Field(
        default=None,
        description="Error message if any",
    )

    def is_error(self) -> bool:
        """Check if the message contains an error."""
        return self.error is not None


class RegistrationResponseMessage(BaseModel):
    """Response to a registration request."""

    status: str = Field(
        ...,
        description="Status of the registration (ok or error)",
    )
    error: Optional[str] = Field(
        default=None,
        description="Error message if registration failed",
    )
