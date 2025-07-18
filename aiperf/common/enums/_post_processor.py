# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

from aiperf.common.enums._base import CaseInsensitiveStrEnum


class PostProcessorType(CaseInsensitiveStrEnum):
    """Type of post processor."""

    METRIC_SUMMARY = "metric_summary"


class ResponseStreamerType(CaseInsensitiveStrEnum):
    """Type of response streamer."""

    PROCESSING_STATS = "processing_stats"
    BASIC_METRICS = "basic_metrics"
