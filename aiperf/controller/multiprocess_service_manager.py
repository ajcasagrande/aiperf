# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
import asyncio
import multiprocessing
import uuid
from multiprocessing import Process
from multiprocessing.context import ForkProcess, SpawnProcess

from pydantic import BaseModel, ConfigDict, Field

from aiperf.common.bootstrap import bootstrap_and_run_service
from aiperf.common.config import ServiceConfig, SystemControllerConfig, UserConfig
from aiperf.common.constants import (
    DEFAULT_SERVICE_REGISTRATION_TIMEOUT,
    TASK_CANCEL_TIMEOUT_SHORT,
)
from aiperf.common.decorators import implements_protocol
from aiperf.common.enums import ServiceRunType
from aiperf.common.factories import ServiceFactory, ServiceManagerFactory
from aiperf.common.protocols import ServiceManagerProtocol
from aiperf.common.service_registry import ServiceRegistry
from aiperf.common.types import ServiceTypeT
from aiperf.controller.base_service_manager import BaseServiceManager


class MultiProcessRunInfo(BaseModel):
    """Information about a service running as a multiprocessing process."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    process: Process | SpawnProcess | ForkProcess | None = Field(default=None)
    service_type: ServiceTypeT = Field(
        ...,
        description="Type of service running in the process",
    )
    service_id: str = Field(
        ...,
        description="ID of the service running in the process",
    )


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
        log_queue: "multiprocessing.Queue | None" = None,
        system_config: SystemControllerConfig | None = None,
        **kwargs,
    ):
        super().__init__(required_services, service_config, user_config, **kwargs)
        self.multi_process_info: list[MultiProcessRunInfo] = []
        self.log_queue = log_queue
        self.system_config = system_config
        self.expected_node_controllers = (
            system_config.node_controllers if system_config else 0
        )

    async def run_service(
        self, service_type: ServiceTypeT, num_replicas: int = 1
    ) -> None:
        """Run a service with the given number of replicas."""
        service_class = ServiceFactory.get_class_from_type(service_type)

        for _ in range(num_replicas):
            service_id = f"{service_type}_{uuid.uuid4().hex[:8]}"
            await ServiceRegistry.expect_service(service_id, service_class.service_type)
            process = Process(
                target=bootstrap_and_run_service,
                name=f"{service_type}_process",
                kwargs={
                    "service_class": service_class,
                    "service_id": service_id,
                    "service_config": self.service_config,
                    "user_config": self.user_config,
                    "log_queue": self.log_queue,
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
        timeout_seconds: float = DEFAULT_SERVICE_REGISTRATION_TIMEOUT,
    ) -> None:
        """Wait for all required services to be registered.

        Args:
            timeout_seconds: Maximum time to wait in seconds

        Raises:
            Exception if any service failed to register, None otherwise
        """
        self.info("Waiting for all required services to register...")
        return await ServiceRegistry.wait_for_all(timeout_seconds)

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
