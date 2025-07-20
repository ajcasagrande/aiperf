# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
import asyncio
import contextlib
import multiprocessing
from multiprocessing import Process
from multiprocessing.context import ForkProcess, SpawnProcess

from pydantic import ConfigDict, Field

from aiperf.common.bootstrap import bootstrap_and_run_service
from aiperf.common.config import ServiceConfig, UserConfig
from aiperf.common.constants import (
    DEFAULT_WAIT_FOR_REGISTRATION_SECONDS,
    DEFAULT_WAIT_FOR_START_SECONDS,
    DEFAULT_WAIT_FOR_STOP_SECONDS,
    TASK_CANCEL_TIMEOUT_SHORT,
)
from aiperf.common.enums import MessageType, ServiceState, ServiceType
from aiperf.common.enums.service_enums import ServiceRunType
from aiperf.common.exceptions import ServiceTimeoutError
from aiperf.common.messages import BaseServiceMessage
from aiperf.common.messages.error_messages import BaseServiceErrorMessage
from aiperf.common.messages.service_messages import (
    HeartbeatMessage,
    RegistrationMessage,
    StatusMessage,
)
from aiperf.common.models import AIPerfBaseModel
from aiperf.common.service.base_service import ServiceFactory
from aiperf.services.service_manager.base import (
    BaseServiceManager,
    ServiceManagerFactory,
)


