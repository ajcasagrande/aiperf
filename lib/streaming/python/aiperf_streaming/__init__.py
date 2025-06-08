#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
"""
High-performance streaming HTTP client for AI performance analysis.

This package provides a Rust-based HTTP client with nanosecond-precision timing
for measuring streaming response performance.
"""

from .aiperf_streaming import (
    PrecisionTimer,
    StreamingChunk,
    StreamingHttpClient,
    StreamingRequest,
    StreamingStats,
)
from .models import (
    StreamingChunkModel,
    StreamingRequestModel,
    StreamingStatsModel,
    TimingAnalysis,
)

__all__ = [
    "StreamingHttpClient",
    "StreamingRequest",
    "StreamingChunk",
    "StreamingStats",
    "PrecisionTimer",
    "StreamingRequestModel",
    "StreamingChunkModel",
    "StreamingStatsModel",
    "TimingAnalysis",
]

__version__ = "0.1.0"
