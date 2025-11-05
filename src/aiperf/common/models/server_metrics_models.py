# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

import numpy as np
from pydantic import Field

from aiperf.common.exceptions import NoMetricValue
from aiperf.common.models.base_models import AIPerfBaseModel
from aiperf.common.models.error_models import ErrorDetails, ErrorDetailsCount
from aiperf.common.models.record_models import MetricResult


class ServerMetrics(AIPerfBaseModel):
    """Server metrics collected at a single point in time from Prometheus /metrics endpoint.

    All fields are optional to handle cases where specific metrics are not available
    from the server or are filtered out due to invalid values.

    Includes support for Dynamo inference server metrics (dynamo_component_*, dynamo_frontend_*).
    """

    # Generic Request metrics
    requests_total: float | None = Field(
        default=None, description="Total number of requests processed"
    )
    requests_in_flight: float | None = Field(
        default=None, description="Current number of requests being processed"
    )
    request_duration_seconds: float | None = Field(
        default=None, description="Request duration in seconds"
    )

    # Generic Response metrics
    response_size_bytes: float | None = Field(
        default=None, description="Response size in bytes"
    )

    # Generic CPU metrics
    cpu_usage_percent: float | None = Field(
        default=None, description="CPU usage percentage (0-100)"
    )
    cpu_system_seconds: float | None = Field(
        default=None, description="Cumulative CPU time spent in system mode in seconds"
    )
    cpu_user_seconds: float | None = Field(
        default=None, description="Cumulative CPU time spent in user mode in seconds"
    )

    # Generic Memory metrics
    memory_usage_bytes: float | None = Field(
        default=None, description="Memory usage in bytes"
    )
    memory_total_bytes: float | None = Field(
        default=None, description="Total available memory in bytes"
    )

    # Generic Process metrics
    process_cpu_seconds: float | None = Field(
        default=None, description="Total CPU time consumed by this process in seconds"
    )
    process_resident_memory_bytes: float | None = Field(
        default=None, description="Resident memory size in bytes"
    )
    process_virtual_memory_bytes: float | None = Field(
        default=None, description="Virtual memory size in bytes"
    )
    process_open_fds: float | None = Field(
        default=None, description="Number of open file descriptors"
    )

    # Generic Network metrics
    network_receive_bytes: float | None = Field(
        default=None, description="Cumulative bytes received over network"
    )
    network_transmit_bytes: float | None = Field(
        default=None, description="Cumulative bytes transmitted over network"
    )

    # Generic HTTP status codes
    http_2xx_total: float | None = Field(
        default=None, description="Total number of 2xx HTTP responses"
    )
    http_4xx_total: float | None = Field(
        default=None, description="Total number of 4xx HTTP responses"
    )
    http_5xx_total: float | None = Field(
        default=None, description="Total number of 5xx HTTP responses"
    )

    # Dynamo Backend Component Metrics (dynamo_component_*)
    component_inflight_requests: float | None = Field(
        default=None,
        description="Dynamo component: Requests currently being processed (gauge)",
    )
    component_request_bytes_total: float | None = Field(
        default=None,
        description="Dynamo component: Total bytes received in requests (counter)",
    )
    component_request_duration_seconds: float | None = Field(
        default=None,
        description="Dynamo component: Request processing time (histogram)",
    )
    component_requests_total: float | None = Field(
        default=None, description="Dynamo component: Total requests processed (counter)"
    )
    component_response_bytes_total: float | None = Field(
        default=None,
        description="Dynamo component: Total bytes sent in responses (counter)",
    )
    component_system_uptime_seconds: float | None = Field(
        default=None, description="Dynamo component: DistributedRuntime uptime (gauge)"
    )

    # Dynamo KV Router Statistics (dynamo_component_kvstats_*)
    kvstats_active_blocks: float | None = Field(
        default=None,
        description="Dynamo KV: Number of active KV cache blocks currently in use (gauge)",
    )
    kvstats_total_blocks: float | None = Field(
        default=None,
        description="Dynamo KV: Total number of KV cache blocks available (gauge)",
    )
    kvstats_gpu_cache_usage_percent: float | None = Field(
        default=None,
        description="Dynamo KV: GPU cache usage as a percentage (0.0-1.0) (gauge)",
    )
    kvstats_gpu_prefix_cache_hit_rate: float | None = Field(
        default=None,
        description="Dynamo KV: GPU prefix cache hit rate as a percentage (0.0-1.0) (gauge)",
    )

    # Dynamo Frontend Metrics (dynamo_frontend_*)
    frontend_inflight_requests: float | None = Field(
        default=None, description="Dynamo frontend: Inflight requests (gauge)"
    )
    frontend_queued_requests: float | None = Field(
        default=None,
        description="Dynamo frontend: Number of requests in HTTP processing queue (gauge)",
    )
    frontend_input_sequence_tokens: float | None = Field(
        default=None, description="Dynamo frontend: Input sequence length (histogram)"
    )
    frontend_inter_token_latency_seconds: float | None = Field(
        default=None, description="Dynamo frontend: Inter-token latency (histogram)"
    )
    frontend_output_sequence_tokens: float | None = Field(
        default=None, description="Dynamo frontend: Output sequence length (histogram)"
    )
    frontend_request_duration_seconds: float | None = Field(
        default=None, description="Dynamo frontend: LLM request duration (histogram)"
    )
    frontend_requests_total: float | None = Field(
        default=None, description="Dynamo frontend: Total LLM requests (counter)"
    )
    frontend_time_to_first_token_seconds: float | None = Field(
        default=None, description="Dynamo frontend: Time to first token (histogram)"
    )

    # Dynamo Model Configuration Metrics (dynamo_frontend_model_*)
    # Runtime Config Metrics
    model_total_kv_blocks: float | None = Field(
        default=None,
        description="Dynamo model: Total KV blocks available for a worker serving the model (gauge)",
    )
    model_max_num_seqs: float | None = Field(
        default=None,
        description="Dynamo model: Maximum number of sequences for a worker serving the model (gauge)",
    )
    model_max_num_batched_tokens: float | None = Field(
        default=None,
        description="Dynamo model: Maximum number of batched tokens for a worker serving the model (gauge)",
    )
    # MDC Metrics
    model_context_length: float | None = Field(
        default=None,
        description="Dynamo model: Maximum context length for a worker serving the model (gauge)",
    )
    model_kv_cache_block_size: float | None = Field(
        default=None,
        description="Dynamo model: KV cache block size for a worker serving the model (gauge)",
    )
    model_migration_limit: float | None = Field(
        default=None,
        description="Dynamo model: Request migration limit for a worker serving the model (gauge)",
    )
    # Worker Management Metrics
    model_workers: float | None = Field(
        default=None,
        description="Dynamo model: Number of worker instances currently serving the model (gauge)",
    )


