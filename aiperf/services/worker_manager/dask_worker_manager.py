#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#  http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
"""
Dask-based worker manager for AIPerf system.

This module provides a scalable, distributed worker management system using Dask
for dynamic worker scaling and efficient task distribution.
"""

import asyncio
import contextlib
import multiprocessing
import random
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any
from uuid import uuid4

from dask.distributed import (
    Client,
    LocalCluster,
    Worker,
)
from distributed.comm.core import CommClosedError
from pydantic import BaseModel, Field, field_validator

from aiperf.common.comms.client_enums import (
    ClientType,
    PullClientType,
    PushClientType,
)
from aiperf.common.config.service_config import ServiceConfig
from aiperf.common.decorators import (
    on_configure,
    on_init,
    on_start,
    on_stop,
)
from aiperf.common.enums import (
    ServiceState,
    ServiceType,
    Topic,
)
from aiperf.common.exceptions import (
    ServiceConfigureError,
    ServiceInitializationError,
)
from aiperf.common.models import (
    BasePayload,
    CreditDropMessage,
    CreditReturnPayload,
    Message,
)
from aiperf.common.service.base_component_service import BaseComponentService


# Task functions must be defined outside the class to avoid serialization issues
async def process_credit_task(credit_message_dict: dict) -> dict:
    """Process a credit drop task (runs on Dask worker)."""
    import asyncio
    import time

    from dask.distributed import get_worker

    # Get worker information
    worker = get_worker()
    worker_id = worker.id

    # Simulate processing work (non-blocking)
    start_time = time.time_ns()

    # Use a small sleep to simulate work without blocking the entire worker
    # In a real scenario, this would be actual computation
    await asyncio.sleep(random.random() * 3)  # Keep this short to avoid blocking

    processing_time = time.time_ns() - start_time

    return {
        "worker_id": worker_id,
        "amount": credit_message_dict.get("amount", 0),
        "processing_time": processing_time,
        "status": "completed",
    }


def health_check_task() -> dict:
    """Perform health check on worker (runs on Dask worker)."""
    import time

    import psutil
    from dask.distributed import get_worker

    worker = get_worker()

    return {
        "worker_id": worker.id,
        "cpu_usage": psutil.cpu_percent(interval=0.1),  # Reduced interval
        "memory_usage": psutil.virtual_memory().percent,
        "timestamp": time.time_ns(),
        "status": "healthy",
    }


def compute_task(data: Any) -> dict:
    """Generic compute task (runs on Dask worker)."""
    from dask.distributed import get_worker

    worker = get_worker()

    # Placeholder for actual computation
    result = {"worker_id": worker.id, "result": "computed", "input": str(data)}

    return result


class WorkerState(StrEnum):
    """States that a worker can be in."""

    PENDING = "pending"
    RUNNING = "running"
    IDLE = "idle"
    BUSY = "busy"
    ERROR = "error"
    TERMINATED = "terminated"


class ScalingStrategy(StrEnum):
    """Strategies for scaling workers."""

    MANUAL = "manual"  # Manual scaling only
    AUTO_CPU = "auto_cpu"  # Scale based on CPU usage
    AUTO_QUEUE = "auto_queue"  # Scale based on queue length
    AUTO_ADAPTIVE = "auto_adaptive"  # Adaptive scaling based on multiple metrics


class WorkerResourceProfile(StrEnum):
    """Predefined resource profiles for workers."""

    MICRO = "micro"  # 1 CPU, 1GB RAM
    SMALL = "small"  # 2 CPUs, 2GB RAM
    MEDIUM = "medium"  # 4 CPUs, 4GB RAM
    LARGE = "large"  # 8 CPUs, 8GB RAM
    XLARGE = "xlarge"  # 16 CPUs, 16GB RAM


@dataclass
class WorkerMetrics:
    """Metrics for a worker instance."""

    worker_id: str
    state: WorkerState
    cpu_usage: float
    memory_usage: float
    tasks_completed: int
    tasks_failed: int
    uptime: float
    last_heartbeat: float


