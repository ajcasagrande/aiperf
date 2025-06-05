<!--
#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
-->
# Decorators and the Hook System

**Summary:** AIPerf implements a sophisticated decorator-based hook system that enables lifecycle management, task automation, and extensible service behavior through clean, declarative patterns.

## Overview

AIPerf's hook system uses Python decorators to create a flexible, event-driven architecture for service lifecycle management. The system allows services to register callbacks for specific lifecycle events (initialization, startup, shutdown) and background tasks without complex inheritance or manual registration. This declarative approach makes service behavior clear and extensible while maintaining clean separation of concerns.

## Key Concepts

- **Lifecycle Hooks**: Decorators for service lifecycle events (init, start, stop, cleanup)
- **Task Decorators**: Automatic background task registration and management
- **Metaclass Integration**: Automatic hook discovery and registration
- **Event-Driven Architecture**: Decoupled service behavior through hook callbacks
- **Declarative Configuration**: Service behavior defined through decorators
- **Extensible Framework**: Easy addition of new hook types and behaviors

## Practical Example

```python
# Core hook decorators for service lifecycle
def on_init(func: Callable) -> Callable:
    """Decorator for initialization hooks."""
    setattr(func, AIPerfHooks.HOOK_TYPE, AIPerfHooks.INIT)
    return func

def on_start(func: Callable) -> Callable:
    """Decorator for service start hooks."""
    setattr(func, AIPerfHooks.HOOK_TYPE, AIPerfHooks.START)
    return func

def on_stop(func: Callable) -> Callable:
    """Decorator for service stop hooks."""
    setattr(func, AIPerfHooks.HOOK_TYPE, AIPerfHooks.STOP)
    return func

def on_cleanup(func: Callable) -> Callable:
    """Decorator for cleanup hooks."""
    setattr(func, AIPerfHooks.HOOK_TYPE, AIPerfHooks.CLEANUP)
    return func

def aiperf_task(func: Callable, interval: float | None = None) -> Callable:
    """Decorator for background task registration."""
    setattr(func, AIPerfHooks.HOOK_TYPE, AIPerfHooks.TASK)
    setattr(func, AIPerfHooks.TASK_INTERVAL, interval)
    return func

def on_set_state(
    func: Callable[[Any, ServiceState], Coroutine[Any, Any, None]]
) -> Callable:
    """Decorator for state change hooks."""
    setattr(func, AIPerfHooks.HOOK_TYPE, AIPerfHooks.SET_STATE)
    return func

# Hook type enumeration
class AIPerfHooks(StrEnum):
    """Hook type constants for the decorator system."""
    HOOK_TYPE = "__aiperf_hook_type__"

    CLEANUP = "__aiperf_on_cleanup__"
    INIT = "__aiperf_on_init__"
    COMMS_INIT = "__aiperf_on_comms_init__"
    STOP = "__aiperf_on_stop__"
    START = "__aiperf_on_start__"
    CONFIGURE = "__aiperf_on_configure__"
    RUN = "__aiperf_on_run__"
    TASK = "__aiperf_task__"
    TASK_INTERVAL = "__aiperf_task_interval__"
    SET_STATE = "__aiperf_on_set_state__"

# Service using hook decorators
class WorkerService(BaseService):
    """Worker service with declarative hook-based behavior."""

    def __init__(self, service_config: ServiceConfig) -> None:
        super().__init__(service_config)
        self.work_queue: asyncio.Queue = asyncio.Queue()
        self.backend_client: BackendClient | None = None
        self.processing_stats = {"requests_processed": 0, "errors": 0}

    @on_init
    async def _initialize_backend_client(self) -> None:
        """Initialize backend client during service initialization."""
        client_config = self.service_config.backend_client_config
        self.backend_client = BackendClientFactory.create_client(client_config)
        logger.info("Backend client initialized")

    @on_start
    async def _start_work_processing(self) -> None:
        """Start work processing when service starts."""
        await self.set_state(ServiceState.RUNNING)
        logger.info("Worker service started and ready for work")

    @on_stop
    async def _stop_work_processing(self) -> None:
        """Stop work processing gracefully."""
        await self.set_state(ServiceState.STOPPING)
        # Finish current work items
        while not self.work_queue.empty():
            try:
                work_item = self.work_queue.get_nowait()
                await self._process_work_item(work_item)
            except asyncio.QueueEmpty:
                break
        logger.info("Work processing stopped")

    @on_cleanup
    async def _cleanup_resources(self) -> None:
        """Clean up resources during service shutdown."""
        if self.backend_client:
            await self.backend_client.cleanup()
        logger.info("Worker resources cleaned up")

    @aiperf_task
    async def _work_processor(self) -> None:
        """Background task for processing work items."""
        while not self.is_shutdown:
            try:
                # Wait for work with timeout
                work_item = await asyncio.wait_for(
                    self.work_queue.get(), timeout=1.0
                )
                await self._process_work_item(work_item)
                self.processing_stats["requests_processed"] += 1

            except asyncio.TimeoutError:
                continue  # No work available, continue loop
            except Exception as e:
                logger.error(f"Error processing work: {e}")
                self.processing_stats["errors"] += 1

    @aiperf_task(interval=30.0)
    async def _status_reporter(self) -> None:
        """Periodic task for reporting service status."""
        while not self.is_shutdown:
            await self.publish_status()
            logger.info(f"Status: {self.processing_stats}")
            await asyncio.sleep(30.0)

    @on_set_state
    async def _handle_state_change(self, new_state: ServiceState) -> None:
        """Handle service state changes."""
        if new_state == ServiceState.RUNNING:
            await self.communication.publish(
                Topic.STATUS,
                StatusMessage(
                    service_id=self.service_id,
                    payload=StatusPayload(
                        state=new_state,
                        service_type=self.service_type
                    )
                )
            )

# ZMQ Client using task decorators
class ZMQSubClient(BaseZMQClient):
    """ZMQ subscriber with automatic background task management."""

    def __init__(self, context, address: str, bind: bool) -> None:
        super().__init__(context, SocketType.SUB, address, bind)
        self._subscribers: dict[str, list[Callable]] = {}

    @aiperf_task
    async def _sub_receiver(self) -> None:
        """Background task for receiving subscription messages."""
        while not self.is_shutdown:
            try:
                if not self.is_initialized:
                    await self.initialized_event.wait()

                # Receive message
                topic_bytes, message_bytes = await self.socket.recv_multipart()
                topic = topic_bytes.decode()
                message_json = message_bytes.decode()

                # Parse and dispatch
                message = BaseMessage.model_validate_json(message_json)
                if topic in self._subscribers:
                    await call_all_functions(self._subscribers[topic], message)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Subscription receiver error: {e}")
                await asyncio.sleep(0.1)

    @on_cleanup
    async def _cleanup_subscriptions(self) -> None:
        """Clean up subscription resources."""
        self._subscribers.clear()
        logger.debug("Subscription cleanup completed")

# Metaclass for automatic hook discovery
class ServiceMetaclass(type):
    """Metaclass that automatically discovers and registers hooks."""

    def __new__(cls, name, bases, namespace, **kwargs):
        # Create the class
        new_class = super().__new__(cls, name, bases, namespace, **kwargs)

        # Discover hooks in the class
        hooks = {}
        for attr_name in dir(new_class):
            attr = getattr(new_class, attr_name)
            if hasattr(attr, AIPerfHooks.HOOK_TYPE):
                hook_type = getattr(attr, AIPerfHooks.HOOK_TYPE)
                if hook_type not in hooks:
                    hooks[hook_type] = []
                hooks[hook_type].append(attr)

        # Store hooks on the class
        new_class._aiperf_hooks = hooks
        return new_class

# Base service with hook execution
class BaseService(metaclass=ServiceMetaclass):
    """Base service with automatic hook discovery and execution."""

    def __init__(self, service_config: ServiceConfig) -> None:
        self.service_config = service_config
        self._task_registry: dict[str, asyncio.Task] = {}
        self.is_shutdown = False

    async def _run_hooks(self, hook_type: AIPerfHooks, *args, **kwargs) -> None:
        """Execute all hooks of a specific type."""
        hooks = self._get_hooks(hook_type)
        for hook in hooks:
            try:
                if asyncio.iscoroutinefunction(hook):
                    await hook(self, *args, **kwargs)
                else:
                    hook(self, *args, **kwargs)
            except Exception as e:
                logger.error(f"Hook {hook.__name__} failed: {e}")

    def _get_hooks(self, hook_type: AIPerfHooks) -> list[Callable]:
        """Get all hooks of a specific type."""
        return getattr(self.__class__, '_aiperf_hooks', {}).get(hook_type, [])

    async def initialize(self) -> None:
        """Initialize service and run init hooks."""
        await self._run_hooks(AIPerfHooks.INIT)

        # Start background tasks
        for hook in self._get_hooks(AIPerfHooks.TASK):
            task_name = hook.__name__
            self._task_registry[task_name] = asyncio.create_task(hook(self))

    async def start(self) -> None:
        """Start service and run start hooks."""
        await self._run_hooks(AIPerfHooks.START)

    async def stop(self) -> None:
        """Stop service and run stop hooks."""
        await self._run_hooks(AIPerfHooks.STOP)

        # Cancel background tasks
        for task in self._task_registry.values():
            task.cancel()

        # Wait for tasks to complete
        if self._task_registry:
            await asyncio.gather(*self._task_registry.values(), return_exceptions=True)

    async def cleanup(self) -> None:
        """Clean up service and run cleanup hooks."""
        self.is_shutdown = True
        await self._run_hooks(AIPerfHooks.CLEANUP)
```

