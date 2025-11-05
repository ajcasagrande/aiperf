# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Constants specific to server metrics collection."""

from aiperf.common.enums.metric_enums import (
    GenericMetricUnit,
    MetricSizeUnit,
    MetricTimeUnit,
    MetricUnitT,
)

# Unit conversion scaling factors
SCALING_FACTORS = {
    # Add any scaling factors needed here
    # For now, most Prometheus metrics are already in the correct units
}

# Prometheus metric mapping to server metrics record fields
# Maps common Prometheus metric names to ServerMetrics model fields
PROMETHEUS_TO_FIELD_MAPPING = {
    # Generic Request metrics
    "http_requests_total": "requests_total",
    "http_request_duration_seconds": "request_duration_seconds",
    "http_requests_in_flight": "requests_in_flight",
    # Generic Response metrics
    "http_response_size_bytes": "response_size_bytes",
    # Generic CPU metrics
    "process_cpu_usage_percent": "cpu_usage_percent",
    "process_cpu_seconds": "process_cpu_seconds",
    "cpu_system_seconds": "cpu_system_seconds",
    "cpu_user_seconds": "cpu_user_seconds",
    # Generic Memory metrics
    "process_resident_memory_bytes": "process_resident_memory_bytes",
    "process_virtual_memory_bytes": "process_virtual_memory_bytes",
    "memory_usage_bytes": "memory_usage_bytes",
    "memory_total_bytes": "memory_total_bytes",
    # Generic Process metrics
    "process_open_fds": "process_open_fds",
    # Generic Network metrics
    "network_receive_bytes": "network_receive_bytes",
    "network_transmit_bytes": "network_transmit_bytes",
    # Generic HTTP status codes
    "http_responses_2xx": "http_2xx_total",
    "http_responses_4xx": "http_4xx_total",
    "http_responses_5xx": "http_5xx_total",
    # Dynamo Backend Component Metrics
    "dynamo_component_inflight_requests": "component_inflight_requests",
    "dynamo_component_request_bytes": "component_request_bytes_total",
    "dynamo_component_request_duration_seconds": "component_request_duration_seconds",
    "dynamo_component_requests": "component_requests_total",
    "dynamo_component_response_bytes": "component_response_bytes_total",
    "dynamo_component_system_uptime_seconds": "component_system_uptime_seconds",
    # Dynamo KV Router Statistics
    "dynamo_component_kvstats_active_blocks": "kvstats_active_blocks",
    "dynamo_component_kvstats_total_blocks": "kvstats_total_blocks",
    "dynamo_component_kvstats_gpu_cache_usage_percent": "kvstats_gpu_cache_usage_percent",
    "dynamo_component_kvstats_gpu_prefix_cache_hit_rate": "kvstats_gpu_prefix_cache_hit_rate",
    # Dynamo Frontend Metrics
    "dynamo_frontend_inflight_requests": "frontend_inflight_requests",
    "dynamo_frontend_queued_requests": "frontend_queued_requests",
    "dynamo_frontend_input_sequence_tokens": "frontend_input_sequence_tokens",
    "dynamo_frontend_inter_token_latency_seconds": "frontend_inter_token_latency_seconds",
    "dynamo_frontend_output_sequence_tokens": "frontend_output_sequence_tokens",
    "dynamo_frontend_request_duration_seconds": "frontend_request_duration_seconds",
    "dynamo_frontend_requests": "frontend_requests_total",
    "dynamo_frontend_time_to_first_token_seconds": "frontend_time_to_first_token_seconds",
    # Dynamo Model Configuration Metrics
    "dynamo_frontend_model_total_kv_blocks": "model_total_kv_blocks",
    "dynamo_frontend_model_max_num_seqs": "model_max_num_seqs",
    "dynamo_frontend_model_max_num_batched_tokens": "model_max_num_batched_tokens",
    "dynamo_frontend_model_context_length": "model_context_length",
    "dynamo_frontend_model_kv_cache_block_size": "model_kv_cache_block_size",
    "dynamo_frontend_model_migration_limit": "model_migration_limit",
    "dynamo_frontend_model_workers": "model_workers",
}

