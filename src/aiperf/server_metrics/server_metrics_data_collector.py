# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

import asyncio
import time
from collections.abc import Awaitable, Callable

import aiohttp
from prometheus_client.parser import text_string_to_metric_families

from aiperf.common.environment import Environment
from aiperf.common.hooks import background_task, on_init, on_stop
from aiperf.common.mixins.aiperf_lifecycle_mixin import AIPerfLifecycleMixin
from aiperf.common.models import ErrorDetails, ServerMetricRecord, ServerMetrics
from aiperf.server_metrics.constants import (
    PROMETHEUS_TO_FIELD_MAPPING,
    SCALING_FACTORS,
)

__all__ = ["ServerMetricsDataCollector"]


class ServerMetricsDataCollector(AIPerfLifecycleMixin):
    """Collects server metrics from Prometheus /metrics endpoint using async architecture.

    Modern async collector that fetches server metrics from Prometheus endpoints and converts them to
    ServerMetricRecord objects. Uses AIPerf lifecycle management and background tasks.
    - Extends AIPerfLifecycleMixin for proper lifecycle management
    - Uses aiohttp for async HTTP requests
    - Uses prometheus_client for robust metric parsing
    - Uses @background_task for periodic collection
    - Sends ServerMetricRecord list via callback function
    - No local storage (follows centralized architecture)

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
        self._server_url = server_url
        self._collection_interval = (
            collection_interval
            if collection_interval is not None
            else Environment.GPU.COLLECTION_INTERVAL  # Reuse same default interval
        )
        self._record_callback = record_callback
        self._error_callback = error_callback
        self._scaling_factors = SCALING_FACTORS
        self._session: aiohttp.ClientSession | None = None

        super().__init__(id=collector_id)

    @on_init
    async def _initialize_http_client(self) -> None:
        """Initialize the aiohttp client session.

        Called automatically by AIPerfLifecycleMixin during initialization phase.
        Creates an aiohttp ClientSession with appropriate timeout settings.
        """
        timeout = aiohttp.ClientTimeout(total=Environment.GPU.REACHABILITY_TIMEOUT)
        self._session = aiohttp.ClientSession(timeout=timeout)

    @on_stop
    async def _cleanup_http_client(self) -> None:
        """Clean up the aiohttp client session.

        Called automatically by AIPerfLifecycleMixin during shutdown phase.
        Race conditions with background tasks are handled by checking
        self.stop_requested in the background task itself.

        Raises:
            Exception: Any exception from session.close() is allowed to propagate
        """
        if self._session:
            await self._session.close()
            self._session = None

    async def is_url_reachable(self) -> bool:
        """Check if server metrics endpoint is accessible.

        Attempts HEAD request first for efficiency, falls back to GET if HEAD is not supported.
        Uses existing session if available, otherwise creates a temporary session.

        Returns:
            bool: True if endpoint responds with HTTP 200, False for any error or other status
        """
        if not self._server_url:
            return False

        # Use existing session if available, otherwise create a temporary one
        if self._session:
            try:
                # Try HEAD first for efficiency
                async with self._session.head(
                    self._server_url, allow_redirects=False
                ) as response:
                    if response.status == 200:
                        return True
                # Fall back to GET if HEAD is not supported
                async with self._session.get(self._server_url) as response:
                    return response.status == 200
            except (aiohttp.ClientError, asyncio.TimeoutError):
                return False
        else:
            # Create a temporary session for reachability check
            timeout = aiohttp.ClientTimeout(total=Environment.GPU.REACHABILITY_TIMEOUT)
            async with aiohttp.ClientSession(timeout=timeout) as temp_session:
                try:
                    # Try HEAD first for efficiency
                    async with temp_session.head(
                        self._server_url, allow_redirects=False
                    ) as response:
                        if response.status == 200:
                            return True
                    # Fall back to GET if HEAD is not supported
                    async with temp_session.get(self._server_url) as response:
                        return response.status == 200
                except (aiohttp.ClientError, asyncio.TimeoutError):
                    return False

    @background_task(immediate=True, interval=lambda self: self._collection_interval)
    async def _collect_metrics_task(self) -> None:
        """Background task for collecting server metrics at regular intervals.

        This uses the @background_task decorator which automatically handles
        lifecycle management and stopping when the collector is stopped.
        The interval is set to the collection_interval so this runs periodically.

        Errors during collection are caught and sent via error_callback if configured.
        CancelledError is propagated to allow graceful shutdown.

        Raises:
            asyncio.CancelledError: Propagated to signal task cancellation during shutdown
        """
        try:
            await self._collect_and_process_metrics()
        except asyncio.CancelledError:
            raise
        except Exception as e:
            if self._error_callback:
                try:
                    await self._error_callback(ErrorDetails.from_exception(e), self.id)
                except Exception as callback_error:
                    self.error(f"Failed to send error via callback: {callback_error}")
            else:
                self.error(f"Server metrics collection error: {e}")

    async def _collect_and_process_metrics(self) -> None:
        """Collect metrics from server endpoint and process them into ServerMetricRecord objects.

        Orchestrates the full collection flow:
        1. Fetches raw metrics data from server endpoint
        2. Parses Prometheus-format data into ServerMetricRecord objects
        3. Sends records via callback (if configured and records are not empty)

        Callback failures are caught and logged as warnings without stopping collection.

        Raises:
            Exception: Any exception from fetch or parse is logged and re-raised
        """
        try:
            metrics_data = await self._fetch_metrics()
            records = self._parse_metrics_to_records(metrics_data)

            if records and self._record_callback:
                try:
                    await self._record_callback(records, self.id)
                except Exception as e:
                    self.warning(
                        f"Failed to send server metric records via callback: {e}"
                    )

        except Exception as e:
            self.error(f"Error collecting and processing server metrics: {e}")
            raise

    async def _fetch_metrics(self) -> str:
        """Fetch raw metrics data from server endpoint using aiohttp.

        Performs safety checks before making HTTP request:
        - Verifies stop_requested flag to allow graceful shutdown
        - Checks session is initialized and not closed

        Returns:
            str: Raw metrics text in Prometheus exposition format

        Raises:
            RuntimeError: If HTTP session is not initialized
            aiohttp.ClientError: If HTTP request fails (4xx, 5xx, network errors)
            asyncio.CancelledError: If collector is being stopped or session is closed
        """
        if self.stop_requested:
            raise asyncio.CancelledError

        if not self._session:
            raise RuntimeError("HTTP session not initialized. Call initialize() first.")

        if self._session.closed:
            raise asyncio.CancelledError

        async with self._session.get(self._server_url) as response:
            response.raise_for_status()
            text = await response.text()
            return text

    def _parse_metrics_to_records(self, metrics_data: str) -> list[ServerMetricRecord]:
        """Parse Prometheus metrics text into ServerMetricRecord objects using prometheus_client.

        Processes Prometheus exposition format metrics from server endpoints:
        1. Parses metric families using prometheus_client parser
        2. Extracts server metadata (instance, hostname, etc.) from labels
        3. Maps Prometheus metric names to ServerMetricRecord field names
        4. Applies scaling factors to convert units if needed
        5. Aggregates metrics by server instance into ServerMetricRecord objects

        Skips non-finite values (NaN, inf) and handles missing labels gracefully.

        Args:
            metrics_data: Raw metrics text from server endpoint in Prometheus format

        Returns:
            list[ServerMetricRecord]: List of ServerMetricRecord objects, one per server instance.
                Returns empty list if metrics_data is empty or parsing fails.
        """
        if not metrics_data.strip():
            return []

        current_timestamp = time.time_ns()
        server_data = {}
        server_metadata = {}

        try:
            for family in text_string_to_metric_families(metrics_data):
                for sample in family.samples:
                    metric_name = sample.name
                    labels = sample.labels
                    value = sample.value

                    # Skip non-finite values early (value != value checks for NaN)
                    if isinstance(value, float) and (
                        value != value or value in (float("inf"), float("-inf"))
                    ):
                        continue

                    # Get server identifier from labels (instance, job, etc.)
                    instance = labels.get("instance", "unknown")
                    job = labels.get("job", "server")
                    hostname = labels.get("hostname", labels.get("instance"))

                    # Create a unique server_id from job and instance
                    server_id = f"{job}-{instance}".replace(":", "-").replace("/", "-")

                    # Store metadata for this server
                    if server_id not in server_metadata:
                        server_metadata[server_id] = {
                            "instance": instance,
                            "hostname": hostname,
                            "server_type": job,
                        }

                    # Map metric name to field name
                    base_metric_name = metric_name.removesuffix("_total")
                    if base_metric_name in PROMETHEUS_TO_FIELD_MAPPING:
                        field_name = PROMETHEUS_TO_FIELD_MAPPING[base_metric_name]
                        server_data.setdefault(server_id, {})[field_name] = value

        except ValueError:
            self.warning("Failed to parse Prometheus metrics - invalid format")
            return []

        records = []
        for server_id, metrics in server_data.items():
            metadata = server_metadata.get(server_id, {})
            scaled_metrics = self._apply_scaling_factors(metrics)

            record = ServerMetricRecord(
                timestamp_ns=current_timestamp,
                server_url=self._server_url,
                server_id=server_id,
                server_type=metadata.get("server_type"),
                hostname=metadata.get("hostname"),
                instance=metadata.get("instance"),
                metrics_data=ServerMetrics(**scaled_metrics),
            )
            records.append(record)

        return records

    def _apply_scaling_factors(self, metrics: dict) -> dict:
        """Apply scaling factors to convert raw units to display units.

        Converts metrics from their native units to human-readable units:
        - Memory: bytes -> bytes (no scaling by default)
        - Time: seconds -> seconds (no scaling by default)

        Only applies scaling to metrics present in the input dict. None values are preserved.

        Args:
            metrics: Dict of metric_name -> raw_value from Prometheus

        Returns:
            dict: New dict with scaled values ready for display. Unscaled metrics are copied as-is.
        """
        scaled_metrics = metrics.copy()
        for metric, factor in self._scaling_factors.items():
            if metric in scaled_metrics and scaled_metrics[metric] is not None:
                scaled_metrics[metric] *= factor
        return scaled_metrics
