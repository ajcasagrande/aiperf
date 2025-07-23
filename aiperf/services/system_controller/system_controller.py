# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
import asyncio
import signal
import sys
import time
from typing import Any

import zmq.asyncio
from pydantic import BaseModel

from aiperf.common.comms.zmq.zmq_proxy_base import BaseZMQProxy
from aiperf.common.config import ServiceConfig, UserConfig
from aiperf.common.constants import TASK_CANCEL_TIMEOUT_SHORT
from aiperf.common.enums import (
    CommandResponseStatus,
    CommandType,
    MessageType,
    ServiceRegistrationStatus,
    ServiceRunType,
    ServiceType,
    ZMQProxyType,
)
from aiperf.common.exceptions import CommunicationError, NotInitializedError
from aiperf.common.factories import ServiceFactory, ZMQProxyFactory
from aiperf.common.hooks import on_init, on_start, on_stop
from aiperf.common.messages import (
    CommandResponseMessage,
    CreditsCompleteMessage,
    HeartbeatMessage,
    NotificationMessage,
    ProcessRecordsCommandData,
    RegistrationMessage,
    StatusMessage,
)
from aiperf.common.messages.command_messages import CommandMessage
from aiperf.common.models import ServiceRunInfo
from aiperf.common.service.base_service import BaseService
from aiperf.services.service_manager import (
    BaseServiceManager,
    KubernetesServiceManager,
    MultiProcessServiceManager,
)
from aiperf.services.system_controller.system_mixins import SignalHandlerMixin


