#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
"""
Pydantic models for aiperf_streaming package.

These models provide Python-native interfaces to the Rust streaming HTTP client
with proper data validation and serialization.
"""

import statistics
from collections.abc import Sequence
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, computed_field


class HttpMethod(str, Enum):
    """HTTP methods supported by the streaming client."""

    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    DELETE = "DELETE"
    PATCH = "PATCH"
    HEAD = "HEAD"


class StreamingTokenChunkModel(BaseModel):
    """Pydantic model for streaming tokens representing SSE data payloads."""

    data: str = Field(..., description="Token data content from SSE payload")
    size_bytes: int = Field(..., description="Size of token in bytes")
    token_index: int = Field(..., description="Index of this token in the stream")

    @computed_field
    @property
    def size_kb(self) -> float:
        """Size in kilobytes."""
        return self.size_bytes / 1024.0

    @computed_field
    @property
    def data_preview(self) -> str:
        """Preview of token data (first 50 characters)."""
        return self.data[:50] + ("..." if len(self.data) > 50 else "")

    class Config:
        frozen = True


class StreamingRequestModel(BaseModel):
    """Pydantic model for streaming HTTP requests."""

    request_id: str = Field(..., description="Unique request identifier")
    url: str = Field(..., description="Request URL")
    method: HttpMethod = Field(HttpMethod.GET, description="HTTP method")
    headers: dict[str, str] = Field(default_factory=dict, description="Request headers")
    body: str | None = Field(None, description="Request body")
    start_time_ns: int = Field(..., description="Request start time in nanoseconds")
    end_time_ns: int | None = Field(None, description="Request end time in nanoseconds")
    tokens: list[StreamingTokenChunkModel] = Field(
        default_factory=list, description="Response tokens"
    )
    total_bytes: int = Field(0, description="Total bytes received")
    token_count: int = Field(0, description="Number of tokens received")
    timeout_ms: int | None = Field(None, description="Request timeout in milliseconds")

    @computed_field
    @property
    def start_time_dt(self) -> datetime:
        """Start time as datetime object."""
        return datetime.fromtimestamp(self.start_time_ns / 1e9, tz=timezone.utc)

    @computed_field
    @property
    def end_time_dt(self) -> datetime | None:
        """End time as datetime object."""
        if self.end_time_ns is None:
            return None
        return datetime.fromtimestamp(self.end_time_ns / 1e9, tz=timezone.utc)

    @computed_field
    @property
    def duration_ns(self) -> int | None:
        """Request duration in nanoseconds."""
        if self.end_time_ns is None:
            return None
        return self.end_time_ns - self.start_time_ns

    @computed_field
    @property
    def duration_ms(self) -> float | None:
        """Request duration in milliseconds."""
        if self.duration_ns is None:
            return None
        return self.duration_ns / 1e6

    @computed_field
    @property
    def throughput_bps(self) -> float | None:
        """Throughput in bytes per second."""
        if self.duration_ns is None or self.duration_ns == 0:
            return None
        return self.total_bytes / (self.duration_ns / 1e9)

    @computed_field
    @property
    def throughput_mbps(self) -> float | None:
        """Throughput in megabytes per second."""
        if self.throughput_bps is None:
            return None
        return self.throughput_bps / (1024 * 1024)


class StreamingStatsModel(BaseModel):
    """Pydantic model for streaming statistics."""

    total_requests: int = Field(0, description="Total number of requests")
    total_bytes: int = Field(0, description="Total bytes transferred")
    avg_token_size: float = Field(0.0, description="Average token size")
    avg_throughput_bps: float = Field(
        0.0, description="Average throughput in bytes/sec"
    )
    total_duration_ns: int = Field(0, description="Total duration in nanoseconds")

    @computed_field
    @property
    def total_duration_ms(self) -> float:
        """Total duration in milliseconds."""
        return self.total_duration_ns / 1e6

    @computed_field
    @property
    def avg_throughput_mbps(self) -> float:
        """Average throughput in megabytes per second."""
        return self.avg_throughput_bps / (1024 * 1024)

    @computed_field
    @property
    def total_size_mb(self) -> float:
        """Total size in megabytes."""
        return self.total_bytes / (1024 * 1024)


class TimingAnalysis(BaseModel):
    """Advanced timing analysis for streaming requests."""

    requests: list[StreamingRequestModel]

    @computed_field
    @property
    def token_stats(self) -> dict[str, Any]:
        """Statistics about streaming tokens."""
        all_token_sizes = []
        all_token_counts = []

        for req in self.requests:
            all_token_counts.append(req.token_count)
            for token in req.tokens:
                all_token_sizes.append(token.size_bytes)

        if not all_token_sizes:
            return {"token_count": 0, "total_requests": len(self.requests)}

        return {
            "token_count": len(all_token_sizes),
            "total_requests": len(self.requests),
            "avg_tokens_per_request": statistics.mean(all_token_counts)
            if all_token_counts
            else 0,
            "min_tokens_per_request": min(all_token_counts) if all_token_counts else 0,
            "max_tokens_per_request": max(all_token_counts) if all_token_counts else 0,
            "mean_token_size": statistics.mean(all_token_sizes),
            "median_token_size": statistics.median(all_token_sizes),
            "min_token_size": min(all_token_sizes),
            "max_token_size": max(all_token_sizes),
            "stdev_token_size": statistics.stdev(all_token_sizes)
            if len(all_token_sizes) > 1
            else 0,
        }

    @computed_field
    @property
    def request_duration_stats(self) -> dict[str, Any]:
        """Statistics about request durations."""
        durations = [
            req.duration_ns for req in self.requests if req.duration_ns is not None
        ]

        if not durations:
            return {}

        return {
            "count": len(durations),
            "mean_ns": statistics.mean(durations),
            "median_ns": statistics.median(durations),
            "min_ns": min(durations),
            "max_ns": max(durations),
            "stdev_ns": statistics.stdev(durations) if len(durations) > 1 else 0,
            "p95_ns": self._percentile(durations, 95),
            "p99_ns": self._percentile(durations, 99),
        }

    @computed_field
    @property
    def throughput_stats(self) -> dict[str, Any]:
        """Statistics about throughput."""
        throughputs = [
            req.throughput_bps
            for req in self.requests
            if req.throughput_bps is not None
        ]

        if not throughputs:
            return {}

        return {
            "count": len(throughputs),
            "mean_bps": statistics.mean(throughputs),
            "median_bps": statistics.median(throughputs),
            "min_bps": min(throughputs),
            "max_bps": max(throughputs),
            "stdev_bps": statistics.stdev(throughputs) if len(throughputs) > 1 else 0,
            "p95_bps": self._percentile(throughputs, 95),
            "p99_bps": self._percentile(throughputs, 99),
        }

    @staticmethod
    def _percentile(data: Sequence[int | float], percentile: float) -> float:
        """Calculate percentile of data."""
        sorted_data = sorted(float(x) for x in data)
        k = (len(sorted_data) - 1) * (percentile / 100)
        f = int(k)
        c = k - f
        if f + 1 < len(sorted_data):
            return sorted_data[f] * (1 - c) + sorted_data[f + 1] * c
        else:
            return sorted_data[f]
