# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

from aiperf.common.config import ServiceConfig, UserConfig
from aiperf.common.decorators import implements_protocol
from aiperf.common.enums import ServiceType
from aiperf.common.environment import Environment
from aiperf.common.factories import ServiceFactory
from aiperf.common.messages import (
    TelemetryRecordsMessage,
    TelemetryStatusMessage,
)
from aiperf.common.metrics.base_metrics_manager import BaseMetricsManager
from aiperf.common.models import ErrorDetails, TelemetryRecord
from aiperf.common.protocols import ServiceProtocol
from aiperf.gpu_telemetry.telemetry_data_collector import TelemetryDataCollector

__all__ = ["TelemetryManager"]


@implements_protocol(ServiceProtocol)
@ServiceFactory.register(ServiceType.TELEMETRY_MANAGER)
class TelemetryManager(BaseMetricsManager[TelemetryDataCollector, TelemetryRecord]):
    """Coordinates multiple TelemetryDataCollector instances for GPU telemetry collection.

    Extends BaseMetricsManager to provide DCGM-specific endpoint management,
    collector creation, and message handling.

    This service:
    - Manages lifecycle of TelemetryDataCollector instances
    - Collects telemetry from multiple DCGM endpoints
    - Sends TelemetryRecordsMessage to RecordsManager via message system
    - Handles errors gracefully with ErrorDetails
    - Follows centralized architecture patterns

    Args:
        service_config: Service-level configuration (logging, communication, etc.)
        user_config: User-provided configuration including gpu_telemetry list
        service_id: Optional unique identifier for this service instance
    """

    def __init__(
        self,
        service_config: ServiceConfig,
        user_config: UserConfig,
        service_id: str | None = None,
    ) -> None:
        # Store user-provided endpoints separately for display filtering (excluding auto-inserted defaults)
        user_endpoints = user_config.gpu_telemetry_urls or []
        if isinstance(user_endpoints, str):
            user_endpoints = [user_endpoints]

        normalized_user_endpoints = [
            self._normalize_dcgm_url(url) for url in user_endpoints
        ]

        self._user_provided_endpoints = [
            ep
            for ep in normalized_user_endpoints
            if ep not in Environment.GPU.DEFAULT_DCGM_ENDPOINTS
        ]

        # Combine defaults + user endpoints before calling super().__init__()
        # This ensures _configured_endpoints in base class has the full list
        combined_endpoints = list(
            dict.fromkeys(
                list(Environment.GPU.DEFAULT_DCGM_ENDPOINTS)
                + self._user_provided_endpoints
            )
        )

        # Temporarily store to pass to base
        self._temp_combined_endpoints = combined_endpoints
        self._user_explicitly_configured_telemetry = (
            user_config.gpu_telemetry is not None
        )

        super().__init__(
            service_config=service_config,
            user_config=user_config,
            service_id=service_id,
        )

    def _get_endpoints_from_config(self, user_config: UserConfig) -> list[str]:
        """Extract DCGM endpoint URLs from user configuration.

        Returns the combined list of default and user-provided endpoints.
        """
        # Return the temporary combined list created in __init__
        return self._temp_combined_endpoints

    def _normalize_endpoint_url(self, url: str) -> str:
        """Ensure DCGM URL ends with /metrics endpoint."""
        return self._normalize_dcgm_url(url)

    @staticmethod
    def _normalize_dcgm_url(url: str) -> str:
        """Ensure DCGM URL ends with /metrics endpoint.

        Args:
            url: Base URL or full metrics URL

        Returns:
            str: URL ending with /metrics
        """
        url = url.rstrip("/")
        if not url.endswith("/metrics"):
            url = f"{url}/metrics"
        return url

    def _compute_endpoints_for_display(
        self, reachable_defaults: list[str]
    ) -> list[str]:
        """Compute which DCGM endpoints should be displayed to the user.

        Filters endpoints for clean console output based on user configuration
        and reachability. This intentional filtering prevents cluttering the UI
        with unreachable default endpoints that the user didn't explicitly configure.

        Args:
            reachable_defaults: List of default DCGM endpoints that are reachable

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
    ) -> TelemetryDataCollector:
        """Create a TelemetryDataCollector instance.

        Args:
            endpoint_url: The DCGM metrics endpoint URL
            collection_interval: Collection interval in seconds
            collector_id: Unique identifier for the collector

        Returns:
            TelemetryDataCollector: A configured telemetry collector
        """
        return TelemetryDataCollector(
            dcgm_url=endpoint_url,
            collection_interval=collection_interval,
            record_callback=self._on_metric_records,
            error_callback=self._on_metric_error,
            collector_id=collector_id,
        )

    def _create_records_message(
        self,
        collector_id: str,
        endpoint_url: str,
        records: list[TelemetryRecord],
        error: ErrorDetails | None,
    ) -> TelemetryRecordsMessage:
        """Create a TelemetryRecordsMessage to send to RecordsManager.

        Args:
            collector_id: ID of the collector that produced the records
            endpoint_url: The DCGM endpoint URL
            records: List of collected telemetry records (empty if error occurred)
            error: Error details if collection failed, None otherwise

        Returns:
            TelemetryRecordsMessage: Message ready to send to RecordsManager
        """
        return TelemetryRecordsMessage(
            service_id=self.service_id,
            collector_id=collector_id,
            dcgm_url=endpoint_url,
            records=records,
            error=error,
        )

    def _create_status_message(
        self,
        enabled: bool,
        reason: str | None,
        endpoints_configured: list[str],
        endpoints_reachable: list[str],
    ) -> TelemetryStatusMessage:
        """Create a TelemetryStatusMessage to send to SystemController.

        Args:
            enabled: Whether telemetry collection is enabled
            reason: Reason for disabled status (if applicable)
            endpoints_configured: List of configured DCGM endpoint URLs
            endpoints_reachable: List of reachable DCGM endpoint URLs

        Returns:
            TelemetryStatusMessage: Status message ready to broadcast
        """
        # Apply display filtering for telemetry
        reachable_defaults = [
            ep
            for ep in Environment.GPU.DEFAULT_DCGM_ENDPOINTS
            if ep in endpoints_reachable
        ]
        endpoints_for_display = self._compute_endpoints_for_display(reachable_defaults)

        return TelemetryStatusMessage(
            service_id=self.service_id,
            enabled=enabled,
            reason=reason,
            endpoints_configured=endpoints_for_display,
            endpoints_reachable=endpoints_reachable,
        )

    def _get_metrics_type_name(self) -> str:
        """Get a human-readable name for this metrics type for logging."""
        return "GPU Telemetry"
