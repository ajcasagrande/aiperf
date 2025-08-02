# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

from aiperf.common.enums.base_enums import CaseInsensitiveStrEnum


class PostProcessorType(CaseInsensitiveStrEnum):
    METRIC_SUMMARY = "metric_summary"


class StreamingPostProcessorType(CaseInsensitiveStrEnum):
    """Type of response streamer."""

    PROCESSING_STATS = "processing_stats"
    """Streamer that provides the processing stats of the records."""

    BASIC_METRICS = "basic_metrics"
    """Streamer that handles the basic metrics of the records."""

    JSONL = "jsonl"
    """Streams all parsed records to a JSONL file."""


class StreamingRecordProcessorType(CaseInsensitiveStrEnum):
    """Type of streaming record processor."""

    METRIC_RECORD_STREAMER = "metric_record_streamer"
    """Streamer that streams records and computes metrics from MetricType.RECORD and MetricType.AGGREGATE.
    This is the first stage of the metrics processing pipeline, and is done is a distributed manner across multiple service instances."""


class StreamingResultsProcessorType(CaseInsensitiveStrEnum):
    """Type of streaming results processor."""

    METRIC_RESULTS_STREAMER = "metric_results_streamer"
    """Streamer that streams the metric results from METRIC_RECORD_STREAMER and computes metrics from MetricType.DERIVED.
    This is the last stage of the metrics processing pipeline, and is done from the RecordsManager after all the service instances have completed their processing."""
