# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
import time
from collections import namedtuple
from functools import cached_property
from typing import Literal

from pydantic import BaseModel, Field

from aiperf.common.messages import BaseServiceMessage, MessageType

# TODO: These can be different for each platform. (below is linux specific)
IOCounters = namedtuple(
    "IOCounters",
    [
        "read_count",  # system calls io read
        "write_count",  # system calls io write
        "read_bytes",  # bytes read (disk io)
        "write_bytes",  # bytes written (disk io)
        "read_chars",  # io read bytes (system calls)
        "write_chars",  # io write bytes (system calls)
    ],
)

CPUTimes = namedtuple(
    "CPUTimes",
    ["user", "system", "iowait"],
)

CtxSwitches = namedtuple("CtxSwitches", ["voluntary", "involuntary"])


class ProcessHealth(BaseModel):
    """Model for process health data."""

    pid: int | None = Field(
        default=None,
        description="The PID of the process",
    )
    create_time: float = Field(
        ..., description="The creation time of the process in seconds"
    )
    uptime: float = Field(..., description="The uptime of the process in seconds")
    cpu_usage: float = Field(
        ..., description="The current CPU usage of the process in %"
    )
    memory_usage: float = Field(
        ..., description="The current memory usage of the process in MiB (rss)"
    )
    io_counters: IOCounters | tuple | None = Field(
        default=None,
        description="The current I/O counters of the process (read_count, write_count, read_bytes, write_bytes, read_chars, write_chars)",
    )
    cpu_times: CPUTimes | tuple | None = Field(
        default=None,
        description="The current CPU times of the process (user, system, iowait)",
    )
    num_ctx_switches: CtxSwitches | tuple | None = Field(
        default=None,
        description="The current number of context switches (voluntary, involuntary)",
    )
    num_threads: int | None = Field(
        default=None,
        description="The current number of threads",
    )


class WorkerHealthMessage(BaseServiceMessage):
    """Message for a worker health check."""

    message_type: Literal[MessageType.WORKER_HEALTH] = MessageType.WORKER_HEALTH

    # override request_ns to be auto-filled if not provided
    request_ns: int = Field(  # type: ignore
        default_factory=time.time_ns,
        description="Timestamp of the request",
    )

    process: ProcessHealth = Field(..., description="The health of the worker process")

    # Worker specific fields
    total_tasks: int = Field(
        ..., description="The total number of tasks that have been attempted"
    )
    completed_tasks: int = Field(
        ..., description="The number of tasks that have been completed successfully"
    )
    failed_tasks: int = Field(..., description="The number of tasks that have failed")
    warmup_tasks: int = Field(
        ...,
        description="The number of warmup tasks that have been completed successfully",
    )
    warmup_failed_tasks: int = Field(
        ..., description="The number of warmup tasks that have failed"
    )

    @cached_property
    def in_progress_tasks(self) -> int:
        """The number of tasks that are in progress."""
        return self.total_tasks - self.completed_tasks - self.failed_tasks

    @cached_property
    def warmup_in_progress_tasks(self) -> int:
        """The number of warmup tasks that are in progress."""
        return self.warmup_total_tasks - self.warmup_tasks - self.warmup_failed_tasks

    @cached_property
    def warmup_total_tasks(self) -> int:
        """The total number of warmup tasks that have been attempted."""
        return self.warmup_tasks + self.warmup_failed_tasks

    @cached_property
    def request_rate(self) -> float:
        """The estimated request rate of the worker in requests per second."""
        return (
            self.total_tasks / self.process.uptime if self.process.uptime > 0 else 0.0
        )

    @cached_property
    def average_response_time(self) -> float:
        """The estimated average response time of the worker in seconds."""
        return self.total_tasks / self.request_rate if self.request_rate > 0 else 0.0


# TODO: This is a work in progress.
class WorkerHealthSummary(BaseModel):
    """Summary of all workers' health data."""

    workers: list[WorkerHealthMessage] = Field(
        ..., description="The health of the workers"
    )

    @cached_property
    def total_tasks(self) -> int:
        """The total number of tasks that have been attempted."""
        return sum(worker.total_tasks for worker in self.workers)

    @cached_property
    def completed_tasks(self) -> int:
        """The number of tasks that have been completed successfully."""
        return sum(worker.completed_tasks for worker in self.workers)

    @cached_property
    def failed_tasks(self) -> int:
        """The number of tasks that have failed."""
        return sum(worker.failed_tasks for worker in self.workers)

    @cached_property
    def warmup_tasks(self) -> int:
        """The number of warmup tasks that have been completed successfully."""
        return sum(worker.warmup_tasks for worker in self.workers)

    @cached_property
    def warmup_failed_tasks(self) -> int:
        """The number of warmup tasks that have failed."""
        return sum(worker.warmup_failed_tasks for worker in self.workers)

    @cached_property
    def warmup_in_progress_tasks(self) -> int:
        """The number of warmup tasks that are in progress."""
        return sum(worker.warmup_in_progress_tasks for worker in self.workers)

    @cached_property
    def warmup_total_tasks(self) -> int:
        """The total number of warmup tasks that have been attempted."""
        return self.warmup_tasks + self.warmup_failed_tasks

    @cached_property
    def total_cpu_usage(self) -> float:
        """The total CPU usage of all workers."""
        return sum(worker.process.cpu_usage for worker in self.workers)

    @cached_property
    def total_memory_usage(self) -> float:
        """The total memory usage of all workers."""
        return sum(worker.process.memory_usage for worker in self.workers)

    @cached_property
    def average_uptime(self) -> float:
        """The average uptime of all workers."""
        return sum(worker.process.uptime for worker in self.workers) / len(self.workers)

    @cached_property
    def average_cpu_usage(self) -> float:
        """The average CPU usage of all workers."""
        return sum(worker.process.cpu_usage for worker in self.workers) / len(
            self.workers
        )

    @cached_property
    def average_memory_usage(self) -> float:
        """The average memory usage of all workers."""
        return sum(worker.process.memory_usage for worker in self.workers) / len(
            self.workers
        )

    @cached_property
    def min_cpu_usage(self) -> float:
        """The minimum CPU usage of all workers."""
        return min(worker.process.cpu_usage for worker in self.workers)

    @cached_property
    def max_cpu_usage(self) -> float:
        """The maximum CPU usage of all workers."""
        return max(worker.process.cpu_usage for worker in self.workers)

    @cached_property
    def min_memory_usage(self) -> float:
        """The minimum memory usage of all workers."""
        return min(worker.process.memory_usage for worker in self.workers)

    @cached_property
    def max_memory_usage(self) -> float:
        """The maximum memory usage of all workers."""
        return max(worker.process.memory_usage for worker in self.workers)
