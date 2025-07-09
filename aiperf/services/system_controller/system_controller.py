# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
import asyncio
import signal
import sys
import time

import zmq.asyncio
from pydantic import BaseModel

from aiperf.common.comms.zmq.zmq_proxy_base import BaseZMQProxy, ZMQProxyFactory
from aiperf.common.config import ServiceConfig
from aiperf.common.config.user_config import UserConfig
from aiperf.common.credit_models import (
    CreditPhaseCompleteMessage,
    CreditPhaseProgressMessage,
    CreditPhaseStartMessage,
    CreditsCompleteMessage,
    RecordsProcessingStatsMessage,
)
from aiperf.common.enums import (
    BenchmarkSuiteType,
    CommandResponseStatus,
    CommandType,
    MessageType,
    ServiceRegistrationStatus,
    ServiceRunType,
    ServiceState,
    ServiceType,
    SystemState,
    ZMQProxyType,
)
from aiperf.common.exceptions import CommunicationError, NotInitializedError
from aiperf.common.factories import ServiceFactory
from aiperf.common.hooks import on_cleanup, on_start, on_stop
from aiperf.common.logging import get_global_log_queue
from aiperf.common.messages import (
    CommandResponseMessage,
    HeartbeatMessage,
    NotificationMessage,
    ProcessRecordsCommandData,
    RegistrationMessage,
    StatusMessage,
)
from aiperf.common.service.base_controller_service import BaseControllerService
from aiperf.common.service_models import ServiceRunInfo
from aiperf.common.worker_models import WorkerHealthMessage
from aiperf.data_exporter.exporter_manager import ExporterManager
from aiperf.progress.progress_logger import SimpleProgressLogger
from aiperf.progress.progress_models import ProfileResultsMessage
from aiperf.progress.progress_tracker import (
    BenchmarkSuiteProgress,
    ProfileRunProgress,
    ProgressTracker,
)
from aiperf.services.service_manager import (
    BaseServiceManager,
    KubernetesServiceManager,
    MultiProcessServiceManager,
)
from aiperf.services.system_controller.profile_runner import ProfileRunner
from aiperf.services.system_controller.system_mixins import SignalHandlerMixin
from aiperf.ui.aiperf_ui import AIPerfUI