class MultiProcessRunInfo(AIPerfBaseModel):
    """Information about a service running as a multiprocessing process."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    process: Process | SpawnProcess | ForkProcess | None = Field(default=None)
    service_type: ServiceType = Field(
        ...,
        description="Type of service running in the process",
    )


@ServiceManagerFactory.register(ServiceRunType.MULTIPROCESSING)
class MultiProcessServiceManager(BaseServiceManager):
    """
    Service Manager for starting and stopping services as multiprocessing processes.
    """

    def __init__(
        self,
        required_services: dict[ServiceType, int],
        service_config: ServiceConfig,
        user_config: UserConfig | None = None,
        log_queue: "multiprocessing.Queue | None" = None,
    ):
        super().__init__(
            required_services=required_services,
            service_config=service_config,
            user_config=user_config,
        )
        self.multi_process_info: list[MultiProcessRunInfo] = []
        self.log_queue = log_queue
        self.registered_events: dict[ServiceType, asyncio.Event] = {
            service_type: asyncio.Event() for service_type in required_services
        }
        self.state_events: dict[ServiceType, dict[ServiceState, asyncio.Event]] = {
            service_type: {state: asyncio.Event() for state in ServiceState}
            for service_type in ServiceType
        }

    async def _run_services(self, service_types: dict[ServiceType, int]) -> None:
        """Run a list of services as multiprocessing processes."""

        # Create and start all service processes
        for service_type, count in service_types.items():
            service_class = ServiceFactory.get_class_from_type(service_type)

            for _ in range(count):
                process = Process(
                    target=bootstrap_and_run_service,
                    name=f"{service_type}_process",
                    kwargs={
                        "service_class": service_class,
                        "service_id": service_type.value if count == 1 else None,
                        "service_config": self.service_config,
                        "user_config": self.user_config,
                        "log_queue": self.log_queue,
                    },
                    daemon=True,
                )
                if service_type in [
                    ServiceType.WORKER_MANAGER,
                ]:
                    process.daemon = False  # Worker manager cannot be a daemon because it needs to be able to spawn worker processes

                process.start()

                self.info(
                    lambda pid=process.pid,
                    type=service_type: f"Service {type} started as process (pid: {pid})"
                )

                self.multi_process_info.append(
                    MultiProcessRunInfo(process=process, service_type=service_type)
                )

    async def run_all_services(self) -> None:
        """Start all required services as multiprocessing processes."""
        self.debug("Starting all required services as multiprocessing processes")

        try:
            await self._run_services(self.required_services)
        except Exception as e:
            self.exception(f"Error starting services: {e}")
            raise e

    async def shutdown_all_services(self) -> None:
        """Stop all required services as multiprocessing processes."""
        self.debug("Stopping all service processes")
        self.info("Attempting to stop all service processes")
        for info in self.multi_process_info:
            if info.process:
                self.info(
                    lambda pid=info.process.pid,
                    type=info.service_type: f"Stopping service {type} process (pid: {pid})"
                )
                info.process.terminate()
            else:
                self.warning(
                    lambda type=info.service_type: f"Service {type} process not found"
                )

    async def kill_all_services(self) -> None:
        """Kill all required services as multiprocessing processes."""
        self.debug("Killing all service processes")

        # Kill all processes
        for info in self.multi_process_info:
            if info.process:
                with contextlib.suppress(Exception):
                    info.process.kill()

        # Wait for all to finish in parallel
        await asyncio.gather(
            *[self._wait_for_process(info) for info in self.multi_process_info]
        )

    async def wait_for_all_services_registration(
        self, timeout_seconds: float = DEFAULT_WAIT_FOR_REGISTRATION_SECONDS
    ) -> None:
        """Wait for all required services to be registered.

        Args:
            stop_event: Event to check if operation should be cancelled
            timeout_seconds: Maximum time to wait in seconds

        Raises:
            Exception if any service failed to register, None otherwise
        """
        self.debug("Waiting for all required services to register...")
        try:
            await asyncio.wait_for(
                asyncio.gather(
                    *[event.wait() for event in self.registered_events.values()]
                ),
                timeout=timeout_seconds,
            )
            self.success("All required services registered")
        except asyncio.TimeoutError as e:
            # Log which services didn't register in time
            for service_type in self.required_services:
                if service_type not in self.registry:
                    self.error(
                        f"Service {service_type} failed to register within timeout"
                    )

            raise ServiceTimeoutError(
                "Some services failed to register within timeout"
            ) from e

    async def wait_for_all_services_to_start(
        self,
        timeout_seconds: float = DEFAULT_WAIT_FOR_START_SECONDS,
    ) -> None:
        """Wait for all services to start."""
        self.debug("Waiting for all services to start...")
        await asyncio.wait_for(
            asyncio.gather(
                *[
                    self.state_events[service_type][ServiceState.READY].wait()
                    for service_type in self.required_services
                ]
            ),
            timeout=timeout_seconds,
        )
        self.success("All services started")

    async def wait_for_all_services_to_stop(
        self,
        timeout_seconds: float = DEFAULT_WAIT_FOR_STOP_SECONDS,
    ) -> None:
        """Wait for all services to stop."""
        self.debug("Waiting for all services to stop...")

        # Wait for all to finish in parallel
        await asyncio.gather(
            *[self._wait_for_process(info) for info in self.multi_process_info]
        )

    async def _wait_for_process(self, info: MultiProcessRunInfo) -> None:
        """Wait for a process to terminate with timeout handling."""
        if not info.process or not info.process.is_alive():
            return

        try:
            await asyncio.to_thread(
                info.process.join, timeout=TASK_CANCEL_TIMEOUT_SHORT
            )
            self.debug(
                lambda pid=info.process.pid,
                type=info.service_type: f"Service {type} process stopped (pid: {pid})"
            )
        except asyncio.TimeoutError:
            self.warning(
                f"Service {info.service_type} process (pid: {info.process.pid}) did not terminate gracefully, killing"
            )
            info.process.kill()

    async def on_message(self, message: BaseServiceMessage) -> None:
        """Handle a message from a service."""
        _handlers = {
            MessageType.REGISTRATION: self._on_registration_message,
            MessageType.HEARTBEAT: self._on_heartbeat_message,
            MessageType.STATUS: self._on_status_message,
            MessageType.SERVICE_ERROR: self._on_service_error_message,
        }
        if message.message_type in _handlers:
            await _handlers[message.message_type](message)

    async def _on_registration_message(self, message: RegistrationMessage) -> None:
        self.registry.register_service(
            message.service_id,
            message.service_type,
            message.state,
        )
        if message.service_type in self.required_services:
            self.debug(lambda: f"Service {message.service_type} registered event set")
            self.registered_events[message.service_type].set()
            self.debug(lambda: f"Registered events: {self.registered_events}")

    async def _on_heartbeat_message(self, message: HeartbeatMessage) -> None:
        self.registry.update_service_heartbeat(message.service_id)

    async def _on_status_message(self, message: StatusMessage) -> None:
        self.registry.update_service_state(message.service_id, message.state)
        self.state_events[message.service_type][message.state].set()
        self.trace(lambda: f"State events: {self.state_events}")

    async def _on_service_error_message(self, message: BaseServiceErrorMessage) -> None:
        self.registry[message.service_id].errors.append(message.error)