@dataclass
class ClusterMetrics:
    """Overall cluster metrics."""

    total_workers: int
    active_workers: int
    pending_tasks: int
    completed_tasks: int
    failed_tasks: int
    cpu_utilization: float
    memory_utilization: float
    queue_length: int


class DaskWorkerConfig(BaseModel):
    """Configuration for Dask worker deployment."""

    # Cluster configuration
    scheduler_port: int = Field(
        default=8786,
        description="Port for the Dask scheduler",
        ge=1024,
        le=65535,
    )
    dashboard_port: int = Field(
        default=8787,
        description="Port for the Dask dashboard",
        ge=1024,
        le=65535,
    )

    # Worker configuration
    min_workers: int = Field(
        default=10,
        description="Minimum number of workers to maintain",
        ge=1,
    )
    max_workers: int = Field(
        default=200,
        description="Maximum number of workers allowed",
        ge=1,
    )
    initial_workers: int = Field(
        default=20,
        description="Initial number of workers to start",
        ge=1,
    )

    # Resource configuration
    worker_profile: WorkerResourceProfile = Field(
        default=WorkerResourceProfile.MEDIUM,
        description="Resource profile for workers",
    )
    threads_per_worker: int = Field(
        default=20,
        description="Number of threads per worker",
        ge=1,
        le=16,
    )
    memory_limit: str = Field(
        default="4GB",
        description="Memory limit per worker",
    )

    # Scaling configuration
    scaling_strategy: ScalingStrategy = Field(
        default=ScalingStrategy.AUTO_ADAPTIVE,
        description="Strategy for automatic scaling",
    )
    scale_up_threshold: float = Field(
        default=0.8,
        description="Threshold for scaling up (CPU usage or queue ratio)",
        ge=0.0,
        le=1.0,
    )
    scale_down_threshold: float = Field(
        default=0.3,
        description="Threshold for scaling down",
        ge=0.0,
        le=1.0,
    )
    scaling_interval: int = Field(
        default=30,
        description="Interval between scaling decisions (seconds)",
        ge=5,
    )

    # Performance configuration
    task_timeout: int = Field(
        default=300,
        description="Task timeout in seconds",
        ge=1,
    )
    heartbeat_interval: int = Field(
        default=10,
        description="Worker heartbeat interval in seconds",
        ge=1,
    )

    # Directory configuration
    worker_log_dir: Path | None = Field(
        default=None,
        description="Directory for worker logs",
    )
    temp_dir: Path | None = Field(
        default=None,
        description="Temporary directory for workers",
    )

    @field_validator("initial_workers")
    @classmethod
    def validate_initial_workers(cls, v: int, info) -> int:
        """Validate that initial_workers is within min/max bounds."""
        if hasattr(info, "data"):
            min_workers = info.data.get("min_workers", 1)
            max_workers = info.data.get("max_workers", multiprocessing.cpu_count())
            if not min_workers <= v <= max_workers:
                raise ValueError(
                    f"initial_workers must be between {min_workers} and {max_workers}"
                )
        return v


