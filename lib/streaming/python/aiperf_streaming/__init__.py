#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
"""
High-performance streaming HTTP client for AI performance analysis.

This package provides a Rust-based HTTP client with nanosecond-precision timing
for measuring streaming response performance.
"""

from .aiperf_streaming import (
    PrecisionTimer,
    RequestTimers,
    StreamingHttpClient,
    StreamingRequest,
    StreamingStats,
    StreamingToken,
    TimestampKind,
)
from .models import (
    StreamingRequestModel,
    StreamingStatsModel,
    StreamingTokenModel,
    TimingAnalysis,
)

__all__ = [
    "StreamingHttpClient",
    "StreamingRequest",
    "StreamingToken",
    "StreamingStats",
    "PrecisionTimer",
    "RequestTimers",
    "TimestampKind",
    "StreamingRequestModel",
    "StreamingTokenModel",
    "StreamingStatsModel",
    "TimingAnalysis",
]

__version__ = "0.1.0"
