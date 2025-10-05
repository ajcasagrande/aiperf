# Chapter 5: Architecture Fundamentals

<!--
# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
-->

## Table of Contents
- [High-Level Architecture Overview](#high-level-architecture-overview)
- [Service Architecture](#service-architecture)
- [Data Flow Architecture](#data-flow-architecture)
- [Communication Architecture](#communication-architecture)
- [Process Model](#process-model)
- [Key Design Patterns](#key-design-patterns)
- [Key Takeaways](#key-takeaways)

## High-Level Architecture Overview

AIPerf follows a distributed, message-driven architecture where independent services communicate through ZeroMQ message passing. The architecture is designed for scalability, modularity, and precise measurement.

### Architectural Diagram

```
┌────────────────────────────────────────────────────────────────────────┐
│                         System Controller                              │
│  - Lifecycle orchestration                                             │
│  - Command distribution                                                │
│  - Result aggregation                                                  │
│  - UI and export                                                       │
└───────────┬─────────────┬──────────────┬───────────────┬──────────────┘
            │             │              │               │
    ┌───────┘             │              │               └───────┐
    │                     │              │                       │
    v                     v              v                       v
┌──────────┐      ┌──────────────┐  ┌──────────────┐  ┌─────────────────┐
│ Timing   │      │   Dataset    │  │    Worker    │  │    Records      │
│ Manager  │      │   Manager    │  │    Manager   │  │    Manager      │
│          │      │              │  │              │  │                 │
│ - Credit │      │ - Data       │  │ - Health     │  │ - Aggregation   │
│   issuing│      │   loading    │  │   monitoring │  │ - Statistics    │
│ - Phases │      │ - Serving    │  │ - Status     │  │ - Completion    │
└────┬─────┘      └──────┬───────┘  │   tracking   │  └────────┬────────┘
     │                   │          └──────┬───────┘           │
     │ Credits           │ Data            │                   │
     │                   │                 │ Spawn             │
     v                   v                 v                   │
┌────────────────────────────────────────────────────┐         │
│                  Workers (N)                       │         │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐        │         │
│  │ Worker 1 │  │ Worker 2 │  │ Worker N │  ...   │         │
│  │          │  │          │  │          │        │         │
│  │ - Pull   │  │ - Pull   │  │ - Pull   │        │         │
│  │   credits│  │   credits│  │   credits│        │         │
│  │ - Request│  │ - Request│  │ - Request│        │         │
│  │   data   │  │   data   │  │   data   │        │         │
│  │ - Execute│  │ - Execute│  │ - Execute│        │         │
│  │ - Measure│  │ - Measure│  │ - Measure│        │         │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘        │         │
└───────┼─────────────┼─────────────┼──────────────┘         │
        │             │             │                         │
        │    Raw Records            │                         │
        └──────────┬──────────────┬─┘                         │
                   v              v                           │
            ┌────────────────────────────┐                    │
            │  Record Processors (M)     │                    │
            │  - Parse responses         │                    │
            │  - Extract metrics         │                    │
            │  - Compute values          │  Metric Records    │
            └──────────────┬─────────────┘──────────────────→─┘
                           │
                           v
                    ┌──────────────┐
                    │  Inference   │
                    │  Server      │
                    │  (Target)    │
                    └──────────────┘
```

### Architecture Principles

1. **Separation of Concerns**: Each service has a single, well-defined responsibility
2. **Message-Driven**: No direct coupling; all communication via messages
3. **Process Isolation**: Each service in its own process for failure isolation
4. **Asynchronous Processing**: Non-blocking operations throughout
5. **Backpressure Support**: Credit system prevents overwhelming services
6. **Observable**: Comprehensive logging and monitoring at all levels

## Service Architecture

### Service Hierarchy

```
BaseLifecycle (abstract)
    │
    ├── BaseService (abstract)
    │      │
    │      ├── SystemController
    │      └── BaseComponentService
    │             │
    │             ├── TimingManager
    │             ├── DatasetManager
    │             ├── WorkerManager
    │             ├── Worker
    │             ├── RecordProcessorService
    │             └── RecordsManager
    │
    └── AIPerfUI (protocol)
           ├── DashboardUI
           ├── SimpleUI
           └── NoUI
```

### Service Composition

Services are composed of mixins for shared behavior:

```python
class Worker(
    PullClientMixin,      # Pull credit drops
    BaseComponentService, # Component service base
    ProcessHealthMixin    # Health reporting
):
    pass

class TimingManager(
    PullClientMixin,           # Pull credit returns
    BaseComponentService,       # Component service base
    CreditPhaseMessagesMixin   # Phase messaging
):
    pass
```

**Key Mixins**:
- `PullClientMixin`: PULL socket management with semaphore
- `PushClientMixin`: PUSH socket management
- `ReplyClientMixin`: ROUTER socket for request/reply
- `CommandHandlerMixin`: Command processing
- `ProcessHealthMixin`: Health metrics collection
- `WorkerTrackerMixin`: Worker status tracking
- `TaskManagerMixin`: Background task management

### Service Configuration

Each service receives two configuration objects:

#### UserConfig
User-provided benchmark configuration:
- Endpoint settings (URL, model, type)
- Load generation (concurrency, rate, duration)
- Dataset settings (input file, synthetic params)
- Output settings (artifact directory)

Location: `/home/anthony/nvidia/projects/aiperf/aiperf/common/config/user_config.py`

#### ServiceConfig
System-level configuration:
- Worker limits (min, max)
- Record processor count
- UI type
- Service run type (multiprocess, k8s)
- Logging configuration

Location: `/home/anthony/nvidia/projects/aiperf/aiperf/common/config/service_config.py`

### Service Registration

Services register with the System Controller on startup:

```python
@on_start
async def _register_with_controller(self):
    await self.publish(
        RegisterServiceCommand(
            service_id=self.service_id,
            service_type=self.service_type,
            state=self.state
        )
    )
```

System Controller tracks all registered services:

```python
self.service_id_map: dict[str, ServiceRunInfo] = {}
self.service_map: dict[ServiceType, list[ServiceRunInfo]] = {}
```

## Data Flow Architecture

### Primary Data Flows

AIPerf has several distinct data flows:

#### 1. Credit Flow (Request Scheduling)

```
Timing Manager
    │ Determine next request time
    │ Select strategy (concurrency/rate/schedule)
    v
Issue Credit Drop
    │ CreditDropMessage(phase, conversation_id, ...)
    │
    v
[PUSH Socket] → [Proxy] → [PULL Socket]
    │
    v
Worker pulls when ready
    │ Semaphore limits concurrency
    │
    v
Execute Request
    │
    v
Return Credit
    │ CreditReturnMessage(phase, credit_drop_id)
    │
    v
[PUSH Socket] → [PULL Socket]
    │
    v
Timing Manager receives return
    │ Update in-flight count
    │ Check phase completion
```

#### 2. Data Request Flow (Conversation Retrieval)

```
Worker needs conversation data
    │
    v
Send Conversation Request
    │ ConversationRequestMessage(conversation_id?)
    │
    v
[DEALER Socket] → [Proxy] → [ROUTER Socket]
    │
    v
Dataset Manager
    │ Lookup or select conversation
    │ Return conversation data
    v
ConversationResponseMessage
    │ Conversation(session_id, turns)
    │
    v
[ROUTER Socket] → [Proxy] → [DEALER Socket]
    │
    v
Worker receives conversation
    │ Format payload
    │ Send to inference server
```

#### 3. Result Flow (Metrics Pipeline)

```
Worker completes request
    │ Capture timestamps
    │ Record response
    v
Create RequestRecord
    │ All timing and response data
    │
    v
InferenceResultsMessage
    │ Contains RequestRecord
    │
    v
[PUSH Socket] → [Proxy] → [PULL Socket]
    │
    v
Record Processor
    │ Parse response
    │ Extract tokens
    │ Compute per-request metrics
    v
MetricRecordsMessage
    │ list[dict[MetricTag, Value]]
    │
    v
[PUSH Socket] → [PULL Socket]
    │
    v
Records Manager
    │ Aggregate across all records
    │ Build statistics
    │ Track completion
    v
Process Records Result
    │ Complete metrics
    │ Error summary
    │
    v
System Controller
    │ Export to files
    │ Display in UI
```

#### 4. Command Flow (Lifecycle Control)

```
System Controller
    │ Orchestrates lifecycle
    │
    v
Broadcast Command
    │ ProfileConfigureCommand
    │ ProfileStartCommand
    │ ShutdownCommand
    │
    v
[PUB Socket] → [Message Bus] → [SUB Sockets]
    │                               │
    │                               v
    │                          All Services
    │                               │
    │                               v
    │                     Execute command handlers
    │                               │
    └───────────────────────────────┤
                                    v
                          CommandResponse
                                    │
                                    v
                          [PUB Socket]
                                    │
                                    v
                          System Controller
                               │ Collect responses
                               │ Wait for all
                               v
                          Continue lifecycle
```

### Data Serialization

AIPerf uses **Pydantic** for all data serialization:

```python
class CreditDropMessage(BaseMessage):
    service_id: str
    phase: CreditPhase
    request_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    # ... more fields

    # Serialization
    def to_bytes(self) -> bytes:
        return self.model_dump_json().encode()

    # Deserialization
    @classmethod
    def from_bytes(cls, data: bytes):
        return cls.model_validate_json(data)
```

**Benefits**:
- Type safety
- Validation
- JSON compatibility
- Easy debugging
- Automatic documentation

## Communication Architecture

### ZeroMQ Socket Types and Patterns

#### PUB/SUB Pattern
```
Publisher                          Subscribers
┌──────────┐                      ┌──────────┐
│  bind()  │                      │ connect()│
│  PUB     │──┐                ┌──│  SUB     │
└──────────┘  │                │  └──────────┘
              │   ┌─────────┐  │  ┌──────────┐
              └──→│ Message │──┼──│  SUB     │
                  │  Bus    │  │  └──────────┘
                  └─────────┘  │  ┌──────────┐
                               └──│  SUB     │
                                  └──────────┘
```

**Characteristics**:
- One-to-many broadcast
- Subscribers can filter by topic
- No delivery guarantees
- Fire and forget

**Usage**: Commands, status updates, phase announcements

#### PUSH/PULL Pattern
```
Pushers                 Proxy                 Pullers
┌──────────┐          ┌─────────┐          ┌──────────┐
│ connect()│          │  PULL   │          │  bind()  │
│  PUSH    │──┐       │   │     │       ┌──│  PULL    │
└──────────┘  │       │   v     │       │  └──────────┘
              │       │  PUSH   │       │  ┌──────────┐
┌──────────┐  │       │         │       ├──│  PULL    │
│  PUSH    │──┼──────→│ (Load   │──────→│  └──────────┘
└──────────┘  │       │  Balance)       │  ┌──────────┐
              │       │         │       └──│  PULL    │
┌──────────┐  │       └─────────┘          └──────────┘
│  PUSH    │──┘
└──────────┘
```

**Characteristics**:
- One-to-many work distribution
- Load balancing (round-robin)
- Fair queuing
- Backpressure support

**Usage**: Credit drops, credit returns, inference results, metric records

#### DEALER/ROUTER Pattern
```
Clients (DEALER)       Proxy                Server (DEALER)
┌──────────┐          ┌─────────┐          ┌──────────┐
│ connect()│  Request │ ROUTER  │  Request │  bind()  │
│  DEALER  │─────────→│    │    │─────────→│  DEALER  │
└──────────┘          │    v    │          └──────────┘
                      │ DEALER  │             │
                      │         │    Response │
                      │         │←────────────┘
                      └─────────┘
```

**Characteristics**:
- Request-reply with routing
- Async request-response
- Multiple concurrent requests
- Identity-based routing

**Usage**: Conversation requests, dataset timing requests

### Proxy Architecture Details

AIPerf uses **Device Proxies** to decouple services:

```python
# In ProxyManager
class ProxyManager:
    async def initialize_and_start(self):
        # PUB/SUB Message Bus
        self.message_bus_proxy = PubSubProxy(
            frontend_address=CommAddress.MESSAGE_BUS_FRONTEND,
            backend_address=CommAddress.MESSAGE_BUS
        )

        # Credit Drop PUSH/PULL
        self.credit_drop_proxy = PushPullProxy(
            frontend_address=CommAddress.CREDIT_DROP,
            backend_address=CommAddress.CREDIT_DROP_BACKEND
        )

        # Dataset Request DEALER/ROUTER
        self.dataset_request_proxy = DealerRouterProxy(
            frontend_address=CommAddress.DATASET_MANAGER_PROXY_FRONTEND,
            backend_address=CommAddress.DATASET_MANAGER_PROXY_BACKEND
        )

        # Start all proxies
        await asyncio.gather(
            self.message_bus_proxy.start(),
            self.credit_drop_proxy.start(),
            # ... more proxies
        )
```

Location: `/home/anthony/nvidia/projects/aiperf/aiperf/controller/proxy_manager.py`

**Proxy Benefits**:
1. **Address Decoupling**: Services don't know about each other
2. **Centralized Routing**: Single point for message flow
3. **Dynamic Topology**: Services can come and go
4. **Monitoring Point**: Can log all messages at proxy
5. **Scalability**: Easy to add more workers

### Message Types

AIPerf defines three message categories:

#### 1. Commands
Request action from services:
- `ProfileConfigureCommand`: Configure for benchmark
- `ProfileStartCommand`: Start benchmarking
- `ProfileCancelCommand`: Cancel benchmark
- `ShutdownCommand`: Shut down service
- `SpawnWorkersCommand`: Create workers
- `RealtimeMetricsCommand`: Request current metrics

#### 2. Messages
Information flow:
- `CreditDropMessage`: Request execution permission
- `CreditReturnMessage`: Return permission
- `HeartbeatMessage`: Service health
- `StatusMessage`: State updates
- `InferenceResultsMessage`: Raw results
- `MetricRecordsMessage`: Processed metrics
- Phase messages (start, sending complete, complete)

#### 3. Responses
Reply to commands/requests:
- `CommandResponse`: Success/failure
- `CommandAcknowledgedResponse`: Received
- `CommandErrorResponse`: Failed with error
- `ConversationResponseMessage`: Conversation data
- `DatasetTimingResponse`: Timing data

### Message Routing

```
Message Type → Routing Pattern

Commands        → PUB/SUB (broadcast)
Status Updates  → PUB/SUB (broadcast)
Credit Drops    → PUSH/PULL (load balanced)
Credit Returns  → PUSH/PULL (direct)
Results         → PUSH/PULL (pipelined)
Data Requests   → DEALER/ROUTER (req/rep)
Responses       → DEALER/ROUTER (reply)
```

## Process Model

### Multiprocess Architecture

AIPerf uses Python's `multiprocessing` module:

```python
# Service spawning
def spawn_service(
    service_type: ServiceType,
    user_config: UserConfig,
    service_config: ServiceConfig
):
    process = multiprocessing.Process(
        target=_service_main,
        args=(service_type, user_config, service_config),
        daemon=False  # Explicit lifecycle
    )
    process.start()
    return process
```

### Process Lifecycle

```
Main Process (CLI)
    │
    └─→ Create ServiceConfig & UserConfig
        │
        └─→ Start System Controller Process
            │
            ├─→ Initialize Proxy Manager
            │   └─→ Start all ZMQ proxies (threads)
            │
            ├─→ Spawn Timing Manager Process
            │
            ├─→ Spawn Dataset Manager Process
            │
            ├─→ Spawn Worker Manager Process
            │   │
            │   └─→ Spawn Worker Processes (N)
            │
            ├─→ Spawn Records Manager Process
            │
            └─→ Spawn Record Processor Processes (M)
```

### Inter-Process Communication

All IPC via ZeroMQ:
- **No shared memory**: Each process has isolated memory
- **No locks needed**: Message passing eliminates shared state
- **Process safety**: Crashes don't affect other processes

### Process Health Monitoring

Workers report health via `psutil`:

```python
import psutil

class ProcessHealthMixin:
    def get_process_health(self) -> ProcessHealth:
        process = psutil.Process()
        return ProcessHealth(
            cpu_usage=process.cpu_percent(),
            memory_mb=process.memory_info().rss / 1024 / 1024,
            io_read_mb=process.io_counters().read_bytes / 1024 / 1024,
            io_write_mb=process.io_counters().write_bytes / 1024 / 1024,
            cpu_times=process.cpu_times(),
            ctx_switches=process.num_ctx_switches()
        )
```

### Process Shutdown

Graceful shutdown sequence:

1. Signal received (SIGINT/SIGTERM)
2. System Controller broadcasts ShutdownCommand
3. Services receive command
4. Services execute @on_stop hooks
5. Services close ZMQ sockets
6. Services cancel background tasks
7. Services set stopped event
8. Processes exit

## Key Design Patterns

### 1. Factory Pattern

Services, clients, and processors created via factories:

```python
@ServiceFactory.register(ServiceType.WORKER)
class Worker(BaseComponentService):
    pass

# Usage
worker = ServiceFactory.create_instance(
    ServiceType.WORKER,
    service_config=service_config,
    user_config=user_config
)
```

### 2. Decorator Pattern

Lifecycle hooks use decorators:

```python
@on_init
async def initialize(self):
    pass

@on_start
async def start(self):
    pass

@background_task(interval=5.0)
async def periodic_task(self):
    pass

@on_command(CommandType.SHUTDOWN)
async def handle_shutdown(self, cmd):
    pass
```

### 3. Protocol Pattern

Interfaces defined via Protocols:

```python
class ServiceProtocol(Protocol):
    async def initialize(self) -> None: ...
    async def start(self) -> None: ...
    async def stop(self) -> None: ...
```

### 4. Mixin Pattern

Shared behavior via mixins:

```python
class Worker(
    PullClientMixin,
    BaseComponentService,
    ProcessHealthMixin
):
    pass
```

### 5. Strategy Pattern

Credit issuing strategies:

```python
class CreditIssuingStrategy(ABC):
    @abstractmethod
    async def _execute_single_phase(self, phase_stats):
        pass

class ConcurrencyStrategy(CreditIssuingStrategy):
    async def _execute_single_phase(self, phase_stats):
        # Concurrency-based implementation
        pass

class RequestRateStrategy(CreditIssuingStrategy):
    async def _execute_single_phase(self, phase_stats):
        # Rate-based implementation
        pass
```

### 6. Observer Pattern

Services observe message bus:

```python
@on_message(MessageType.STATUS)
async def observe_status(self, msg: StatusMessage):
    self.service_statuses[msg.service_id] = msg.state
```

## Key Takeaways

1. **Distributed Architecture**: AIPerf is a true distributed system, even when running on a single machine.

2. **Message-Driven Design**: All communication via typed messages over ZeroMQ enables loose coupling and scalability.

3. **Process-Per-Service**: Each service runs in its own process for isolation, parallelism, and fault tolerance.

4. **Proxy Decoupling**: ZeroMQ proxies decouple services, simplifying addressing and enabling dynamic topology.

5. **Multiple Data Flows**: Credit flow, data flow, result flow, and command flow operate independently and concurrently.

6. **Composition Over Inheritance**: Mixins provide shared behavior without deep inheritance hierarchies.

7. **Type-Safe Messages**: Pydantic models ensure type safety and validation throughout the system.

8. **Hook-Based Lifecycle**: Decorator-based hooks provide clean separation of lifecycle concerns.

9. **Strategy-Based Extensibility**: Load generation strategies, metric types, and exporters are easily extensible.

10. **Health Monitoring**: Comprehensive health and status tracking at every level enables observability and debugging.

This architecture enables AIPerf to scale from simple benchmarks to complex, high-concurrency testing scenarios while maintaining measurement precision and system reliability.

---

Next: [Chapter 6: System Controller](chapter-06-system-controller.md)