@ServiceFactory.register(ServiceType.SYSTEM_CONTROLLER)
class SystemController(SignalHandlerMixin, BaseService):
    """System Controller service.

    This service is responsible for managing the lifecycle of all other services.
    It will start, stop, and configure all other services.
    """

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
        self.debug("Creating System Controller")
        # List of required service types, in no particular order
        # These are services that must be running before the system controller can start profiling
        self.required_services = {
            ServiceType.DATASET_MANAGER: 1,
            ServiceType.TIMING_MANAGER: 1,
            ServiceType.WORKER_MANAGER: 1,
            ServiceType.RECORDS_MANAGER: 1,
            ServiceType.INFERENCE_RESULT_PARSER: service_config.result_parser_service_count,
        }

        self.service_manager: BaseServiceManager = None  # type: ignore - is set in _initialize

        self.event_bus_proxy: BaseZMQProxy | None = None
        self.event_bus_proxy_task: asyncio.Task | None = None

        self.dataset_manager_proxy: BaseZMQProxy | None = None
        self.dataset_manager_proxy_task: asyncio.Task | None = None

        self.raw_inference_proxy: BaseZMQProxy | None = None
        self.raw_inference_proxy_task: asyncio.Task | None = None

        self.debug("System Controller created")

    @on_init
    async def _initialize_system_controller(self) -> None:
        self.debug("Initializing System Controller")

        self.setup_signal_handlers(self._handle_signal)
        self.debug("Setup signal handlers")

        await self._initialize_proxies()
        await self._initialize_service_manager()
        await self._setup_subscriptions()

    async def _initialize_proxies(self) -> None:
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

    async def _initialize_service_manager(self) -> None:
        if self.service_config.service_run_type == ServiceRunType.MULTIPROCESSING:
            self.service_manager = MultiProcessServiceManager(
                required_services=self.required_services,
                user_config=self.user_config,
                config=self.service_config,
            )

        elif self.service_config.service_run_type == ServiceRunType.KUBERNETES:
            self.service_manager = KubernetesServiceManager(
                required_services=self.required_services,
                user_config=self.user_config,
                config=self.service_config,
            )

        else:
            raise self._service_error(
                f"Unsupported service run type: {self.service_config.service_run_type}",
            )

    async def _setup_subscriptions(self) -> None:
        # Subscribe to relevant messages
        message_callback_map = {
            MessageType.REGISTRATION: self._process_registration_message,
            MessageType.HEARTBEAT: self._process_heartbeat_message,
            MessageType.STATUS: self._process_status_message,
            MessageType.CREDITS_COMPLETE: self._process_credits_complete_message,
            MessageType.NOTIFICATION: self._process_notification_message,
            MessageType.COMMAND_RESPONSE: self._process_command_response_message,
        }
        try:
            await self.sub_client.subscribe_all(message_callback_map)
        except Exception as e:
            self.exception(f"Failed to subscribe to all messages: {e}")
            raise CommunicationError(
                f"Failed to subscribe to all messages: {e}",
            ) from e

    @on_start
    async def _start_services(self) -> None:
        """Bootstrap the system services.

        This method will:
        - Initialize all required services
        - Wait for all required services to be registered
        - Start all required services
        """
        self.debug("System Controller is bootstrapping services")

        # Start all required services
        try:
            await self.service_manager.run_all_services()
        except Exception as e:
            raise self._service_error(
                "Failed to initialize all services",
            ) from e

        # TODO: HACK: Wait for 1 second to ensure registrations made. This needs to be
        # removed once we have the ability to track registrations of services and their state before
        # starting the profiling.
        await asyncio.sleep(1)

        self.info("AIPerf System is READY")

        await self._start_profiling_all_services()

        self.debug("All required services started successfully")
        self.info("AIPerf System is RUNNING")

    @on_stop
    async def _stop(self) -> None:
        """Stop the system controller and all running services.

        This method will:
        - Stop all running services
        """
        self.debug("Stopping System Controller")
        self.info("AIPerf System is EXITING")

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

        tasks = []
        if self.event_bus_proxy:
            await self.event_bus_proxy.stop()
            if self.event_bus_proxy_task:
                self.event_bus_proxy_task.cancel()
                tasks.append(self.event_bus_proxy_task)

        if self.dataset_manager_proxy:
            await self.dataset_manager_proxy.stop()
            if self.dataset_manager_proxy_task:
                self.dataset_manager_proxy_task.cancel()
                tasks.append(self.dataset_manager_proxy_task)

        if self.raw_inference_proxy:
            await self.raw_inference_proxy.stop()
            if self.raw_inference_proxy_task:
                self.raw_inference_proxy_task.cancel()
                tasks.append(self.raw_inference_proxy_task)

        await asyncio.wait_for(
            asyncio.gather(*tasks),
            timeout=TASK_CANCEL_TIMEOUT_SHORT,
        )

    async def _handle_signal(self, sig: int) -> None:
        """Handle received signals by triggering graceful shutdown.

        Args:
            sig: The signal number received
        """
        self.debug(lambda: f"Received signal {sig}, initiating graceful shutdown")
        if sig == signal.SIGINT or sig == signal.SIGTERM:
            await self.stop()
            return

    async def _start_profiling_all_services(self) -> None:
        """Tell all services to start profiling."""
        # TODO: HACK: Wait for 1 second to ensure services are ready
        await asyncio.sleep(1)

        self.debug("Sending START_PROFILING command to all services")
        await self.send_command_to_service(
            target_service_id=None,
            command=CommandType.START_PROFILING,
        )

    async def _process_registration_message(self, message: RegistrationMessage) -> None:
        """Process a registration message from a service. It will
        add the service to the service manager and send a configure command
        to the service.

        Args:
            message: The registration message to process
        """
        service_id = message.service_id
        service_type = message.service_type

        self.info(
            lambda: f"Processing registration from {service_type} with ID: {service_id}"
        )

        service_info = ServiceRunInfo(
            registration_status=ServiceRegistrationStatus.REGISTERED,
            service_type=service_type,
            service_id=service_id,
            first_seen=time.time_ns(),
            state=message.state,
            last_seen=time.time_ns(),
        )

        self.service_manager.service_id_map[service_id] = service_info
        if service_type not in self.service_manager.service_map:
            self.service_manager.service_map[service_type] = []
        self.service_manager.service_map[service_type].append(service_info)

        is_required = service_type in self.required_services
        self.info(
            lambda: f"Registered {is_required} service: {service_type} with ID: {service_id}"
        )

        # Send configure command to the newly registered service
        try:
            await self.send_command_to_service(
                target_service_id=service_id,
                command=CommandType.CONFIGURE_PROFILING,
                data=self.user_config,
            )
        except Exception as e:
            raise self._service_error(
                f"Failed to send configure command to {service_type} (ID: {service_id})",
            ) from e

        self.debug(
            lambda: f"Sent configure command to {service_type} (ID: {service_id})"
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

        self.debug(lambda: f"Received heartbeat from {service_type} (ID: {service_id})")

        # Update the last heartbeat timestamp if the component exists
        try:
            service_info = self.service_manager.service_id_map[service_id]
            service_info.last_seen = timestamp
            service_info.state = message.state
            self.debug(f"Updated heartbeat for {service_id} to {timestamp}")
        except Exception:
            self.warning(
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
        self.info(f"Received credits complete from {service_id}")

    async def _process_status_message(self, message: StatusMessage) -> None:
        """Process a status message from a service. It will
        update the state of the service with the service manager.

        Args:
            message: The status message to process
        """
        service_id = message.service_id
        service_type = message.service_type
        state = message.state

        self.debug(
            lambda: f"Received status update from {service_type} (ID: {service_id}): {state}"
        )

        # Update the component state if the component exists
        if service_id not in self.service_manager.service_id_map:
            self.debug(
                lambda: f"Received status update from un-registered service: {service_id} ({service_type})"
            )
            return

        service_info = self.service_manager.service_id_map.get(service_id)
        if service_info is None:
            return

        service_info.state = message.state

        self.debug(f"Updated state for {service_id} to {message.state}")

    async def _process_notification_message(self, message: NotificationMessage) -> None:
        """Process a notification message."""
        self.info(f"Received notification message: {message}")

    async def _process_command_response_message(
        self, message: CommandResponseMessage
    ) -> None:
        """Process a command response message."""
        self.debug(lambda: f"Received command response message: {message}")
        if message.status == CommandResponseStatus.SUCCESS:
            self.logger.debug(
                f"Command {message.command} succeeded with data: {message.data}"
            )
        else:
            self.error(f"Command {message.command} failed: {message.error}")
            if message.error:
                self.error(f"Error details: {message.error}")

        if message.command == CommandType.PROCESS_RECORDS:
            await self.stop()

        if message.command == CommandType.SHUTDOWN:
            await self.kill()

    def create_command_message(
        self,
        command: CommandType,
        target_service_id: str | None,
        target_service_type: ServiceType | None = None,
        data: BaseModel | None = None,
    ) -> CommandMessage:
        """Create a command message to be sent to a specific service.

        Args:
            command: The command to send
            target_service_id: The ID of the service to send the command to
            target_service_type: The type of the service to send the command to
            data: Optional data to send with the command.

        Returns:
            A command message
        """
        return CommandMessage(
            service_id=self.service_id,
            command=command,
            target_service_id=target_service_id,
            target_service_type=target_service_type,
            data=data,
        )

    async def send_command_to_service(
        self,
        target_service_id: str | None,
        command: CommandType,
        data: Any | None = None,
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
            raise CommunicationError(f"Failed to publish command: {e}") from e

    async def kill(self):
        """Kill the system controller."""
        try:
            await self.service_manager.kill_all_services()
        except Exception as e:
            raise self._service_error("Failed to stop all services") from e

        await super().kill()


def main() -> None:
    """Main entry point for the system controller."""

    from aiperf.common.bootstrap import bootstrap_and_run_service

    bootstrap_and_run_service(SystemController)


if __name__ == "__main__":
    sys.exit(main())
