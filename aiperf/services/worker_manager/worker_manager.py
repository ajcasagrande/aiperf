# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
import asyncio
import multiprocessing
import os
import sys
from multiprocessing import Process
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from aiperf.common.bootstrap import bootstrap_and_run_service
from aiperf.common.config.service_config import ServiceConfig
from aiperf.common.enums import ServiceRunType, ServiceType
from aiperf.common.exceptions import ConfigError
from aiperf.common.factories import ServiceFactory
from aiperf.common.hooks import (
    on_cleanup,
    on_configure,
    on_init,
    on_start,
    on_stop,
)
from aiperf.common.messages import Message
from aiperf.common.service.base_component_service import BaseComponentService
from aiperf.services.worker import worker
from aiperf.services.worker.worker import MultiWorkerProcess


class WorkerProcess(BaseModel):
    """Information about a worker process."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    worker_id: str = Field(..., description="ID of the worker process")
    process: Any = Field(None, description="Process object or task")
    multi_worker_process: MultiWorkerProcess = Field(
        ..., description="Multi worker process object"
    )


@ServiceFactory.register(ServiceType.WORKER_MANAGER)
class WorkerManager(BaseComponentService):
    """
    The WorkerManager service is primary responsibility is to pull data from the dataset manager
    after receiving the timing credit from the timing manager. It will then push the request data
    to the worker to issue to the request.
    """

    def __init__(
        self, service_config: ServiceConfig, service_id: str | None = None
    ) -> None:
        super().__init__(service_config=service_config, service_id=service_id)
        self.logger.debug("Initializing worker manager")
        self.workers: dict[str, WorkerProcess] = {}
        # TODO: Need to implement some sort of max workers
        self.cpu_count = multiprocessing.cpu_count()
        self.max_concurrency = int(os.environ.get("MAX_CONCURRENCY", 100))
        self.worker_count = min(
            self.max_concurrency + 1,
            int(os.getenv("AIPERF_WORKERS", self.cpu_count - 1)),
        )
        self.logger.info(
            "Detected %s CPU threads. Spawning %s worker processes",
            self.cpu_count,
            self.worker_count,
        )

    @property
    def service_type(self) -> ServiceType:
        """The type of service."""
        return ServiceType.WORKER_MANAGER

    @on_init
    async def _initialize(self) -> None:
        """Initialize worker manager-specific components."""
        self.logger.debug("Initializing worker manager")

        # Spawn workers based on CPU count
        if self.service_config.service_run_type == ServiceRunType.MULTIPROCESSING:
            await self._spawn_multiprocessing_workers()

        elif self.service_config.service_run_type == ServiceRunType.KUBERNETES:
            await self._spawn_kubernetes_workers()

        else:
            self.logger.warning(
                f"Unsupported run type: {self.service_config.service_run_type}"
            )
            raise ConfigError(
                f"Unsupported run type: {self.service_config.service_run_type}"
            )

    @on_start
    async def _start(self) -> None:
        """Start the worker manager."""
        self.logger.debug("Starting worker manager")

    @on_stop
    async def _stop(self) -> None:
        """Stop the worker manager."""
        self.logger.debug("Stopping worker manager")
        # TODO: This needs to be investigated, as currently we handle the exit signal
        #       by all workers already, so need to understand best way to handle this
        # Stop all workers
        if self.service_config.service_run_type == ServiceRunType.MULTIPROCESSING:
            await self._stop_multiprocessing_workers()
        elif self.service_config.service_run_type == ServiceRunType.KUBERNETES:
            await self._stop_kubernetes_workers()
        else:
            self.logger.warning(
                f"Unsupported run type: {self.service_config.service_run_type}"
            )

    @on_cleanup
    async def _cleanup(self) -> None:
        """Clean up worker manager-specific components."""
        self.logger.debug("Cleaning up worker manager")
        self.workers.clear()

    async def _spawn_kubernetes_workers(self) -> None:
        """Spawn worker processes using Kubernetes."""
        self.logger.debug(f"Spawning {self.worker_count} worker pods")

        # TODO: Implement Kubernetes start
        raise NotImplementedError("Kubernetes start not implemented")

    async def _stop_kubernetes_workers(self) -> None:
        """Stop worker processes using Kubernetes."""
        self.logger.debug("Stopping all worker processes")

        # TODO: Implement Kubernetes stop
        raise NotImplementedError("Kubernetes stop not implemented")

    async def _spawn_multiprocessing_workers(self) -> None:
        """Spawn worker processes using multiprocessing."""
        self.logger.debug(f"Spawning {self.worker_count} worker processes")

        for i in range(self.worker_count):
            multi_worker_process = worker.MultiWorkerProcess(
                service_config=self.service_config, service_id=f"worker_{i}"
            )
            worker_id = f"worker_{i}"
            process = Process(
                target=bootstrap_and_run_service,
                name=f"worker_{i}_process",
                args=(
                    MultiWorkerProcess,
                    self.service_config,
                ),
                kwargs={"service_id": f"worker_{i}"},
                daemon=True,
            )
            process.start()

            self.workers[worker_id] = WorkerProcess(
                worker_id=worker_id,
                process=process,
                multi_worker_process=multi_worker_process,
            )
            self.logger.debug(
                f"Started worker process {worker_id} (pid: {process.pid})"
            )

    async def _stop_multiprocessing_workers(self) -> None:
        """Stop all multiprocessing worker processes."""
        self.logger.debug("Stopping all worker processes")

        # First terminate all processes
        for worker_id, worker_info in self.workers.items():
            self.logger.debug(f"Stopping worker process {worker_id} {worker_info}")
            multi_worker_process = worker_info.multi_worker_process
            multi_worker_process.stop_event.set()
            process = worker_info.process
            if process and process.is_alive():
                self.logger.debug(
                    f"Terminating worker process {worker_id} (pid: {process.pid})"
                )
                process.terminate()

        # Then wait for all to finish
        await asyncio.gather(
            *[
                self._wait_for_process(worker_id, worker_info.process)
                for worker_id, worker_info in self.workers.items()
                if worker_info.process
            ]
        )

        self.logger.debug("All worker processes stopped")

    async def _wait_for_process(self, worker_id: str, process: Process) -> None:
        """Wait for a process to terminate with timeout handling."""
        try:
            await asyncio.wait_for(
                asyncio.to_thread(process.join, timeout=1.0),  # Add timeout to join
                timeout=5.0,  # Overall timeout
            )
            self.logger.debug(
                f"Worker process {worker_id} (pid: {process.pid}) stopped"
            )
        except asyncio.TimeoutError:
            self.logger.warning(
                f"Worker process {worker_id} (pid: {process.pid}) did not "
                f"terminate gracefully, killing"
            )
            process.kill()

    @on_configure
    async def _configure(self, message: Message) -> None:
        """Configure the worker manager."""
        self.logger.debug(f"Configuring worker manager with message: {message}")
        # TODO: Implement worker manager configuration


def main() -> None:
    """Main entry point for the worker manager."""

    from aiperf.common.bootstrap import bootstrap_and_run_service

    bootstrap_and_run_service(WorkerManager)


if __name__ == "__main__":
    sys.exit(main())
