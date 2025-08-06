# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

import asyncio
import sys
import time
from typing import cast

from aiperf.common.base_service import BaseService
from aiperf.common.config import ServiceConfig, UserConfig
from aiperf.common.constants import (
    DEFAULT_PROFILE_CANCEL_TIMEOUT,
    DEFAULT_PROFILE_CONFIGURE_TIMEOUT,
    DEFAULT_PROFILE_START_TIMEOUT,
    DEFAULT_SHUTDOWN_ACK_TIMEOUT,
)
from aiperf.common.enums import (
    CommandResponseStatus,
    CommandType,
    MessageType,
    ServiceType,
)
from aiperf.common.factories import ServiceFactory, ServiceManagerFactory
from aiperf.common.hooks import on_command, on_init, on_message, on_start, on_stop
from aiperf.common.logging import get_global_log_queue
from aiperf.common.messages import (
    CommandResponse,
    CreditsCompleteMessage,
    HeartbeatMessage,
    NotificationMessage,
    ProcessRecordsResultMessage,
    ShutdownWorkersCommand,
    SpawnWorkersCommand,
    StatusMessage,
)
from aiperf.common.messages.command_messages import (
    CommandErrorResponse,
    ProfileCancelCommand,
    ProfileConfigureCommand,
    ProfileStartCommand,
    RegisterServiceCommand,
    ShutdownCommand,
)
from aiperf.common.protocols import ServiceManagerProtocol
from aiperf.common.registry.enhanced_command_handler_mixin import (
    EnhancedCommandHandlerMixin,
)
from aiperf.common.registry.enhanced_service_registry_mixin import (
    EnhancedServiceRegistryMixin,
)
from aiperf.common.types import ServiceTypeT
from aiperf.controller.proxy_manager import ProxyManager
from aiperf.controller.system_mixins import SignalHandlerMixin
from aiperf.exporters.exporter_manager import ExporterManager


