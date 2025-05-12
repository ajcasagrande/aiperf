import sys
import os
import asyncio
import multiprocessing
from typing import List, Dict, Any

from aiperf.common.config.service_config import ServiceConfig
from aiperf.common.enums import ServiceType, Topic, ServiceRunType
from aiperf.common.models.messages import BaseMessage
from aiperf.common.service import ServiceBase
from aiperf.services.worker.main import Worker
from aiperf.common.bootstrap import bootstrap_and_run_service
from pydantic import BaseModel, Field


class WorkerProcess(BaseModel):
    """Information about a worker process."""
    worker_id: str = Field(..., description="ID of the worker process")
    process: Any = Field(None, description="Process object or task")


class WorkerManager(ServiceBase):
    def __init__(self, config: ServiceConfig) -> None:
        super().__init__(service_type=ServiceType.WORKER_MANAGER, config=config)
        self.logger.debug("Initializing worker manager")
        self.workers: Dict[str, WorkerProcess] = {}
        self.cpu_count = multiprocessing.cpu_count()
        self.logger.info(f"Detected {self.cpu_count} CPU threads")

    async def _initialize(self) -> None:
        """Initialize worker manager-specific components."""
        self.logger.debug("Initializing worker manager")

    async def _on_start(self) -> None:
        """Start the worker manager."""
        self.logger.debug("Starting worker manager")
        
        # Spawn workers based on CPU count
        if self.config.service_run_type == ServiceRunType.ASYNC:
            await self._spawn_async_workers()
        elif self.config.service_run_type == ServiceRunType.MULTIPROCESSING:
            self._spawn_multiprocessing_workers()
        else:
            self.logger.warning(f"Unsupported run type: {self.config.service_run_type}")

    async def _on_stop(self) -> None:
        """Stop the worker manager."""
        self.logger.debug("Stopping worker manager")

    async def _cleanup(self) -> None:
        """Clean up worker manager-specific components."""
        self.logger.debug("Cleaning up worker manager")
        self.workers.clear()

    async def _process_message(self, topic: Topic, message: BaseMessage) -> None:
        """Process a message from another service.

        Args:
            topic: The topic the message was received on
            message: The message to process
        """
        self.logger.debug(f"Processing message: {topic}, {message}")

    async def _spawn_async_workers(self) -> None:
        """Spawn worker tasks using asyncio."""
        self.logger.info(f"Spawning {self.cpu_count} worker async tasks")
        
        for i in range(self.cpu_count):
            worker_id = f"worker_{i}"
            worker_task = asyncio.create_task(self._run_worker_task(worker_id))
            self.workers[worker_id] = WorkerProcess(worker_id=worker_id, process=worker_task)
            self.logger.info(f"Started async worker task {worker_id}")

    async def _run_worker_task(self, worker_id: str) -> None:
        """Run a worker task."""
        self.logger.info(f"Starting worker task {worker_id}")
        # Create a worker service with the same config
        worker = Worker(self.config)
        try:
            await worker.run()
        except Exception as e:
            self.logger.error(f"Worker {worker_id} failed: {e}")
        finally:
            self.logger.info(f"Worker task {worker_id} stopped")

    async def _stop_async_workers(self) -> None:
        """Stop all async worker tasks."""
        self.logger.info("Stopping all worker tasks")
        
        stop_tasks = []
        for worker_id, worker_info in self.workers.items():
            if worker_info.process and not worker_info.process.done():
                self.logger.info(f"Cancelling worker task {worker_id}")
                worker_info.process.cancel()
                stop_tasks.append(worker_info.process)
        
        if stop_tasks:
            await asyncio.gather(*stop_tasks, return_exceptions=True)
        
        self.logger.info("All worker tasks stopped")

    def _spawn_multiprocessing_workers(self) -> None:
        """Spawn worker processes using multiprocessing."""
        self.logger.info(f"Spawning {self.cpu_count} worker processes")
        
        for i in range(self.cpu_count):
            worker_id = f"worker_{i}"
            process = multiprocessing.Process(
                target=bootstrap_and_run_service,
                name=f"worker_{i}_process",
                args=(Worker, self.config),
                daemon=True
            )
            process.start()
            self.workers[worker_id] = WorkerProcess(worker_id=worker_id, process=process)
            self.logger.info(f"Started worker process {worker_id} (pid: {process.pid})")
    
    async def _stop_multiprocessing_workers(self) -> None:
        """Stop all multiprocessing worker processes."""
        self.logger.info("Stopping all worker processes")
        
        # First terminate all processes
        for worker_id, worker_info in self.workers.items():
            self.logger.debug(f"Stopping worker process {worker_id} {worker_info}")
            process = worker_info.process
            if process and process.is_alive():
                self.logger.info(f"Terminating worker process {worker_id} (pid: {process.pid})")
                process.terminate()
        
        # Then wait for all to finish
        await asyncio.gather(
            *[
                self._wait_for_process(worker_id, worker_info.process)
                for worker_id, worker_info in self.workers.items()
                if worker_info.process
            ]
        )
        
        self.logger.info("All worker processes stopped")
    
    async def _wait_for_process(self, worker_id: str, process: multiprocessing.Process) -> None:
        """Wait for a process to terminate with timeout handling."""
        try:
            await asyncio.wait_for(
                asyncio.to_thread(process.join, timeout=1.0),  # Add timeout to join
                timeout=5.0,  # Overall timeout
            )
            self.logger.info(f"Worker process {worker_id} (pid: {process.pid}) stopped")
        except asyncio.TimeoutError:
            self.logger.warning(
                f"Worker process {worker_id} (pid: {process.pid}) did not terminate gracefully, killing"
            )
            process.kill()


def main() -> None:
    from aiperf.common.bootstrap import bootstrap_and_run_service

    bootstrap_and_run_service(WorkerManager)


if __name__ == "__main__":
    sys.exit(main())
