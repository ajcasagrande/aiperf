# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
import asyncio
import multiprocessing
import uuid
from dataclasses import dataclass
from multiprocessing import Process, Queue
from multiprocessing.context import ForkProcess, SpawnProcess
from typing import Optional

from aiperf.common.bootstrap import bootstrap_and_run_service
from aiperf.common.config import ServiceConfig, UserConfig
from aiperf.common.constants import (
    DEFAULT_SERVICE_REGISTRATION_TIMEOUT,
    DEFAULT_SERVICE_START_TIMEOUT,
    TASK_CANCEL_TIMEOUT_SHORT,
)
from aiperf.common.decorators import implements_protocol
from aiperf.common.enums import ServiceRegistrationStatus, ServiceRunType
from aiperf.common.exceptions import AIPerfError
from aiperf.common.factories import ServiceFactory, ServiceManagerFactory
from aiperf.common.protocols import ServiceManagerProtocol
from aiperf.common.types import ServiceTypeT
from aiperf.controller.base_service_manager import BaseServiceManager

# Process cleanup timeout
PROCESS_CLEANUP_TIMEOUT = 1.0


@dataclass
class MultiProcessRunInfo:
    """Information about a service running as a multiprocessing process."""

    service_type: ServiceTypeT
    service_id: str
    process: Process | SpawnProcess | ForkProcess | None = None
    error_queue: "Queue | None" = None


