# Chapter 6: System Controller

<!--
# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
-->

## Table of Contents
- [Role and Responsibilities](#role-and-responsibilities)
- [Service Registration and Management](#service-registration-and-management)
- [Command Handling](#command-handling)
- [Lifecycle Orchestration](#lifecycle-orchestration)
- [Error Handling](#error-handling)
- [Implementation Details](#implementation-details)
- [Key Takeaways](#key-takeaways)

## Role and Responsibilities

The System Controller (`/home/anthony/nvidia/projects/aiperf/aiperf/controller/system_controller.py`) is the orchestrator of the entire AIPerf system. It's the single service that coordinates all others and ensures proper system-wide execution.

### Primary Responsibilities

1. **Lifecycle Orchestration**: Start, configure, and stop all services in correct order
2. **Service Management**: Track all running services and their states
3. **Command Distribution**: Broadcast commands to all services
4. **Result Aggregation**: Collect final results and export them
5. **Error Handling**: Detect and handle system-wide errors
6. **UI Management**: Display progress and metrics to user
7. **Signal Handling**: Handle OS signals (SIGINT, SIGTERM)

### Initialization

```python
class SystemController(SignalHandlerMixin, BaseService):
    def __init__(
        self,
        user_config: UserConfig,
        service_config: ServiceConfig,
        service_id: str | None = None,
    ) -> None:
        super().__init__(
            service_config=service_config,
            user_config=user_config,
            service_id=service_id,
        )

        # Define required services
        self.required_services: dict[ServiceTypeT, int] = {
            ServiceType.DATASET_MANAGER: 1,
            ServiceType.TIMING_MANAGER: 1,
            ServiceType.WORKER_MANAGER: 1,
            ServiceType.RECORDS_MANAGER: 1,
        }

        # Record processor count (auto-scaled or fixed)
        if self.service_config.record_processor_service_count is not None:
            self.required_services[ServiceType.RECORD_PROCESSOR] = (
                self.service_config.record_processor_service_count
            )
            self.scale_record_processors_with_workers = False
        else:
            self.scale_record_processors_with_workers = True

        # Create proxy manager for ZMQ proxies
        self.proxy_manager: ProxyManager = ProxyManager(
            service_config=self.service_config
        )

        # Create service manager for spawning services
        self.service_manager: ServiceManagerProtocol = (
            ServiceManagerFactory.create_instance(
                self.service_config.service_run_type.value,
                required_services=self.required_services,
                user_config=self.user_config,
                service_config=self.service_config,
                log_queue=get_global_log_queue(),
            )
        )

        # Create UI for user interaction
        self.ui: AIPerfUIProtocol = AIPerfUIFactory.create_instance(
            self.service_config.ui_type,
            service_config=self.service_config,
            user_config=self.user_config,
            log_queue=get_global_log_queue(),
            controller=self,
        )
```

## Service Registration and Management

### Service Tracking

System Controller maintains two data structures for service tracking:

```python
# Map service_id → ServiceRunInfo
self.service_manager.service_id_map: dict[str, ServiceRunInfo] = {}

# Map service_type → list[ServiceRunInfo]
self.service_manager.service_map: dict[ServiceType, list[ServiceRunInfo]] = {}
```

Where `ServiceRunInfo` contains:

```python
class ServiceRunInfo:
    registration_status: ServiceRegistrationStatus
    service_type: ServiceType
    service_id: str
    first_seen: int  # nanoseconds
    state: LifecycleState
    last_seen: int  # nanoseconds
```

### Registration Process

When a service starts, it registers with the System Controller:

```python
@on_command(CommandType.REGISTER_SERVICE)
async def _handle_register_service_command(
    self, message: RegisterServiceCommand
) -> None:
    self.debug(
        f"Processing registration from {message.service_type} "
        f"with ID: {message.service_id}"
    )

    service_info = ServiceRunInfo(
        registration_status=ServiceRegistrationStatus.REGISTERED,
        service_type=message.service_type,
        service_id=message.service_id,
        first_seen=time.time_ns(),
        state=message.state,
        last_seen=time.time_ns(),
    )

    # Add to maps
    self.service_manager.service_id_map[message.service_id] = service_info

    if message.service_type not in self.service_manager.service_map:
        self.service_manager.service_map[message.service_type] = []
    self.service_manager.service_map[message.service_type].append(service_info)

    self.info(f"Registered {message.service_type} (id: '{message.service_id}')")
```

### Heartbeat Processing

Services send periodic heartbeats to indicate they're alive:

```python
@on_message(MessageType.HEARTBEAT)
async def _process_heartbeat_message(self, message: HeartbeatMessage) -> None:
    service_id = message.service_id
    timestamp = message.request_ns

    # Update last seen timestamp and state
    try:
        service_info = self.service_manager.service_id_map[service_id]
        service_info.last_seen = timestamp
        service_info.state = message.state
    except Exception:
        self.warning(
            f"Received heartbeat from unknown service: {service_id}"
        )
```

## Command Handling

System Controller broadcasts commands to orchestrate the system.

### Command Flow

```
System Controller
    │
    │ Create command
    v
ProfileConfigureCommand
    │
    │ Broadcast via publish()
    v
Message Bus (PUB/SUB)
    │
    │ All services subscribed
    v
All Services
    │
    │ Execute @on_command handler
    │ Do configuration
    v
CommandResponse
    │
    │ Publish response
    v
System Controller
    │
    │ Collect all responses
    │ Check for errors
    │ Wait for timeout
    v
Continue to next phase
```

### Configuring All Services

```python
async def _profile_configure_all_services(self) -> None:
    """Configure all services to start profiling."""
    self.info("Configuring all services to start profiling")
    begin = time.perf_counter()

    # Send command to all registered services
    responses = await self.send_command_and_wait_for_all_responses(
        ProfileConfigureCommand(
            service_id=self.service_id,
            config=self.user_config,
        ),
        list(self.service_manager.service_id_map.keys()),
        timeout=DEFAULT_PROFILE_CONFIGURE_TIMEOUT,
    )

    duration = time.perf_counter() - begin

    # Check for errors
    self._parse_responses_for_errors(responses, "Configure Profiling")

    self.info(f"All services configured in {duration:.2f} seconds")
```

### Starting Profiling

```python
async def _start_profiling_all_services(self) -> None:
    """Tell all services to start profiling."""
    self.debug("Sending PROFILE_START command to all services")

    responses = await self.send_command_and_wait_for_all_responses(
        ProfileStartCommand(
            service_id=self.service_id,
        ),
        list(self.service_manager.service_id_map.keys()),
        timeout=DEFAULT_PROFILE_START_TIMEOUT,
    )

    self._parse_responses_for_errors(responses, "Start Profiling")
    self.info("All services started profiling successfully")
```

### Response Parsing

```python
def _parse_responses_for_errors(
    self, responses: list[CommandResponse | ErrorDetails], operation: str
) -> None:
    """Parse the responses for errors."""
    for response in responses:
        if isinstance(response, ErrorDetails):
            self._exit_errors.append(
                ExitErrorInfo(
                    error_details=response,
                    operation=operation,
                    service_id=None
                )
            )
        elif isinstance(response, CommandErrorResponse):
            self._exit_errors.append(
                ExitErrorInfo(
                    error_details=response.error,
                    operation=operation,
                    service_id=response.service_id,
                )
            )

    # Raise if any errors found
    if self._exit_errors:
        raise LifecycleOperationError(
            operation=operation,
            original_exception=None,
            lifecycle_id=self.id,
        )
```

## Lifecycle Orchestration

### Startup Sequence

```python
@on_start
async def _start_services(self) -> None:
    """Bootstrap the system services."""
    self.debug("System Controller is bootstrapping services")

    # 1. Start all required services
    async with self.try_operation_or_stop("Start Service Manager"):
        await self.service_manager.start()

    # 2. Wait for all services to register
    async with self.try_operation_or_stop("Register Services"):
        await self.service_manager.wait_for_all_services_registration(
            stop_event=self._stop_requested_event,
        )

    # 3. Configure all services
    self.info("AIPerf System is CONFIGURING")
    await self._profile_configure_all_services()
    self.info("AIPerf System is CONFIGURED")

    # 4. Start profiling
    await self._start_profiling_all_services()
    self.info("AIPerf System is PROFILING")
```

### Worker Spawning

System Controller handles dynamic worker spawning:

```python
@on_command(CommandType.SPAWN_WORKERS)
async def _handle_spawn_workers_command(
    self, message: SpawnWorkersCommand
) -> None:
    self.debug(f"Received spawn workers command: {message}")

    # Spawn the workers
    await self.service_manager.run_service(
        ServiceType.WORKER,
        message.num_workers
    )

    # If auto-scaling record processors, spawn them too
    if self.scale_record_processors_with_workers:
        num_processors = max(
            1,
            message.num_workers // DEFAULT_RECORD_PROCESSOR_SCALE_FACTOR
        )
        await self.service_manager.run_service(
            ServiceType.RECORD_PROCESSOR,
            num_processors
        )
```

### Result Collection

System Controller receives final results:

```python
@on_message(MessageType.PROCESS_RECORDS_RESULT)
async def _on_process_records_result_message(
    self, message: ProcessRecordsResultMessage
) -> None:
    """Handle a profile results message."""
    self.debug(f"Received profile results message: {message}")

    if message.results.errors:
        self.error(
            f"Received process records result message with errors: "
            f"{message.results.errors}"
        )

    # Store results
    self._profile_results = message.results

    # Export data
    if message.results.results:
        await ExporterManager(
            results=message.results.results,
            input_config=self.user_config,
            service_config=self.service_config,
        ).export_data()
    else:
        self.error("Received result message with no records")

    # Stop system after exporting
    self.debug("Stopping system controller after exporting records")
    await asyncio.shield(self.stop())
```

### Shutdown Sequence

```python
@on_stop
async def _stop_system_controller(self) -> None:
    """Stop the system controller and all running services."""

    # 1. Broadcast shutdown to all services
    await self.publish(ShutdownCommand(service_id=self.service_id))
    await asyncio.sleep(0.5)  # Let message propagate

    # 2. Shutdown all services
    await self.service_manager.shutdown_all_services()

    # 3. Stop communication
    await self.comms.stop()
    await self.proxy_manager.stop()

    # 4. Stop UI
    await self.ui.stop()
    await self.ui.wait_for_tasks()
    await asyncio.sleep(0.1)  # Let screen clear

    # 5. Display results or errors
    if not self._exit_errors:
        await self._print_post_benchmark_info_and_metrics()
    else:
        self._print_exit_errors_and_log_file()

    # 6. Exit process
    os._exit(1 if self._exit_errors else 0)
```

## Error Handling

### Signal Handling

System Controller handles OS signals gracefully:

```python
async def _handle_signal(self, sig: int) -> None:
    """Handle received signals by triggering graceful shutdown."""
    if self.stop_requested:
        # Already stopping - force kill
        self.warning(f"Received signal {sig}, killing")
        await self._kill()
        return

    self.debug(f"Received signal {sig}, initiating graceful shutdown")
    await self._cancel_profiling()
```

### Cancellation

User can cancel profiling mid-run:

```python
async def _cancel_profiling(self) -> None:
    self.debug("Cancelling profiling of all services")
    self._was_cancelled = True

    # Broadcast cancel command
    await self.publish(ProfileCancelCommand(service_id=self.service_id))

    # Wait for cancellation to propagate
    await asyncio.sleep(2)

    # Stop system
    self.debug("Stopping system controller after profiling cancelled")
    await asyncio.shield(self.stop())
```

### Error Collection

System Controller collects errors from all operations:

```python
# Error storage
self._exit_errors: list[ExitErrorInfo] = []

# Error info structure
class ExitErrorInfo:
    error_details: ErrorDetails
    operation: str
    service_id: str | None
```

### Error Display

```python
def _print_exit_errors_and_log_file(self) -> None:
    """Print post exit errors and log file info to the console."""
    console = Console()
    print_exit_errors(self._exit_errors, console=console)
    self._print_log_file_info(console)
    console.print()
    console.file.flush()
```

## Implementation Details

### Service Manager

System Controller delegates service spawning to a Service Manager:

```python
class ServiceManagerProtocol(Protocol):
    async def initialize(self) -> None: ...
    async def start(self) -> None: ...
    async def run_service(
        self, service_type: ServiceType, count: int
    ) -> None: ...
    async def stop_service(self, service_type: ServiceType) -> None: ...
    async def shutdown_all_services(self) -> None: ...
    async def kill_all_services(self) -> None: ...
    async def wait_for_all_services_registration(
        self, stop_event: asyncio.Event
    ) -> None: ...
```

**Implementation**: `/home/anthony/nvidia/projects/aiperf/aiperf/controller/service_manager.py`

### Proxy Manager

Manages all ZeroMQ proxies:

```python
class ProxyManager:
    async def initialize_and_start(self) -> None:
        """Initialize and start all proxies."""
        # Message bus proxy (PUB/SUB)
        self.message_bus_proxy = ...

        # Credit drop proxy (PUSH/PULL)
        self.credit_drop_proxy = ...

        # Credit return proxy (PULL/PUSH)
        self.credit_return_proxy = ...

        # Dataset request proxy (DEALER/ROUTER)
        self.dataset_request_proxy = ...

        # Raw inference proxy (PUSH/PULL)
        self.raw_inference_proxy = ...

        # Records proxy (PUSH/PULL)
        self.records_proxy = ...

        # Start all
        await asyncio.gather(
            self.message_bus_proxy.start(),
            self.credit_drop_proxy.start(),
            # ... more
        )

    async def stop(self) -> None:
        """Stop all proxies."""
        await asyncio.gather(
            self.message_bus_proxy.stop(),
            self.credit_drop_proxy.stop(),
            # ... more
        )
```

**Implementation**: `/home/anthony/nvidia/projects/aiperf/aiperf/controller/proxy_manager.py`

### UI Integration

System Controller manages the user interface:

```python
self.ui: AIPerfUIProtocol = AIPerfUIFactory.create_instance(
    self.service_config.ui_type,  # dashboard, simple, or none
    service_config=self.service_config,
    user_config=self.user_config,
    log_queue=get_global_log_queue(),
    controller=self,
)

# UI is a child lifecycle
self.attach_child_lifecycle(self.ui)
```

UI types:
- **Dashboard**: Rich TUI with real-time progress
- **Simple**: Simple progress bar
- **None**: No UI, just logs

### Result Export

After benchmark completion:

```python
async def _print_post_benchmark_info_and_metrics(self) -> None:
    """Print post benchmark info and metrics to the console."""
    if not self._profile_results:
        self.warning("No profile results to export")
        return

    console = Console()
    if console.width < 100:
        console.width = 100

    # Export to console
    exporter_manager = ExporterManager(
        results=self._profile_results.results,
        input_config=self.user_config,
        service_config=self.service_config,
    )
    await exporter_manager.export_console(console=console)

    # Print metadata
    console.print()
    self._print_cli_command(console)
    self._print_benchmark_duration(console)
    self._print_exported_file_infos(exporter_manager, console)
    self._print_log_file_info(console)

    if self._was_cancelled:
        console.print(
            "[italic yellow]The profile run was cancelled early. "
            "Results shown may be incomplete or inaccurate.[/italic yellow]"
        )

    console.print()
    console.file.flush()
```

## Key Takeaways

1. **Central Orchestrator**: System Controller is the single point of coordination for the entire system.

2. **Service Tracking**: Maintains comprehensive maps of all running services and their states.

3. **Command Broadcast**: Uses PUB/SUB pattern to distribute commands to all services.

4. **Response Collection**: Waits for and validates responses from all services before proceeding.

5. **Lifecycle Coordination**: Manages the precise sequence of initialization, configuration, start, and shutdown.

6. **Dynamic Worker Management**: Handles worker spawning and shutdown commands from Worker Manager.

7. **Error Aggregation**: Collects errors from all operations and displays them comprehensively.

8. **Signal Handling**: Gracefully handles OS signals for clean user-initiated shutdown.

9. **UI Management**: Integrates user interface as a child lifecycle.

10. **Result Export**: Coordinates final result export and display after benchmark completion.

The System Controller is the orchestration brain of AIPerf, ensuring all services work together harmoniously to execute benchmarks accurately and reliably.

---

Next: [Chapter 7: Workers Architecture](chapter-07-workers-architecture.md)
