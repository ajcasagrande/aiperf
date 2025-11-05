# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

from aiperf.common.config import ServiceConfig, UserConfig
from aiperf.common.decorators import implements_protocol
from aiperf.common.enums import ServiceType
from aiperf.common.factories import ServiceFactory
from aiperf.common.messages import (
    ServerMetricRecordsMessage,
    ServerMetricsStatusMessage,
)
from aiperf.common.metrics.base_metrics_manager import BaseMetricsManager
from aiperf.common.models import ErrorDetails, ServerMetricRecord
from aiperf.common.protocols import ServiceProtocol
from aiperf.server_metrics.server_metrics_data_collector import (
    ServerMetricsDataCollector,
)

__all__ = ["ServerMetricsManager"]


@implements_protocol(ServiceProtocol)
@ServiceFactory.register(ServiceType.SERVER_METRICS_MANAGER)
class ServerMetricsManager(
    BaseMetricsManager[ServerMetricsDataCollector, ServerMetricRecord]
):
    """Coordinates multiple ServerMetricsDataCollector instances for server metrics collection.

    Extends BaseMetricsManager to provide server metrics-specific endpoint management,
    collector creation, and message handling.

    This service:
    - ALWAYS attempts to collect server metrics from inference endpoint URL + /metrics
    - Collection happens automatically even without --server-metrics flag (like GPU telemetry)
    - Console display only enabled when --server-metrics flag is provided
    - JSONL export always happens if data is collected
    - Manages lifecycle of ServerMetricsDataCollector instances
    - Collects metrics from multiple server endpoints (inference + user-specified)
    - Sends ServerMetricRecordsMessage to RecordsManager via message system
    - Handles errors gracefully with ErrorDetails
    - Follows centralized architecture patterns

    Args:
        service_config: Service-level configuration (logging, communication, etc.)
        user_config: User-provided configuration including server_metrics list
        service_id: Optional unique identifier for this service instance
    """

    def __init__(
        self,
        service_config: ServiceConfig,
        user_config: UserConfig,
        service_id: str | None = None,
    ) -> None:
        # ALWAYS derive default server metrics endpoint from inference endpoint URL
        # This ensures server metrics are attempted even without --server-metrics flag
        # (similar to how GPU telemetry always tries default DCGM endpoints)
        inference_url = user_config.endpoint.url
        default_server_metrics_endpoint = self._derive_metrics_endpoint(inference_url)

        # Store user-provided endpoints separately for display filtering
        user_endpoints = user_config.server_metrics_urls or []
        if isinstance(user_endpoints, str):
            user_endpoints = [user_endpoints]

        normalized_user_endpoints = [
            self._normalize_metrics_url(url) for url in user_endpoints
        ]

        self._user_provided_endpoints = [
            ep
            for ep in normalized_user_endpoints
            if ep != default_server_metrics_endpoint
        ]

        # Store the default endpoint for display filtering
        self._default_server_metrics_endpoint = default_server_metrics_endpoint

        # ALWAYS combine default + user endpoints before calling super().__init__()
        # This ensures server metrics are ALWAYS attempted from the inference endpoint
        # Console display is still gated by --server-metrics flag in the exporter
        combined_endpoints = list(
            dict.fromkeys(
                [default_server_metrics_endpoint] + self._user_provided_endpoints
            )
        )

        # Temporarily store to pass to base
        self._temp_combined_endpoints = combined_endpoints
        self._user_explicitly_configured_server_metrics = (
            user_config.server_metrics is not None
        )

        super().__init__(
            service_config=service_config,
            user_config=user_config,
            service_id=service_id,
        )

    @staticmethod
    def _derive_metrics_endpoint(inference_url: str) -> str:
        """Derive server metrics endpoint from inference endpoint URL.

        Args:
            inference_url: The inference endpoint URL (e.g., "localhost:8000", "http://server:9090")

        Returns:
            str: Metrics endpoint URL (e.g., "http://localhost:8000/metrics")
        """
        url = inference_url.strip()

        # Add http:// if no protocol specified
        if not url.startswith(("http://", "https://")):
            url = f"http://{url}"

        # Remove trailing slash
        url = url.rstrip("/")

        # Add /metrics endpoint
        if not url.endswith("/metrics"):
            url = f"{url}/metrics"

        return url

    @staticmethod
    def _normalize_metrics_url(url: str) -> str:
        """Ensure metrics URL ends with /metrics endpoint.

        Args:
            url: Base URL or full metrics URL

        Returns:
            str: URL ending with /metrics
        """
        url = url.strip()

        # Add http:// if no protocol specified
        if not url.startswith(("http://", "https://")):
            url = f"http://{url}"

        # Remove trailing slash
        url = url.rstrip("/")

        # Add /metrics if not present
        if not url.endswith("/metrics"):
            url = f"{url}/metrics"

        return url

    def _get_endpoints_from_config(self, user_config: UserConfig) -> list[str]:
        """Extract server endpoint URLs from user configuration.

        Returns the combined list of default (derived from inference URL) and user-provided endpoints.

        Args:
            user_config: User configuration object

        Returns:
            list[str]: List of server endpoint URLs
        """
        # Return the temporary combined list created in __init__
        return self._temp_combined_endpoints

    def _normalize_endpoint_url(self, url: str) -> str:
        """Ensure metrics URL ends with /metrics endpoint.

        Args:
            url: Base URL or full metrics URL

        Returns:
            str: URL ending with /metrics
        """
        return self._normalize_metrics_url(url)

    def _compute_endpoints_for_display(
        self, reachable_defaults: list[str]
    ) -> list[str]:
        """Compute which server metrics endpoints should be displayed to the user.

        Filters endpoints for clean console output based on user configuration
        and reachability. This intentional filtering prevents cluttering the UI
        with unreachable default endpoints that the user didn't explicitly configure.

        Args:
            reachable_defaults: List of default server metrics endpoints that are reachable

        Returns:
            List of endpoint URLs to display in console/export output
        """
        if reachable_defaults and self._user_provided_endpoints:
            return list(self._user_provided_endpoints) + reachable_defaults
        elif reachable_defaults:
            return reachable_defaults
        elif self._user_provided_endpoints:
            return self._user_provided_endpoints
        return []

    def _create_collector(
        self,
        endpoint_url: str,
        collection_interval: float,
        collector_id: str,
    ) -> ServerMetricsDataCollector:
        """Create a ServerMetricsDataCollector instance.

        Args:
            endpoint_url: The server metrics endpoint URL
            collection_interval: Collection interval in seconds
            collector_id: Unique identifier for the collector

        Returns:
            ServerMetricsDataCollector: A configured server metrics collector
        """
        return ServerMetricsDataCollector(
            server_url=endpoint_url,
            collection_interval=collection_interval,
            record_callback=self._on_metric_records,
            error_callback=self._on_metric_error,
            collector_id=collector_id,
        )

    def _create_records_message(
        self,
        collector_id: str,
        endpoint_url: str,
        records: list[ServerMetricRecord],
        error: ErrorDetails | None,
    ) -> ServerMetricRecordsMessage:
        """Create a ServerMetricRecordsMessage to send to RecordsManager.

        Args:
            collector_id: ID of the collector that produced the records
            endpoint_url: The server endpoint URL
            records: List of collected server metric records (empty if error occurred)
            error: Error details if collection failed, None otherwise

        Returns:
            ServerMetricRecordsMessage: Message ready to send to RecordsManager
        """
        return ServerMetricRecordsMessage(
            service_id=self.service_id,
            collector_id=collector_id,
            server_url=endpoint_url,
            records=records,
            error=error,
        )

    def _create_status_message(
        self,
        enabled: bool,
        reason: str | None,
        endpoints_configured: list[str],
        endpoints_reachable: list[str],
    ) -> ServerMetricsStatusMessage:
        """Create a ServerMetricsStatusMessage to send to SystemController.

        Args:
            enabled: Whether server metrics collection is enabled
            reason: Reason for disabled status (if applicable)
            endpoints_configured: List of configured server endpoint URLs
            endpoints_reachable: List of reachable server endpoint URLs

        Returns:
            ServerMetricsStatusMessage: Status message ready to broadcast
        """
        # Apply display filtering for server metrics
        reachable_defaults = [
            ep
            for ep in [self._default_server_metrics_endpoint]
            if ep in endpoints_reachable
        ]
        endpoints_for_display = self._compute_endpoints_for_display(reachable_defaults)

        return ServerMetricsStatusMessage(
            service_id=self.service_id,
            enabled=enabled,
            reason=reason,
            endpoints_configured=endpoints_for_display,
            endpoints_reachable=endpoints_reachable,
        )

    def _get_metrics_type_name(self) -> str:
        """Get a human-readable name for this metrics type for logging."""
        return "Server Metrics"
