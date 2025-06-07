# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

import sys
import time
from datetime import datetime, timezone
from typing import Any, Generic

from pydantic import BaseModel, Field

from aiperf.common.constants import NANOS_PER_SECOND
from aiperf.common.enums import RequestTimerKind
from aiperf.common.types import ResponseT

################################################################################
# Backend Client Models
################################################################################


class BaseBackendClientConfig(BaseModel):
    """Base configuration options for all backend clients."""

    ...


class GenericHTTPBackendClientConfig(BaseBackendClientConfig):
    """Configuration options for a generic HTTP backend client."""

    url: str = Field(
        default="localhost:8080", description="The URL of the backend client."
    )
    protocol: str = Field(
        default="http", description="The protocol to use for the backend client."
    )
    ssl_options: dict[str, Any] | None = Field(
        default=None,
        description="The SSL options to use for the backend client.",
    )
    timeout_ms: int = Field(
        default=5000,
        description="The timeout in milliseconds for the backend client.",
    )
    headers: dict[str, str] = Field(
        default_factory=dict,
        description="The headers to use for the backend client.",
    )
    api_key: str | None = Field(
        default=None,
        description="The API key to use for the backend client.",
    )


class BackendClientResponse(BaseModel, Generic[ResponseT]):
    """Response from a backend client."""

    timestamp_ns: int = Field(
        ...,
        description="The timestamp of the response in nanoseconds since the epoch.",
    )
    response: ResponseT | None = None


class BackendClientErrorRecord(BaseModel):
    """Error response from a backend client."""

    timestamp_ns: int = Field(
        ...,
        description="The timestamp of the response in nanoseconds since the epoch.",
    )
    error: str = Field(
        ...,
        description="The error message.",
    )


################################################################################
# Inference Data Models
################################################################################


class InferResult(BaseModel):
    """Result of an inference request."""

    id: str
    model_name: str
    model_version: str | None = None
    outputs: dict[str, Any] = Field(default_factory=dict)
    client_id: int | None = None
    request_id: int | None = None
    raw_response: Any | None = None


class InferInput(BaseModel):
    """Input for an inference request."""

    name: str
    shape: list[int] | None = None
    datatype: str | None = None
    data: Any | None = None


class InferRequestOptions(BaseModel):
    """Options for an inference request."""

    sequence_id: int | None = None
    sequence_start: bool = False
    sequence_end: bool = False
    priority: int | None = None
    timeout_ms: int | None = None
    headers: dict[str, str] = Field(default_factory=dict)


################################################################################
# Worker Internal Models
################################################################################


class BaseRequestRecord(BaseModel):
    """Base record of a request."""

    ...


class RequestErrorRecord(BaseRequestRecord):
    """Record of a request error."""

    error: str = Field(
        ...,
        description="The error message.",
    )


class RequestRecord(BaseRequestRecord, Generic[ResponseT]):
    """Record of a request."""

    start_time_ns: int = Field(
        default_factory=time.time_ns,
        description="The start time of the request in nanoseconds since the epoch.",
    )
    responses: list[BackendClientResponse[ResponseT]] = Field(
        default_factory=list,
        description="The responses received from the request.",
    )
    has_null_last_response: bool = Field(
        default=False, description="Whether the last response received was null."
    )
    sequence_end: bool = Field(
        default=False, description="Whether the sequence has ended."
    )
    delayed: bool = Field(default=False, description="Whether the request was delayed.")

    @property
    def valid(self) -> bool:
        """Check if the request record is valid by ensuring that the start time
        and response timestamps are within valid ranges.

        Returns:
            bool: True if the record is valid, False otherwise.
        """
        return (
            0 < self.start_time_ns < sys.maxsize
            and len(self.responses) > 0
            and all(
                0 < response.timestamp_ns < sys.maxsize for response in self.responses
            )
        )

    @property
    def start_time_(self) -> datetime:
        """Get start time as a datetime object."""

        return datetime.fromtimestamp(
            self.start_time_ns / NANOS_PER_SECOND, tz=timezone.utc
        )

    @property
    def response_timestamps_(self):
        """Get response timestamps as datetime objects."""

        return [
            datetime.fromtimestamp(
                response.timestamp_ns / NANOS_PER_SECOND, tz=timezone.utc
            )
            for response in self.responses
        ]

    @property
    def time_to_first_response_ns(self) -> int:
        """Get the time to the first response in nanoseconds."""
        if not self.valid:
            return sys.maxsize
        return self.responses[0].timestamp_ns - self.start_time_ns

    @property
    def time_to_last_response_ns(self) -> int:
        """Get the time to the last response in nanoseconds."""
        if not self.valid:
            return sys.maxsize
        return self.responses[-1].timestamp_ns - self.start_time_ns


class RequestTimers:
    """Records timestamps for different stages of request handling."""

    def __init__(self):
        """Initialize timer with zeroed timestamps."""
        self.timestamps: dict[RequestTimerKind, int] = {}
        self.reset()

    def reset(self) -> None:
        """Reset all timestamp values to zero. Must be called before re-using the timer."""
        self.timestamps = {}

    def timestamp(self, kind: RequestTimerKind) -> int:
        """Get the timestamp, in nanoseconds, for a kind.

        Args:
            kind: The timestamp kind.

        Returns:
            The timestamp in nanoseconds.
        """
        return self.timestamps[kind]

    def capture_timestamp(self, kind: RequestTimerKind) -> int:
        """Set a timestamp to the current time, in nanoseconds.

        Args:
            kind: The timestamp kind.

        Returns:
            The timestamp in nanoseconds.
        """
        ts = time.perf_counter_ns()
        self.timestamps[kind] = ts
        return ts

    def duration(self, start: RequestTimerKind, end: RequestTimerKind) -> int:
        """Return the duration between start time point and end timepoint in nanoseconds.

        Args:
            start: The start time point.
            end: The end time point.

        Returns:
            Duration in nanoseconds, or sys.maxsize to indicate that duration
            could not be calculated.
        """
        start_time = self.timestamps[start]
        end_time = self.timestamps[end]

        # If the start or end timestamp is 0 then can't calculate the
        # duration, so return max to indicate error.
        if start_time == 0 or end_time == 0:
            return sys.maxsize

        return sys.maxsize if start_time > end_time else end_time - start_time
