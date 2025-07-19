# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
import json
import time
import uuid
from typing import ClassVar

from pydantic import Field

from aiperf.common.enums import CommandType, MessageType
from aiperf.common.models import ExcludeIfNoneModel
from aiperf.common.pydantic_utils import exclude_if_none


@exclude_if_none(["request_id"])
class Message(ExcludeIfNoneModel):
    """Base message class for optimized message handling.

    This class provides a base for all messages, including common fields like message_type,
    request_ns, and request_id. It also supports optional field exclusion based on the
    @exclude_if_none decorator.

    Each message model should inherit from this class, set the message_type field,
    and define its own additional fields.
    Optionally, the @exclude_if_none decorator can be used to specify which fields
    should be excluded from the serialized message if they are None.

    Example:
    ```python
    @exclude_if_none(["some_field"])
    class ExampleMessage(Message):
        some_field: int | None = Field(default=None)
        other_field: int = Field(default=1)
    ```
    """

    _exclude_if_none_fields: ClassVar[set[str]] = set()
    """Set of field names that should be excluded from the serialized message if they
    are None. This is set by the @exclude_if_none decorator.
    """

    _message_type_lookup: ClassVar[
        dict[MessageType | CommandType, type["Message"]]
    ] = {}

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        if hasattr(cls, "message_type"):
            cls._message_type_lookup[cls.message_type] = cls

    message_type: ClassVar[MessageType | CommandType] = Field(
        ...,
        description="The type of the message. Must be set in the subclass.",
    )
    """The type of the message. Must be set in the subclass."""

    request_ns: int = Field(
        default_factory=time.time_ns,
        description="Timestamp of the request",
    )

    request_id: str | None = Field(
        default=None,
        description="ID of the request",
    )

    @classmethod
    def __get_validators__(cls):
        yield cls.from_json

    @classmethod
    def from_json(cls, json_str: str | bytes | bytearray) -> "Message":
        data = json.loads(json_str)
        message_type = data.get("message_type")
        if not message_type:
            raise ValueError(f"Missing message_type: {json_str}")

        # Use cached message type lookup
        message_class = cls._message_type_lookup[message_type]
        if not message_class:
            raise ValueError(f"Unknown message type: {message_type}")

        return message_class.model_validate(data)

    @classmethod
    def from_json_with_type(
        cls, message_type: MessageType | CommandType, json_str: str | bytes | bytearray
    ) -> "Message":
        data = json.loads(json_str)
        # Use cached message type lookup
        message_class = cls._message_type_lookup[message_type]
        if not message_class:
            raise ValueError(f"Unknown message type: {message_type}")
        return message_class.model_validate(data)

    def to_json(self) -> str:
        return self.model_dump_json()


class AutoRequestID:
    """Mixin to make request_id field required for a message, with a default value of a random UUID4."""

    request_id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="The ID of the request. If not provided, a random UUID4 will be generated.",
    )


class RequiresRequestID:
    """Mixin to make request_id field required for a message.
    This one does not generate a random UUID4, so it is useful for things like command responses."""

    request_id: str = Field(
        ...,
        description="The ID of the request.",
    )
