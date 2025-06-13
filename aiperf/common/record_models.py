# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

import os
import sys
import time
from typing import Any, Generic

from pydantic import BaseModel, Field, SerializeAsAny

from aiperf.common.enums import CaseInsensitiveStrEnum
from aiperf.common.types import ResponseT

################################################################################
# Inference Client Models
################################################################################


class BaseClientConfig(BaseModel):
    """Base configuration options for all clients."""

    ...


class GenericHTTPClientConfig(BaseClientConfig):
    """Configuration options for a generic HTTP inference client."""

    url: str = Field(
        default=f"http://localhost:{os.getenv('AIPERF_PORT', 8080)}",
        description="The URL of the inference client.",
    )
    protocol: str = Field(
        default="http", description="The protocol to use for the inference client."
    )
    ssl_options: dict[str, Any] | None = Field(
        default=None,
        description="The SSL options to use for the inference client.",
    )
    timeout_ms: int = Field(
        default=300000,
        description="The timeout in milliseconds for the inference client.",
    )
    headers: dict[str, str] = Field(
        default_factory=dict,
        description="The headers to use for the inference client.",
    )
    api_key: str | None = Field(
        default=None,
        description="The API key to use for the inference client.",
    )


################################################################################
# Inference Client Response Models
################################################################################


class InferenceServerResponse(BaseModel):
    """Response from a inference client."""

    perf_ns: int = Field(
        ...,
        description="The timestamp of the response in nanoseconds (perf_counter_ns).",
    )


class InferenceServerErrorResponse(InferenceServerResponse):
    """Error response from a inference client."""

    error: str = Field(
        ...,
        description="The error message.",
    )


class SSEFieldType(CaseInsensitiveStrEnum):
    """Field types in an SSE message."""

    DATA = "data"
    EVENT = "event"
    ID = "id"
    RETRY = "retry"
    COMMENT = "comment"


class SSEEventType(CaseInsensitiveStrEnum):
    """Event types in an SSE message."""

    ERROR = "error"
    LLM_METRICS = "llm_metrics"


class SSEField(BaseModel):
    """Base model for a single field in an SSE message."""

    name: SSEFieldType | str = Field(
        ...,
        description="The name of the field. e.g. 'data', 'event', 'id', 'retry', 'comment'.",
    )
    value: str | None = Field(
        default=None,
        description="The value of the field.",
    )


class SSEMessage(InferenceServerResponse):
    """Individual SSE message from an SSE stream. Delimited by \n\n."""

    # Note: "fields" is a restricted keyword in pydantic
    packets: list[SSEField] = Field(
        default_factory=list, description="The fields contained in the message."
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

    start_perf_ns: int = Field(
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

    responses: SerializeAsAny[list[InferenceServerResponse]] = Field(
        default_factory=list,
        description="The raw responses received from the request.",
    )
    sequence_end: bool = Field(
        default=True, description="Whether the sequence has ended."
    )
    delayed: bool = Field(default=False, description="Whether the request was delayed.")

    @property
    def has_null_last_response(self) -> bool:
        """Whether the last response received was null."""
        return len(self.responses) > 0 and self.responses[-1] is None

    @property
    def has_error(self) -> bool:
        """Check if the request record has an error."""
        return any(
            isinstance(response, InferenceServerErrorResponse)
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
            0 <= self.start_perf_ns < sys.maxsize
            and len(self.responses) > 0
            and all(0 < response.perf_ns < sys.maxsize for response in self.responses)
        )

    @property
    def time_to_first_response_ns(self) -> int | None:
        """Get the time to the first response in nanoseconds."""
        if not self.valid:
            return None
        return self.responses[0].perf_ns - self.start_perf_ns

    @property
    def time_to_second_response_ns(self) -> int | None:
        """Get the time to the second response in nanoseconds."""
        if not self.valid or len(self.responses) < 2:
            return None
        return self.responses[1].perf_ns - self.responses[0].perf_ns

    @property
    def time_to_last_response_ns(self) -> int | None:
        """Get the time to the last response in nanoseconds."""
        if not self.valid:
            return None
        return self.responses[-1].perf_ns - self.start_perf_ns

    @property
    def inter_token_latency_ns(self) -> float | None:
        """Get the interval between responses in nanoseconds."""
        if not self.valid or len(self.responses) < 2:
            return None
        return (self.responses[-1].perf_ns - self.responses[0].perf_ns) / (
            len(self.responses) - 1
        )