class ServerMetricRecord(AIPerfBaseModel):
    """Single server metric data point from monitoring.

    This record contains all metrics for one server at one point in time,
    along with metadata to identify the source metrics endpoint and specific server.
    Used for hierarchical storage: server_url -> server_id -> time series data.
    """

    timestamp_ns: int = Field(
        description="Nanosecond wall-clock timestamp when metrics were collected (time_ns)"
    )

    server_url: str = Field(
        description="Source server metrics endpoint URL (e.g., 'http://frontend:8080/metrics')"
    )

    server_id: str = Field(
        description="Unique server identifier (e.g., 'frontend-0', 'worker-1')"
    )
    server_type: str | None = Field(
        default=None, description="Server type (e.g., 'frontend', 'worker', 'backend')"
    )
    hostname: str | None = Field(
        default=None, description="Hostname where server is running"
    )
    instance: str | None = Field(
        default=None, description="Instance identifier (e.g., 'localhost:8080')"
    )

    metrics_data: ServerMetrics = Field(
        description="Server metrics snapshot collected at this timestamp"
    )


class ServerMetadata(AIPerfBaseModel):
    """Static metadata for a server that doesn't change over time.

    This is stored once per server and referenced by all metric data points
    to avoid duplicating metadata in every time-series entry.
    """

    server_id: str = Field(description="Unique server identifier - primary key")
    server_type: str | None = Field(
        default=None, description="Server type classification"
    )
    hostname: str | None = Field(default=None, description="Host machine name")
    instance: str | None = Field(default=None, description="Instance identifier")


