# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
import asyncio
import signal
import sys
import time

from aiperf.common.config import ServiceConfig
from aiperf.common.config.user_config import UserConfig
from aiperf.common.enums import (
    BenchmarkSuiteType,
    CommandResponseStatus,
    CommandType,
    MessageType,
    ServiceType,
    SystemState,
)
from aiperf.common.exceptions import (
    AIPerfError,
    CommandError,
    CommunicationError,
    InitializationError,
    NotInitializedError,
)
from aiperf.common.factories import ServiceFactory
from aiperf.common.hooks import on_cleanup, on_message, on_start, on_stop
from aiperf.common.messages import (
    CommandResponseMessage,
    HeartbeatMessage,
    Message,
    ProcessRecordsCommandData,
    ProfileResultsMessage,
    RecordsProcessingStatsMessage,
    RegistrationMessage,
    StatusMessage,
)
from aiperf.common.mixins import EventBusClientMixin
from aiperf.common.models import AIPerfBaseModel
from aiperf.common.service.base_controller_service import BaseControllerService
from aiperf.data_exporter.exporter_manager import ExporterManager
from aiperf.progress.progress_tracker import (
    BenchmarkSuiteProgress,
    ProfileRunProgress,
    ProgressTracker,
)
from aiperf.services.system_controller.profile_runner import ProfileRunner
from aiperf.services.system_controller.proxy_mixins import ProxyMixin
from aiperf.services.system_controller.service_manager_mixin import ServiceManagerMixin
from aiperf.services.system_controller.system_mixins import SignalHandlerMixin
from aiperf.ui import AIPerfUIProtocol
from aiperf.ui.ui_protocol import AIPerfUIFactory


