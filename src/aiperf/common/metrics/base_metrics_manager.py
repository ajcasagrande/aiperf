# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Base class for metrics manager services that orchestrate data collectors.

This module provides a reusable abstract base class for managing multiple metrics
data collectors and coordinating their lifecycle.
"""

import asyncio
from abc import abstractmethod
from typing import Generic, TypeVar

from aiperf.common.base_component_service import BaseComponentService
from aiperf.common.config import ServiceConfig, UserConfig
from aiperf.common.decorators import implements_protocol
from aiperf.common.enums import (
    CommAddress,
    CommandType,
)
from aiperf.common.environment import Environment
from aiperf.common.hooks import on_command, on_init, on_stop
from aiperf.common.messages import (
    ProfileCancelCommand,
    ProfileConfigureCommand,
)
from aiperf.common.models import ErrorDetails
from aiperf.common.protocols import (
    PushClientProtocol,
    ServiceProtocol,
)

__all__ = ["BaseMetricsManager"]

# Generic types
CollectorT = TypeVar(
    "CollectorT"
)  # Type of data collector (e.g., TelemetryDataCollector)
RecordT = TypeVar("RecordT")  # Type of record (e.g., TelemetryRecord)


@implements_protocol(ServiceProtocol)
class BaseMetricsManager(BaseComponentService, Generic[CollectorT, RecordT]):
    """Abstract base class for metrics manager services.

    This class provides common functionality for:
    - Managing multiple data collector instances
    - Lifecycle coordination (configure, start, stop)
    - Endpoint reachability testing
    - Status message broadcasting
    - Error handling
    - Push client communication with RecordsManager

    Subclasses must implement:
    - _create_collector(): Create a data collector instance
    - _create_records_message(): Create a records message from collected data
    - _create_status_message(): Create a status message
    - _get_endpoints_from_config(): Extract endpoint URLs from user config
    - _normalize_endpoint_url(): Normalize endpoint URL format

    Args:
        service_config: Service-level configuration (logging, communication, etc.)
        user_config: User-provided configuration
        service_id: Optional unique identifier for this service instance
    """

    def __init__(
        self,
        service_config: ServiceConfig,
        user_config: UserConfig,
        service_id: str | None = None,
    ) -> None:
        super().__init__(
            service_config=service_config,
            user_config=user_config,
            service_id=service_id,
        )

        self.records_push_client: PushClientProtocol = self.comms.create_push_client(
            CommAddress.RECORDS,
        )

        self._collectors: dict[str, CollectorT] = {}
        self._collector_id_to_url: dict[str, str] = {}

        # Get endpoints from user config (subclass-specific)
        user_endpoints = self._get_endpoints_from_config(user_config)
        if isinstance(user_endpoints, str):
            user_endpoints = [user_endpoints]

        # Normalize endpoint URLs
        valid_endpoints = [self._normalize_endpoint_url(url) for url in user_endpoints]

        # Store configured endpoints
        self._configured_endpoints = list(dict.fromkeys(valid_endpoints))

        self._collection_interval = Environment.GPU.COLLECTION_INTERVAL

    @on_init
    async def _initialize(self) -> None:
        """Initialize metrics manager.

        Called automatically during service startup via @on_init hook.
        Actual collector initialization happens in _profile_configure_command
        after configuration is received from SystemController.
        """
        pass

    @on_command(CommandType.PROFILE_CONFIGURE)
    async def _profile_configure_command(
        self, message: ProfileConfigureCommand
    ) -> None:
        """Configure the metrics collectors but don't start them yet.

        Creates collector instances for each configured endpoint,
        tests reachability, and sends status message.
        If no endpoints are reachable, disables metrics and prepares for shutdown.

        Args:
            message: Profile configuration command from SystemController
        """
        self._collectors.clear()
        self._collector_id_to_url.clear()

        for endpoint_url in self._configured_endpoints:
            self.debug(
                f"{self._get_metrics_type_name()}: Testing reachability of {endpoint_url}"
            )
            collector_id = (
                f"collector_{endpoint_url.replace(':', '_').replace('/', '_')}"
            )
            self._collector_id_to_url[collector_id] = endpoint_url

            collector = self._create_collector(
                endpoint_url=endpoint_url,
                collection_interval=self._collection_interval,
                collector_id=collector_id,
            )

            try:
                is_reachable = await collector.is_url_reachable()
                if is_reachable:
                    self._collectors[endpoint_url] = collector
                    self.debug(
                        f"{self._get_metrics_type_name()}: Endpoint {endpoint_url} is reachable"
                    )
                else:
                    self.debug(
                        f"{self._get_metrics_type_name()}: Endpoint {endpoint_url} is not reachable"
                    )
            except Exception as e:
                self.error(
                    f"{self._get_metrics_type_name()}: Exception testing {endpoint_url}: {e}"
                )

        reachable_endpoints = list(self._collectors.keys())

        if not self._collectors:
            await self._send_status_message(
                enabled=False,
                reason="no endpoints reachable",
                endpoints_configured=self._configured_endpoints,
                endpoints_reachable=[],
            )
            return

        await self._send_status_message(
            enabled=True,
            reason=None,
            endpoints_configured=self._configured_endpoints,
            endpoints_reachable=reachable_endpoints,
        )

    @on_command(CommandType.PROFILE_START)
    async def _on_start_profiling(self, message) -> None:
        """Start all metrics collectors.

        Initializes and starts each configured collector.
        If no collectors start successfully, sends disabled status.

        Args:
            message: Profile start command from SystemController
        """
        if not self._collectors:
            # Metrics disabled status already sent in _profile_configure_command
            self._shutdown_task = asyncio.create_task(self._delayed_shutdown())
            return

        started_count = 0
        for endpoint_url, collector in self._collectors.items():
            try:
                await collector.initialize()
                await collector.start()
                started_count += 1
            except Exception as e:
                self.error(f"Failed to start collector for {endpoint_url}: {e}")

        if started_count == 0:
            self.warning(
                f"No {self._get_metrics_type_name()} collectors successfully started"
            )
            await self._send_status_message(
                enabled=False,
                reason="all collectors failed to start",
                endpoints_configured=self._configured_endpoints,
                endpoints_reachable=[],
            )
            self._shutdown_task = asyncio.create_task(self._delayed_shutdown())
            return

    @on_command(CommandType.PROFILE_CANCEL)
    async def _handle_profile_cancel_command(
        self, message: ProfileCancelCommand
    ) -> None:
        """Stop all metrics collectors when profiling is cancelled.

        Called when user cancels profiling or an error occurs during profiling.
        Stops all running collectors gracefully and cleans up resources.

        Args:
            message: Profile cancel command from SystemController
        """
        await self._stop_all_collectors()

    @on_stop
    async def _metrics_manager_stop(self) -> None:
        """Stop all metrics collectors during service shutdown.

        Called automatically by BaseComponentService lifecycle management via @on_stop hook.
        Ensures all collectors are properly stopped and cleaned up even if shutdown
        command was not received.
        """
        await self._stop_all_collectors()

    async def _delayed_shutdown(self) -> None:
        """Shutdown service after a delay to allow command response to be sent.

        Waits before calling stop() to ensure the command response
        has time to be published and transmitted to the SystemController.
        """
        await asyncio.sleep(Environment.GPU.SHUTDOWN_DELAY)
        await self.stop()

    async def _stop_all_collectors(self) -> None:
        """Stop all metrics collectors.

        Attempts to stop each collector gracefully, logging errors but continuing with
        remaining collectors to ensure all resources are released. Does nothing if no
        collectors are configured.

        Errors during individual collector shutdown do not prevent other collectors
        from being stopped.
        """
        if not self._collectors:
            return

        for endpoint_url, collector in self._collectors.items():
            try:
                await collector.stop()
            except Exception as e:
                self.error(f"Failed to stop collector for {endpoint_url}: {e}")

    async def _on_metric_records(
        self, records: list[RecordT], collector_id: str
    ) -> None:
        """Async callback for receiving metric records from collectors.

        Sends records message to RecordsManager via message system.
        Empty record lists are ignored.

        Args:
            records: List of record objects from a collector
            collector_id: Unique identifier of the collector that sent the records
        """
        if not records:
            return

        try:
            endpoint_url = self._collector_id_to_url.get(collector_id, "")
            message = self._create_records_message(
                collector_id=collector_id,
                endpoint_url=endpoint_url,
                records=records,
                error=None,
            )

            await self.records_push_client.push(message)

        except Exception as e:
            self.error(f"Failed to send metric records: {e}")

    async def _on_metric_error(self, error: ErrorDetails, collector_id: str) -> None:
        """Async callback for receiving metric errors from collectors.

        Sends error message to RecordsManager via message system.
        The message contains an empty records list and the error details.

        Args:
            error: ErrorDetails describing the collection error
            collector_id: Unique identifier of the collector that encountered the error
        """
        try:
            endpoint_url = self._collector_id_to_url.get(collector_id, "")
            error_message = self._create_records_message(
                collector_id=collector_id,
                endpoint_url=endpoint_url,
                records=[],
                error=error,
            )

            await self.records_push_client.push(error_message)

        except Exception as e:
            self.error(f"Failed to send metric error message: {e}")

    async def _send_status_message(
        self,
        enabled: bool,
        reason: str | None = None,
        endpoints_configured: list[str] | None = None,
        endpoints_reachable: list[str] | None = None,
    ) -> None:
        """Send metrics status message to SystemController.

        Publishes status message to inform SystemController about metrics
        availability and endpoint reachability.

        Args:
            enabled: Whether metrics collection is enabled/available
            reason: Optional human-readable reason for status
            endpoints_configured: List of endpoint URLs configured
            endpoints_reachable: List of endpoint URLs that are accessible
        """
        try:
            status_message = self._create_status_message(
                enabled=enabled,
                reason=reason,
                endpoints_configured=endpoints_configured or [],
                endpoints_reachable=endpoints_reachable or [],
            )

            await self.publish(status_message)

        except Exception as e:
            self.error(f"Failed to send metrics status message: {e}")

    # Abstract methods that subclasses must implement

    @abstractmethod
    def _create_collector(
        self,
        endpoint_url: str,
        collection_interval: float,
        collector_id: str,
    ) -> CollectorT:
        """Create a data collector instance.

        Args:
            endpoint_url: The metrics endpoint URL
            collection_interval: Collection interval in seconds
            collector_id: Unique identifier for the collector

        Returns:
            CollectorT: A configured collector instance

        Example:
            return TelemetryDataCollector(
                dcgm_url=endpoint_url,
                collection_interval=collection_interval,
                record_callback=self._on_metric_records,
                error_callback=self._on_metric_error,
                collector_id=collector_id,
            )
        """
        pass

    @abstractmethod
    def _create_records_message(
        self,
        collector_id: str,
        endpoint_url: str,
        records: list[RecordT],
        error: ErrorDetails | None,
    ):
        """Create a records message to send to RecordsManager.

        Args:
            collector_id: ID of the collector that produced the records
            endpoint_url: The endpoint URL
            records: List of collected records (empty if error occurred)
            error: Error details if collection failed, None otherwise

        Returns:
            A message object (e.g., TelemetryRecordsMessage, ServerMetricRecordsMessage)

        Example:
            return TelemetryRecordsMessage(
                service_id=self.service_id,
                collector_id=collector_id,
                dcgm_url=endpoint_url,
                records=records,
                error=error,
            )
        """
        pass

    @abstractmethod
    def _create_status_message(
        self,
        enabled: bool,
        reason: str | None,
        endpoints_configured: list[str],
        endpoints_reachable: list[str],
    ):
        """Create a status message to send to SystemController.

        Args:
            enabled: Whether metrics collection is enabled
            reason: Reason for disabled status (if applicable)
            endpoints_configured: List of configured endpoint URLs
            endpoints_reachable: List of reachable endpoint URLs

        Returns:
            A status message object (e.g., TelemetryStatusMessage, ServerMetricsStatusMessage)

        Example:
            return TelemetryStatusMessage(
                service_id=self.service_id,
                enabled=enabled,
                reason=reason,
                endpoints_configured=endpoints_configured,
                endpoints_reachable=endpoints_reachable,
            )
        """
        pass

    @abstractmethod
    def _get_endpoints_from_config(self, user_config: UserConfig) -> list[str]:
        """Extract endpoint URLs from user configuration.

        Args:
            user_config: User configuration object

        Returns:
            list[str]: List of endpoint URLs

        Example:
            return user_config.gpu_telemetry_urls or []
        """
        pass

    @abstractmethod
    def _normalize_endpoint_url(self, url: str) -> str:
        """Normalize endpoint URL to ensure consistent format.

        Args:
            url: Raw endpoint URL from user config

        Returns:
            str: Normalized URL

        Example:
            url = url.rstrip("/")
            if not url.endswith("/metrics"):
                url = f"{url}/metrics"
            return url
        """
        pass

    @abstractmethod
    def _get_metrics_type_name(self) -> str:
        """Get a human-readable name for this metrics type for logging.

        Returns:
            str: Metrics type name (e.g., "GPU Telemetry", "Server Metrics")
        """
        pass