class ServerMetricSnapshot(AIPerfBaseModel):
    """All metrics for a single server at one point in time.

    Groups all metric values collected during a single collection cycle,
    eliminating timestamp duplication across individual metrics.
    """

    timestamp_ns: int = Field(description="Collection timestamp for all metrics")
    metrics: dict[str, float] = Field(
        default_factory=dict, description="All metric values at this timestamp"
    )


class ServerMetricTimeSeries(AIPerfBaseModel):
    """Time series data for all metrics on a single server.

    Uses grouped snapshots instead of individual metric time series to eliminate
    timestamp duplication and improve storage efficiency.
    """

    snapshots: list[ServerMetricSnapshot] = Field(
        default_factory=list, description="Chronological snapshots of all metrics"
    )

    def append_snapshot(self, metrics: dict[str, float], timestamp_ns: int) -> None:
        """Add new snapshot with all metrics at once.

        Args:
            metrics: Dictionary of metric_name -> value for this timestamp
            timestamp_ns: Timestamp when measurements were taken
        """
        snapshot = ServerMetricSnapshot(
            timestamp_ns=timestamp_ns,
            metrics={k: v for k, v in metrics.items() if v is not None},
        )
        self.snapshots.append(snapshot)

    def get_metric_values(self, metric_name: str) -> list[tuple[float, int]]:
        """Extract time series data for a specific metric.

        Args:
            metric_name: Name of the metric to extract

        Returns:
            List of (value, timestamp_ns) tuples for the specified metric
        """
        return [
            (snapshot.metrics[metric_name], snapshot.timestamp_ns)
            for snapshot in self.snapshots
            if metric_name in snapshot.metrics
        ]

    def to_metric_result(
        self, metric_name: str, tag: str, header: str, unit: str
    ) -> MetricResult:
        """Convert metric time series to MetricResult with statistical summary.

        Args:
            metric_name: Name of the metric to analyze
            tag: Unique identifier for this metric (used by dashboard, exports, API)
            header: Human-readable name for display
            unit: Unit of measurement (e.g., "%" for percentage, "bytes" for bytes)

        Returns:
            MetricResult with min/max/avg/percentiles computed from time series

        Raises:
            NoMetricValue: If no data points are available for the specified metric
        """
        data_points = self.get_metric_values(metric_name)

        if not data_points:
            raise NoMetricValue(
                f"No server metric data available for metric '{metric_name}'"
            )

        values = np.array([point[0] for point in data_points])
        p1, p5, p10, p25, p50, p75, p90, p95, p99 = np.percentile(
            values, [1, 5, 10, 25, 50, 75, 90, 95, 99]
        )

        return MetricResult(
            tag=tag,
            header=header,
            unit=unit,
            min=np.min(values),
            max=np.max(values),
            avg=float(np.mean(values)),
            std=float(np.std(values)),
            count=len(values),
            current=float(data_points[-1][0]),
            p1=p1,
            p5=p5,
            p10=p10,
            p25=p25,
            p50=p50,
            p75=p75,
            p90=p90,
            p95=p95,
            p99=p99,
        )


