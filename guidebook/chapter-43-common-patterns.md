<!--
# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
-->
# Chapter 43: Common Patterns

## Overview

This chapter covers common design patterns used throughout AIPerf. Understanding these patterns helps you write code that integrates seamlessly with the rest of the system and follows established conventions.

## Table of Contents

- [Design Philosophy](#design-philosophy)
- [Service Pattern](#service-pattern)
- [Factory Pattern](#factory-pattern)
- [Mixin Composition](#mixin-composition)
- [Hook System](#hook-system)
- [Message Passing](#message-passing)
- [Configuration Pattern](#configuration-pattern)
- [Protocol-Based Design](#protocol-based-design)
- [Async Patterns](#async-patterns)
- [Error Handling Patterns](#error-handling-patterns)

---

## Design Philosophy

### Core Principles

AIPerf is built on these design principles:

1. **Modularity**: Components are independent and reusable
2. **Extensibility**: New functionality can be added without modifying core code
3. **Type Safety**: Strong typing with Pydantic and type hints
4. **Async-First**: Built for high concurrency with asyncio
5. **Configuration-Driven**: Behavior controlled through configuration

### Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                   Design Patterns in AIPerf                  │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌──────────────┐      ┌──────────────┐                    │
│  │   Factory    │──────│   Service    │                    │
│  │   Pattern    │      │   Pattern    │                    │
│  └──────────────┘      └──────────────┘                    │
│         │                      │                            │
│         │              ┌───────┴────────┐                   │
│         │              │                │                   │
│  ┌──────▼──────┐  ┌───▼─────┐   ┌─────▼────┐             │
│  │  Protocol   │  │  Mixin  │   │   Hook   │             │
│  │   Pattern   │  │ Pattern │   │  System  │             │
│  └─────────────┘  └─────────┘   └──────────┘             │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

---

## Service Pattern

### Overview

The Service Pattern provides lifecycle management for AIPerf components. All services inherit from `BaseService` and implement standardized initialization, startup, and shutdown.

### Base Service Structure

**File**: `/home/anthony/nvidia/projects/aiperf/aiperf/common/base_service.py`

```python
from aiperf.common.base_service import BaseService
from aiperf.common.config import ServiceConfig, UserConfig
from aiperf.common.enums import ServiceType

class MyService(BaseService):
    """Custom service example"""

    # Service type set by factory registration
    service_type = ServiceType.CUSTOM

    def __init__(
        self,
        service_config: ServiceConfig,
        user_config: UserConfig,
        **kwargs
    ):
        super().__init__(service_config, user_config, **kwargs)
        # Custom initialization
        self.custom_state = {}

    async def _initialize(self):
        """Initialize resources"""
        self.info("Initializing custom service")
        # Setup resources
        await self._setup_resources()

    async def _start(self):
        """Start service operations"""
        self.info("Starting custom service")
        # Begin processing
        await self._begin_processing()

    async def _stop(self):
        """Stop service and cleanup"""
        self.info("Stopping custom service")
        # Cleanup resources
        await self._cleanup_resources()
```

### Service Lifecycle

```
┌──────────┐
│   INIT   │ ─── __init__() called
└────┬─────┘
     │
     ▼
┌──────────┐
│ STARTING │ ─── _initialize() called
└────┬─────┘     _start() called
     │
     ▼
┌──────────┐
│ RUNNING  │ ─── Service operational
└────┬─────┘
     │
     ▼
┌──────────┐
│ STOPPING │ ─── _stop() called
└────┬─────┘
     │
     ▼
┌──────────┐
│ STOPPED  │ ─── Service terminated
└──────────┘
```

### Service Registration

```python
from aiperf.common.factories import ServiceFactory
from aiperf.common.enums import ServiceType

@ServiceFactory.register(ServiceType.CUSTOM)
class MyService(BaseService):
    """Service automatically registered"""
    pass

# Usage
service = ServiceFactory.create_instance(
    ServiceType.CUSTOM,
    service_config=service_config,
    user_config=user_config
)
```

---

## Factory Pattern

### Overview

The Factory Pattern enables registration and creation of components without direct instantiation. AIPerf uses factories extensively for metrics, datasets, endpoints, and services.

### Base Factory

**File**: `/home/anthony/nvidia/projects/aiperf/aiperf/common/factories.py`

```python
from aiperf.common.factories import AIPerfFactory
from aiperf.common.enums import CaseInsensitiveStrEnum

# Define component types
class DataLoaderType(CaseInsensitiveStrEnum):
    FILE = "file"
    S3 = "s3"
    DATABASE = "database"

# Define protocol
from typing import Protocol

class DataLoaderProtocol(Protocol):
    def load(self) -> list:
        ...

# Create factory
class DataLoaderFactory(AIPerfFactory[DataLoaderType, DataLoaderProtocol]):
    pass

# Register implementations
@DataLoaderFactory.register(DataLoaderType.FILE)
class FileDataLoader:
    def __init__(self, path: str):
        self.path = path

    def load(self) -> list:
        with open(self.path) as f:
            return f.readlines()

@DataLoaderFactory.register(DataLoaderType.S3)
class S3DataLoader:
    def __init__(self, bucket: str, key: str):
        self.bucket = bucket
        self.key = key

    def load(self) -> list:
        # S3 loading logic
        return []

# Usage
loader = DataLoaderFactory.create_instance(
    DataLoaderType.FILE,
    path="/data/dataset.txt"
)
data = loader.load()
```

### Singleton Factory

For components that should be shared:

```python
from aiperf.common.factories import AIPerfSingletonFactory

class ConfigurationFactory(AIPerfSingletonFactory[ConfigType, ConfigProtocol]):
    pass

# First call creates instance
config1 = ConfigurationFactory.create_instance(ConfigType.DEFAULT)

# Second call returns same instance
config2 = ConfigurationFactory.create_instance(ConfigType.DEFAULT)

assert config1 is config2  # True
```

### Factory Override Priority

```python
# Built-in implementation (priority 0)
@MetricFactory.register(MetricType.LATENCY, override_priority=0)
class BuiltInLatencyMetric:
    pass

# Custom override (priority 10)
@MetricFactory.register(MetricType.LATENCY, override_priority=10)
class CustomLatencyMetric:
    pass

# Custom implementation will be used
metric = MetricFactory.create_instance(MetricType.LATENCY)
assert isinstance(metric, CustomLatencyMetric)
```

---

## Mixin Composition

### Overview

Mixins provide reusable functionality that can be composed into classes. AIPerf uses mixins extensively for logging, hooks, communication, and more.

### Common Mixins

**File**: `/home/anthony/nvidia/projects/aiperf/aiperf/common/mixins/`

```python
from aiperf.common.mixins import (
    AIPerfLoggerMixin,      # Logging functionality
    HooksMixin,             # Hook support
    MessageBusMixin,        # Message bus communication
    WorkerTrackerMixin,     # Worker tracking
    ProgressTrackerMixin,   # Progress tracking
    RealtimeMetricsMixin,   # Realtime metrics
)
```

### Mixin Example: Logger

```python
from aiperf.common.mixins import AIPerfLoggerMixin

class MyComponent(AIPerfLoggerMixin):
    def __init__(self):
        super().__init__()

    def process(self):
        # Logging methods available
        self.debug("Processing started")
        self.info("Processing item")
        self.warning("Unusual condition")
        self.error("Error occurred")

        # Lazy evaluation
        self.debug(lambda: f"Expensive: {expensive_operation()}")
```

### Mixin Composition

Combine multiple mixins:

```python
from aiperf.common.mixins import (
    AIPerfLoggerMixin,
    HooksMixin,
    MessageBusMixin,
    AIPerfLifecycleMixin
)
from aiperf.common.hooks import on_start, on_stop, provides_hooks
from aiperf.common.enums import AIPerfHook

@provides_hooks(AIPerfHook.ON_START, AIPerfHook.ON_STOP)
class FullFeaturedService(
    MessageBusMixin,
    HooksMixin,
    AIPerfLifecycleMixin,
    AIPerfLoggerMixin
):
    """Service with full mixin composition"""

    def __init__(self):
        super().__init__()

    @on_start
    async def _on_service_start(self):
        self.info("Service starting")
        await self.publish(StartMessage())

    @on_stop
    async def _on_service_stop(self):
        self.info("Service stopping")
        await self.publish(StopMessage())
```

### Mixin Design Pattern

```python
from aiperf.common.mixins.base_mixin import BaseMixin

class MyMixin(BaseMixin):
    """Custom mixin pattern"""

    def __init__(self, **kwargs):
        # Always call super().__init__()
        super().__init__(**kwargs)
        # Initialize mixin state
        self._mixin_state = {}

    def mixin_method(self):
        """Method provided by mixin"""
        pass

    def _mixin_internal(self):
        """Internal mixin method (prefixed with _)"""
        pass
```

---

## Hook System

### Overview

The Hook System provides declarative event handling. Hooks are registered using decorators and automatically invoked at specific lifecycle points.

### Hook Types

**File**: `/home/anthony/nvidia/projects/aiperf/aiperf/common/hooks.py`

```python
from aiperf.common.enums import AIPerfHook

# Available hooks:
AIPerfHook.ON_INIT              # Initialization
AIPerfHook.ON_START             # Service start
AIPerfHook.ON_STOP              # Service stop
AIPerfHook.ON_STATE_CHANGE      # State transitions
AIPerfHook.ON_MESSAGE           # Message received
AIPerfHook.ON_COMMAND           # Command received
AIPerfHook.ON_REQUEST           # Request received
AIPerfHook.BACKGROUND_TASK      # Background task
AIPerfHook.ON_WORKER_UPDATE     # Worker status update
AIPerfHook.ON_REALTIME_METRICS  # Realtime metrics
```

### Using Hooks

```python
from aiperf.common.hooks import (
    on_init,
    on_start,
    on_stop,
    on_message,
    background_task,
    provides_hooks
)
from aiperf.common.enums import MessageType, AIPerfHook

@provides_hooks(
    AIPerfHook.ON_INIT,
    AIPerfHook.ON_START,
    AIPerfHook.ON_STOP,
    AIPerfHook.ON_MESSAGE
)
class ServiceWithHooks(HooksMixin):
    """Service using hooks"""

    @on_init
    def _initialize_resources(self):
        """Called during initialization"""
        self.info("Initializing resources")
        self.resources = {}

    @on_start
    async def _start_processing(self):
        """Called when service starts"""
        self.info("Starting processing")
        await self.start_workers()

    @on_stop
    async def _cleanup(self):
        """Called when service stops"""
        self.info("Cleaning up")
        await self.stop_workers()

    @on_message(MessageType.STATUS)
    async def _handle_status(self, message):
        """Called when STATUS message received"""
        self.debug(f"Status: {message.status}")

    @background_task(interval=1.0, immediate=True)
    async def _periodic_task(self):
        """Called every 1 second"""
        self.debug("Periodic task running")
```

### Hook Parameters

```python
from aiperf.common.hooks import on_message

# Static parameters
@on_message(MessageType.STATUS, MessageType.ERROR)
async def _handle_messages(self, message):
    pass

# Dynamic parameters (callable)
@on_message(lambda self: self.get_subscribed_message_types())
async def _handle_dynamic(self, message):
    pass
```

### Background Tasks

```python
from aiperf.common.hooks import background_task

class TaskService:
    @background_task(interval=5.0, immediate=True, stop_on_error=False)
    async def _monitor_health(self):
        """Runs every 5 seconds"""
        health = await self.check_health()
        self.debug(f"Health: {health}")

    @background_task(interval=None, immediate=True)
    async def _one_time_setup(self):
        """Runs once on start"""
        await self.initialize_resources()

    @background_task(
        interval=lambda self: self.config.poll_interval,
        immediate=False
    )
    async def _dynamic_interval(self):
        """Interval determined by config"""
        await self.poll_updates()
```

---

## Message Passing

### Overview

AIPerf uses a message bus (ZMQ) for inter-service communication. Messages are strongly typed using Pydantic models.

### Message Pattern

```python
from pydantic import BaseModel
from aiperf.common.messages import BaseMessage
from aiperf.common.enums import MessageType

class CustomMessage(BaseMessage):
    """Custom message type"""

    message_type: MessageType = MessageType.CUSTOM
    data: dict
    timestamp: float

# Publishing
await self.publish(CustomMessage(
    data={"key": "value"},
    timestamp=time.time()
))

# Subscribing
@on_message(MessageType.CUSTOM)
async def _handle_custom(self, message: CustomMessage):
    self.info(f"Received: {message.data}")
```

### Request-Reply Pattern

```python
from aiperf.common.hooks import on_request
from aiperf.common.messages import RequestMessage, ResponseMessage

class RequestHandler:
    @on_request(MessageType.DATA_REQUEST)
    async def _handle_request(self, request: RequestMessage) -> ResponseMessage:
        """Handle request and return response"""
        data = await self.fetch_data(request.query)
        return ResponseMessage(
            request_id=request.request_id,
            data=data
        )
```

### Publish-Subscribe Pattern

```python
# Publisher
class EventPublisher(MessageBusMixin):
    async def notify_event(self, event_data):
        await self.publish(EventMessage(data=event_data))

# Subscriber
class EventSubscriber(MessageBusMixin):
    @on_message(MessageType.EVENT)
    async def _handle_event(self, message: EventMessage):
        await self.process_event(message.data)
```

---

## Configuration Pattern

### Overview

Configuration in AIPerf uses Pydantic models with strong typing, validation, and documentation.

### Configuration Model

```python
from pydantic import BaseModel, Field, field_validator
from aiperf.common.config.base_config import BaseConfig

class MyServiceConfig(BaseConfig):
    """Configuration for MyService"""

    # Required fields
    service_name: str = Field(
        description="Name of the service"
    )

    # Optional with defaults
    max_workers: int = Field(
        default=10,
        ge=1,
        le=1000,
        description="Maximum number of workers"
    )

    # With validation
    endpoint_url: str = Field(
        description="Endpoint URL"
    )

    @field_validator('endpoint_url')
    @classmethod
    def validate_url(cls, v):
        if not v.startswith(('http://', 'https://')):
            raise ValueError('URL must start with http:// or https://')
        return v

    # Nested configuration
    advanced: dict = Field(
        default_factory=dict,
        description="Advanced configuration options"
    )
```

### Configuration Usage

```python
# Create configuration
config = MyServiceConfig(
    service_name="custom_service",
    endpoint_url="http://localhost:8000",
    max_workers=20
)

# Access fields
print(config.service_name)
print(config.max_workers)

# Validate
config.model_validate(config.model_dump())

# Export/Import
json_str = config.model_dump_json()
config2 = MyServiceConfig.model_validate_json(json_str)
```

---

## Protocol-Based Design

### Overview

Protocols define interfaces without requiring inheritance. AIPerf uses protocols extensively for type checking and flexibility.

### Protocol Pattern

```python
from typing import Protocol, runtime_checkable

@runtime_checkable
class DataLoaderProtocol(Protocol):
    """Protocol for data loaders"""

    def load(self, path: str) -> list:
        """Load data from path"""
        ...

    def validate(self) -> bool:
        """Validate loaded data"""
        ...

# Implementations don't need to inherit
class FileLoader:
    def load(self, path: str) -> list:
        with open(path) as f:
            return f.readlines()

    def validate(self) -> bool:
        return True

# Type checking works
loader: DataLoaderProtocol = FileLoader()

# Runtime checking
assert isinstance(loader, DataLoaderProtocol)
```

### Protocol Registration

```python
from aiperf.common.decorators import implements_protocol

@implements_protocol(ServiceProtocol)
class MyService:
    """Explicitly declare protocol implementation"""
    pass
```

---

## Async Patterns

### Async Service Pattern

```python
class AsyncService:
    async def start(self):
        """Start async operations"""
        await self._initialize()
        self._tasks = []
        self._tasks.append(asyncio.create_task(self._process_loop()))

    async def _process_loop(self):
        """Main processing loop"""
        while not self.stop_requested:
            try:
                await self._process_batch()
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.error(f"Error in process loop: {e}")

    async def stop(self):
        """Stop async operations"""
        self.stop_requested = True
        for task in self._tasks:
            task.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)
```

### Async Context Manager

```python
from contextlib import asynccontextmanager

class ResourceManager:
    @asynccontextmanager
    async def managed_resource(self):
        """Async context manager for resources"""
        resource = await self.acquire_resource()
        try:
            yield resource
        finally:
            await self.release_resource(resource)

# Usage
async with resource_manager.managed_resource() as resource:
    await resource.process()
```

---

## Error Handling Patterns

### Exception Hierarchy

```python
from aiperf.common.exceptions import AIPerfError

# Custom exceptions
class ServiceError(AIPerfError):
    """Service-specific error"""
    pass

class ConfigurationError(AIPerfError):
    """Configuration error"""
    pass

# Usage
try:
    service.start()
except ServiceError as e:
    logger.error(f"Service failed: {e}")
except AIPerfError as e:
    logger.error(f"AIPerf error: {e}")
except Exception as e:
    logger.exception(f"Unexpected error: {e}")
```

### Error Recovery Pattern

```python
class ResilientService:
    async def process_with_retry(self, item, max_retries=3):
        """Process with retry logic"""
        for attempt in range(max_retries):
            try:
                return await self.process(item)
            except TransientError as e:
                if attempt == max_retries - 1:
                    raise
                self.warning(f"Retry {attempt + 1}/{max_retries}: {e}")
                await asyncio.sleep(2 ** attempt)  # Exponential backoff
```

---

## Key Takeaways

1. **Service Pattern**: Standardized lifecycle management
2. **Factory Pattern**: Flexible component creation
3. **Mixin Composition**: Reusable functionality
4. **Hook System**: Declarative event handling
5. **Message Passing**: Decoupled communication
6. **Configuration**: Strongly-typed validation
7. **Protocols**: Interface definitions
8. **Async Patterns**: Concurrent operations
9. **Error Handling**: Robust failure management

---

## Navigation

- [Previous Chapter: Chapter 42 - Performance Profiling](chapter-42-performance-profiling.md)
- [Next Chapter: Chapter 44 - Custom Metrics Development](chapter-44-custom-metrics-development.md)
- [Return to Index](INDEX.md)

---

**Document Information**
- **File**: `/home/anthony/nvidia/projects/aiperf/guidebook/chapter-43-common-patterns.md`
- **Purpose**: Common design patterns in AIPerf
- **Target Audience**: Developers extending AIPerf
- **Related Files**:
  - `/home/anthony/nvidia/projects/aiperf/aiperf/common/base_service.py`
  - `/home/anthony/nvidia/projects/aiperf/aiperf/common/factories.py`
  - `/home/anthony/nvidia/projects/aiperf/aiperf/common/hooks.py`
  - `/home/anthony/nvidia/projects/aiperf/aiperf/common/mixins/`
