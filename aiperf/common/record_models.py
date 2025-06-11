# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

import os
import sys
import time
from typing import Any, Generic

from pydantic import BaseModel, Field

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
        default=f"http://localhost:{os.getenv('AIPERF_PORT', 8080)}",
        description="The URL of the backend client.",
    )
    protocol: str = Field(
        default="http", description="The protocol to use for the backend client."
    )
    ssl_options: dict[str, Any] | None = Field(
        default=None,
        description="The SSL options to use for the backend client.",
    )
    timeout_ms: int = Field(
        default=300000,
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


class BackendClientErrorResponse(BackendClientResponse[None]):
    """Error response from a backend client."""

    error: str = Field(
        ...,
        description="The error message.",
    )


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

# TODO: Maybe a RecordType like a MessageType for discriminated unions?


class BaseRequestRecord(BaseModel):
    """Base record of a request."""

    start_perf_counter_ns: int = Field(
        default_factory=time.perf_counter_ns,
        description="The start time of the request in nanoseconds since the epoch.",
    )


class RequestErrorRecord(BaseRequestRecord):
    """Record of a request error."""

    error: str = Field(
        ...,
        description="The error message.",
    )


class RequestRecord(BaseRequestRecord, Generic[ResponseT]):
    """Record of a request."""

    responses: list[BackendClientResponse[ResponseT] | BackendClientErrorResponse] = (
        Field(
            default_factory=list,
            description="The raw responses received from the request.",
        )
    )
    sequence_end: bool = Field(
        default=True, description="Whether the sequence has ended."
    )
    delayed: bool = Field(default=False, description="Whether the request was delayed.")

    @property
    def has_null_last_response(self) -> bool:
        """Whether the last response received was null."""
        return len(self.responses) > 0 and self.responses[-1].response is None

    @property
    def has_error(self) -> bool:
        """Check if the request record has an error."""
        return any(
            isinstance(response, BackendClientErrorResponse)
            for response in self.responses
        )

    @property
    def valid(self) -> bool:
        """Check if the request record is valid by ensuring that the start time
        and response timestamps are within valid ranges.

        Returns:
            bool: True if the record is valid, False otherwise.
        """
        return not self.has_error and (
            0 <= self.start_perf_counter_ns < sys.maxsize
            and len(self.responses) > 0
            and all(
                0 < response.timestamp_ns < sys.maxsize for response in self.responses
            )
        )

    @property
    def time_to_first_response_ns(self) -> int | None:
        """Get the time to the first response in nanoseconds."""
        if not self.valid:
            return None
        return self.responses[0].timestamp_ns - self.start_perf_counter_ns

    @property
    def time_to_second_response_ns(self) -> int | None:
        """Get the time to the second response in nanoseconds."""
        if not self.valid or len(self.responses) < 2:
            return None
        return self.responses[1].timestamp_ns - self.responses[0].timestamp_ns

    @property
    def time_to_last_response_ns(self) -> int | None:
        """Get the time to the last response in nanoseconds."""
        if not self.valid:
            return None
        return self.responses[-1].timestamp_ns - self.start_perf_counter_ns

    @property
    def inter_token_latency_ns(self) -> float | None:
        """Get the interval between responses in nanoseconds."""
        if not self.valid:
            return None
        return (self.responses[-1].timestamp_ns - self.responses[0].timestamp_ns) / (
            len(self.responses) - 1
        )
