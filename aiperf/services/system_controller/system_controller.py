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
    ServiceState,
    ServiceType,
    SystemState,
)
from aiperf.common.enums.ui import AIPerfUIType
from aiperf.common.exceptions import CommunicationError, NotInitializedError
from aiperf.common.factories import ServiceFactory
from aiperf.common.hooks import on_cleanup, on_message, on_start, on_stop
from aiperf.common.messages import (
    CommandResponseMessage,
    HeartbeatMessage,
    Message,
    ProcessRecordsCommandData,
    RecordsProcessingStatsMessage,
    RegistrationMessage,
    StatusMessage,
)
from aiperf.common.messages.progress import ProfileResultsMessage
from aiperf.common.mixins.aiperf_message_handler import AIPerfMessageHandlerMixin
from aiperf.common.pydantic_utils import AIPerfBaseModel
from aiperf.common.service.base_controller_service import BaseControllerService
from aiperf.common.service_models import ServiceRegistrationInfo
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
    ServiceManagerMixin,
    AIPerfMessageHandlerMixin,
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
        self.service_config: ServiceConfig = service_config
        self.user_config: UserConfig = user_config
        self._system_state: SystemState = SystemState.INITIALIZING

        self.progress_tracker: ProgressTracker = ProgressTracker()

        self.ui_type = (
            AIPerfUIType.TQDM if self.service_config.disable_ui else AIPerfUIType.RICH
        )
        self.ui: AIPerfUIProtocol = AIPerfUIFactory.create_instance(
            self.ui_type, progress_tracker=self.progress_tracker
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
        await self._setup_subscriptions()
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

    async def _setup_subscriptions(self) -> None:
        """Setup subscriptions for the system controller."""
        # Subscribe to relevant messages
        subscribe_callbacks = [
            # Specific handlers
            (MessageType.REGISTRATION, self._process_registration_message),
            (MessageType.HEARTBEAT, self._process_heartbeat_message),
            (MessageType.STATUS, self._process_status_message),
            (MessageType.PROCESSING_STATS, self._process_processing_stats_message),
            (MessageType.PROFILE_RESULTS, self._process_profile_results_message),
            (MessageType.COMMAND_RESPONSE, self._process_command_response_message),
            # Generic handlers
            (MessageType.CREDITS_COMPLETE, self._forward_generic_message),
            (MessageType.WORKER_HEALTH, self._forward_generic_message),
            (MessageType.NOTIFICATION, self._forward_generic_message),
            (
                MessageType.CREDIT_PHASE_PROGRESS,
                self._forward_generic_message,
            ),
            (MessageType.CREDIT_PHASE_START, self._forward_generic_message),
            (
                MessageType.CREDIT_PHASE_COMPLETE,
                self._forward_generic_message,
            ),
            (MessageType.CREDIT_PHASE_SENDING_COMPLETE, self._forward_generic_message),
        ]
        for message_type, callback in subscribe_callbacks:
            try:
                await self.sub_client.subscribe(
                    message_type=message_type, callback=callback
                )
            except Exception as e:
                self.exception(
                    f"Failed to subscribe to message_type {message_type}: {e}"
                )
                raise CommunicationError(
                    f"Failed to subscribe to message_type {message_type}: {e}",
                ) from e

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
            current_profile_run=suite.profile_runs[0],
        )

        self.create_service_manager(
            service_config=self.service_config,
            user_config=self.user_config,
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
        except Exception as e:
            raise self._service_error(
                "Failed to initialize all services",
            ) from e

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
        self.trace("SC: Received message: %s", message)
        self.progress_tracker.on_message(message)
        await self.ui.on_message(message)
        if message.message_type == MessageType.CREDIT_PHASE_SENDING_COMPLETE:
            self.info("Credit phase sending complete, sending process records command")
        if message.message_type == MessageType.CREDIT_PHASE_COMPLETE:
            self.info("Profile completed, sending process records command")

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
        service_id = message.service_id
        service_type = message.service_type

        self.debug(
            lambda: f"Processing registration from {service_type} with ID: {service_id}"
        )

        await self.service_manager.on_message(message)

        service_info = ServiceRegistrationInfo(
            service_type=service_type,
            service_id=service_id,
            first_seen=time.time_ns(),
            state=ServiceState.READY,
            last_seen=time.time_ns(),
        )

        self.service_manager.service_id_map[service_id] = service_info
        if service_type not in self.service_manager.service_map:
            self.service_manager.service_map[service_type] = []
        self.service_manager.service_map[service_type].append(service_info)

        is_required = service_type in self.required_services
        self.info(
            lambda: f"Registered {'required' if is_required else 'non-required'} service: {service_type} with ID: {service_id}"
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

        self.debug(
            lambda: f"Sent configure command to {service_type} (ID: {service_id})"
        )

    @on_message(MessageType.HEARTBEAT)
    async def _process_heartbeat_message(self, message: HeartbeatMessage) -> None:
        """Process a heartbeat message from a service. It will
        update the last seen timestamp and state of the service.

        Args:
            message: The heartbeat message to process
        """
        service_id = message.service_id
        service_type = message.service_type
        timestamp = message.request_ns

        self.trace(lambda: f"Received heartbeat from {service_type} (ID: {service_id})")
        await self.service_manager.on_message(message)

        # Update the last heartbeat timestamp if the component exists
        try:
            service_info = self.service_manager.service_id_map[service_id]
            service_info.last_seen = timestamp
            service_info.state = message.state
            self.trace(lambda: f"Updated heartbeat for {service_id} to {timestamp}")
        except Exception:
            self.warning(
                lambda: f"Received heartbeat from unknown service: {service_id} ({service_type})"
            )
            # HACK: If the service is not registered, we need to register it
            await self._process_registration_message(
                RegistrationMessage(
                    service_id=service_id,
                    service_type=service_type,
                )
            )

    @on_message(MessageType.STATUS)
    async def _process_status_message(self, message: StatusMessage) -> None:
        """Process a status message from a service. It will
        update the state of the service with the service manager.

        Args:
            message: The status message to process
        """
        await self.service_manager.on_message(message)

        service_id = message.service_id
        service_type = message.service_type
        state = message.state

        self.debug(
            lambda: f"Received status update from {service_type} (ID: {service_id}): {state}"
        )

        # Update the component state if the component exists
        if service_id not in self.service_manager.service_id_map:
            self.trace(
                lambda: f"Received status update from un-registered service: {service_id} ({service_type})"
            )
            return

        service_info = self.service_manager.service_id_map.get(service_id)
        if service_info is None:
            return

        service_info.state = message.state

        self.trace(lambda: f"Updated state for {service_id} to {message.state}")

    @on_message(MessageType.COMMAND_RESPONSE)
    async def _process_command_response_message(
        self, message: CommandResponseMessage
    ) -> None:
        """Process a command response message."""
        self.trace(lambda: f"SC: Received command response message: {message}")
        if message.status == CommandResponseStatus.SUCCESS:
            self.debug(
                lambda: f"SC: Command {message.command} succeeded with data: {message.data}"
            )
        else:
            self.error(lambda: f"SC: Command {message.command} failed: {message.error}")
            if message.error:
                self.error(lambda: f"SC: Error details: {message.error}")

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
        except Exception as e:
            raise self._service_error("Failed to stop all services") from e

        await self.comms.shutdown()


def main() -> None:
    """Main entry point for the system controller."""

    from aiperf.common.bootstrap import bootstrap_and_run_service

    bootstrap_and_run_service(SystemController)


if __name__ == "__main__":
    sys.exit(main())
