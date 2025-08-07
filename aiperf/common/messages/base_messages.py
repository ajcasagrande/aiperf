# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
import time
from functools import lru_cache
from typing import ClassVar

import orjson
from pydantic import Field, field_serializer

from aiperf.common.aiperf_logger import AIPerfLogger
from aiperf.common.enums.message_enums import MessageType
from aiperf.common.models.base_models import AIPerfBaseModel, exclude_if_none
from aiperf.common.models.error_models import ErrorDetails
from aiperf.common.types import MessageTypeT

_logger = AIPerfLogger(__name__)

# Cache for JSON serialized message types for faster lookups
_MESSAGE_TYPE_CACHE: dict[str, MessageTypeT] = {}


@exclude_if_none("request_ns", "request_id")
class Message(AIPerfBaseModel):
    """Base message class for optimized message handling. Based on the AIPerfBaseModel class,
    so it supports @exclude_if_none decorator. see :class:`AIPerfBaseModel` for more details.

    This class provides a base for all messages, including common fields like message_type,
    request_ns, and request_id. It also supports optional field exclusion based on the
    @exclude_if_none decorator.

    Each message model should inherit from this class, set the message_type field,
    and define its own additional fields.

    Example:
    ```python
    @exclude_if_none("some_field")
    class ExampleMessage(Message):
        some_field: int | None = Field(default=None)
        other_field: int = Field(default=1)
    ```
    """

    _message_type_lookup: ClassVar[dict[MessageTypeT, type["Message"]]] = {}
    """Lookup table for message types to their corresponding message classes. This is used to automatically
    deserialize messages from JSON strings to their corresponding class type."""

    # Cache for JSON bytes to avoid repeated encoding
    _json_cache: ClassVar[dict[int, bytes]] = {}
    _cache_size_limit: ClassVar[int] = 10000

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        if hasattr(cls, "message_type") and cls.message_type is not None:
            # Store concrete message classes in the lookup table
            cls._message_type_lookup[cls.message_type] = cls
            # Cache string representation for faster lookups
            _MESSAGE_TYPE_CACHE[str(cls.message_type)] = cls.message_type
            _logger.trace(f"Added {cls.message_type} to message type lookup")

    message_type: MessageTypeT = Field(
        ...,
        description="The type of the message. Must be set in the subclass.",
    )

    request_ns: int | None = Field(
        default=None,
        description="Timestamp of the request",
    )

    request_id: str | None = Field(
        default=None,
        description="ID of the request",
    )

    @field_serializer("message_type")
    def _serialize_message_type(self, value: MessageTypeT) -> str:
        """Optimized message type serialization."""
        return str(value)

    @classmethod
    @lru_cache(maxsize=1000)
    def _get_message_class(cls, message_type: MessageTypeT) -> type["Message"]:
        """Cached lookup for message classes to avoid repeated dictionary access."""
        message_class = cls._message_type_lookup.get(message_type)
        if not message_class:
            raise ValueError(f"Unknown message type: {message_type}")
        return message_class

    @classmethod
    def from_json(cls, json_str: str | bytes | bytearray) -> "Message":
        """Deserialize a message from a JSON string, attempting to auto-detect the message type.

        Optimized version with:
        - Faster JSON parsing with orjson
        - Cached message type lookups
        - Direct model construction
        """
        try:
            # orjson.loads is much faster than json.loads
            data = orjson.loads(json_str)
        except orjson.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in message: {e}") from e

        message_type = data.get("message_type")
        if not message_type:
            raise ValueError("Missing message_type field")

        # Use cached lookup for better performance
        message_class = cls._get_message_class(message_type)

        # Use model_construct for better performance (skips validation)
        # This is safe since we're deserializing trusted internal messages
        return message_class.model_construct(**data)

    @classmethod
    def from_json_with_type(
        cls, message_type: MessageTypeT, json_str: str | bytes | bytearray
    ) -> "Message":
        """Deserialize a message from a JSON string with a specific message type.

        Optimized version that skips message type detection when already known.
        """
        try:
            data = orjson.loads(json_str)
        except orjson.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in message: {e}") from e

        # Use cached lookup
        message_class = cls._get_message_class(message_type)
        return message_class.model_construct(**data)

    def model_dump_json_fast(self) -> bytes:
        """Ultra-fast JSON serialization using orjson directly.

        Returns bytes instead of string for better performance in network operations.
        Uses object hashing for caching identical messages.
        """
        # Create a hash key based on model content
        hash_key = hash(self)

        # Check cache first
        if hash_key in self._json_cache:
            return self._json_cache[hash_key]

        # Use Pydantic's model_dump with mode='json' to ensure JSON-serializable data
        model_data = self.model_dump(mode="json")

        # Serialize using orjson (faster than Pydantic's JSON encoder)
        json_bytes = orjson.dumps(
            model_data, option=orjson.OPT_SERIALIZE_NUMPY | orjson.OPT_OMIT_MICROSECONDS
        )

        # Cache result (with size limit to prevent memory issues)
        if len(self._json_cache) < self._cache_size_limit:
            self._json_cache[hash_key] = json_bytes

        return json_bytes

    def model_dump_json(self, **kwargs) -> str:
        """Standard JSON serialization that returns string.

        For maximum performance, use model_dump_json_fast() instead.
        """
        if kwargs:
            # If custom kwargs are provided, use Pydantic's serializer
            return super().model_dump_json(**kwargs)

        # Otherwise use our optimized version
        return self.model_dump_json_fast().decode("utf-8")

    def __str__(self) -> str:
        return self.model_dump_json()

    def __hash__(self) -> int:
        """Optimized hash for caching purposes."""
        try:
            # Create hash from message type and key fields for better cache performance
            model_data = self.model_dump()

            # Convert to hashable representation
            hashable_items = []
            for k, v in sorted(model_data.items()):
                if isinstance(v, (dict, list)):
                    # Convert complex types to string representation
                    hashable_items.append((k, str(v)))
                else:
                    hashable_items.append((k, v))

            return hash(
                (
                    str(self.message_type),
                    self.request_id,
                    self.request_ns,
                    tuple(hashable_items),
                )
            )
        except Exception:
            # Fallback: use object id if hashing fails
            return hash(id(self))

    @classmethod
    def clear_cache(cls) -> None:
        """Clear the JSON serialization cache."""
        cls._json_cache.clear()
        cls._get_message_class.cache_clear()


class RequiresRequestNSMixin(Message):
    """Mixin for messages that require a request_ns field."""

    request_ns: int = Field(  # type: ignore[assignment]
        default_factory=time.time_ns,
        description="Timestamp of the request in nanoseconds",
    )


class ErrorMessage(Message):
    """Message containing error data."""

    message_type: MessageTypeT = MessageType.ERROR

    error: ErrorDetails = Field(..., description="Error information")