class DaskWorkerManager(BaseComponentService):
    """
    Dask-based worker manager for scalable distributed processing.

    This class provides:
    - Dynamic worker scaling based on configurable strategies
    - Comprehensive monitoring and metrics collection
    - Fault tolerance and automatic recovery
    - Integration with AIPerf's credit system
    - Resource-aware worker management
    """

    def __init__(
        self,
        service_config: ServiceConfig,
        service_id: str | None = None,
        config: DaskWorkerConfig | None = None,
    ) -> None:
        """Initialize the Dask worker manager."""
        super().__init__(service_config=service_config, service_id=service_id)

        self.config = config or DaskWorkerConfig()
        self.cluster: LocalCluster | None = None
        self.client: Client | None = None

        # Worker tracking
        self.worker_metrics: dict[str, WorkerMetrics] = {}
        self.pending_tasks: dict[str, Any] = {}
        self.completed_tasks: int = 0
        self.failed_tasks: int = 0

        # Scaling state
        self._last_scale_time = 0.0
        self._scaling_lock = asyncio.Lock()
        self._monitoring_task: asyncio.Task | None = None
        self._scaling_task: asyncio.Task | None = None

        # Task processing
        self._task_handlers: dict[str, Callable] = {}
        self._credit_queue: asyncio.Queue = asyncio.Queue()

        self.logger.info(f"Initialized Dask worker manager with config: {self.config}")

    @property
    def service_type(self) -> ServiceType:
        """The type of service."""
        return ServiceType.WORKER_MANAGER

    @property
    def required_clients(self) -> list[ClientType]:
        """The communication clients required by the service."""
        return [
            *(super().required_clients or []),
            PullClientType.CREDIT_DROP,
            PushClientType.CREDIT_RETURN,
        ]

    @on_init
    async def _on_init(self) -> None:
        """Initialize the Dask worker manager."""
        self.logger.info("Initializing Dask worker manager")

        try:
            await self._setup_directories()
            await self._initialize_cluster()
            await self._register_task_handlers()

        except Exception as e:
            self.logger.error(f"Failed to initialize Dask worker manager: {e}")
            raise ServiceInitializationError(
                f"Dask worker manager initialization failed: {e}"
            ) from e

    @on_start
    async def _start(self) -> None:
        """Start the Dask worker manager."""
        self.logger.info("Starting Dask worker manager")

        try:
            # Start the cluster and client
            await self._start_cluster()

            # Subscribe to credit drops
            await self.comms.pull(
                topic=Topic.CREDIT_DROP,
                callback=self._on_credit_drop,
            )

            # Start monitoring and scaling tasks
            self._monitoring_task = asyncio.create_task(self._monitoring_loop())
            self._scaling_task = asyncio.create_task(self._scaling_loop())

            # Start task processing
            asyncio.create_task(self._process_credit_queue())

            await self.set_state(ServiceState.RUNNING)
            self.logger.info("Dask worker manager started successfully")

        except Exception as e:
            self.logger.error(f"Failed to start Dask worker manager: {e}")
            raise ServiceInitializationError(
                f"Dask worker manager start failed: {e}"
            ) from e

    @on_stop
    async def _on_stop(self) -> None:
        """Stop the Dask worker manager."""
        self.logger.info("Stopping Dask worker manager")

        # Cancel monitoring tasks
        if self._monitoring_task and not self._monitoring_task.done():
            self._monitoring_task.cancel()
            with contextlib.suppress(asyncio.CancelledError, CommClosedError):
                await self._monitoring_task

        if self._scaling_task and not self._scaling_task.done():
            self._scaling_task.cancel()
            with contextlib.suppress(asyncio.CancelledError, CommClosedError):
                await self._scaling_task

        # Gracefully shutdown cluster
        await self._shutdown_cluster()

        self.logger.info("Dask worker manager stopped")

        await self._cleanup()

    # @on_cleanup
    async def _cleanup(self) -> None:
        """Clean up resources."""
        self.logger.info("Cleaning up Dask worker manager")

        # Ensure cluster is fully shutdown
        if self.client:
            try:
                self.logger.info("Closing client")
                await self.client.close()
            except TypeError:
                self.client.close()
            except CommClosedError:
                pass
            self.client = None

        if self.cluster:
            try:
                self.logger.info("Closing cluster")
                await self.cluster.close()
            except TypeError:
                self.cluster.close()
            except CommClosedError:
                pass
            self.cluster = None
        self.logger.info("Dask worker manager cleaned up")

    @on_configure
    async def _configure(self, payload: BasePayload) -> None:
        """Configure the worker manager."""
        self.logger.info(f"Configuring Dask worker manager with payload: {payload}")

        try:
            # Handle different configuration updates
            payload_dict = (
                payload.model_dump() if hasattr(payload, "model_dump") else {}
            )

            if "min_workers" in payload_dict:
                await self._update_worker_scaling(
                    min_workers=payload_dict["min_workers"],
                    max_workers=payload_dict.get(
                        "max_workers", self.config.max_workers
                    ),
                )

            if "scaling_strategy" in payload_dict:
                self.config.scaling_strategy = ScalingStrategy(
                    payload_dict["scaling_strategy"]
                )
                self.logger.info(
                    f"Updated scaling strategy to: {self.config.scaling_strategy}"
                )

        except Exception as e:
            self.logger.error(f"Failed to configure Dask worker manager: {e}")
            raise ServiceConfigureError(f"Configuration failed: {e}") from e

    async def _setup_directories(self) -> None:
        """Set up required directories."""
        if self.config.worker_log_dir:
            self.config.worker_log_dir.mkdir(parents=True, exist_ok=True)
            self.logger.info(f"Worker log directory: {self.config.worker_log_dir}")

        if self.config.temp_dir:
            self.config.temp_dir.mkdir(parents=True, exist_ok=True)
            self.logger.info(f"Temporary directory: {self.config.temp_dir}")

    async def _initialize_cluster(self) -> None:
        """Initialize the Dask cluster."""
        self.logger.info("Initializing Dask cluster")

        cluster_kwargs = {
            "n_workers": self.config.initial_workers,
            "threads_per_worker": self.config.threads_per_worker,
            "memory_limit": self.config.memory_limit,
            "scheduler_port": self.config.scheduler_port,
            "dashboard_address": f":{self.config.dashboard_port}",
            "silence_logs": False,
        }

        # Add optional directory configurations
        if self.config.worker_log_dir:
            cluster_kwargs["worker_class"] = Worker
            cluster_kwargs["worker_options"] = {
                "local_directory": str(self.config.temp_dir)
                if self.config.temp_dir
                else None
            }

        self.cluster = LocalCluster(asynchronous=True, **cluster_kwargs)
        if self.cluster and hasattr(self.cluster, "scheduler_address"):
            self.logger.info(
                f"Dask cluster initialized with scheduler at: {self.cluster.scheduler_address}"
            )
        else:
            self.logger.info("Dask cluster initialized")

    async def _start_cluster(self) -> None:
        """Start the Dask cluster and client."""
        if not self.cluster:
            raise ServiceInitializationError("Cluster not initialized")

        # Create client
        self.client = await Client(self.cluster, asynchronous=True)

        # Wait for workers to be ready
        await self._wait_for_workers(self.config.initial_workers, timeout=60)

        if self.client:
            scheduler_info = self.client.scheduler_info()
            worker_count = len(scheduler_info["workers"])
            self.logger.info(f"Dask cluster started with {worker_count} workers")

    async def _shutdown_cluster(self) -> None:
        """Gracefully shutdown the Dask cluster."""
        if self.client:
            # Cancel all pending tasks
            if self.pending_tasks:
                self.client.cancel(list(self.pending_tasks.keys()))

            # Close client (check if it's async)
            try:
                await self.client.close()
            except TypeError:
                # If close() is not async, call it synchronously
                self.client.close()
            self.client = None

        if self.cluster:
            # Close cluster (check if it's async)
            try:
                await self.cluster.close()
            except TypeError:
                # If close() is not async, call it synchronously
                self.cluster.close()
            self.cluster = None

    async def _wait_for_workers(self, count: int, timeout: int = 60) -> None:
        """Wait for a specific number of workers to be available."""
        start_time = time.time()

        while time.time() - start_time < timeout:
            if not self.client:
                raise ServiceInitializationError("Client not available")

            workers = self.client.scheduler_info()["workers"]
            if len(workers) >= count:
                self.logger.info(f"Successfully waited for {len(workers)} workers")
                return

            await asyncio.sleep(1)

        raise ServiceInitializationError(f"Timeout waiting for {count} workers")

    async def _register_task_handlers(self) -> None:
        """Register task handlers for different types of work."""
        self._task_handlers = {
            "process_credit": process_credit_task,
            "health_check": health_check_task,
            "compute": compute_task,
        }

        self.logger.info(f"Registered {len(self._task_handlers)} task handlers")

    async def _on_credit_drop(self, message: Message) -> None:
        """Handle incoming credit drops."""
        self.logger.debug(f"Received credit drop: {message}")

        try:
            # Extract credit drop message with proper type checking
            # Handle both CreditDropMessage and generic Message with credit payload
            if hasattr(message, "payload"):
                payload = message.payload
                if hasattr(payload, "amount") and isinstance(
                    payload.amount, (int, float)
                ):
                    credit_dict = {
                        "amount": payload.amount,
                        "timestamp": getattr(payload, "timestamp", time.time()),
                    }
                    # Add credit to processing queue (non-blocking)
                    self._credit_queue.put_nowait(credit_dict)
                    self.logger.debug(f"Credit queued: {credit_dict}")
                else:
                    self.logger.warning(f"Invalid credit payload format: {payload}")
            else:
                self.logger.warning(f"Invalid credit drop message format: {message}")

        except Exception as e:
            self.logger.error(f"Error processing credit drop: {e}")

    async def _process_credit_queue(self) -> None:
        """Process credits from the queue using Dask workers."""
        while True:
            try:
                # Get credit from queue (non-blocking with timeout)
                try:
                    credit_dict = await asyncio.wait_for(
                        self._credit_queue.get(), timeout=0.1
                    )
                except asyncio.TimeoutError:
                    # No credits in queue, continue loop
                    await asyncio.sleep(0.01)
                    continue

                # Submit task to Dask (non-blocking)
                if self.client:
                    future = self.client.submit(
                        process_credit_task,
                        credit_dict,
                        key=f"credit-{uuid4().hex[:8]}",
                        priority=1,
                    )

                    # Track the task
                    self.pending_tasks[future.key] = future

                    # Handle completion asynchronously (fire and forget)
                    asyncio.create_task(self._handle_task_completion(future))

                    self.logger.debug(f"Credit task submitted: {future.key}")

            except Exception as e:
                self.logger.error(f"Error in credit queue processing: {e}")
                await asyncio.sleep(0.1)

    async def _handle_task_completion(self, future) -> None:
        """Handle completion of a Dask task."""
        try:
            # Wait for the future to complete (this is async)
            result = await future

            # Remove from pending tasks
            self.pending_tasks.pop(future.key, None)
            self.completed_tasks += 1

            # Send credit return if result indicates success
            if result and isinstance(result, dict) and result.get("amount"):
                await self.comms.push(
                    topic=Topic.CREDIT_RETURN,
                    message=self.create_message(
                        payload=CreditReturnPayload(amount=result["amount"])
                    ),
                )

            self.logger.debug(f"Task {future.key} completed successfully")

        except Exception as e:
            self.pending_tasks.pop(future.key, None)
            self.failed_tasks += 1
            self.logger.error(f"Task {future.key} failed: {e}")

    async def _process_credit_task(
        self, credit_message: CreditDropMessage
    ) -> dict[str, Any]:
        """Process a credit drop task (runs on Dask worker)."""
        # This method is deprecated - use the standalone function instead
        return await process_credit_task({"amount": credit_message.payload.amount})

    def _health_check_task(self) -> dict[str, Any]:
        """Perform health check on worker (runs on Dask worker)."""
        # This method is deprecated - use the standalone function instead
        return health_check_task()

    def _compute_task(self, data: Any) -> Any:
        """Generic compute task (runs on Dask worker)."""
        # This method is deprecated - use the standalone function instead
        return compute_task(data)

    async def _monitoring_loop(self) -> None:
        """Main monitoring loop for collecting metrics."""
        while True:
            try:
                await self._collect_metrics()
                await asyncio.sleep(self.config.heartbeat_interval)

            except asyncio.CancelledError:
                self.logger.info("Monitoring loop cancelled")
                break
            except Exception as e:
                self.logger.error(f"Error in monitoring loop: {e}")
                await asyncio.sleep(5)

    async def _collect_metrics(self) -> None:
        """Collect metrics from all workers."""
        if not self.client:
            return

        try:
            # Submit health check tasks to all workers
            worker_count = len(self.client.scheduler_info()["workers"])
            if worker_count > 0:
                # Create a simple task that calls health_check_task without arguments
                futures = []
                for _ in range(worker_count):
                    future = self.client.submit(health_check_task)
                    futures.append(future)

                # Collect results with timeout (this must be awaited!)
                results = await asyncio.gather(*futures, return_exceptions=True)

                # Update worker metrics
                for result in results:
                    if isinstance(result, dict) and "worker_id" in result:
                        worker_id = result["worker_id"]
                        self.worker_metrics[worker_id] = WorkerMetrics(
                            worker_id=worker_id,
                            state=WorkerState.RUNNING,
                            cpu_usage=result.get("cpu_usage", 0.0),
                            memory_usage=result.get("memory_usage", 0.0),
                            tasks_completed=0,  # Would need to track this separately
                            tasks_failed=0,
                            uptime=0.0,
                            last_heartbeat=result.get("timestamp", time.time()),
                        )

        except Exception as e:
            self.logger.error(f"Error collecting metrics: {e}")

    async def _scaling_loop(self) -> None:
        """Main scaling loop for automatic worker scaling."""
        while True:
            try:
                if self.config.scaling_strategy != ScalingStrategy.MANUAL:
                    await self._evaluate_scaling()

                await asyncio.sleep(self.config.scaling_interval)

            except asyncio.CancelledError:
                self.logger.info("Scaling loop cancelled")
                break
            except Exception as e:
                self.logger.error(f"Error in scaling loop: {e}")
                await asyncio.sleep(10)

    async def _evaluate_scaling(self) -> None:
        """Evaluate whether to scale workers up or down."""
        if not self.client:
            return

        async with self._scaling_lock:
            current_time = time.time()

            # Avoid too frequent scaling
            if current_time - self._last_scale_time < self.config.scaling_interval:
                return

            cluster_metrics = await self._get_cluster_metrics()

            if self.config.scaling_strategy == ScalingStrategy.AUTO_CPU:
                await self._scale_based_on_cpu(cluster_metrics)
            elif self.config.scaling_strategy == ScalingStrategy.AUTO_QUEUE:
                await self._scale_based_on_queue(cluster_metrics)
            elif self.config.scaling_strategy == ScalingStrategy.AUTO_ADAPTIVE:
                await self._scale_adaptive(cluster_metrics)

            self._last_scale_time = current_time

    async def _get_cluster_metrics(self) -> ClusterMetrics:
        """Get overall cluster metrics."""
        if not self.client:
            return ClusterMetrics(0, 0, 0, 0, 0, 0.0, 0.0, 0)

        workers = self.client.scheduler_info()["workers"]
        active_workers = len([w for w in workers.values() if w["status"] == "running"])

        # Calculate average CPU and memory usage
        cpu_usage = (
            sum(m.cpu_usage for m in self.worker_metrics.values())
            / len(self.worker_metrics)
            if self.worker_metrics
            else 0.0
        )
        memory_usage = (
            sum(m.memory_usage for m in self.worker_metrics.values())
            / len(self.worker_metrics)
            if self.worker_metrics
            else 0.0
        )

        return ClusterMetrics(
            total_workers=len(workers),
            active_workers=active_workers,
            pending_tasks=len(self.pending_tasks),
            completed_tasks=self.completed_tasks,
            failed_tasks=self.failed_tasks,
            cpu_utilization=cpu_usage,
            memory_utilization=memory_usage,
            queue_length=self._credit_queue.qsize(),
        )

    async def _scale_based_on_cpu(self, metrics: ClusterMetrics) -> None:
        """Scale based on CPU utilization."""
        if metrics.cpu_utilization > self.config.scale_up_threshold * 100:
            await self._scale_up(1)
        elif metrics.cpu_utilization < self.config.scale_down_threshold * 100:
            await self._scale_down(1)

    async def _scale_based_on_queue(self, metrics: ClusterMetrics) -> None:
        """Scale based on queue length."""
        queue_ratio = metrics.queue_length / max(metrics.active_workers, 1)

        if (
            queue_ratio > self.config.scale_up_threshold * 10
        ):  # More than 8 tasks per worker
            await self._scale_up(min(2, metrics.queue_length // 10))
        elif (
            queue_ratio < self.config.scale_down_threshold * 2
        ):  # Less than 0.6 tasks per worker
            await self._scale_down(1)

    async def _scale_adaptive(self, metrics: ClusterMetrics) -> None:
        """Adaptive scaling based on multiple metrics."""
        # Combine CPU, memory, and queue metrics
        cpu_score = metrics.cpu_utilization / 100.0
        memory_score = metrics.memory_utilization / 100.0
        queue_score = min(1.0, metrics.queue_length / (metrics.active_workers * 5))

        combined_score = cpu_score * 0.4 + memory_score * 0.3 + queue_score * 0.3

        if combined_score > self.config.scale_up_threshold:
            scale_amount = min(3, int(combined_score * 2))
            await self._scale_up(scale_amount)
        elif combined_score < self.config.scale_down_threshold:
            await self._scale_down(1)

    async def _scale_up(self, amount: int) -> None:
        """Scale up workers by the specified amount."""
        if not self.cluster:
            return

        current_workers = len(self.cluster.workers)
        new_total = min(current_workers + amount, self.config.max_workers)

        if new_total > current_workers:
            self.cluster.scale(new_total)
            self.logger.info(
                f"Scaling up from {current_workers} to {new_total} workers"
            )

    async def _scale_down(self, amount: int) -> None:
        """Scale down workers by the specified amount."""
        if not self.cluster:
            return

        current_workers = len(self.cluster.workers)
        new_total = max(current_workers - amount, self.config.min_workers)

        if new_total < current_workers:
            self.cluster.scale(new_total)
            self.logger.info(
                f"Scaling down from {current_workers} to {new_total} workers"
            )

    async def _update_worker_scaling(self, min_workers: int, max_workers: int) -> None:
        """Update worker scaling parameters."""
        self.config.min_workers = min_workers
        self.config.max_workers = max_workers

        # Adjust current workers if needed
        if self.cluster:
            current_workers = len(self.cluster.workers)
            if current_workers < min_workers:
                await self._scale_up(min_workers - current_workers)
            elif current_workers > max_workers:
                await self._scale_down(current_workers - max_workers)

    async def get_cluster_status(self) -> dict[str, Any]:
        """Get comprehensive cluster status."""
        if not self.client:
            return {"status": "not_initialized"}

        metrics = await self._get_cluster_metrics()

        return {
            "cluster_metrics": metrics,
            "worker_metrics": list(self.worker_metrics.values()),
            "configuration": self.config.model_dump(),
            "scheduler_address": self.cluster.scheduler_address
            if self.cluster
            else None,
            "dashboard_link": self.cluster.dashboard_link if self.cluster else None,
        }

    async def submit_task(self, task_type: str, *args, **kwargs) -> str:
        """Submit a task to the cluster."""
        if not self.client or task_type not in self._task_handlers:
            raise ValueError(f"Invalid task type: {task_type}")

        handler = self._task_handlers[task_type]
        future = self.client.submit(handler, *args, **kwargs)

        # Track the task
        self.pending_tasks[future.key] = future

        # Handle completion asynchronously
        asyncio.create_task(self._handle_task_completion(future))

        return future.key


def main() -> None:
    """Main entry point for the Dask worker manager."""
    from aiperf.common.bootstrap import bootstrap_and_run_service

    bootstrap_and_run_service(DaskWorkerManager)


if __name__ == "__main__":
    sys.exit(main())
