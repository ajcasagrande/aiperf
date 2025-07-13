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
    GRACEFUL_SHUTDOWN_TIMEOUT_SECONDS,
    TASK_CANCEL_TIMEOUT_SHORT,
)
from aiperf.common.enums import ServiceType
from aiperf.common.enums.message import MessageType
from aiperf.common.enums.service import ServiceState
from aiperf.common.exceptions import ServiceTimeoutError
from aiperf.common.factories import ServiceFactory
from aiperf.common.messages import BaseServiceMessage
from aiperf.common.messages.error import BaseServiceErrorMessage
from aiperf.common.messages.service import (
    HeartbeatMessage,
    RegistrationMessage,
    StatusMessage,
)
from aiperf.common.pydantic_utils import AIPerfBaseModel
from aiperf.services.service_manager.base import BaseServiceManager
from aiperf.services.service_registry import GlobalServiceRegistry


class MultiProcessRunInfo(AIPerfBaseModel):
    """Information about a service running as a multiprocessing process."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    process: Process | SpawnProcess | ForkProcess | None = Field(default=None)
    service_type: ServiceType = Field(
        ...,
        description="Type of service running in the process",
    )


class MultiProcessServiceManager(BaseServiceManager):
    """
    Service Manager for starting and stopping services as multiprocessing processes.
    """

    def __init__(
        self,
        required_services: dict[ServiceType, int],
        config: ServiceConfig,
        user_config: UserConfig | None = None,
        log_queue: "multiprocessing.Queue | None" = None,
    ):
        super().__init__(required_services, config)
        self.multi_process_info: list[MultiProcessRunInfo] = []
        self.log_queue = log_queue
        self.user_config = user_config
        self.registry = GlobalServiceRegistry
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
                        "service_config": self.config,
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

                self.debug(
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
            self.exception(lambda e=e: f"Error starting services: {e}")
            raise e

    async def shutdown_all_services(self) -> None:
        """Stop all required services as multiprocessing processes."""
        self.debug("Stopping all service processes")
        for info in self.multi_process_info:
            if info.process:
                info.process.terminate()

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
                    self.state_events[service_type][ServiceState.RUNNING].wait()
                    for service_type in self.required_services
                ]
            ),
            timeout=timeout_seconds,
        )

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
            await asyncio.wait_for(
                asyncio.to_thread(
                    info.process.join, timeout=TASK_CANCEL_TIMEOUT_SHORT
                ),  # Add timeout to join
                timeout=GRACEFUL_SHUTDOWN_TIMEOUT_SECONDS,  # Overall timeout
            )
            self.debug(
                lambda pid=info.process.pid,
                type=info.service_type: f"Service {type} process stopped (pid: {pid})"
            )
        except asyncio.TimeoutError:
            self.warning(
                lambda pid=info.process.pid,
                type=info.service_type: f"Service {type} process (pid: {pid}) did not terminate gracefully, killing"
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
            self.registered_events[message.service_type].set()

    async def _on_heartbeat_message(self, message: HeartbeatMessage) -> None:
        self.registry.update_service_heartbeat(message.service_id)

    async def _on_status_message(self, message: StatusMessage) -> None:
        self.registry.update_service_state(message.service_id, message.state)

    async def _on_service_error_message(self, message: BaseServiceErrorMessage) -> None:
        self.registry[message.service_id].errors.append(message.error)
