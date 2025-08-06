# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

import asyncio
import multiprocessing
import uuid
from multiprocessing import Process
from multiprocessing.context import ForkProcess, SpawnProcess

from pydantic import BaseModel, ConfigDict, Field

from aiperf.common.bootstrap import bootstrap_and_run_service
from aiperf.common.config import ServiceConfig, UserConfig
from aiperf.common.constants import (
    DEFAULT_SERVICE_REGISTRATION_TIMEOUT,
    DEFAULT_SERVICE_START_TIMEOUT,
    TASK_CANCEL_TIMEOUT_SHORT,
)
from aiperf.common.decorators import implements_protocol
from aiperf.common.enums import ServiceRunType
from aiperf.common.exceptions import AIPerfError
from aiperf.common.factories import ServiceFactory, ServiceManagerFactory
from aiperf.common.protocols import ServiceManagerProtocol
from aiperf.common.registry.enhanced_service_registry_mixin import (
    EnhancedServiceRegistryMixin,
)
from aiperf.common.types import ServiceTypeT
from aiperf.controller.base_service_manager import BaseServiceManager


class EnhancedMultiProcessRunInfo(BaseModel):
    """Enhanced information about a service running as a multiprocessing process."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    process: Process | SpawnProcess | ForkProcess | None = Field(default=None)
    service_type: ServiceTypeT = Field(
        description="Type of service running in the process"
    )
    service_id: str = Field(description="ID of the service running in the process")
    start_time: float = Field(description="Timestamp when the process was started")
    termination_requested: bool = Field(
        default=False, description="Whether termination has been requested"
    )


@implements_protocol(ServiceManagerProtocol)
@ServiceManagerFactory.register(ServiceRunType.MULTIPROCESSING)
class EnhancedMultiProcessServiceManager(
    BaseServiceManager, EnhancedServiceRegistryMixin
):
    """Enhanced multiprocess service manager with atomic operations and proper cleanup."""

    def __init__(
        self,
        required_services: dict[ServiceTypeT, int],
        service_config: ServiceConfig,
        user_config: UserConfig,
        log_queue: "multiprocessing.Queue | None" = None,
        **kwargs,
    ):
        BaseServiceManager.__init__(
            self, required_services, service_config, user_config, **kwargs
        )
        EnhancedServiceRegistryMixin.__init__(self, **kwargs)

        self._process_info: dict[str, EnhancedMultiProcessRunInfo] = {}
        self._process_management_lock = asyncio.RLock()
        self._termination_lock = asyncio.Lock()
        self.log_queue = log_queue

    async def run_service(
        self, service_type: ServiceTypeT, num_replicas: int = 1
    ) -> None:
        """Run services with atomic process tracking and proper registration."""
        service_class = ServiceFactory.get_class_from_type(service_type)

        async with self._process_management_lock:
            for _ in range(num_replicas):
                service_id = f"{service_type}_{uuid.uuid4().hex[:8]}"

                process = Process(
                    target=bootstrap_and_run_service,
                    name=f"{service_type}_process_{service_id}",
                    kwargs={
                        "service_class": service_class,
                        "service_id": service_id,
                        "service_config": self.service_config,
                        "user_config": self.user_config,
                        "log_queue": self.log_queue,
                    },
                    daemon=True,
                )

                try:
                    process.start()

                    process_info = EnhancedMultiProcessRunInfo(
                        process=process,
                        service_type=service_type,
                        service_id=service_id,
                        start_time=asyncio.get_event_loop().time(),
                    )

                    self._process_info[service_id] = process_info

                    self.debug(
                        "Service %s started as process (pid: %s, service_id: %s)",
                        service_type,
                        process.pid,
                        service_id,
                    )

                except Exception as e:
                    self.error(
                        "Failed to start service %s with service_id %s: %s",
                        service_type,
                        service_id,
                        e,
                    )
                    if process.is_alive():
                        process.terminate()
                    raise

    async def stop_service(
        self, service_type: ServiceTypeT, service_id: str | None = None
    ) -> list[BaseException | None]:
        """Stop services with atomic cleanup and proper synchronization."""
        async with self._process_management_lock:
            processes_to_stop = []

            for process_service_id, info in list(self._process_info.items()):
                if (
                    info.service_type == service_type
                    and (service_id is None or process_service_id == service_id)
                    and not info.termination_requested
                ):
                    info.termination_requested = True
                    processes_to_stop.append((process_service_id, info))

            if not processes_to_stop:
                return []

            self.debug(
                "Stopping %s process(es) of type %s",
                len(processes_to_stop),
                service_type,
            )

            tasks = []
            for process_service_id, info in processes_to_stop:
                task = asyncio.create_task(
                    self._terminate_process_safely(process_service_id, info)
                )
                tasks.append(task)

            results = await asyncio.gather(*tasks, return_exceptions=True)

            for process_service_id, _ in processes_to_stop:
                await self.unregister_service(process_service_id)
                self._process_info.pop(process_service_id, None)

            return results

    async def shutdown_all_services(self) -> list[BaseException | None]:
        """Shutdown all services with proper synchronization and cleanup."""
        async with self._process_management_lock:
            if not self._process_info:
                return []

            self.debug("Shutting down %s service processes", len(self._process_info))

            processes_to_stop = []
            for service_id, info in list(self._process_info.items()):
                if not info.termination_requested:
                    info.termination_requested = True
                    processes_to_stop.append((service_id, info))

            tasks = []
            for service_id, info in processes_to_stop:
                task = asyncio.create_task(
                    self._terminate_process_safely(service_id, info)
                )
                tasks.append(task)

            results = await asyncio.gather(*tasks, return_exceptions=True)

            for service_id, _ in processes_to_stop:
                await self.unregister_service(service_id)

            self._process_info.clear()

            return results

    async def kill_all_services(self) -> list[BaseException | None]:
        """Force kill all services with immediate cleanup."""
        async with self._process_management_lock:
            if not self._process_info:
                return []

            self.debug("Force killing %s service processes", len(self._process_info))

            processes_to_kill = list(self._process_info.items())

            for service_id, info in processes_to_kill:
                if info.process and info.process.is_alive():
                    try:
                        info.process.kill()
                    except Exception as e:
                        self.warning(
                            "Failed to kill process for service %s: %s",
                            service_id,
                            e,
                        )

            tasks = []
            for service_id, info in processes_to_kill:
                task = asyncio.create_task(
                    self._wait_for_process_termination(service_id, info)
                )
                tasks.append(task)

            results = await asyncio.gather(*tasks, return_exceptions=True)

            for service_id, _ in processes_to_kill:
                await self.unregister_service(service_id)

            self._process_info.clear()

            return results

    async def wait_for_all_services_registration(
        self,
        stop_event: asyncio.Event,
        timeout_seconds: float = DEFAULT_SERVICE_REGISTRATION_TIMEOUT,
    ) -> None:
        """Wait for required services to be registered using the enhanced registry."""
        try:
            success = await self.wait_for_required_services(
                required_services=self.required_services,
                timeout=timeout_seconds,
            )

            if not success:
                raise AIPerfError("Some services failed to register within timeout")

        except asyncio.TimeoutError as e:
            for service_type in self.required_services:
                type_services = await self.get_registered_services_by_type(service_type)
                if not type_services:
                    self.error(
                        "Service type %s failed to register within timeout",
                        service_type,
                    )

            raise AIPerfError("Some services failed to register within timeout") from e

    async def wait_for_all_services_start(
        self,
        stop_event: asyncio.Event,
        timeout_seconds: float = DEFAULT_SERVICE_START_TIMEOUT,
    ) -> None:
        """Wait for all required services to reach running state."""
        from aiperf.common.enums.service_enums import LifecycleState

        start_time = asyncio.get_event_loop().time()

        while not stop_event.is_set():
            all_started = True

            for service_type in self.required_services:
                running_services = await self.get_registered_services_by_type(
                    service_type, state=LifecycleState.RUNNING
                )

                if len(running_services) < self.required_services[service_type]:
                    all_started = False
                    break

            if all_started:
                self.debug("All required services have started successfully")
                return

            current_time = asyncio.get_event_loop().time()
            if current_time - start_time > timeout_seconds:
                raise AIPerfError("Some services failed to start within timeout")

            await asyncio.sleep(0.5)

    async def get_process_info(
        self, service_id: str
    ) -> EnhancedMultiProcessRunInfo | None:
        """Get process information for a specific service."""
        async with self._process_management_lock:
            return self._process_info.get(service_id)

    async def get_all_process_info(self) -> dict[str, EnhancedMultiProcessRunInfo]:
        """Get process information for all managed services."""
        async with self._process_management_lock:
            return self._process_info.copy()

    async def _terminate_process_safely(
        self,
        service_id: str,
        info: EnhancedMultiProcessRunInfo,
    ) -> None:
        """Safely terminate a process with proper error handling."""
        async with self._termination_lock:
            if not info.process or not info.process.is_alive():
                return

            try:
                self.debug(
                    "Terminating process for service %s (pid: %s)",
                    service_id,
                    info.process.pid,
                )

                info.process.terminate()

                await asyncio.to_thread(
                    info.process.join, timeout=TASK_CANCEL_TIMEOUT_SHORT
                )

                self.debug(
                    "Process for service %s terminated gracefully",
                    service_id,
                )

            except Exception as e:
                self.warning(
                    "Process for service %s (pid: %s) did not terminate gracefully, forcing kill: %s",
                    service_id,
                    info.process.pid if info.process else "unknown",
                    e,
                )

                if info.process and info.process.is_alive():
                    try:
                        info.process.kill()
                        await asyncio.to_thread(info.process.join, timeout=1.0)
                    except Exception as kill_error:
                        self.error(
                            "Failed to kill process for service %s: %s",
                            service_id,
                            kill_error,
                        )

    async def _wait_for_process_termination(
        self,
        service_id: str,
        info: EnhancedMultiProcessRunInfo,
    ) -> None:
        """Wait for process termination after kill signal."""
        if not info.process:
            return

        try:
            await asyncio.to_thread(
                info.process.join, timeout=TASK_CANCEL_TIMEOUT_SHORT
            )

            self.debug(
                "Process for service %s terminated after kill signal",
                service_id,
            )

        except Exception as e:
            self.warning(
                "Process for service %s may not have terminated cleanly: %s",
                service_id,
                e,
            )