# Server Metrics Configuration
# Format: (display_name, field_name, unit_enum)
# - display_name: Human-readable metric name shown in outputs
# - field_name: Corresponds to ServerMetrics model field name
# - unit_enum: MetricUnitT enum (use .value in exporters to get string)
SERVER_METRICS_CONFIG: list[tuple[str, str, MetricUnitT]] = [
    # Generic Request metrics
    ("Requests Total", "requests_total", GenericMetricUnit.COUNT),
    ("Requests In Flight", "requests_in_flight", GenericMetricUnit.COUNT),
    ("Request Duration", "request_duration_seconds", MetricTimeUnit.SECONDS),
    # Generic Response metrics
    ("Response Size", "response_size_bytes", MetricSizeUnit.BYTES),
    # Generic CPU metrics
    ("CPU Usage", "cpu_usage_percent", GenericMetricUnit.PERCENT),
    ("CPU System Time", "cpu_system_seconds", MetricTimeUnit.SECONDS),
    ("CPU User Time", "cpu_user_seconds", MetricTimeUnit.SECONDS),
    ("Process CPU Time", "process_cpu_seconds", MetricTimeUnit.SECONDS),
    # Generic Memory metrics
    ("Memory Usage", "memory_usage_bytes", MetricSizeUnit.BYTES),
    ("Memory Total", "memory_total_bytes", MetricSizeUnit.BYTES),
    ("Process Resident Memory", "process_resident_memory_bytes", MetricSizeUnit.BYTES),
    ("Process Virtual Memory", "process_virtual_memory_bytes", MetricSizeUnit.BYTES),
    # Generic Process metrics
    ("Open File Descriptors", "process_open_fds", GenericMetricUnit.COUNT),
    # Generic Network metrics
    ("Network Received", "network_receive_bytes", MetricSizeUnit.BYTES),
    ("Network Transmitted", "network_transmit_bytes", MetricSizeUnit.BYTES),
    # Generic HTTP status codes
    ("HTTP 2xx Responses", "http_2xx_total", GenericMetricUnit.COUNT),
    ("HTTP 4xx Responses", "http_4xx_total", GenericMetricUnit.COUNT),
    ("HTTP 5xx Responses", "http_5xx_total", GenericMetricUnit.COUNT),
    # Dynamo Backend Component Metrics
    (
        "Component Inflight Requests",
        "component_inflight_requests",
        GenericMetricUnit.COUNT,
    ),
    ("Component Request Bytes", "component_request_bytes_total", MetricSizeUnit.BYTES),
    (
        "Component Request Duration",
        "component_request_duration_seconds",
        MetricTimeUnit.SECONDS,
    ),
    ("Component Requests Total", "component_requests_total", GenericMetricUnit.COUNT),
    (
        "Component Response Bytes",
        "component_response_bytes_total",
        MetricSizeUnit.BYTES,
    ),
    (
        "Component System Uptime",
        "component_system_uptime_seconds",
        MetricTimeUnit.SECONDS,
    ),
    # Dynamo KV Router Statistics
    ("KV Active Blocks", "kvstats_active_blocks", GenericMetricUnit.COUNT),
    ("KV Total Blocks", "kvstats_total_blocks", GenericMetricUnit.COUNT),
    (
        "KV GPU Cache Usage",
        "kvstats_gpu_cache_usage_percent",
        GenericMetricUnit.PERCENT,
    ),
    (
        "KV GPU Prefix Cache Hit Rate",
        "kvstats_gpu_prefix_cache_hit_rate",
        GenericMetricUnit.PERCENT,
    ),
    # Dynamo Frontend Metrics
    (
        "Frontend Inflight Requests",
        "frontend_inflight_requests",
        GenericMetricUnit.COUNT,
    ),
    ("Frontend Queued Requests", "frontend_queued_requests", GenericMetricUnit.COUNT),
    (
        "Frontend Input Sequence Tokens",
        "frontend_input_sequence_tokens",
        GenericMetricUnit.COUNT,
    ),
    (
        "Frontend Inter Token Latency",
        "frontend_inter_token_latency_seconds",
        MetricTimeUnit.SECONDS,
    ),
    (
        "Frontend Output Sequence Tokens",
        "frontend_output_sequence_tokens",
        GenericMetricUnit.COUNT,
    ),
    (
        "Frontend Request Duration",
        "frontend_request_duration_seconds",
        MetricTimeUnit.SECONDS,
    ),
    ("Frontend Requests Total", "frontend_requests_total", GenericMetricUnit.COUNT),
    (
        "Frontend Time to First Token",
        "frontend_time_to_first_token_seconds",
        MetricTimeUnit.SECONDS,
    ),
    # Dynamo Model Configuration Metrics
    ("Model Total KV Blocks", "model_total_kv_blocks", GenericMetricUnit.COUNT),
    ("Model Max Sequences", "model_max_num_seqs", GenericMetricUnit.COUNT),
    (
        "Model Max Batched Tokens",
        "model_max_num_batched_tokens",
        GenericMetricUnit.COUNT,
    ),
    ("Model Context Length", "model_context_length", GenericMetricUnit.COUNT),
    ("Model KV Cache Block Size", "model_kv_cache_block_size", GenericMetricUnit.COUNT),
    ("Model Migration Limit", "model_migration_limit", GenericMetricUnit.COUNT),
    ("Model Workers", "model_workers", GenericMetricUnit.COUNT),
]