## Visual Diagram

```mermaid
graph TD
    subgraph "Hook Decorator System"
        D1[@on_init] --> M1[Method Registration]
        D2[@on_start] --> M1
        D3[@on_stop] --> M1
        D4[@aiperf_task] --> M1
        D5[@on_cleanup] --> M1
        M1 --> MC[Metaclass Discovery]
    end

    subgraph "Service Lifecycle"
        INIT[Initialize] --> RH1[Run Init Hooks]
        RH1 --> ST[Start Tasks]
        ST --> START[Start Service]
        START --> RH2[Run Start Hooks]
        RH2 --> RUN[Running State]
        RUN --> STOP[Stop Service]
        STOP --> RH3[Run Stop Hooks]
        RH3 --> CT[Cancel Tasks]
        CT --> CLEAN[Cleanup]
        CLEAN --> RH4[Run Cleanup Hooks]
    end

    subgraph "Background Tasks"
        BT1[Work Processor Task]
        BT2[Status Reporter Task]
        BT3[Message Receiver Task]
        ST --> BT1
        ST --> BT2
        ST --> BT3
    end

    subgraph "Hook Types"
        HT1[Lifecycle Hooks]
        HT2[Task Hooks]
        HT3[State Change Hooks]
        HT4[Communication Hooks]
    end

    style D1 fill:#ffeb3b
    style D2 fill:#4caf50
    style D3 fill:#f44336
    style D4 fill:#2196f3
    style MC fill:#ff9800
    style BT1 fill:#e1f5fe
    style BT2 fill:#e1f5fe
    style BT3 fill:#e1f5fe
```

## Best Practices and Pitfalls

**Best Practices:**
- Use descriptive names for hook methods (prefix with `_` for internal hooks)
- Keep hook methods focused on single responsibilities
- Handle exceptions gracefully within hook methods
- Use async hooks for I/O operations and sync hooks for simple setup
- Document hook execution order and dependencies clearly
- Prefer declarative hooks over manual registration
- Use task intervals appropriately to avoid overwhelming the system

**Common Pitfalls:**
- Forgetting to handle exceptions in hook methods (can break service lifecycle)
- Creating circular dependencies between hooks
- Using blocking operations in async hooks
- Not properly cleaning up resources in cleanup hooks
- Overusing hooks for simple method calls
- Missing error handling in background tasks
- Creating too many background tasks affecting performance

## Discussion Points

- How does the decorator-based hook system improve code organization compared to traditional inheritance patterns?
- What are the trade-offs between automatic hook discovery and explicit registration?
- How can we ensure proper error handling and recovery in hook-based architectures?