@ServiceFactory.register(ServiceType.SYSTEM_CONTROLLER)
class SystemController(BaseControllerService, SignalHandlerMixin):
    """System Controller service.

    This service is responsible for managing the lifecycle of all other services.
    It will start, stop, and configure all other services.
    """

    def __init__(
        self,
        service_config: ServiceConfig,
        user_config: UserConfig | None = None,
        service_id: str | None = None,
    ) -> None:
        super().__init__(
            service_config=service_config,
            user_config=user_config,
            service_id=service_id,
        )
        self.logger.debug("Creating System Controller")

        self._system_state: SystemState = SystemState.INITIALIZING
        self.user_config: UserConfig | None = user_config

        # List of required service types, in no particular order
        # These are services that must be running before the system controller can start profiling
        self.required_service_types: list[tuple[ServiceType, int]] = [
            (ServiceType.DATASET_MANAGER, 1),
            (ServiceType.TIMING_MANAGER, 1),
            (ServiceType.WORKER_MANAGER, 1),
            (ServiceType.RECORDS_MANAGER, 1),
            (
                ServiceType.INFERENCE_RESULT_PARSER,
                self.service_config.result_parser_service_count,
            ),
        ]

        self.service_manager: BaseServiceManager = None  # type: ignore - is set in _initialize

        self.event_bus_proxy: BaseZMQProxy | None = None
        self.event_bus_proxy_task: asyncio.Task | None = None

        self.dataset_manager_proxy: BaseZMQProxy | None = None
        self.dataset_manager_proxy_task: asyncio.Task | None = None

        self.raw_inference_proxy: BaseZMQProxy | None = None
        self.raw_inference_proxy_task: asyncio.Task | None = None

        self.progress_tracker: ProgressTracker = ProgressTracker()
        self.ui_enabled: bool = not self.service_config.disable_ui
        self.ui: AIPerfUI | None = (
            AIPerfUI(self.progress_tracker) if self.ui_enabled else None
        )
        self.progress_logger: SimpleProgressLogger | None = (
            SimpleProgressLogger(self.progress_tracker) if not self.ui_enabled else None
        )

        self.profile_runner: ProfileRunner | None = None

        self.logger.debug("System Controller created")

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
        if self.ui:
            await self.ui.run_async()

        self.logger.debug("Initializing System Controller")

        self.setup_signal_handlers(self._handle_signal)
        self.logger.debug("Setup signal handlers")

        self.zmq_context = zmq.asyncio.Context.instance()

        self.event_bus_proxy = ZMQProxyFactory.create_instance(
            ZMQProxyType.XPUB_XSUB,
            context=self.zmq_context,
            zmq_proxy_config=self.service_config.comm_config.event_bus_proxy_config,
        )
        self.event_bus_proxy_task = asyncio.create_task(self.event_bus_proxy.run())

        self.dataset_manager_proxy = ZMQProxyFactory.create_instance(
            ZMQProxyType.DEALER_ROUTER,
            context=self.zmq_context,
            zmq_proxy_config=self.service_config.comm_config.dataset_manager_proxy_config,
        )
        self.dataset_manager_proxy_task = asyncio.create_task(
            self.dataset_manager_proxy.run()
        )

        self.raw_inference_proxy = ZMQProxyFactory.create_instance(
            ZMQProxyType.PUSH_PULL,
            context=self.zmq_context,
            zmq_proxy_config=self.service_config.comm_config.raw_inference_proxy_config,
        )
        self.raw_inference_proxy_task = asyncio.create_task(
            self.raw_inference_proxy.run()
        )

    async def _setup_subscriptions(self) -> None:
        """Setup subscriptions for the system controller."""
        # Subscribe to relevant messages
        subscribe_callbacks = [
            (MessageType.REGISTRATION, self._process_registration_message),
            (MessageType.HEARTBEAT, self._process_heartbeat_message),
            (MessageType.STATUS, self._process_status_message),
            (MessageType.CREDITS_COMPLETE, self._process_credits_complete_message),
            (MessageType.PROCESSING_STATS, self._process_processing_stats_message),
            (MessageType.PROFILE_RESULTS, self._process_profile_results_message),
            (MessageType.WORKER_HEALTH, self._process_worker_health_message),
            (MessageType.NOTIFICATION, self._process_notification_message),
            (MessageType.COMMAND_RESPONSE, self._process_command_response_message),
            (
                MessageType.CREDIT_PHASE_PROGRESS,
                self._process_credit_phase_progress_message,
            ),
            (MessageType.CREDIT_PHASE_START, self._process_credit_phase_start_message),
            (
                MessageType.CREDIT_PHASE_COMPLETE,
                self._process_credit_phase_complete_message,
            ),
        ]
        for message_type, callback in subscribe_callbacks:
            try:
                await self.sub_client.subscribe(
                    message_type=message_type, callback=callback
                )
            except Exception as e:
                self.logger.exception(
                    "Failed to subscribe to message_type %s: %s", message_type, e
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

        if self.service_config.service_run_type == ServiceRunType.MULTIPROCESSING:
            self.service_manager = MultiProcessServiceManager(
                required_service_types=self.required_service_types,
                config=self.service_config,
                user_config=self.user_config,
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

        await self._setup_subscriptions()

        self._system_state = SystemState.CONFIGURING

    @on_start
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
            raise self._service_error(
                "Failed to initialize all services",
            ) from e

        try:
            # Wait for all required services to be registered
            await self.service_manager.wait_for_all_services_registration(
                self.stop_event
            )

            if self.stop_event.is_set():
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

    async def _handle_signal(self, sig: int) -> None:
        """Handle received signals by triggering graceful shutdown.

        Args:
            sig: The signal number received
        """
        self.logger.debug("Received signal %s, initiating graceful shutdown", sig)
        if sig == signal.SIGINT:
            if self.stop_event.is_set():
                self.logger.debug("Stop event is already set, killing all services")
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
        self.logger.debug("Stopping System Controller")
        self.logger.info("AIPerf System is EXITING")

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
            self.logger.exception("Failed to stop all services: %s", e)
            await self.kill()
        finally:
            if self.comms:
                await self.comms.shutdown()

    @on_cleanup
    async def _cleanup(self) -> None:
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
        self, message: RecordsProcessingStatsMessage
    ) -> None:
        """Process a profile stats message."""
        self.logger.debug("Received profile stats: %s", message)
        self.progress_tracker.on_phase_processing_stats(message)

        if self.ui:
            await self.ui.on_message(message)
        if self.progress_logger:
            await self.progress_logger.on_message(message)

        if (
            self.progress_tracker.current_profile_run
            and self.progress_tracker.current_profile_run.is_complete
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

    async def _process_credit_phase_progress_message(
        self, message: CreditPhaseProgressMessage
    ) -> None:
        """Process a credit phase progress message."""
        self.logger.debug("Received credit phase progress: %s", message)
        self.progress_tracker.on_credit_phase_progress(message)
        if self.ui:
            await self.ui.on_message(message)
        if self.progress_logger:
            await self.progress_logger.on_message(message)

    async def _process_credit_phase_start_message(
        self, message: CreditPhaseStartMessage
    ) -> None:
        """Process a credit phase start message."""
        self.logger.debug("Received credit phase start: %s", message)
        self.progress_tracker.on_credit_phase_start(message)
        if self.ui:
            await self.ui.on_message(message)
        if self.progress_logger:
            await self.progress_logger.on_message(message)

    async def _process_credit_phase_complete_message(
        self, message: CreditPhaseCompleteMessage
    ) -> None:
        """Process a credit phase complete message."""
        self.logger.debug("Received credit phase complete: %s", message)
        self.progress_tracker.on_credit_phase_complete(message)
        if self.ui:
            await self.ui.on_message(message)
        if self.progress_logger:
            await self.progress_logger.on_message(message)

    async def _process_profile_results_message(
        self, message: ProfileResultsMessage
    ) -> None:
        """Process a profile results message."""
        try:
            self.logger.debug("Received profile results: %s", message)
            self.progress_tracker.on_profile_results(message)
            if self.ui:
                await self.ui.on_message(message)
                await self.ui.shutdown()
            if self.progress_logger:
                await self.progress_logger.on_message(message)

            # Export the results
            if self.user_config:
                await ExporterManager(
                    results=message, input_config=self.user_config
                ).export_all()

        except Exception as e:
            self.logger.exception("Failed to export results: %s", e)
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

        service_info = ServiceRunInfo(
            registration_status=ServiceRegistrationStatus.REGISTERED,
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

        # Update the last heartbeat timestamp if the component exists
        try:
            service_info = self.service_manager.service_id_map[service_id]
            service_info.last_seen = timestamp
            service_info.state = message.state
            self.logger.debug("Updated heartbeat for %s to %s", service_id, timestamp)
        except Exception:
            self.logger.warning(
                f"Received heartbeat from unknown service: {service_id} ({service_type})"
            )
            # HACK: If the service is not registered, we need to register it
            await self._process_registration_message(
                RegistrationMessage(
                    service_id=service_id,
                    service_type=service_type,
                )
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
        self.logger.info(
            "Received credits complete from %s for phase %s",
            service_id,
            message.phase_stats,
        )

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

        # Update the component state if the component exists
        if service_id not in self.service_manager.service_id_map:
            self.logger.debug(
                "Received status update from un-registered service: %s (%s)",
                service_id,
                service_type,
            )
            return

        service_info = self.service_manager.service_id_map.get(service_id)
        if service_info is None:
            return

        service_info.state = message.state

        self.logger.debug("Updated state for %s to %s", service_id, state)

    async def _process_worker_health_message(
        self, message: WorkerHealthMessage
    ) -> None:
        """Process a worker health message."""
        self.logger.debug("SC: Received worker health message: %s", message)
        self.progress_tracker.on_worker_health(message)
        if self.ui:
            await self.ui.on_message(message)

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
            self.logger.exception("Exception publishing command: %s", e)
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
