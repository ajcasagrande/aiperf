# Chapter 8: Worker Manager

<!--
# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
-->

## Table of Contents
- [Worker Manager Responsibilities](#worker-manager-responsibilities)
- [Health Monitoring](#health-monitoring)
- [Auto-Scaling Logic](#auto-scaling-logic)
- [Status Tracking](#status-tracking)
- [Worker Lifecycle Management](#worker-lifecycle-management)
- [Implementation Details](#implementation-details)
- [Key Takeaways](#key-takeaways)

## Worker Manager Responsibilities

The Worker Manager (`/home/anthony/nvidia/projects/aiperf/aiperf/workers/worker_manager.py`) is responsible for managing the lifecycle and health of all worker processes.

### Primary Responsibilities

1. **Worker Spawning**: Request workers from System Controller
2. **Health Monitoring**: Track health metrics from all workers
3. **Status Classification**: Classify workers as healthy, idle, high-load, error, or stale
4. **Status Reporting**: Publish worker status summaries
5. **Future: Auto-Scaling**: Dynamically adjust worker count (planned)

### Initialization

```python
@ServiceFactory.register(ServiceType.WORKER_MANAGER)
class WorkerManager(BaseComponentService):
    def __init__(
        self,
        service_config: ServiceConfig,
        user_config: UserConfig,
        service_id: str | None = None,
        **kwargs,
    ):
        super().__init__(service_config, user_config, service_id, **kwargs)

        self.worker_infos: dict[str, WorkerStatusInfo] = {}
        self.cpu_count = multiprocessing.cpu_count()

        # Determine max workers
        self.max_concurrency = self.user_config.loadgen.concurrency
        self.max_workers = self.service_config.workers.max

        if self.max_workers is None:
            # Auto-calculate: 75% of CPU cores - 1, capped at 32
            self.max_workers = max(
                1,
                min(int(self.cpu_count * 0.75) - 1, DEFAULT_MAX_WORKERS_CAP)
            )

        # Cap by concurrency if in concurrency mode
        if self.max_concurrency and self.max_concurrency < self.max_workers:
            self.max_workers = self.max_concurrency

        # Ensure minimum
        self.max_workers = max(
            self.max_workers,
            self.service_config.workers.min or 1,
        )

        self.initial_workers = self.max_workers
```

## Health Monitoring

### Worker Status Information

```python
class WorkerStatusInfo(WorkerStats):
    worker_id: str
    last_error_ns: int | None
    last_high_load_ns: int | None
```

### Health Message Processing

```python
@on_message(MessageType.WORKER_HEALTH)
async def _on_worker_health(self, message: WorkerHealthMessage) -> None:
    worker_id = message.service_id
    info = self.worker_infos.get(worker_id)

    if not info:
        # Create new info
        info = WorkerStatusInfo(
            worker_id=worker_id,
            last_update_ns=time.time_ns(),
            status=WorkerStatus.HEALTHY,
            health=message.health,
            task_stats=message.task_stats,
        )
        self.worker_infos[worker_id] = info

    # Update status
    self._update_worker_status(info, message)
```

### Status Classification

```python
def _update_worker_status(
    self, info: WorkerStatusInfo, message: WorkerHealthMessage
) -> None:
    """Check the status of a worker."""
    info.last_update_ns = time.time_ns()

    # Error Status (failures increased)
    if message.task_stats.failed > info.task_stats.failed:
        info.last_error_ns = time.time_ns()
        info.status = WorkerStatus.ERROR
    elif (time.time_ns() - (info.last_error_ns or 0)) / NANOS_PER_SECOND < DEFAULT_WORKER_ERROR_RECOVERY_TIME:
        info.status = WorkerStatus.ERROR

    # High Load Status (high CPU usage)
    elif message.health.cpu_usage > DEFAULT_WORKER_HIGH_LOAD_CPU_USAGE:
        info.last_high_load_ns = time.time_ns()
        info.status = WorkerStatus.HIGH_LOAD
    elif (time.time_ns() - (info.last_high_load_ns or 0)) / NANOS_PER_SECOND < DEFAULT_WORKER_HIGH_LOAD_RECOVERY_TIME:
        info.status = WorkerStatus.HIGH_LOAD

    # Idle Status (no tasks)
    elif message.task_stats.total == 0 or message.task_stats.in_progress == 0:
        info.status = WorkerStatus.IDLE

    # Healthy Status
    else:
        info.status = WorkerStatus.HEALTHY

    # Update stats
    info.health = message.health
    info.task_stats = message.task_stats
```

### Status Enumerations

```python
class WorkerStatus(str, Enum):
    HEALTHY = "healthy"      # Normal operation
    IDLE = "idle"            # No work currently
    HIGH_LOAD = "high_load"  # High CPU usage
    ERROR = "error"          # Recent failures
    STALE = "stale"          # No recent updates
```

### Constants

```python
DEFAULT_WORKER_ERROR_RECOVERY_TIME = 30.0      # seconds
DEFAULT_WORKER_HIGH_LOAD_CPU_USAGE = 90.0      # percent
DEFAULT_WORKER_HIGH_LOAD_RECOVERY_TIME = 10.0  # seconds
DEFAULT_WORKER_STALE_TIME = 60.0               # seconds
DEFAULT_WORKER_CHECK_INTERVAL = 5.0            # seconds
DEFAULT_WORKER_STATUS_SUMMARY_INTERVAL = 2.0   # seconds
```

## Auto-Scaling Logic

### Current Implementation

Currently, Worker Manager starts a fixed number of workers:

```python
@on_start
async def _start(self) -> None:
    """Start worker manager-specific components."""
    self.debug("WorkerManager starting")

    # Request worker spawning from System Controller
    await self.send_command_and_wait_for_response(
        SpawnWorkersCommand(
            service_id=self.service_id,
            num_workers=self.initial_workers,
            target_service_type=ServiceType.SYSTEM_CONTROLLER,
        )
    )

    self.debug("WorkerManager started")
```

### Future Auto-Scaling

The architecture supports future auto-scaling based on:
- Worker status (too many idle = scale down, too many high-load = scale up)
- Request rate
- Queue depth
- Latency metrics

## Status Tracking

### Staleness Detection

Workers that stop reporting health become stale:

```python
@background_task(immediate=False, interval=DEFAULT_WORKER_CHECK_INTERVAL)
async def _worker_status_loop(self) -> None:
    """Check the status of all workers."""
    self.debug("Checking worker status")

    for _, info in self.worker_infos.items():
        # Check if worker hasn't reported recently
        if (time.time_ns() - (info.last_update_ns or 0)) / NANOS_PER_SECOND > DEFAULT_WORKER_STALE_TIME:
            info.status = WorkerStatus.STALE
```

### Status Summary Publishing

```python
@background_task(immediate=False, interval=DEFAULT_WORKER_STATUS_SUMMARY_INTERVAL)
async def _worker_summary_loop(self) -> None:
    """Generate a summary of the worker status."""
    summary = WorkerStatusSummaryMessage(
        service_id=self.service_id,
        worker_statuses={
            worker_id: info.status
            for worker_id, info in self.worker_infos.items()
        },
    )
    self.debug(f"Publishing worker status summary: {summary}")
    await self.publish(summary)
```

## Worker Lifecycle Management

### Shutdown Handling

```python
@on_stop
async def _stop(self) -> None:
    self.debug("WorkerManager stopping")

    # Request worker shutdown from System Controller
    await self.publish(
        ShutdownWorkersCommand(
            service_id=self.service_id,
            all_workers=True,
            target_service_type=ServiceType.SYSTEM_CONTROLLER,
        )
    )
```

## Implementation Details

### Worker Info Structure

```python
class WorkerStatusInfo(WorkerStats):
    # Identity
    worker_id: str

    # Timing
    last_update_ns: int
    last_error_ns: int | None
    last_high_load_ns: int | None

    # Status
    status: WorkerStatus

    # Metrics
    health: ProcessHealth
    task_stats: WorkerTaskStats
```

### Process Health Metrics

```python
class ProcessHealth:
    cpu_usage: float         # Percent
    memory_mb: float         # Megabytes
    io_read_mb: float        # Megabytes
    io_write_mb: float       # Megabytes
    cpu_times: CPUTimes      # User/system time
    ctx_switches: CtxSwitches # Voluntary/involuntary
```

### Task Statistics

```python
class WorkerTaskStats:
    total: int = 0           # Total tasks
    in_progress: int = 0     # Currently executing
    completed: int = 0       # Successful
    failed: int = 0          # Errors

    @property
    def success_rate(self) -> float:
        if self.total == 0:
            return 0.0
        return self.completed / self.total
```

## Key Takeaways

1. **Health Monitoring**: Worker Manager continuously tracks health metrics from all workers.

2. **Status Classification**: Workers are classified into five states: healthy, idle, high-load, error, and stale.

3. **Recovery Windows**: Status classifications use time-based recovery windows to avoid flapping.

4. **Staleness Detection**: Workers that stop reporting are marked as stale.

5. **Auto-Calculated Workers**: Default worker count is calculated based on CPU cores with sensible limits.

6. **Concurrency Capping**: Worker count is capped by concurrency setting when applicable.

7. **Status Publishing**: Periodic status summaries keep the system informed of worker health.

8. **Future Extensibility**: Architecture supports future auto-scaling capabilities.

9. **Command-Based Control**: Uses commands to System Controller for spawning/stopping workers.

10. **Background Monitoring**: Uses background tasks for health checks and status reporting.

Worker Manager provides the monitoring and lifecycle management layer that ensures workers remain healthy and the system can respond to changes in worker availability.

---

Next: [Chapter 9: Dataset Manager](chapter-09-dataset-manager.md)
