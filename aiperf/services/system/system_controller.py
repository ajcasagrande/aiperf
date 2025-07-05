# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
import asyncio
import signal
import sys

from pydantic import BaseModel

from aiperf.common.config import ServiceConfig
from aiperf.common.config.user_config import UserConfig
from aiperf.common.enums import (
    CommandResponseStatus,
    CommandType,
    MessageType,
    ServiceRegistrationStatus,
    ServiceRunType,
    ServiceState,
    ServiceType,
    SystemState,
)
from aiperf.common.exceptions import (
    CommunicationError,
    InitializationError,
    NotInitializedError,
)
from aiperf.common.factories import ServiceFactory
from aiperf.common.hooks import on_post_stop, on_pre_init, on_stop
from aiperf.common.logging import get_global_log_queue
from aiperf.common.messages import (
    CommandResponseMessage,
    CreditsCompleteMessage,
    HeartbeatMessage,
    NotificationMessage,
    ProcessRecordsCommandData,
    RegistrationMessage,
    StatusMessage,
    WorkerHealthMessage,
)
from aiperf.common.service.base_controller_service import BaseControllerService
from aiperf.data_exporter.exporter_manager import ExporterManager
from aiperf.progress.progress_logger import SimpleProgressLogger
from aiperf.progress.progress_models import (
    BenchmarkSuiteType,
    ProcessingStatsMessage,
    ProfileProgressMessage,
    ProfileResultsMessage,
)
from aiperf.progress.progress_tracker import ProgressTracker
from aiperf.services.system import (
    BaseServiceManager,
    KubernetesServiceManager,
    MultiProcessServiceManager,
)
from aiperf.services.system.command_coordinator import CommandCoordinator
from aiperf.services.system.profile_runner import ProfileRunner
from aiperf.services.system.proxy_mixins import SystemControllerProxyMixin
from aiperf.services.system.system_mixins import SignalHandlerMixin
from aiperf.ui.aiperf_ui import AIPerfUI


