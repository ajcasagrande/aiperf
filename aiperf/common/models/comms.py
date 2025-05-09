from typing import Optional

from pydantic import BaseModel, Field


class ZMQCommunicationConfig(BaseModel):
    """Configuration for ZMQ communication."""

    pub_address: str = Field(
        default="tcp://127.0.0.1:5555", description="Address for publishing messages"
    )
    sub_address: str = Field(
        default="tcp://127.0.0.1:5555",
        description="Address for subscribing to messages",
    )
    req_address: str = Field(
        default="tcp://127.0.0.1:5556", description="Address for sending requests"
    )
    rep_address: str = Field(
        default="tcp://127.0.0.1:5556",
        description="Address for receiving requests and sending responses",
    )
    push_address: str = Field(
        default="tcp://127.0.0.1:5557", description="Address for pushing data"
    )
    pull_address: str = Field(
        default="tcp://127.0.0.1:5557", description="Address for pulling data"
    )
    client_id: Optional[str] = Field(
        default=None, description="Client ID, will be generated if not provided"
    )
