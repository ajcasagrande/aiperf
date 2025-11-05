# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

import asyncio

from aiperf.common.base_component_service import BaseComponentService
from aiperf.common.config import ServiceConfig, UserConfig
from aiperf.common.decorators import implements_protocol
from aiperf.common.enums import (
    CommAddress,
    CommandType,
    ServiceType,
)
from aiperf.common.environment import Environment
from aiperf.common.factories import ServiceFactory
from aiperf.common.hooks import on_command, on_init, on_stop
from aiperf.common.messages import (
    ProfileCancelCommand,
    ProfileConfigureCommand,
    ServerMetricRecordsMessage,
    ServerMetricsStatusMessage,
)
from aiperf.common.models import ErrorDetails, ServerMetricRecord
from aiperf.common.protocols import (
    PushClientProtocol,
    ServiceProtocol,
)
from aiperf.server_metrics.server_metrics_data_collector import (
    ServerMetricsDataCollector,
)

__all__ = ["ServerMetricsManager"]


@implements_protocol(ServiceProtocol)
@ServiceFactory.register(ServiceType.SERVER_METRICS_MANAGER)
class ServerMetricsManager(BaseComponentService):
    """Coordinates multiple ServerMetricsDataCollector instances for server metrics collection.

    The ServerMetricsManager coordinates multiple ServerMetricsDataCollector instances
    to collect server metrics from multiple Prometheus /metrics endpoints and send unified
    ServerMetricRecordsMessage to RecordsManager.

    This service:
    - Manages lifecycle of ServerMetricsDataCollector instances
    - Collects metrics from multiple server endpoints
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
        super().__init__(
            service_config=service_config,
            user_config=user_config,
            service_id=service_id,
        )

        self.records_push_client: PushClientProtocol = self.comms.create_push_client(
            CommAddress.RECORDS,
        )

        self._collectors: dict[str, ServerMetricsDataCollector] = {}
        self._collector_id_to_url: dict[str, str] = {}

        self._user_explicitly_configured_metrics = (
            user_config.server_metrics is not None
        )

        user_endpoints = user_config.server_metrics_urls or []
        if isinstance(user_endpoints, str):
            user_endpoints = [user_endpoints]

        valid_endpoints = [self._normalize_metrics_url(url) for url in user_endpoints]

        # Store user-provided endpoints
        self._user_provided_endpoints = valid_endpoints

        # Use user-provided endpoints
        self._server_endpoints = list(dict.fromkeys(self._user_provided_endpoints))

        self._collection_interval = (
            Environment.GPU.COLLECTION_INTERVAL
        )  # Reuse same interval

    @staticmethod
    def _normalize_metrics_url(url: str) -> str:
        """Ensure metrics URL ends with /metrics endpoint.

        Args:
            url: Base URL or full metrics URL

        Returns:
            str: URL ending with /metrics
        """
        url = url.rstrip("/")
        if not url.endswith("/metrics"):
            url = f"{url}/metrics"
        return url

    @on_init
    async def _initialize(self) -> None:
        """Initialize server metrics manager.

        Called automatically during service startup via @on_init hook.
        Actual collector initialization happens in _profile_configure_command
        after configuration is received from SystemController.
        """
        pass

    @on_command(CommandType.PROFILE_CONFIGURE)
    async def _profile_configure_command(
        self, message: ProfileConfigureCommand
    ) -> None:
        """Configure the server metrics collectors but don't start them yet.

        Creates ServerMetricsDataCollector instances for each configured endpoint,
        tests reachability, and sends status message to RecordsManager.
        If no endpoints are reachable, disables metrics collection and stops the service.

        Args:
            message: Profile configuration command from SystemController
        """

        self._collectors.clear()
        self._collector_id_to_url.clear()
        for server_url in self._server_endpoints:
            self.debug(f"Server Metrics: Testing reachability of {server_url}")
            collector_id = f"collector_{server_url.replace(':', '_').replace('/', '_')}"
            self._collector_id_to_url[collector_id] = server_url
            collector = ServerMetricsDataCollector(
                server_url=server_url,
                collection_interval=self._collection_interval,
                record_callback=self._on_server_metric_records,
                error_callback=self._on_server_metric_error,
                collector_id=collector_id,
            )

            try:
                is_reachable = await collector.is_url_reachable()
                if is_reachable:
                    self._collectors[server_url] = collector
                    self.debug(f"Server Metrics: Endpoint {server_url} is reachable")
                else:
                    self.debug(
                        f"Server Metrics: Endpoint {server_url} is not reachable"
                    )
            except Exception as e:
                self.error(f"Server Metrics: Exception testing {server_url}: {e}")

        reachable_endpoints = list(self._collectors.keys())

        if not self._collectors:
            # Server metrics manager shutdown occurs in _on_start_profiling to prevent hang
            await self._send_server_metrics_status(
                enabled=False,
                reason="no server metrics endpoints reachable",
                endpoints_configured=self._user_provided_endpoints,
                endpoints_reachable=[],
            )
            return

        await self._send_server_metrics_status(
            enabled=True,
            reason=None,
            endpoints_configured=self._user_provided_endpoints,
            endpoints_reachable=reachable_endpoints,
        )

    @on_command(CommandType.PROFILE_START)
    async def _on_start_profiling(self, message) -> None:
        """Start all server metrics collectors.

        Initializes and starts each configured collector.
        If no collectors start successfully, sends disabled status to SystemController.

        Args:
            message: Profile start command from SystemController
        """
        if not self._collectors:
            # Metrics disabled status already sent in _profile_configure_command, only shutdown here
            self._shutdown_task = asyncio.create_task(self._delayed_shutdown())
            return

        started_count = 0
        for server_url, collector in self._collectors.items():
            try:
                await collector.initialize()
                await collector.start()
                started_count += 1
            except Exception as e:
                self.error(f"Failed to start collector for {server_url}: {e}")

        if started_count == 0:
            self.warning("No server metrics collectors successfully started")
            await self._send_server_metrics_status(
                enabled=False,
                reason="all collectors failed to start",
                endpoints_configured=self._user_provided_endpoints,
                endpoints_reachable=[],
            )
            self._shutdown_task = asyncio.create_task(self._delayed_shutdown())
            return

    @on_command(CommandType.PROFILE_CANCEL)
    async def _handle_profile_cancel_command(
        self, message: ProfileCancelCommand
    ) -> None:
        """Stop all server metrics collectors when profiling is cancelled.

        Called when user cancels profiling or an error occurs during profiling.
        Stops all running collectors gracefully and cleans up resources.

        Args:
            message: Profile cancel command from SystemController
        """
        await self._stop_all_collectors()

    @on_stop
    async def _server_metrics_manager_stop(self) -> None:
        """Stop all server metrics collectors during service shutdown.

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
        """Stop all server metrics collectors.

        Attempts to stop each collector gracefully, logging errors but continuing with
        remaining collectors to ensure all resources are released. Does nothing if no
        collectors are configured.

        Errors during individual collector shutdown do not prevent other collectors
        from being stopped.
        """

        if not self._collectors:
            return

        for server_url, collector in self._collectors.items():
            try:
                await collector.stop()
            except Exception as e:
                self.error(f"Failed to stop collector for {server_url}: {e}")

    async def _on_server_metric_records(
        self, records: list[ServerMetricRecord], collector_id: str
    ) -> None:
        """Async callback for receiving server metric records from collectors.

        Sends ServerMetricRecordsMessage to RecordsManager via message system.
        Empty record lists are ignored.

        Args:
            records: List of ServerMetricRecord objects from a collector
            collector_id: Unique identifier of the collector that sent the records
        """

        if not records:
            return

        try:
            server_url = self._collector_id_to_url.get(collector_id, "")
            message = ServerMetricRecordsMessage(
                service_id=self.service_id,
                collector_id=collector_id,
                server_url=server_url,
                records=records,
                error=None,
            )

            await self.records_push_client.push(message)

        except Exception as e:
            self.error(f"Failed to send server metric records: {e}")

    async def _on_server_metric_error(
        self, error: ErrorDetails, collector_id: str
    ) -> None:
        """Async callback for receiving server metric errors from collectors.

        Sends error ServerMetricRecordsMessage to RecordsManager via message system.
        The message contains an empty records list and the error details.

        Args:
            error: ErrorDetails describing the collection error
            collector_id: Unique identifier of the collector that encountered the error
        """

        try:
            server_url = self._collector_id_to_url.get(collector_id, "")
            error_message = ServerMetricRecordsMessage(
                service_id=self.service_id,
                collector_id=collector_id,
                server_url=server_url,
                records=[],
                error=error,
            )

            await self.records_push_client.push(error_message)

        except Exception as e:
            self.error(f"Failed to send server metric error message: {e}")

    async def _send_server_metrics_status(
        self,
        enabled: bool,
        reason: str | None = None,
        endpoints_configured: list[str] | None = None,
        endpoints_reachable: list[str] | None = None,
    ) -> None:
        """Send server metrics status message to SystemController.

        Publishes ServerMetricsStatusMessage to inform SystemController about metrics
        availability and endpoint reachability. Used during configuration phase and
        when metrics are disabled due to errors.

        Args:
            enabled: Whether server metrics collection is enabled/available
            reason: Optional human-readable reason for status (e.g., "no endpoints reachable")
            endpoints_configured: List of server endpoint URLs configured for monitoring
            endpoints_reachable: List of server endpoint URLs that are accessible
        """
        try:
            status_message = ServerMetricsStatusMessage(
                service_id=self.service_id,
                enabled=enabled,
                reason=reason,
                endpoints_configured=endpoints_configured or [],
                endpoints_reachable=endpoints_reachable or [],
            )

            await self.publish(status_message)

        except Exception as e:
            self.error(f"Failed to send server metrics status message: {e}")