@ServiceFactory.register(ServiceType.SYSTEM_CONTROLLER)
class SystemController(
    SignalHandlerMixin, BaseControllerService, SystemControllerProxyMixin
):
    """System Controller service.

    This service is responsible for managing the lifecycle of all other services.
    It will start, stop, and configure all other services.
    """

    def __init__(
        self,
        service_config: ServiceConfig,
        user_config: UserConfig,
        service_id: str | None = None,
    ) -> None:
        super().__init__(service_config=service_config, service_id=service_id)
        self.logger.debug("Creating System Controller")

        self._system_state: SystemState = SystemState.INITIALIZING
        self.user_config = user_config

        # List of required service types, in no particular order
        # These are services that must be running before the system controller can start profiling
        self.required_service_types: list[tuple[ServiceType, int]] = [
            (ServiceType.DATASET_MANAGER, 1),
            (ServiceType.TIMING_MANAGER, 1),
            (ServiceType.WORKER_MANAGER, 1),
            (ServiceType.RECORDS_MANAGER, 1),
            (ServiceType.INFERENCE_RESULT_PARSER, 4),
        ]

        self.service_manager: BaseServiceManager = None  # type: ignore - is set in _initialize

        self.progress_tracker: ProgressTracker = ProgressTracker()
        self.ui_enabled: bool = not self.service_config.disable_ui
        self.ui: AIPerfUI | None = (
            AIPerfUI(self.progress_tracker) if self.ui_enabled else None
        )
        self.progress_logger: SimpleProgressLogger | None = (
            SimpleProgressLogger(self.progress_tracker) if not self.ui_enabled else None
        )
        self.command_coordinator: CommandCoordinator = CommandCoordinator(
            default_timeout=self.service_config.command_timeout
        )
        self.profile_runner: ProfileRunner | None = None

        self.logger.debug("System Controller created")

    @property
    def service_type(self) -> ServiceType:
        """The type of service."""
        return ServiceType.SYSTEM_CONTROLLER

    @on_pre_init
    async def _pre_initialize(self) -> None:
        """Initialize system controller-specific components.

        This method will:
        - Initialize the service manager
        - Subscribe to relevant messages
        """
        if self.ui:
            await self.ui.run_lifecycle_async()
            await self.ui.wait_until_started()

        self.logger.debug("Initializing System Controller")

        self.setup_signal_handlers(self._handle_signal)
        self.logger.debug("Setup signal handlers")

    async def _post_initialize(self) -> None:
        """Post-initialize the system controller."""

        # TODO: make this configurable
        self.progress_tracker.configure(BenchmarkSuiteType.SINGLE_PROFILE)

        if self.service_config.service_run_type == ServiceRunType.MULTIPROCESSING:
            self.service_manager = MultiProcessServiceManager(
                required_service_types=self.required_service_types,
                config=self.service_config,
                log_queue=get_global_log_queue(),
            )

        elif self.service_config.service_run_type == ServiceRunType.KUBERNETES:
            self.service_manager = KubernetesServiceManager(
                required_service_types=self.required_service_types,
                config=self.service_config,
            )

        else:
            raise self._service_error(
                f"Unsupported service run type: {self.service_config.service_run_type}",
            )

        # Subscribe to relevant messages
        subscribe_callbacks = [
            (MessageType.REGISTRATION, self._process_registration_message),
            (MessageType.HEARTBEAT, self._process_heartbeat_message),
            (MessageType.STATUS, self._process_status_message),
            (MessageType.CREDITS_COMPLETE, self._process_credits_complete_message),
            (MessageType.PROFILE_PROGRESS, self._process_profile_progress_message),
            (MessageType.PROCESSING_STATS, self._process_processing_stats_message),
            (MessageType.PROFILE_RESULTS, self._process_profile_results_message),
            (MessageType.WORKER_HEALTH, self._process_worker_health_message),
            (MessageType.NOTIFICATION, self._process_notification_message),
            (MessageType.COMMAND_RESPONSE, self._process_command_response_message),
        ]
        for message_type, callback in subscribe_callbacks:
            try:
                await self.sub_client.subscribe(
                    message_type=message_type, callback=callback
                )
            except Exception as e:
                self.logger.error(
                    "Failed to subscribe to message_type %s: %s", message_type, e
                )
                raise CommunicationError(
                    f"Failed to subscribe to message_type {message_type}: {e}",
                ) from e

        # TODO: HACK: Wait for the subscriptions to be established
        await asyncio.sleep(1)

        self._system_state = SystemState.CONFIGURING
        await self._bootstrap_system()

    async def _handle_signal(self, sig: int) -> None:
        """Handle received signals by triggering graceful shutdown.

        Args:
            sig: The signal number received
        """
        self.logger.debug("Received signal %s, initiating graceful shutdown", sig)
        if sig == signal.SIGINT or sig == signal.SIGTERM:
            if self.profile_runner and self.profile_runner.is_complete:
                self.cancel_event.set()
                return

            if self.profile_runner and self.profile_runner.was_cancelled:
                self.logger.error("Profile was cancelled, killing all services")
                await self.kill()
                return

            if self.pub_client.stop_requested:
                self.logger.error("Pub client is shutdown, killing all services")
                await self.kill()
                return

            await self.send_command_to_service(
                target_service_id=None,
                target_service_type=ServiceType.RECORDS_MANAGER,
                command=CommandType.PROCESS_RECORDS,
                data=ProcessRecordsCommandData(cancelled=True),
            )

            if self.profile_runner:
                await self.profile_runner.cancel_profile()

        self.cancel_event.set()

    async def _bootstrap_system(self) -> None:
        """Bootstrap the system services.

        This method will:
        - Initialize all required services
        - Wait for all required services to be registered
        - Start all required services
        """
        self.logger.debug("Starting System Controller")

        # Start all required services
        try:
            await self.service_manager.run_all_services()
        except Exception as e:
            raise InitializationError("Failed to initialize all services") from e

        try:
            # Wait for all required services to be registered
            await self.service_manager.wait_for_all_services_registration(
                self.cancel_event
            )

            if self.cancel_event.is_set():
                self.logger.debug(
                    "System Controller stopped before all services registered"
                )
                return  # Don't continue with the rest of the initialization

        except Exception as e:
            raise self._service_error(
                "Not all required services registered within the timeout period",
            ) from e

        self.logger.debug("All required services registered successfully")

        self.logger.info("AIPerf System is READY")
        self._system_state = SystemState.READY

        await self.start_profiling_all_services()

        if self.stop_event.is_set():
            self.logger.debug("System Controller stopped before all services started")
            return  # Don't continue with the rest of the initialization

        self.logger.debug("All required services started successfully")
        self.logger.info("AIPerf System is RUNNING")

    @on_stop
    async def _stop(self) -> None:
        """Stop the system controller and all running services.

        This method will:
        - Stop all running services
        """
        self.logger.debug("Stopping System Controller")
        self.logger.info("AIPerf System is EXITING")
        # logging.root.setLevel(logging.DEBUG)

        self._system_state = SystemState.STOPPING

        if self.ui:
            await self.ui.shutdown()
            await self.ui.wait_for_shutdown()

        # TODO: This is a hack to force printing results again
        # Process records command
        await self.send_command_to_service(
            target_service_id=None,
            target_service_type=ServiceType.RECORDS_MANAGER,
            command=CommandType.PROCESS_RECORDS,
            data=ProcessRecordsCommandData(cancelled=False),
        )

        # Broadcast a stop command to all services
        await self.send_command_to_service(
            target_service_id=None,
            command=CommandType.SHUTDOWN,
        )

        try:
            await self.service_manager.shutdown_all_services()
        except Exception as e:
            raise self._service_error(
                "Failed to stop all services",
            ) from e

    @on_post_stop
    async def _post_stop(self) -> None:
        """Clean up system controller-specific components."""
        self.logger.debug("Cleaning up System Controller")

        if self.ui:
            await self.ui.shutdown()
            await self.ui.wait_for_shutdown()

        await self.kill()

        self._system_state = SystemState.SHUTDOWN

    async def start_profiling_all_services(self) -> None:
        """Tell all services to start profiling."""

        self.profile_runner = ProfileRunner(self)
        await self.profile_runner.run()

    async def _process_processing_stats_message(
        self, message: ProcessingStatsMessage
    ) -> None:
        """Process a profile stats message."""
        self.logger.debug("Received profile stats: %s", message)
        self.progress_tracker.update_processing_stats(message)

        if self.ui:
            await self.ui.on_profile_stats_update()
        if self.progress_logger:
            await self.progress_logger.update_stats()

        if (
            self.progress_tracker.current_profile
            and self.progress_tracker.current_profile.is_complete
        ):
            self.logger.info("Profile completed, sending process records command")
            await self.send_command_to_service(
                target_service_id=None,
                target_service_type=ServiceType.RECORDS_MANAGER,
                command=CommandType.PROCESS_RECORDS,
                data=ProcessRecordsCommandData(cancelled=False),
            )
            if self.profile_runner:
                await self.profile_runner.profile_completed()

    async def _process_profile_progress_message(
        self, message: ProfileProgressMessage
    ) -> None:
        """Process a profile progress message."""
        self.logger.debug("Received profile progress: %s", message)
        self.progress_tracker.update_profile_progress(message)
        if self.ui:
            await self.ui.on_profile_progress_update()
        if self.progress_logger:
            await self.progress_logger.update_progress()

    async def _process_profile_results_message(
        self, message: ProfileResultsMessage
    ) -> None:
        """Process a profile results message."""
        try:
            self.logger.debug("Received profile results: %s", message)
            self.progress_tracker.update_profile_results(message)
            if self.ui:
                await self.ui.on_profile_results_update()
                await self.ui.shutdown()
            if self.progress_logger:
                await self.progress_logger.update_results()

            # Export the results
            await ExporterManager(
                results=message, input_config=self.user_config
            ).export_all()

        except Exception as e:
            self.logger.error("Failed to export results: %s", e)
            raise self._service_error(
                "Failed to export results",
            ) from e
        finally:
            self.stop_event.set()

    async def _process_registration_message(self, message: RegistrationMessage) -> None:
        """Process a registration message from a service. It will
        add the service to the service manager and send a configure command
        to the service.

        Args:
            message: The registration message to process
        """
        service_id = message.service_id
        service_type = message.service_type

        self.logger.info(
            "Processing registration from %s with ID: %s", service_type, service_id
        )

        # Register service using the service registry
        _ = self.service_manager.service_registry.register_service(
            service_id=service_id,
            service_type=service_type,
            state=ServiceState.READY,
            registration_status=ServiceRegistrationStatus.REGISTERED,
        )

        is_required = service_type in self.required_service_types
        self.logger.info(
            "Registered %s service: %s with ID: %s",
            "required" if is_required else "non-required",
            service_type,
            service_id,
        )

        # Send configure command to the newly registered service
        try:
            await self.send_command_to_service(
                target_service_id=service_id,
                command=CommandType.PROFILE_CONFIGURE,
                data=self.user_config,
            )
        except Exception as e:
            raise self._service_error(
                f"Failed to send configure command to {service_type} (ID: {service_id})",
            ) from e

        self.logger.debug(
            "Sent configure command to %s (ID: %s)", service_type, service_id
        )

    async def _process_heartbeat_message(self, message: HeartbeatMessage) -> None:
        """Process a heartbeat message from a service. It will
        update the last seen timestamp and state of the service.

        Args:
            message: The heartbeat message to process
        """
        service_id = message.service_id
        service_type = message.service_type
        timestamp = message.request_ns

        self.logger.debug(
            "Received heartbeat from %s (ID: %s)", service_type, service_id
        )

        # Update the last heartbeat timestamp using the service registry
        if self.service_manager.service_registry.update_service_heartbeat(service_id):
            # Also update the state
            self.service_manager.service_registry.update_service_state(
                service_id, message.state
            )
            self.logger.debug("Updated heartbeat for %s to %s", service_id, timestamp)
        else:
            self.logger.warning(
                f"Received heartbeat from unknown service: {service_id} ({service_type})"
            )

    async def _process_credits_complete_message(
        self, message: CreditsCompleteMessage
    ) -> None:
        """Process a credits complete message from a service. It will
        update the state of the service with the service manager.

        Args:
            message: The credits complete message to process
        """
        service_id = message.service_id
        self.logger.info("Received credits complete from %s", service_id)

    async def _process_status_message(self, message: StatusMessage) -> None:
        """Process a status message from a service. It will
        update the state of the service with the service manager.

        Args:
            message: The status message to process
        """
        service_id = message.service_id
        service_type = message.service_type
        state = message.state

        self.logger.debug(
            f"Received status update from {service_type} (ID: {service_id}): {state}"
        )

        # Update the component state using the service registry
        if self.service_manager.service_registry.update_service_state(
            service_id, state
        ):
            self.logger.debug(f"Updated state for {service_id} to {state}")
        else:
            self.logger.debug(
                "Received status update from un-registered service: %s (%s)",
                service_id,
                service_type,
            )

    async def _process_worker_health_message(
        self, message: WorkerHealthMessage
    ) -> None:
        """Process a worker health message."""
        self.logger.debug("SC: Received worker health message: %s", message)
        if self.ui:
            await self.ui.on_worker_health_update(message)

    async def _process_notification_message(self, message: NotificationMessage) -> None:
        """Process a notification message."""
        self.logger.info("SC: Received notification message: %s", message)

    async def _process_command_response_message(
        self, message: CommandResponseMessage
    ) -> None:
        """Process a command response message."""
        self.logger.debug("SC: Received command response message: %s", message)
        if message.status == CommandResponseStatus.SUCCESS:
            self.logger.debug(
                "SC: Command %s succeeded with data: %s", message.command, message.data
            )
        else:
            self.logger.error(
                "SC: Command %s failed: %s", message.command, message.error
            )
            if message.error:
                self.logger.error("SC: Error details: %s", message.error)

        # Feed response to coordinator for tracking
        self.command_coordinator.process_response(message)

    async def send_command_to_service(
        self,
        target_service_id: str | None,
        command: CommandType,
        data: BaseModel | None = None,
        target_service_type: ServiceType | None = None,
    ) -> None:
        """Send a command to a specific service.

        Args:
            target_service_id: ID of the target service, or None to send to all services
            target_service_type: Type of the target service, or None to send to all services
            command: The command to send (from CommandType enum).
            data: Optional data to send with the command.

        Raises:
            CommunicationError: If the communication is not initialized
                or the command was not sent successfully
        """
        if not self.comms:
            self.logger.error("Cannot send command: Communication is not initialized")
            raise NotInitializedError(
                "Communication channels are not initialized",
            )

        # Publish command message
        try:
            await self.pub_client.publish(
                self.create_command_message(
                    command=command,
                    target_service_id=target_service_id,
                    target_service_type=target_service_type,
                    data=data,
                )
            )
        except Exception as e:
            self.logger.error("Exception publishing command: %s", e)
            raise CommunicationError(
                f"Failed to publish command: {e}",
            ) from e

    async def send_command_and_wait_for_responses(
        self,
        command: CommandType,
        target_service_ids: set[str] | None = None,
        target_service_type: ServiceType | None = None,
        data: BaseModel | None = None,
        timeout_seconds: float | None = None,
        require_all_success: bool = True,
    ) -> bool:
        """
        Send a command to services and wait for responses with timeout.

        Args:
            command: The command to send
            target_service_ids: Specific service IDs to target (if None, uses target_service_type)
            target_service_type: Type of services to target (if target_service_ids is None)
            data: Optional data to send with the command
            timeout_seconds: Custom timeout for this command
            require_all_success: Whether all responses must be successful

        Returns:
            True if command coordination was successful, False otherwise

        Raises:
            CommunicationError: If command sending fails
            asyncio.TimeoutError: If timeout exceeded
            ValueError: If neither target_service_ids nor target_service_type specified
        """
        # Determine target services
        if target_service_ids is None:
            if target_service_type is None:
                raise ValueError(
                    "Either target_service_ids or target_service_type must be specified"
                )

            # Get all services of the specified type using the service registry
            target_service_ids = (
                self.service_manager.service_registry.get_service_ids_by_type(
                    target_service_type
                )
            )

            if not target_service_ids:
                self.logger.warning(f"No services found of type {target_service_type}")
                return False

        # Create command message
        command_message = self.create_command_message(
            command=command,
            target_service_id=None,  # Will be handled by service filtering
            target_service_type=target_service_type,
            data=data,
        )

        # Set require_response to True for coordination
        command_message.require_response = True

        # Register command for coordination
        self.command_coordinator.register_command(
            command_id=command_message.command_id,
            command_type=command,
            target_service_ids=target_service_ids,
            timeout_seconds=timeout_seconds,
        )

        try:
            await self.pub_client.publish(command_message)
            self.logger.debug(
                "Sent coordinated command %s to %d services",
                command,
                len(target_service_ids),
            )
        except Exception as e:
            # Clean up registration on send failure
            self.command_coordinator.pending_commands.pop(
                command_message.command_id, None
            )
            raise CommunicationError(f"Failed to publish command: {e}") from e

        try:
            success = await self.command_coordinator.wait_for_responses(
                command_id=command_message.command_id, timeout_seconds=timeout_seconds
            )

            if require_all_success and not success:
                self.logger.error(
                    "Command %s failed - not all services responded successfully",
                    command,
                )
                return False

            return True

        except asyncio.TimeoutError:
            self.logger.error("Command %s timed out waiting for responses", command)
            raise

    async def kill(self):
        """Kill the system controller."""
        try:
            await self.service_manager.kill_all_services()
        except Exception as e:
            raise self._service_error("Failed to stop all services") from e


def main() -> None:
    """Main entry point for the system controller."""

    from aiperf.common.bootstrap import bootstrap_and_run_service

    bootstrap_and_run_service(SystemController)


if __name__ == "__main__":
    sys.exit(main())