@ServiceFactory.register(ServiceType.SYSTEM_CONTROLLER)
class SystemController(
    BaseControllerService,
    SignalHandlerMixin,
    ProxyMixin,
    EventBusClientMixin,
    ServiceManagerMixin,
):
    """System Controller service.

    This service is responsible for managing the lifecycle of all other services.
    It will start, stop, and configure all other services.
    """

    def __init__(
        self,
        service_config: ServiceConfig,
        user_config: UserConfig | None = None,
        service_id: str | None = None,
        **kwargs,
    ) -> None:
        super().__init__(
            service_config=service_config,
            user_config=user_config,
            service_id=service_id,
            **kwargs,
        )
        self.debug("Creating System Controller")
        self._system_state: SystemState = SystemState.INITIALIZING

        self.progress_tracker: ProgressTracker = ProgressTracker()

        self.ui: AIPerfUIProtocol = AIPerfUIFactory.create_instance(
            self.service_config.ui_type, progress_tracker=self.progress_tracker
        )

        self.profile_runner: ProfileRunner | None = None

        self.debug("System Controller created")

    @property
    def service_type(self) -> ServiceType:
        """The type of service."""
        return ServiceType.SYSTEM_CONTROLLER

    async def initialize(self) -> None:
        """Override the base initialize method to add pre-initialization and
        post-initialization steps. This allows us to run the UI and progress
        logger before the system is fully initialized.
        """
        await self._pre_initialize()
        await super().initialize()
        await self._post_initialize()

    async def _pre_initialize(self) -> None:
        """Initialize system controller-specific components.

        This method will:
        - Initialize the service manager
        - Subscribe to relevant messages
        """
        self.debug("Initializing System Controller")
        await self.ui.run_async()

        self.setup_signal_handlers(self._handle_signal)
        self.debug("Setup signal handlers")

        if not self.service_config or not self.service_config.comm_config:
            raise ValueError("Communication configuration is not set")
        await self.run_proxies(self.service_config.comm_config)

    async def _post_initialize(self) -> None:
        """Post-initialize the system controller."""

        # TODO: make this configurable
        suite = BenchmarkSuiteProgress(
            type=BenchmarkSuiteType.SINGLE_PROFILE,
            profile_runs=[
                ProfileRunProgress(
                    profile_id="profile_1",
                    start_ns=time.time_ns(),
                )
            ],
        )
        self.progress_tracker.configure(
            suite=suite,
            current_profile_run=suite.  # It looks like the code snippet is a comment in Python. The `#`
            # symbol is used to indicate a comment in Python, which means
            # that the line is not executed as code but is there for human
            # readability. The text `profile_runs` seems to be a placeholder
            # or a reminder for the programmer.
            profile_runs[0],
        )

        self._system_state = SystemState.CONFIGURING

    @on_start
    async def _bootstrap_system(self) -> None:
        """Bootstrap the system services.

        This method will:
        - Initialize all required services
        - Wait for all required services to be registered
        - Start all required services
        """
        self.debug("Starting System Controller")

        # Start all required services
        try:
            await self.service_manager.run_all_services()
        except AIPerfError:
            raise  # re-raise it up the stack
        except Exception as e:
            raise InitializationError("Failed to initialize all services") from e

        try:
            # Wait for all required services to be registered
            await self.service_manager.wait_for_all_services_registration()

            if self.stop_event.is_set():
                self.debug("System Controller stopped before all services registered")
                raise asyncio.CancelledError()

        except Exception as e:
            raise asyncio.CancelledError() from e

        self.debug("All required services registered successfully")

        self.info("AIPerf System is READY")
        self._system_state = SystemState.READY

        try:
            await self.service_manager.wait_for_all_services_to_start()
        except Exception as e:
            raise asyncio.CancelledError() from e

        self.debug("All required services started successfully")

        await self.start_profiling_all_services()

        if self.stop_event.is_set():
            self.debug("System Controller stopped before all services started")
            raise asyncio.CancelledError()

        self.info("AIPerf System is RUNNING")

    async def _handle_signal(self, sig: int) -> None:
        """Handle received signals by triggering graceful shutdown.

        Args:
            sig: The signal number received
        """
        self.debug(lambda: f"Received signal {sig}, initiating graceful shutdown")
        if sig == signal.SIGINT:
            if self.stop_event.is_set():
                self.debug("Stop event is already set, killing all services")
                await self.kill()
                return

            if self.profile_runner and not self.profile_runner.is_complete:
                await self.profile_runner.cancel_profile()

        self.stop_event.set()

    @on_stop
    async def _stop(self) -> None:
        """Stop the system controller and all running services.

        This method will:
        - Stop all running services
        """
        self.debug("Stopping System Controller")
        self.info("AIPerf System is EXITING")

        self._system_state = SystemState.STOPPING

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
            self.exception(f"Failed to stop all services: {e}")
            await self.kill()
        finally:
            if self.comms:
                await self.comms.shutdown()
            await self.stop_proxies()

    @on_cleanup
    async def _cleanup(self) -> None:
        """Clean up system controller-specific components."""
        self.debug("Cleaning up System Controller")

        await self.ui.shutdown()
        await self.ui.wait_for_shutdown()

        await self.kill()

        self._system_state = SystemState.SHUTDOWN

    async def start_profiling_all_services(self) -> None:
        """Tell all services to start profiling."""

        self.profile_runner = ProfileRunner(self)
        await self.profile_runner.run()

    @on_message(
        MessageType.CREDITS_COMPLETE,
        MessageType.WORKER_HEALTH,
        MessageType.NOTIFICATION,
        MessageType.CREDIT_PHASE_PROGRESS,
        MessageType.CREDIT_PHASE_START,
        MessageType.CREDIT_PHASE_COMPLETE,
        MessageType.CREDIT_PHASE_SENDING_COMPLETE,
    )
    async def _forward_generic_message(self, message: Message) -> None:
        """Generic message handler for all messages that don't have or need a specific handler."""
        self.trace(lambda: f"Received message: {message}")
        self.progress_tracker.on_message(message)
        await self.ui.on_message(message)
        if message.message_type == MessageType.CREDIT_PHASE_SENDING_COMPLETE:
            self.info(
                lambda: f"Received credit phase sending complete message: {message}"
            )
        if message.message_type == MessageType.CREDIT_PHASE_COMPLETE:
            self.info(lambda: f"Received credit phase complete message: {message}")

    @on_message(MessageType.PROCESSING_STATS)
    async def _process_processing_stats_message(
        self, message: RecordsProcessingStatsMessage
    ) -> None:
        """Process a profile stats message."""
        await self._forward_generic_message(message)

        if (
            self.progress_tracker.current_profile_run
            and self.progress_tracker.current_profile_run.is_complete
        ):
            self.info("Profile completed, sending process records command")
            await self.send_command_to_service(
                target_service_id=None,
                target_service_type=ServiceType.RECORDS_MANAGER,
                command=CommandType.PROCESS_RECORDS,
                data=ProcessRecordsCommandData(cancelled=False),
            )
            if self.profile_runner:
                await self.profile_runner.profile_completed()

    @on_message(MessageType.PROFILE_RESULTS)
    async def _process_profile_results_message(
        self, message: ProfileResultsMessage
    ) -> None:
        """Process a profile results message."""
        try:
            await self._forward_generic_message(message)

            # Export the results
            if self.user_config:
                await ExporterManager(
                    results=message, input_config=self.user_config
                ).export_all()

        except Exception as e:
            self.exception(f"Failed to export results: {e}")
        finally:
            self.stop_event.set()

    @on_message(MessageType.REGISTRATION)
    async def _process_registration_message(self, message: RegistrationMessage) -> None:
        """Process a registration message from a service. It will
        add the service to the service manager and send a configure command
        to the service.

        Args:
            message: The registration message to process
        """
        await self.service_manager.on_message(message)

        is_required = message.service_type in self.service_manager.required_services
        self.info(
            lambda: f"Registered {'required' if is_required else 'non-required'} service: {message.service_type} with ID: {message.service_id}"
        )

        # Send configure command to the newly registered service
        try:
            await self.send_command_to_service(
                target_service_id=message.service_id,
                command=CommandType.PROFILE_CONFIGURE,
                data=self.user_config,
            )
        except AIPerfError:
            raise  # re-raise it up the stack
        except Exception as e:
            raise CommandError(
                f"Failed to send configure command to {message.service_type} (ID: {message.service_id})",
            ) from e

        self.debug(
            lambda: f"Sent configure command to {message.service_type} (ID: {message.service_id})"
        )

    @on_message(MessageType.HEARTBEAT)
    async def _process_heartbeat_message(self, message: HeartbeatMessage) -> None:
        """Process a heartbeat message from a service. It will
        update the last seen timestamp and state of the service.

        Args:
            message: The heartbeat message to process
        """
        self.trace(
            lambda: f"Received heartbeat from {message.service_type} (ID: {message.service_id})"
        )
        await self.service_manager.on_message(message)

    @on_message(MessageType.STATUS)
    async def _process_status_message(self, message: StatusMessage) -> None:
        """Process a status message from a service. It will
        update the state of the service with the service manager.

        Args:
            message: The status message to process
        """
        self.trace(
            lambda: f"Received status update from {message.service_type} (ID: {message.service_id}): {message.state}"
        )
        await self.service_manager.on_message(message)

    @on_message(MessageType.COMMAND_RESPONSE)
    async def _process_command_response_message(
        self, message: CommandResponseMessage
    ) -> None:
        """Process a command response message."""
        self.trace(lambda: f"Received command response message: {message}")
        if message.status == CommandResponseStatus.SUCCESS:
            self.debug(
                lambda: f"Command {message.command} succeeded with data: {message.data}"
            )
        else:
            self.error(f"Command {message.command} failed: {message.error}")
            if message.error:
                self.error(f"Error details: {message.error}")

    async def send_command_to_service(
        self,
        target_service_id: str | None,
        command: CommandType,
        data: AIPerfBaseModel | None = None,
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
            self.error("Cannot send command: Communication is not initialized")
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
            self.exception(f"Exception publishing command: {e}")
            raise CommunicationError(
                f"Failed to publish command: {e}",
            ) from e

    async def kill(self):
        """Kill the system controller."""
        try:
            await self.service_manager.kill_all_services()
        except AIPerfError:
            raise  # re-raise it up the stack
        except Exception as e:
            raise AIPerfError("Failed to stop all services") from e

        await self.comms.shutdown()


def main() -> int:
    """Main entry point for the system controller."""

    from aiperf.common.bootstrap import bootstrap_and_run_service

    bootstrap_and_run_service(SystemController)

    return 0


if __name__ == "__main__":
    sys.exit(main())