@ServiceFactory.register(ServiceType.SYSTEM_CONTROLLER)
class EnhancedSystemController(
    SignalHandlerMixin,
    EnhancedServiceRegistryMixin,
    EnhancedCommandHandlerMixin,
    BaseService,
):
    """Enhanced system controller with atomic operations and race condition prevention."""

    def __init__(
        self,
        user_config: UserConfig,
        service_config: ServiceConfig,
        service_id: str | None = None,
    ) -> None:
        super().__init__(
            service_config=service_config,
            user_config=user_config,
            service_id=service_id,
        )

        self.debug("Creating Enhanced System Controller")

        self.required_services: dict[ServiceTypeT, int] = {
            ServiceType.DATASET_MANAGER: 1,
            ServiceType.TIMING_MANAGER: 1,
            ServiceType.WORKER_MANAGER: 1,
            ServiceType.RECORDS_MANAGER: 1,
        }

        if self.service_config.record_processor_service_count is not None:
            self.required_services[ServiceType.RECORD_PROCESSOR] = (
                self.service_config.record_processor_service_count
            )
            self.auto_scale_record_processor_service_count = False
        else:
            self.auto_scale_record_processor_service_count = True

        self.proxy_manager: ProxyManager = ProxyManager(
            service_config=self.service_config
        )

        self.service_manager: ServiceManagerProtocol = (
            ServiceManagerFactory.create_instance(
                "enhanced_multiprocessing",
                required_services=self.required_services,
                user_config=self.user_config,
                service_config=self.service_config,
                log_queue=get_global_log_queue(),
            )
        )

        self._lifecycle_lock = asyncio.Lock()
        self._shutdown_initiated = False

        self.debug("Enhanced System Controller created")

    async def initialize(self) -> None:
        """Initialize with proxy manager startup before base service initialization."""
        self.debug("Running ZMQ Proxy Manager Before Initialize")
        await self.proxy_manager.initialize_and_start()
        await super().initialize()

    @on_init
    async def _initialize_system_controller(self) -> None:
        self.debug("Initializing Enhanced System Controller")
        self.setup_signal_handlers(self._handle_signal)
        self.debug("Setup signal handlers")
        await self.service_manager.initialize()

    @on_start
    async def _start_services(self) -> None:
        """Bootstrap system services with enhanced registry and tracking."""
        async with self._lifecycle_lock:
            if self._shutdown_initiated:
                return

            self.debug("Enhanced System Controller is bootstrapping services")

            await self.service_manager.start()
            await self.service_manager.wait_for_all_services_registration(
                stop_event=self._stop_requested_event,
            )

            if self._shutdown_initiated:
                return

            self.info("AIPerf System is CONFIGURING")
            await self._profile_configure_all_services()

            if self._shutdown_initiated:
                return

            self.info("AIPerf System is CONFIGURED")
            await self._start_profiling_all_services()
            self.info("AIPerf System is PROFILING")

    async def _profile_configure_all_services(self) -> None:
        """Configure all services with enhanced command tracking."""
        self.info("Configuring all services to start profiling")
        begin = time.perf_counter()

        service_ids = await self.get_all_service_ids()

        await self.send_command_and_wait_for_all_responses(
            ProfileConfigureCommand(
                service_id=self.service_id,
                config=self.user_config,
            ),
            list(service_ids),
            timeout=DEFAULT_PROFILE_CONFIGURE_TIMEOUT,
        )

        duration = time.perf_counter() - begin
        self.info(f"All services configured in {duration:.2f} seconds")

    async def _start_profiling_all_services(self) -> None:
        """Start profiling on all services with enhanced tracking."""
        self.debug("Sending PROFILE_START command to all services")

        service_ids = await self.get_all_service_ids()

        await self.send_command_and_wait_for_all_responses(
            ProfileStartCommand(service_id=self.service_id),
            list(service_ids),
            timeout=DEFAULT_PROFILE_START_TIMEOUT,
        )

        self.info("All services started profiling successfully")

    @on_command(CommandType.REGISTER_SERVICE)
    async def _handle_register_service_command(
        self, message: RegisterServiceCommand
    ) -> None:
        """Handle service registration with atomic registry updates."""
        self.debug(
            "Processing registration from %s with ID: %s",
            message.service_type,
            message.service_id,
        )

        success = await self.handle_service_registration(message)

        if success:
            try:
                type_name = (
                    ServiceType(message.service_type).name.title().replace("_", " ")
                )
            except (TypeError, ValueError):
                type_name = str(message.service_type)

            self.info("Registered %s (id: '%s')", type_name, message.service_id)
        else:
            self.warning(
                "Failed to register service %s (id: '%s')",
                message.service_type,
                message.service_id,
            )

    @on_message(MessageType.HEARTBEAT)
    async def _process_heartbeat_message(self, message: HeartbeatMessage) -> None:
        """Process heartbeat with atomic registry updates."""
        self.debug(
            "Received heartbeat from %s (ID: %s)",
            message.service_type,
            message.service_id,
        )

        success = await self.handle_service_heartbeat(message)

        if not success:
            self.warning(
                "Received heartbeat from unknown service: %s (%s)",
                message.service_id,
                message.service_type,
            )

    @on_message(MessageType.CREDITS_COMPLETE)
    async def _process_credits_complete_message(
        self, message: CreditsCompleteMessage
    ) -> None:
        """Process credits complete message."""
        self.info("Received credits complete from %s", message.service_id)

    @on_message(MessageType.STATUS)
    async def _process_status_message(self, message: StatusMessage) -> None:
        """Process status updates with atomic registry updates."""
        self.debug(
            "Received status update from %s (ID: %s): %s",
            message.service_type,
            message.service_id,
            message.state,
        )

        if not await self.is_service_registered(message.service_id):
            self.debug(
                "Received status update from un-registered service: %s (%s)",
                message.service_id,
                message.service_type,
            )
            return

        await self.handle_service_status_update(message)
        self.debug("Updated state for %s to %s", message.service_id, message.state)

    @on_message(MessageType.NOTIFICATION)
    async def _process_notification_message(self, message: NotificationMessage) -> None:
        """Process notification messages."""
        self.info(f"Received notification message: {message}")

    @on_message(MessageType.COMMAND_RESPONSE)
    async def _process_command_response_message(self, message: CommandResponse) -> None:
        """Process command responses with enhanced tracking."""
        self.debug(f"Received command response message: {message}")

        if message.status == CommandResponseStatus.SUCCESS:
            self.debug(
                "Command %s succeeded from %s", message.command, message.service_id
            )
        elif message.status == CommandResponseStatus.ACKNOWLEDGED:
            self.debug(
                "Command %s acknowledged from %s", message.command, message.service_id
            )
        elif message.status == CommandResponseStatus.UNHANDLED:
            self.debug(
                "Command %s unhandled from %s", message.command, message.service_id
            )
        elif message.status == CommandResponseStatus.FAILURE:
            error_response = cast(CommandErrorResponse, message)
            self.error(
                "Command %s failed from %s: %s",
                message.command,
                message.service_id,
                error_response.error,
            )

    @on_command(CommandType.SPAWN_WORKERS)
    async def _handle_spawn_workers_command(self, message: SpawnWorkersCommand) -> None:
        """Handle worker spawning with atomic process management."""
        self.debug(f"Received spawn workers command: {message}")

        await self.service_manager.run_service(ServiceType.WORKER, message.num_workers)

        if self.auto_scale_record_processor_service_count:
            await self.service_manager.run_service(
                ServiceType.RECORD_PROCESSOR, message.num_workers
            )

    @on_command(CommandType.SHUTDOWN_WORKERS)
    async def _handle_shutdown_workers_command(
        self, message: ShutdownWorkersCommand
    ) -> None:
        """Handle worker shutdown with atomic process management."""
        self.debug(f"Received shutdown workers command: {message}")

        await self.service_manager.stop_service(ServiceType.WORKER)
        if self.auto_scale_record_processor_service_count:
            await self.service_manager.stop_service(ServiceType.RECORD_PROCESSOR)

    @on_message(MessageType.PROCESS_RECORDS_RESULT)
    async def _on_process_records_result_message(
        self, message: ProcessRecordsResultMessage
    ) -> None:
        """Handle profile results with proper shutdown coordination."""
        self.debug(f"Received profile results message: {message}")

        if message.results.errors:
            self.error(
                "Received process records result message with errors: %s",
                message.results.errors,
            )

        self.debug("Error summary: %s", message.results.results.error_summary)

        if message.results.results:
            await ExporterManager(
                results=message.results.results,
                input_config=self.user_config,
            ).export_all()
        else:
            self.error(
                "Received process records result message with no records: %s",
                message.results.results,
            )

        self.debug("Stopping system controller after exporting records")
        await asyncio.shield(self.stop())

    async def _handle_signal(self, sig: int) -> None:
        """Handle signals with proper shutdown coordination."""
        async with self._lifecycle_lock:
            if self._shutdown_initiated:
                self.warning("Received signal %s, killing", sig)
                await self._kill()
                return

            self._shutdown_initiated = True
            self.debug("Received signal %s, initiating graceful shutdown", sig)
            await self._cancel_profiling()

    async def _cancel_profiling(self) -> None:
        """Cancel profiling with enhanced command tracking."""
        self.debug("Cancelling profiling of all services")

        service_ids = await self.get_all_service_ids()

        await self.send_command_and_wait_for_all_responses(
            ProfileCancelCommand(service_id=self.service_id),
            list(service_ids),
            timeout=DEFAULT_PROFILE_CANCEL_TIMEOUT,
        )

        self.debug("Stopping system controller after profiling cancelled")
        await asyncio.shield(self.stop())

    @on_stop
    async def _stop_system_controller(self) -> None:
        """Stop system controller with proper cleanup and synchronization."""
        async with self._lifecycle_lock:
            self._shutdown_initiated = True

            service_ids = await self.get_all_service_ids()

            if service_ids:
                await self.send_command_and_wait_for_all_responses(
                    ShutdownCommand(service_id=self.service_id),
                    list(service_ids),
                    timeout=DEFAULT_SHUTDOWN_ACK_TIMEOUT,
                )

            await self.service_manager.shutdown_all_services()
            await self.comms.stop()
            await self.proxy_manager.stop()

    async def _kill(self) -> None:
        """Force kill system controller with immediate cleanup."""
        try:
            await self.service_manager.kill_all_services()
        except Exception as e:
            raise self._service_error("Failed to stop all services") from e

        await super()._kill()

    async def get_system_health_report(self) -> dict[str, any]:
        """Get comprehensive system health report."""
        registry_stats = await self.service_registry.get_registry_stats()
        command_stats = await self.get_command_execution_stats()

        return {
            "timestamp": time.time(),
            "service_registry": {
                "total_services": registry_stats.total_services,
                "services_by_type": registry_stats.services_by_type,
                "services_by_status": registry_stats.services_by_status,
                "services_by_state": registry_stats.services_by_state,
                "last_updated": registry_stats.last_updated,
            },
            "command_tracking": {
                "total_commands": command_stats["total_commands"],
                "active_commands": command_stats["active_commands"],
                "completed_commands": command_stats["completed_commands"],
                "failed_commands": command_stats["failed_commands"],
                "timeout_commands": command_stats["timeout_commands"],
                "average_response_time": command_stats["average_response_time"],
            },
            "required_services": self.required_services,
            "shutdown_initiated": self._shutdown_initiated,
        }


def main() -> None:
    """Main entry point for the enhanced system controller."""
    from aiperf.common.bootstrap import bootstrap_and_run_service

    bootstrap_and_run_service(EnhancedSystemController)


if __name__ == "__main__":
    main()
    sys.exit(0)