@implements_protocol(ServiceManagerProtocol)
@ServiceManagerFactory.register(ServiceRunType.MULTIPROCESSING)
class MultiProcessServiceManager(BaseServiceManager):
    """
    Service Manager for starting and stopping services as multiprocessing processes.
    """

    def __init__(
        self,
        required_services: dict[ServiceTypeT, int],
        service_config: ServiceConfig,
        user_config: UserConfig,
        log_queue: Optional["multiprocessing.Queue"] = None,
        **kwargs,
    ):
        super().__init__(required_services, service_config, user_config, **kwargs)
        self.multi_process_info: list[MultiProcessRunInfo] = []
        self.log_queue = log_queue
        self.startup_errors: list[dict] = []

    async def run_service(
        self, service_type: ServiceTypeT, num_replicas: int = 1
    ) -> None:
        """Run a service with the given number of replicas."""
        service_class = ServiceFactory.get_class_from_type(service_type)

        for _ in range(num_replicas):
            service_id = f"{service_type}_{uuid.uuid4().hex[:8]}"
            error_queue = Queue()

            process = Process(
                target=bootstrap_and_run_service,
                name=f"{service_type}_process",
                kwargs={
                    "service_class": service_class,
                    "service_id": service_id,
                    "service_config": self.service_config,
                    "user_config": self.user_config,
                    "log_queue": self.log_queue,
                    "error_queue": error_queue,
                },
                daemon=True,
            )

            process.start()

            self.debug(
                lambda pid=process.pid,
                type=service_type: f"Service {type} started as process (pid: {pid})"
            )

            self.multi_process_info.append(
                MultiProcessRunInfo(
                    process=process,
                    service_type=service_type,
                    service_id=service_id,
                    error_queue=error_queue,
                )
            )

    async def stop_service(
        self, service_type: ServiceTypeT, service_id: str | None = None
    ) -> list[BaseException | None]:
        self.debug(lambda: f"Stopping {service_type} process(es) with id: {service_id}")
        tasks = []
        for info in list(self.multi_process_info):
            if info.service_type == service_type and (
                service_id is None or info.service_id == service_id
            ):
                task = asyncio.create_task(self._wait_for_process(info))
                task.add_done_callback(
                    lambda _, info=info: self.multi_process_info.remove(info)
                )
                tasks.append(task)
        return await asyncio.gather(*tasks, return_exceptions=True)

    async def shutdown_all_services(self) -> list[BaseException | None]:
        """Stop all required services as multiprocessing processes."""
        self.debug("Stopping all service processes")

        # Wait for all to finish in parallel
        return await asyncio.gather(
            *[self._wait_for_process(info) for info in self.multi_process_info],
            return_exceptions=True,
        )

    async def kill_all_services(self) -> list[BaseException | None]:
        """Kill all required services as multiprocessing processes."""
        self.debug("Killing all service processes")

        # Kill all processes
        for info in self.multi_process_info:
            if info.process:
                info.process.kill()

        # Wait for all to finish in parallel
        return await asyncio.gather(
            *[self._wait_for_process(info) for info in self.multi_process_info],
            return_exceptions=True,
        )

    async def wait_for_all_services_registration(
        self,
        stop_event: asyncio.Event,
        timeout_seconds: float = DEFAULT_SERVICE_REGISTRATION_TIMEOUT,
    ) -> None:
        """Wait for all required services to be registered.

        Args:
            stop_event: Event to check if operation should be cancelled
            timeout_seconds: Maximum time to wait in seconds

        Raises:
            Exception if any service failed to register, None otherwise
        """
        self.debug("Waiting for all required services to register...")

        # Get the set of required service types for checking completion
        required_types = set(self.required_services.keys())

        # TODO: Can this be done better by using asyncio.Event()?

        async def _wait_for_registration():
            # Give processes an initial moment to start up before checking
            await asyncio.sleep(0.5)

            while not stop_event.is_set():
                # Check for startup errors first
                startup_errors = await self.check_for_startup_errors()
                if startup_errors:
                    # If we have startup errors, raise an exception to fail fast
                    error_messages = []
                    for error in startup_errors:
                        service_type = error.get("service_type", "unknown")
                        error_info = error.get("error", {})
                        message = error_info.get("message", "Unknown error")
                        error_messages.append(f"{service_type}: {message}")

                    raise AIPerfError(
                        f"Services failed to start: {'; '.join(error_messages)}"
                    )

                # Also check if any processes have died unexpectedly
                dead_processes = []
                for info in self.multi_process_info:
                    if info.process and not info.process.is_alive():
                        dead_processes.append(
                            f"{info.service_type} ({info.service_id})"
                        )

                if dead_processes:
                    raise AIPerfError(
                        f"Service processes died unexpectedly: {', '.join(dead_processes)}"
                    )

                # Get all registered service types from the id map
                registered_types = {
                    service_info.service_type
                    for service_info in self.service_id_map.values()
                    if service_info.registration_status
                    == ServiceRegistrationStatus.REGISTERED
                }

                # Check if all required types are registered
                if required_types.issubset(registered_types):
                    return

                # Check more frequently for faster error detection
                await asyncio.sleep(0.2)

        try:
            await asyncio.wait_for(_wait_for_registration(), timeout=timeout_seconds)
        except asyncio.TimeoutError as e:
            # Log which services didn't register in time
            registered_types_set = set(
                service_info.service_type
                for service_info in self.service_id_map.values()
                if service_info.registration_status
                == ServiceRegistrationStatus.REGISTERED
            )

            for service_type in required_types:
                if service_type not in registered_types_set:
                    self.error(
                        f"Service {service_type} failed to register within timeout"
                    )

            raise AIPerfError("Some services failed to register within timeout") from e

    async def check_for_startup_errors(self) -> list[dict]:
        """Check for startup errors from child processes.

        Returns:
            List of error dictionaries containing service_type, service_id, and error details
        """
        errors: list[dict] = []
        failed_processes: list[MultiProcessRunInfo] = []

        for info in self.multi_process_info:
            error_dict = self._check_process_for_errors(info)
            if error_dict:
                errors.append(error_dict)
                failed_processes.append(info)

        # Clean up failed processes immediately
        await self._cleanup_failed_processes(failed_processes)

        # Store errors for later display
        self.startup_errors.extend(errors)
        return errors

    def _check_process_for_errors(self, info: MultiProcessRunInfo) -> dict | None:
        """Check a single process for errors.

        Args:
            info: Process information to check

        Returns:
            Error dictionary if error found, None otherwise
        """
        # Check for errors in error queue
        if info.error_queue and not info.error_queue.empty():
            return self._extract_queue_error(info)

        # Check if process died without reporting an error
        if info.process and not info.process.is_alive():
            return self._create_dead_process_error(info)

        return None

    def _extract_queue_error(self, info: MultiProcessRunInfo) -> dict | None:
        """Extract error from process error queue."""
        try:
            # Get the first error from queue (there might be multiple)
            error_info = info.error_queue.get_nowait()
            return {
                "service_type": info.service_type,
                "service_id": info.service_id,
                "error": error_info,
                "process_alive": info.process.is_alive() if info.process else False,
            }
        except Exception as e:
            self.warning(f"Failed to read error from queue for {info.service_id}: {e}")
            return None

    def _create_dead_process_error(self, info: MultiProcessRunInfo) -> dict:
        """Create error dictionary for dead process."""
        return {
            "service_type": info.service_type,
            "service_id": info.service_id,
            "error": {
                "stage": "startup",
                "exception_type": "ProcessDied",
                "message": f"Process died unexpectedly with exit code {info.process.exitcode}",
                "traceback": "N/A - Process died without reporting error",
            },
            "process_alive": False,
        }

    async def _cleanup_failed_processes(
        self, failed_processes: list[MultiProcessRunInfo]
    ) -> None:
        """Clean up failed processes immediately."""
        for info in failed_processes:
            if info.process:
                try:
                    await self._terminate_process(info)
                except Exception as e:
                    self.warning(
                        f"Failed to cleanup failed process {info.service_id}: {e}"
                    )

    async def _terminate_process(self, info: MultiProcessRunInfo) -> None:
        """Terminate a process gracefully, then forcefully if needed."""
        if not info.process or not info.process.is_alive():
            return

        info.process.terminate()
        # Don't wait long for cleanup during error handling
        await asyncio.to_thread(info.process.join, timeout=PROCESS_CLEANUP_TIMEOUT)

        if info.process.is_alive():
            info.process.kill()

    async def _wait_for_process(self, info: MultiProcessRunInfo) -> None:
        """Wait for a process to terminate with timeout handling."""
        if not info.process or not info.process.is_alive():
            return

        try:
            info.process.terminate()
            await asyncio.to_thread(
                info.process.join, timeout=TASK_CANCEL_TIMEOUT_SHORT
            )
            self.debug(
                f"Service {info.service_type} process stopped (pid: {info.process.pid})"
            )
        except asyncio.TimeoutError:
            self.warning(
                f"Service {info.service_type} process (pid: {info.process.pid}) did not terminate gracefully, killing"
            )
            info.process.kill()

    async def wait_for_all_services_start(
        self,
        stop_event: asyncio.Event,
        timeout_seconds: float = DEFAULT_SERVICE_START_TIMEOUT,
    ) -> None:
        """Wait for all required services to be started."""
        self.debug("Waiting for all required services to start...")
        self.warning(
            "Waiting for all required services to start is not implemented for multiprocessing"
        )
