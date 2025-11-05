# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

from collections.abc import Awaitable, Callable

from aiperf.common.metrics.base_metrics_data_collector import BaseMetricsDataCollector
from aiperf.common.models import ErrorDetails, ServerMetricRecord, ServerMetrics
from aiperf.server_metrics.constants import (
    PROMETHEUS_TO_FIELD_MAPPING,
    SCALING_FACTORS,
)

__all__ = ["ServerMetricsDataCollector"]


class ServerMetricsDataCollector(BaseMetricsDataCollector[ServerMetricRecord]):
    """Collects server metrics from Prometheus /metrics endpoint using async architecture.

    Extends BaseMetricsDataCollector to provide server metrics-specific parsing and
    record creation. Fetches server metrics from Prometheus endpoints and converts them to
    ServerMetricRecord objects.

    Args:
        server_url: URL of the Prometheus metrics endpoint (e.g., "http://frontend:8080/metrics")
        collection_interval: Interval in seconds between metric collections (default: 1.0)
        record_callback: Optional async callback to receive collected records.
            Signature: async (records: list[ServerMetricRecord], collector_id: str) -> None
        error_callback: Optional async callback to receive collection errors.
            Signature: async (error: ErrorDetails, collector_id: str) -> None
        collector_id: Unique identifier for this collector instance
    """

    def __init__(
        self,
        server_url: str,
        collection_interval: float | None = None,
        record_callback: Callable[[list[ServerMetricRecord], str], Awaitable[None]]
        | None = None,
        error_callback: Callable[[ErrorDetails, str], Awaitable[None]] | None = None,
        collector_id: str = "server_metrics_collector",
    ) -> None:
        super().__init__(
            endpoint_url=server_url,
            collection_interval=collection_interval,
            record_callback=record_callback,
            error_callback=error_callback,
            collector_id=collector_id,
        )

    def _extract_resource_info(
        self, labels: dict[str, str]
    ) -> tuple[str | None, dict[str, str]]:
        """Extract server identifier and metadata from Prometheus labels.

        Args:
            labels: Prometheus metric labels

        Returns:
            tuple: (server_id, metadata_dict) or (None, {}) to skip this metric
        """
        # Get server identifier from labels (instance, job, etc.)
        instance = labels.get("instance", "unknown")
        job = labels.get("job", "server")
        hostname = labels.get("hostname", labels.get("instance"))

        # Create a unique server_id from job and instance
        server_id = f"{job}-{instance}".replace(":", "-").replace("/", "-")

        metadata = {
            "instance": instance,
            "hostname": hostname,
            "server_type": job,
        }

        return server_id, metadata

    def _create_records(
        self,
        resource_data: dict[str, dict[str, float]],
        resource_metadata: dict[str, dict[str, str]],
        timestamp_ns: int,
    ) -> list[ServerMetricRecord]:
        """Create ServerMetricRecord objects from parsed server metrics.

        Args:
            resource_data: Dict mapping server_id -> {field_name: value}
            resource_metadata: Dict mapping server_id -> metadata
            timestamp_ns: Timestamp when metrics were collected

        Returns:
            list[ServerMetricRecord]: List of ServerMetricRecord objects, one per server
        """
        records = []
        for server_id, metrics in resource_data.items():
            metadata = resource_metadata.get(server_id, {})
            scaled_metrics = self._apply_scaling_factors(metrics)

            record = ServerMetricRecord(
                timestamp_ns=timestamp_ns,
                server_url=self.endpoint_url,
                server_id=server_id,
                server_type=metadata.get("server_type"),
                hostname=metadata.get("hostname"),
                instance=metadata.get("instance"),
                metrics_data=ServerMetrics(**scaled_metrics),
            )
            records.append(record)

        return records

    def _get_field_mapping(self) -> dict[str, str]:
        """Get Prometheus metric name to ServerMetrics field name mapping."""
        return PROMETHEUS_TO_FIELD_MAPPING

    def _get_scaling_factors(self) -> dict[str, float]:
        """Get scaling factors for server metrics unit conversion."""
        return SCALING_FACTORS