class ServerMetricsData(AIPerfBaseModel):
    """Complete metrics data for one server: metadata + grouped metric time series.

    This combines static server information with dynamic time-series data,
    providing the complete picture for one server's metrics using efficient grouped snapshots.
    """

    metadata: ServerMetadata = Field(description="Static server information")
    time_series: ServerMetricTimeSeries = Field(
        default_factory=ServerMetricTimeSeries,
        description="Grouped time series for all metrics",
    )

    def add_record(self, record: ServerMetricRecord) -> None:
        """Add metric record as a grouped snapshot.

        Args:
            record: New metric data point from server collector

        Note: Groups all metric values from the record into a single snapshot
        """
        metric_mapping = record.metrics_data.model_dump()
        valid_metrics = {k: v for k, v in metric_mapping.items() if v is not None}
        if valid_metrics:
            self.time_series.append_snapshot(valid_metrics, record.timestamp_ns)

    def get_metric_result(
        self, metric_name: str, tag: str, header: str, unit: str
    ) -> MetricResult:
        """Get MetricResult for a specific metric.

        Args:
            metric_name: Name of the metric to analyze
            tag: Unique identifier for this metric
            header: Human-readable name for display
            unit: Unit of measurement

        Returns:
            MetricResult with statistical summary for the specified metric
        """
        return self.time_series.to_metric_result(metric_name, tag, header, unit)


class ServerMetricsHierarchy(AIPerfBaseModel):
    """Hierarchical storage: server_url -> server_id -> complete server metrics data.

    This provides hierarchical structure while maintaining efficient
    access patterns for both real-time display and final aggregation.

    Structure:
    {
        "http://frontend:8080/metrics": {
            "frontend-0": ServerMetricsData(metadata + time series),
            "frontend-1": ServerMetricsData(metadata + time series)
        },
        "http://worker:8081/metrics": {
            "worker-0": ServerMetricsData(metadata + time series)
        }
    }
    """

    server_endpoints: dict[str, dict[str, ServerMetricsData]] = Field(
        default_factory=dict,
        description="Nested dict: server_url -> server_id -> metrics data",
    )

    def add_record(self, record: ServerMetricRecord) -> None:
        """Add metric record to hierarchical storage.

        Args:
            record: New metric data from server monitoring

        Note: Automatically creates hierarchy levels as needed:
        - New server endpoints get empty server dict
        - New servers get initialized with metadata and empty metrics
        """

        if record.server_url not in self.server_endpoints:
            self.server_endpoints[record.server_url] = {}

        server_data = self.server_endpoints[record.server_url]

        if record.server_id not in server_data:
            metadata = ServerMetadata(
                server_id=record.server_id,
                server_type=record.server_type,
                hostname=record.hostname,
                instance=record.instance,
            )
            server_data[record.server_id] = ServerMetricsData(metadata=metadata)

        server_data[record.server_id].add_record(record)


class ServerMetricsResults(AIPerfBaseModel):
    """Results from server metrics collection during a profile run.

    This class contains all server metrics data and metadata collected during
    a benchmarking session, separate from inference performance results.
    """

    metrics_data: ServerMetricsHierarchy = Field(
        description="Hierarchical metrics data organized by server endpoint and server ID"
    )
    start_ns: int = Field(description="Start time of metrics collection in nanoseconds")
    end_ns: int = Field(description="End time of metrics collection in nanoseconds")
    endpoints_configured: list[str] = Field(
        default_factory=list,
        description="List of server endpoint URLs configured for monitoring",
    )
    endpoints_successful: list[str] = Field(
        default_factory=list,
        description="List of server endpoint URLs that successfully provided metrics data",
    )
    error_summary: list[ErrorDetailsCount] = Field(
        default_factory=list,
        description="A list of the unique error details and their counts",
    )


class ProcessServerMetricsResult(AIPerfBaseModel):
    """Result of server metrics processing - mirrors ProcessTelemetryResult pattern.

    This provides a parallel structure to ProcessTelemetryResult for the server metrics pipeline,
    maintaining complete separation while following the same architectural patterns.
    """

    results: ServerMetricsResults = Field(
        description="The processed server metrics results"
    )
    errors: list[ErrorDetails] = Field(
        default_factory=list,
        description="Any errors that occurred while processing server metrics data",
    )
