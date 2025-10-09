<!--
SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
SPDX-License-Identifier: Apache-2.0
-->

# AIPerf Developer Guide

This comprehensive guide provides technical documentation for developers working with the AIPerf codebase. It covers architecture, implementation details, design patterns, and extension points.

---

## Table of Contents

- [Architecture Overview](#architecture-overview)
- [Project Structure](#project-structure)
- [Core Systems](#core-systems)
- [Design Patterns](#design-patterns)
- [Component Details](#component-details)
- [Data Flow](#data-flow)
- [Extension Points](#extension-points)
- [Development Workflow](#development-workflow)
- [Testing](#testing)
- [Performance Considerations](#performance-considerations)

---

## Architecture Overview

### High-Level Architecture

AIPerf follows a **microservices architecture** where independent services communicate via ZeroMQ messaging. This design enables:

- **Scalability**: Multiple worker processes can run concurrently
- **Modularity**: Services can be modified or replaced independently
- **Fault Isolation**: Service failures don't cascade to other components
- **Flexibility**: Supports both single-node (multiprocess) and multi-node (Kubernetes) deployments

### Service-Based Design

```
┌─────────────────────────────────────────────────────────────┐
│                      System Controller                      │
│  (Central orchestrator managing all services and lifecycle) │
└──────────────┬──────────────────────────────────────────────┘
               │
               ├── Orchestrates initialization, configuration, and execution
               │
       ┌───────┴──────┬──────────┬─────────────┬──────────┐
       │              │          │             │          │
       ▼              ▼          ▼             ▼          ▼
   ┌────────┐  ┌──────────┐ ┌────────┐  ┌──────────┐ ┌─────────┐
   │Dataset │  │  Timing  │ │Worker  │  │  Record  │ │Records  │
   │Manager │  │ Manager  │ │Manager │  │Processor │ │ Manager │
   └────────┘  └──────────┘ └────────┘  └──────────┘ └─────────┘
       │              │          │             │          │
       │              │          └──────┬──────┘          │
       │              │                 │                 │
       │              ▼                 ▼                 │
       │         ┌─────────────────────────┐             │
       │         │      ZMQ Proxies        │             │
       │         │  (Message forwarding)   │             │
       │         └─────────────────────────┘             │
       │                                                  │
       ▼                                                  ▼
  Conversations                                      Final Results
  & Prompts                                         & Metrics
```

### Communication Infrastructure

AIPerf uses **ZeroMQ (ZMQ)** for inter-service communication. Key patterns:

1. **PUB/SUB**: Broadcast messages (e.g., status updates, commands)
2. **PUSH/PULL**: One-way data flow with load balancing (e.g., credits, records)
3. **REQ/REP**: Request-response pattern (e.g., dataset queries)

**ZMQ Proxies** enable many-to-many communication by forwarding messages between multiple sources and destinations.

Source: `aiperf/zmq/`, `aiperf/controller/proxy_manager.py`

---

## Project Structure

### Directory Layout

```
aiperf/
├── aiperf/                      # Main package
│   ├── cli.py                   # CLI entry point
│   ├── cli_runner.py            # System controller runner
│   ├── cli_utils.py             # CLI utilities
│   │
│   ├── clients/                 # HTTP clients for inference servers
│   │   ├── http/                # HTTP client implementations
│   │   ├── openai/              # OpenAI-specific clients
│   │   └── model_endpoint_info.py  # Endpoint metadata
│   │
│   ├── common/                  # Shared code and infrastructure
│   │   ├── base_service.py      # Base service class
│   │   ├── base_component_service.py  # Component service base
│   │   ├── bootstrap.py         # Service bootstrapping
│   │   ├── constants.py         # System constants
│   │   ├── decorators.py        # Python decorators
│   │   ├── exceptions.py        # Custom exceptions
│   │   ├── factories.py         # Factory classes
│   │   ├── hooks.py             # Lifecycle hooks
│   │   ├── logging.py           # Logging configuration
│   │   ├── protocols.py         # Type protocols
│   │   ├── tokenizer.py         # Tokenization wrapper
│   │   ├── types.py             # Type aliases
│   │   ├── utils.py             # Utility functions
│   │   │
│   │   ├── comms/               # Communication layer
│   │   │   └── zmq_comms.py     # ZMQ communication wrapper
│   │   │
│   │   ├── config/              # Configuration management
│   │   │   ├── base_config.py   # Base configuration class
│   │   │   ├── user_config.py   # User-facing configuration
│   │   │   ├── service_config.py # Service configuration
│   │   │   ├── cli_parameter.py # CLI parameter definitions
│   │   │   └── ...              # Specific config modules
│   │   │
│   │   ├── enums/               # Enumeration types
│   │   │   ├── service_enums.py
│   │   │   ├── metric_enums.py
│   │   │   ├── timing_enums.py
│   │   │   ├── dataset_enums.py
│   │   │   └── ...
│   │   │
│   │   ├── messages/            # Message types for IPC
│   │   │   ├── base_messages.py
│   │   │   ├── command_messages.py
│   │   │   ├── credit_messages.py
│   │   │   └── ...
│   │   │
│   │   ├── mixins/              # Reusable service mixins
│   │   │   ├── communication_mixin.py
│   │   │   ├── pull_client_mixin.py
│   │   │   ├── push_client_mixin.py
│   │   │   └── ...
│   │   │
│   │   ├── models/              # Data models (Pydantic)
│   │   │   ├── record_models.py
│   │   │   ├── service_models.py
│   │   │   ├── error_models.py
│   │   │   └── ...
│   │   │
│   │   └── service/             # Service base implementations
│   │
│   ├── controller/              # System orchestration
│   │   ├── system_controller.py # Main controller
│   │   ├── base_service_manager.py
│   │   ├── multiprocess_service_manager.py
│   │   ├── kubernetes_service_manager.py
│   │   ├── proxy_manager.py     # ZMQ proxy management
│   │   └── system_mixins.py
│   │
│   ├── dataset/                 # Dataset management
│   │   ├── dataset_manager.py   # Dataset service
│   │   ├── composer/            # Dataset composers
│   │   │   ├── synthetic.py
│   │   │   ├── custom.py
│   │   │   └── ...
│   │   ├── generator/           # Data generators
│   │   │   ├── prompt.py
│   │   │   ├── audio.py
│   │   │   └── image.py
│   │   └── loader/              # Dataset loaders
│   │       ├── sharegpt.py
│   │       ├── mooncake_trace.py
│   │       └── ...
│   │
│   ├── exporters/               # Results export
│   │   ├── exporter_manager.py
│   │   ├── console_metrics_exporter.py
│   │   ├── csv_exporter.py
│   │   └── json_exporter.py
│   │
│   ├── metrics/                 # Metrics system
│   │   ├── base_metric.py       # Base metric class
│   │   ├── base_record_metric.py
│   │   ├── base_aggregate_metric.py
│   │   ├── base_derived_metric.py
│   │   ├── metric_registry.py   # Metric registration
│   │   ├── metric_dicts.py      # Metric data structures
│   │   └── types/               # Metric implementations
│   │       ├── request_latency_metric.py
│   │       ├── ttft_metric.py
│   │       └── ...
│   │
│   ├── parsers/                 # Response parsing
│   │   ├── inference_result_parser.py
│   │   └── openai_parsers.py
│   │
│   ├── post_processors/         # Results processing
│   │   ├── metric_record_processor.py
│   │   └── metric_results_processor.py
│   │
│   ├── records/                 # Records management
│   │   ├── records_manager.py   # Records service
│   │   ├── record_processor_service.py
│   │   └── phase_completion.py  # Phase tracking
│   │
│   ├── timing/                  # Request timing
│   │   ├── timing_manager.py    # Timing service
│   │   ├── credit_manager.py
│   │   ├── credit_issuing_strategy.py
│   │   ├── request_rate_strategy.py
│   │   ├── fixed_schedule_strategy.py
│   │   └── request_cancellation_strategy.py
│   │
│   ├── ui/                      # User interfaces
│   │   ├── dashboard/           # Rich TUI dashboard
│   │   ├── tqdm_ui.py           # Simple progress bar
│   │   └── no_ui.py             # No UI mode
│   │
│   ├── workers/                 # Request execution
│   │   ├── worker.py            # Worker service
│   │   ├── worker_manager.py    # Worker orchestration
│   │   └── credit_processor_mixin.py
│   │
│   └── zmq/                     # ZMQ infrastructure
│       ├── zmq_comms.py
│       ├── zmq_base_client.py
│       ├── pub_client.py
│       ├── sub_client.py
│       ├── push_client.py
│       ├── pull_client.py
│       ├── dealer_request_client.py
│       ├── router_reply_client.py
│       └── zmq_proxy_*.py
│
├── tests/                       # Test suite
│   ├── clients/
│   ├── common/
│   ├── metrics/
│   └── ...
│
├── docs/                        # Documentation
│   ├── architecture.md
│   ├── metrics_reference.md
│   ├── cli_options.md
│   ├── terminology-glossary.md
│   ├── developer-guide.md       # This file
│   └── user-guide.md
│
├── integration-tests/           # Integration tests
├── pyproject.toml              # Project configuration
└── README.md                   # Main documentation
```

### Module Organization Principles

1. **Separation of Concerns**: Each module has a single, well-defined responsibility
2. **Layered Architecture**: Clear separation between services, infrastructure, and business logic
3. **Common Infrastructure**: Shared code in `common/` used by all services
4. **Plugin Architecture**: Factories and registries enable extensibility

---

## Core Systems

### 1. Service Lifecycle System

**Purpose**: Manage the lifecycle of services from creation to shutdown.

**Key Components**:
- `BaseService` - Base class for all services
- `BaseComponentService` - Base for component services (not System Controller)
- Lifecycle hooks: `@on_init`, `@on_start`, `@on_stop`
- Lifecycle states: CREATED → INITIALIZING → INITIALIZED → STARTING → RUNNING → STOPPING → STOPPED

**Source**: `aiperf/common/base_service.py`, `aiperf/common/base_component_service.py`

**Implementation Details**:

```python
class BaseService:
    async def initialize(self) -> None:
        """Initialize the service - call @on_init hooks"""
        self._lifecycle_state = LifecycleState.INITIALIZING
        await self._run_lifecycle_hooks("on_init")
        self._lifecycle_state = LifecycleState.INITIALIZED

    async def start(self) -> None:
        """Start the service - call @on_start hooks"""
        self._lifecycle_state = LifecycleState.STARTING
        await self._run_lifecycle_hooks("on_start")
        self._lifecycle_state = LifecycleState.RUNNING

    async def stop(self) -> None:
        """Stop the service - call @on_stop hooks"""
        self._lifecycle_state = LifecycleState.STOPPING
        await self._run_lifecycle_hooks("on_stop")
        self._lifecycle_state = LifecycleState.STOPPED
```

**Key Patterns**:
- Services use **asyncio** for concurrency
- **Hooks** (@on_init, @on_start, @on_stop) execute lifecycle logic
- **Context managers** enable automatic lifecycle management
- Services can have **child lifecycles** that are managed automatically

### 2. Communication System (ZeroMQ)

**Purpose**: Enable high-performance inter-service communication.

**Key Components**:
- `ZMQComms` - Main communication wrapper
- Client classes: `PushClient`, `PullClient`, `PubClient`, `SubClient`, `RequestClient`, `ReplyClient`
- Mixins: `PullClientMixin`, `PushClientMixin`, `ReplyClientMixin`
- Proxies: `ZMQProxyBase`, `PullPushProxy`, `RouterDealerProxy`

**Source**: `aiperf/zmq/`, `aiperf/common/mixins/`, `aiperf/controller/proxy_manager.py`

**Communication Patterns**:

1. **PUB/SUB** (Broadcast):
   - System Controller → All Services (commands, status)
   - Workers → System (health, status updates)

2. **PUSH/PULL** (Load Balanced Pipeline):
   - Timing Manager → Workers (credit distribution)
   - Workers → Record Processors (inference results)
   - Record Processors → Records Manager (processed records)

3. **REQ/REP** (Request-Response):
   - Workers → Dataset Manager (conversation requests)
   - Timing Manager → Dataset Manager (timing data requests)

**Key Design Decisions**:
- **Asynchronous I/O**: All ZMQ operations use async/await
- **Proxies for Scalability**: Enable many-to-many connections without N² socket connections
- **Type-Safe Messages**: All messages are Pydantic models
- **Automatic Serialization**: Messages serialize to/from JSON automatically

### 3. Metrics System

**Purpose**: Compute, collect, and aggregate performance metrics.

**Architecture**:

```
Metric Computation Flow:
1. Worker sends request to inference server
2. Worker receives response(s)
3. Worker creates raw inference result with timestamps
4. Record Processor receives raw result
5. Record Processor computes per-request metrics (Record Metrics)
6. Record Processor sends MetricRecordsMessage to Records Manager
7. Records Manager updates aggregate metrics (Aggregate Metrics)
8. After all records collected, compute derived metrics (Derived Metrics)
9. Export final results
```

**Metric Types**:

1. **Record Metrics** (per-request):
   - Computed by `MetricRecordProcessor`
   - Produce distributions (min, max, mean, percentiles)
   - Examples: request_latency, ttft, itl, token counts
   - Implementation: Inherit from `BaseRecordMetric[T]`

2. **Aggregate Metrics** (across all requests):
   - Computed incrementally by `Records Manager`
   - Produce single values
   - Examples: request_count, error_count, min/max timestamps
   - Implementation: Inherit from `BaseAggregateMetric[T]`

3. **Derived Metrics** (computed from other metrics):
   - Computed by `MetricResultsProcessor` after collection
   - Use formulas based on other metrics
   - Examples: request_throughput, output_token_throughput
   - Implementation: Inherit from `BaseDerivedMetric[T]`

**Source**: `aiperf/metrics/`, `aiperf/post_processors/`

**Metric Registration**:

```python
from aiperf.metrics import BaseRecordMetric

class MyCustomMetric(BaseRecordMetric[float]):
    tag = "my_custom_metric"
    header = "My Custom Metric"
    unit = MetricTimeUnit.MILLISECONDS
    display_order = 100

    def compute(self, record: ParsedResponseRecord) -> float:
        # Implement computation logic
        return some_value
```

Metrics are **automatically registered** via `__init_subclass__` and stored in `MetricRegistry`.

**Key Features**:
- **Type-Safe**: Generic types ensure value type correctness
- **Auto-Registration**: Metrics register themselves on definition
- **Extensible**: Easy to add new metrics
- **Conditional Computation**: Metrics can specify requirements (streaming, token-producing, etc.)
- **Unit Conversion**: Built-in unit conversion system

### 4. Configuration System

**Purpose**: Manage user configuration and service settings.

**Key Components**:
- `UserConfig` - User-facing configuration (from CLI)
- `ServiceConfig` - Internal service configuration
- `CLIParameter` - CLI parameter definitions with validation
- Config groups: `EndpointConfig`, `LoadGenConfig`, `InputConfig`, etc.

**Source**: `aiperf/common/config/`

**Configuration Flow**:

```
CLI Args → Cyclopts → UserConfig (Pydantic validation) → Services
```

**Implementation**:

```python
class UserConfig(BaseModel):
    endpoint: EndpointConfig
    input: InputConfig
    prompt: PromptConfig
    loadgen: LoadGenConfig
    output: OutputConfig
    tokenizer: TokenizerConfig
    # ... other config groups

    @validator("...")
    def validate_something(cls, value, values):
        # Custom validation logic
        return value
```

**Key Features**:
- **Pydantic Models**: Type-safe with automatic validation
- **Nested Structure**: Logically grouped configuration
- **CLI Integration**: Seamless mapping from CLI to config
- **Validators**: Custom validation logic for complex constraints
- **Defaults**: Sensible defaults for all parameters

### 5. Factory & Registry Pattern

**Purpose**: Enable extensibility and plugin architecture.

**Key Factories**:
- `ServiceFactory` - Creates service instances by type
- `ComposerFactory` - Creates dataset composers
- `InferenceClientFactory` - Creates HTTP clients
- `RequestConverterFactory` - Creates request formatters
- `MetricRegistry` - Registers and retrieves metrics

**Source**: `aiperf/common/factories.py`, `aiperf/metrics/metric_registry.py`

**Implementation Pattern**:

```python
class MyFactory:
    _registry: dict[str, Type] = {}

    @classmethod
    def register(cls, key: str):
        """Decorator to register a class"""
        def decorator(registered_class):
            cls._registry[key] = registered_class
            return registered_class
        return decorator

    @classmethod
    def create_instance(cls, key: str, **kwargs):
        """Create an instance by key"""
        if key not in cls._registry:
            raise ValueError(f"Unknown key: {key}")
        return cls._registry[key](**kwargs)
```

**Usage Example**:

```python
@ServiceFactory.register(ServiceType.MY_SERVICE)
class MyService(BaseService):
    pass

# Later:
service = ServiceFactory.create_instance(ServiceType.MY_SERVICE, ...)
```

**Benefits**:
- **Decoupling**: Components don't need to know about implementations
- **Extensibility**: New implementations register themselves
- **Type Safety**: Registry ensures correct types
- **Discovery**: Can enumerate all registered types

---

## Design Patterns

### 1. Mixin Pattern

**Purpose**: Provide reusable functionality to services via multiple inheritance.

**Key Mixins**:
- `PullClientMixin` - Adds ZMQ PULL client and message handling
- `PushClientMixin` - Adds ZMQ PUSH client functionality
- `ReplyClientMixin` - Adds ZMQ REP server functionality
- `ProcessHealthMixin` - Adds CPU/memory monitoring
- `CommunicationMixin` - Adds message bus subscription

**Source**: `aiperf/common/mixins/`

**Implementation**:

```python
class PullClientMixin:
    """Mixin that adds PULL client functionality"""

    def __init__(self, pull_client_address, pull_client_max_concurrency=1000, **kwargs):
        super().__init__(**kwargs)  # Pass to next in MRO
        self.pull_client = self.comms.create_pull_client(
            address=pull_client_address,
            max_concurrency=pull_client_max_concurrency,
            message_handler=self._dispatch_pull_message,
        )

    async def _dispatch_pull_message(self, message):
        """Route messages to registered handlers"""
        handler = self._pull_message_handlers.get(message.type)
        if handler:
            await handler(message)
```

**Usage**:

```python
class MyService(PullClientMixin, BaseComponentService):
    def __init__(self, **kwargs):
        super().__init__(
            pull_client_address=CommAddress.MY_ADDRESS,
            pull_client_max_concurrency=1000,
            **kwargs
        )

    @on_pull_message(MessageType.MY_MESSAGE)
    async def handle_my_message(self, message):
        # Handle message
        pass
```

**MRO (Method Resolution Order)** ensures mixins cooperate correctly via `super()`.

### 2. Hook Pattern

**Purpose**: Enable declarative lifecycle and event handling.

**Hook Types**:
- `@on_init` - Called during initialization
- `@on_start` - Called when service starts
- `@on_stop` - Called when service stops
- `@on_command(CommandType.X)` - Handle specific command types
- `@on_message(MessageType.X)` - Handle specific message types
- `@on_pull_message(MessageType.X)` - Handle messages from PULL client
- `@on_request(MessageType.X)` - Handle REQ/REP requests
- `@background_task(interval=X)` - Run periodic background tasks

**Source**: `aiperf/common/hooks.py`

**Implementation**:

```python
def on_init(func):
    """Mark method to be called during initialization"""
    func._aiperf_hook = "on_init"
    return func

class BaseService:
    def __init__(self):
        # Discover all hooks during initialization
        self._hooks = defaultdict(list)
        for name in dir(self):
            method = getattr(self, name)
            if hasattr(method, "_aiperf_hook"):
                hook_type = method._aiperf_hook
                self._hooks[hook_type].append(method)

    async def _run_lifecycle_hooks(self, hook_name):
        """Execute all hooks for a lifecycle event"""
        for hook in self._hooks[hook_name]:
            await hook()
```

**Usage**:

```python
class MyService(BaseService):
    @on_init
    async def setup_resources(self):
        self.resource = await create_resource()

    @on_start
    async def start_processing(self):
        self.task = asyncio.create_task(self.process_loop())

    @on_stop
    async def cleanup(self):
        await self.resource.close()

    @on_command(CommandType.PROFILE_CONFIGURE)
    async def configure(self, message):
        self.config = message.config

    @background_task(interval=5.0)
    async def periodic_check(self):
        await self.check_health()
```

### 3. Protocol Pattern (Type Protocols)

**Purpose**: Define interfaces for type checking without inheritance.

**Key Protocols**:
- `ServiceProtocol` - Interface for services
- `ServiceManagerProtocol` - Interface for service managers
- `AIPerfUIProtocol` - Interface for UI implementations
- `ResultsProcessorProtocol` - Interface for results processors

**Source**: `aiperf/common/protocols.py`

**Definition**:

```python
from typing import Protocol

class ServiceProtocol(Protocol):
    """Protocol defining the service interface"""

    service_id: str
    service_type: ServiceType

    async def initialize(self) -> None: ...
    async def start(self) -> None: ...
    async def stop(self) -> None: ...
```

**Usage**:

```python
def accept_service(service: ServiceProtocol):
    """Accept any object implementing ServiceProtocol"""
    print(f"Service {service.service_id} of type {service.service_type}")
    await service.start()
```

**Benefits**:
- **Duck Typing**: No inheritance required
- **Type Safety**: Type checkers validate interface compliance
- **Flexibility**: Multiple implementations without common base class
- **Documentation**: Protocols serve as interface documentation

### 4. Strategy Pattern

**Purpose**: Encapsulate algorithms and make them interchangeable.

**Example: Credit Issuing Strategies**

Different timing strategies implement the same interface:

```python
class CreditIssuingStrategy(ABC):
    @abstractmethod
    async def start(self) -> None:
        """Start issuing credits"""
        pass

    @abstractmethod
    async def stop(self) -> None:
        """Stop issuing credits"""
        pass

class RequestRateStrategy(CreditIssuingStrategy):
    """Issue credits at a target rate"""
    async def start(self):
        while True:
            await asyncio.sleep(delay_until_next_credit)
            await self.issue_credit()

class FixedScheduleStrategy(CreditIssuingStrategy):
    """Issue credits at predetermined timestamps"""
    async def start(self):
        for timestamp in self.schedule:
            await asyncio.sleep(timestamp - now)
            await self.issue_credit()
```

**Factory Integration**:

```python
strategy = CreditIssuingStrategyFactory.create_instance(
    timing_mode,  # REQUEST_RATE or FIXED_SCHEDULE
    config=config,
    credit_manager=manager,
)
await strategy.start()
```

**Source**: `aiperf/timing/credit_issuing_strategy.py`

---

## Component Details

### System Controller

**Responsibility**: Orchestrate all services and manage benchmark execution.

**Key Methods**:

```python
class SystemController(BaseService):
    async def initialize(self):
        # 1. Start ZMQ proxies
        # 2. Initialize service manager
        # 3. Setup signal handlers

    async def start(self):
        # 1. Start all required services
        # 2. Wait for services to register
        # 3. Configure all services (ProfileConfigureCommand)
        # 4. Start profiling (ProfileStartCommand)
        # 5. Wait for completion
        # 6. Export results
        # 7. Shutdown services

    async def _profile_configure_all_services(self):
        # Send ProfileConfigureCommand to all services
        # Wait for all to acknowledge

    async def _start_profiling_all_services(self):
        # Send ProfileStartCommand
        # Wait for completion
        # Process results
```

**Service Registration**:

```python
required_services = {
    ServiceType.DATASET_MANAGER: 1,
    ServiceType.TIMING_MANAGER: 1,
    ServiceType.WORKER_MANAGER: 1,
    ServiceType.RECORDS_MANAGER: 1,
    ServiceType.RECORD_PROCESSOR: N,  # Dynamically determined
}

await service_manager.wait_for_all_services_registration()
```

**Source**: `aiperf/controller/system_controller.py`

### Dataset Manager

**Responsibility**: Provide conversation data to workers.

**Key Methods**:

```python
class DatasetManager(ReplyClientMixin, BaseComponentService):
    @on_command(CommandType.PROFILE_CONFIGURE)
    async def _profile_configure_command(self, message):
        # 1. Configure tokenizer
        # 2. Load or generate dataset
        # 3. Generate inputs.json file
        await self._configure_tokenizer()
        await self._configure_dataset()
        await self._generate_inputs_json_file()

    @on_request(MessageType.CONVERSATION_REQUEST)
    async def _conversation_request(self, message):
        # Return a conversation from the dataset
        conversation = self._get_next_conversation()
        return ConversationResponseMessage(conversation=conversation)

    @on_request(MessageType.CONVERSATION_TURN_REQUEST)
    async def _conversation_turn_request(self, message):
        # Return the next turn in a conversation
        turn = self._get_conversation_turn(message.session_id, message.turn_index)
        return ConversationTurnResponseMessage(turn=turn)
```

**Dataset Loading**:

```python
composer = ComposerFactory.create_instance(
    composer_type,  # SYNTHETIC, CUSTOM, PUBLIC_DATASET
    user_config=config,
    tokenizer=tokenizer,
)
self.dataset = await composer.compose()
```

**Source**: `aiperf/dataset/dataset_manager.py`

### Timing Manager

**Responsibility**: Control request timing via credit issuance.

**Key Methods**:

```python
class TimingManager(PullClientMixin, BaseComponentService):
    @on_command(CommandType.PROFILE_CONFIGURE)
    async def _profile_configure_command(self, message):
        # Create the appropriate credit issuing strategy
        if timing_mode == TimingMode.FIXED_SCHEDULE:
            # Request timing data from Dataset Manager
            response = await self.dataset_request_client.request(
                DatasetTimingRequest()
            )
            strategy = FixedScheduleStrategy(schedule=response.timing_data)
        else:
            strategy = RequestRateStrategy(rate=config.request_rate)

        self._credit_issuing_strategy = strategy

    @on_command(CommandType.PROFILE_START)
    async def _on_start_profiling(self, message):
        # Start the credit issuing strategy
        await self._credit_issuing_strategy.start()

    @on_pull_message(MessageType.CREDIT_RETURN)
    async def _credit_return(self, message):
        # Track returned credits for phase completion
        await self._track_credit_return(message)
```

**Credit Flow**:

```
Timing Manager --[CreditDropMessage]--> Workers
Workers --[CreditReturnMessage]--> Timing Manager
```

**Source**: `aiperf/timing/timing_manager.py`

### Worker

**Responsibility**: Execute requests to the inference server.

**Key Methods**:

```python
class Worker(PullClientMixin, ProcessHealthMixin, BaseComponentService):
    @on_pull_message(MessageType.CREDIT_DROP)
    async def _credit_drop_callback(self, message: CreditDropMessage):
        # 1. Request conversation/turn from Dataset Manager
        # 2. Format payload for endpoint
        # 3. Send request to inference server
        # 4. Collect response(s) and timestamps
        # 5. Send raw result to Record Processor
        # 6. Return credit to Timing Manager

        try:
            await self._process_credit_drop_internal(message)
        finally:
            await self.credit_return_push_client.push(
                CreditReturnMessage(phase=message.phase)
            )
```

**Request Execution**:

```python
async def _process_credit_drop_internal(self, credit: CreditDropMessage):
    # Get conversation
    conversation = await self.conversation_request_client.request(
        ConversationRequestMessage()
    )

    # Format payload
    payload = await self.request_converter.format_payload(
        self.model_endpoint, conversation.turns[0]
    )

    # Execute request
    start_time = time.perf_counter_ns()
    responses = []
    async for response in self.inference_client.infer(payload):
        response_time = time.perf_counter_ns()
        responses.append(InferenceResponse(
            content=response,
            perf_ns=response_time,
        ))

    # Send to Record Processor
    result = InferenceResult(
        start_perf_ns=start_time,
        responses=responses,
        session_id=conversation.session_id,
        turn_index=0,
    )
    await self.inference_results_push_client.push(result)
```

**Source**: `aiperf/workers/worker.py`

### Record Processor

**Responsibility**: Parse responses and compute per-request metrics.

**Key Methods**:

```python
class RecordProcessorService(PullClientMixin, BaseComponentService):
    @on_pull_message(MessageType.INFERENCE_RESULT)
    async def _on_inference_result(self, message: InferenceResultMessage):
        # 1. Parse raw inference result
        # 2. Compute per-request metrics
        # 3. Send to Records Manager

        parsed = await self.inference_result_parser.parse(message.result)
        metrics = await self.metric_record_processor.process(parsed)

        await self.records_push_client.push(
            MetricRecordsMessage(
                results=metrics,
                valid=parsed.valid,
                phase=message.phase,
            )
        )
```

**Metric Computation**:

```python
class MetricRecordProcessor:
    def process(self, record: ParsedResponseRecord) -> MetricRecordDict:
        metrics = {}
        for metric_class in MetricRegistry.get_record_metrics():
            try:
                value = metric_class().compute(record)
                metrics[metric_class.tag] = value
            except NoMetricValue:
                # Metric not applicable for this record
                pass
        return metrics
```

**Source**: `aiperf/records/record_processor_service.py`, `aiperf/post_processors/metric_record_processor.py`

### Records Manager

**Responsibility**: Collect and aggregate all results.

**Key Methods**:

```python
class RecordsManager(PullClientMixin, BaseComponentService):
    @on_pull_message(MessageType.METRIC_RECORDS)
    async def _on_metric_records(self, message: MetricRecordsMessage):
        # 1. Check if record should be included (duration filter)
        # 2. Send to results processors
        # 3. Update processing statistics
        # 4. Check for phase completion

        if self._should_include_request_by_duration(message.results):
            await self._send_results_to_results_processors(message.results)
            self.processing_stats.processed += 1

        if self._completion_checker.is_phase_complete():
            await self._finalize_results()

    async def _finalize_results(self):
        # 1. Compute derived metrics
        # 2. Aggregate results
        # 3. Send to System Controller

        results = ProfileResults()
        for processor in self._results_processors:
            processor_results = await processor.finalize()
            results.merge(processor_results)

        await self.publish(ProcessRecordsResultMessage(results=results))
```

**Results Processing**:

```python
# Multiple results processors work in parallel
self._results_processors = [
    MetricRecordProcessor(),   # Computes per-request metrics
    MetricResultsProcessor(),  # Aggregates and computes derived metrics
]

for message in incoming_records:
    for processor in self._results_processors:
        await processor.process(message)
```

**Source**: `aiperf/records/records_manager.py`

---

## Data Flow

### Complete Request Flow

```
1. System Controller sends ProfileStartCommand
   ↓
2. Timing Manager starts issuing CreditDropMessages
   ↓
3. Worker receives CreditDropMessage
   ↓
4. Worker requests Conversation from Dataset Manager
   ↓
5. Dataset Manager returns Conversation
   ↓
6. Worker formats payload and sends HTTP request to inference server
   ↓
7. Inference server streams response (SSE) back to Worker
   ↓
8. Worker collects all responses with timestamps
   ↓
9. Worker sends InferenceResult to Record Processor
   ↓
10. Worker returns CreditReturnMessage to Timing Manager
   ↓
11. Record Processor parses response
   ↓
12. Record Processor computes per-request metrics
   ↓
13. Record Processor sends MetricRecordsMessage to Records Manager
   ↓
14. Records Manager updates aggregate metrics
   ↓
15. Records Manager checks phase completion
   ↓
16. When complete, Records Manager computes derived metrics
   ↓
17. Records Manager sends ProcessRecordsResultMessage to System Controller
   ↓
18. System Controller exports results (JSON, CSV, console)
```

### Message Flow Diagram

```
┌──────────────┐
│   System     │
│  Controller  │
└───────┬──────┘
        │ ProfileStartCommand (PUB/SUB)
        ▼
┌──────────────┐       CreditDropMessage        ┌─────────┐
│   Timing     │──────────(PUSH/PULL)──────────▶│ Worker  │
│   Manager    │◀──────────────────────────────│ (N)     │
└──────────────┘       CreditReturnMessage      └────┬────┘
        │                                            │
        │                                            │ ConversationRequest
        │                                            │ (REQ/REP)
        │                                            ▼
        │                                      ┌──────────┐
        │                                      │ Dataset  │
        │                                      │ Manager  │
        │                                      └──────────┘
        │                                            ▲
        │                                            │
        │                                   ConversationResponse
        │                                            │
┌──────────────┐                                    │
│   Worker     │────────────────────────────────────┘
│   (sends     │
│   request)   │──▶ Inference Server (HTTP)
└───────┬──────┘       │
        │              │ SSE Response Stream
        │              ▼
        │    ┌──────────────────┐
        │    │ Worker (receives)│
        │    └────────┬──────────┘
        │             │ InferenceResult
        │             │ (PUSH/PULL)
        │             ▼
        │       ┌──────────────┐
        │       │   Record     │
        │       │  Processor   │
        │       └──────┬───────┘
        │              │ MetricRecordsMessage
        │              │ (PUSH/PULL)
        │              ▼
        │        ┌──────────────┐
        │        │   Records    │
        │        │   Manager    │
        │        └──────┬───────┘
        │               │ ProcessRecordsResultMessage
        │               │ (PUB/SUB)
        │               ▼
        └─────────▶ System Controller
```

---

## Extension Points

### 1. Adding a New Metric

**Steps**:

1. Create a new metric class inheriting from the appropriate base:
   - `BaseRecordMetric[T]` for per-request metrics
   - `BaseAggregateMetric[T]` for aggregate metrics
   - `BaseDerivedMetric[T]` for derived metrics

2. Define class attributes:
   - `tag`: Unique identifier
   - `header`: Display name
   - `unit`: Measurement unit
   - `display_order`: Display ordering
   - `flags`: Metric flags (optional)
   - `required_metrics`: Dependencies (for derived metrics)

3. Implement computation method:
   - `compute(record)` for Record Metrics
   - `update(record)` and `finalize()` for Aggregate Metrics
   - `compute(metrics)` for Derived Metrics

**Example**:

```python
# File: aiperf/metrics/types/my_metric.py
from aiperf.metrics import BaseRecordMetric
from aiperf.common.enums import MetricTimeUnit, MetricFlags

class MyCustomLatencyMetric(BaseRecordMetric[float]):
    """Custom latency metric measuring X."""

    tag = "my_custom_latency"
    header = "My Custom Latency"
    unit = MetricTimeUnit.MILLISECONDS
    display_order = 50
    flags = MetricFlags.STREAMING_ONLY

    def compute(self, record: ParsedResponseRecord) -> float:
        if len(record.responses) < 2:
            raise NoMetricValue("Requires at least 2 responses")

        first = record.responses[0].perf_ns
        last = record.responses[-1].perf_ns
        latency_ns = last - first

        # Convert to milliseconds
        return latency_ns / NANOS_PER_MILLIS
```

The metric will be **automatically registered** and included in results.

**Source**: `aiperf/metrics/types/`

### 2. Adding a New Endpoint Type

**Steps**:

1. Define the endpoint in `EndpointType` enum
2. Create an inference client implementation
3. Create a request converter implementation
4. Register both with factories

**Example**:

```python
# 1. Add to EndpointType enum
# File: aiperf/common/enums/endpoints_enums.py
class EndpointType(BasePydanticBackedStrEnum):
    MY_ENDPOINT = EndpointTypeInfo(
        tag="my_endpoint",
        service_kind=EndpointServiceKind.OPENAI,
        supports_streaming=True,
        produces_tokens=True,
        endpoint_path="/v1/my_endpoint",
        metrics_title="My Endpoint Metrics",
    )

# 2. Create inference client
# File: aiperf/clients/my_endpoint/my_endpoint_client.py
@InferenceClientFactory.register(EndpointType.MY_ENDPOINT)
class MyEndpointClient(BaseInferenceClient):
    async def infer(self, payload: dict) -> AsyncIterator[dict]:
        async with self.session.post(
            self.url,
            json=payload,
            headers=self.headers,
        ) as response:
            async for line in response.content:
                yield self._parse_sse_line(line)

# 3. Create request converter
# File: aiperf/clients/my_endpoint/my_endpoint_converter.py
@RequestConverterFactory.register(EndpointType.MY_ENDPOINT)
class MyEndpointRequestConverter(BaseRequestConverter):
    async def format_payload(
        self,
        model_endpoint: ModelEndpointInfo,
        turn: ConversationTurn,
    ) -> dict:
        return {
            "model": model_endpoint.model_name,
            "prompt": turn.prompt.text,
            "stream": model_endpoint.streaming,
            # ... endpoint-specific fields
        }
```

**Source**: `aiperf/clients/`, `aiperf/common/factories.py`

### 3. Adding a New Dataset Loader

**Steps**:

1. Create a loader class implementing the loading logic
2. Register it with `ComposerFactory` or create a custom composer

**Example**:

```python
# File: aiperf/dataset/loader/my_dataset.py
class MyDatasetLoader:
    """Load data from my custom format."""

    @classmethod
    async def load(cls, file_path: Path, tokenizer: Tokenizer) -> dict[str, Conversation]:
        conversations = {}

        async with aiofiles.open(file_path) as f:
            async for line in f:
                data = json.loads(line)
                conversation = cls._parse_conversation(data, tokenizer)
                conversations[conversation.session_id] = conversation

        return conversations

    @staticmethod
    def _parse_conversation(data: dict, tokenizer: Tokenizer) -> Conversation:
        # Parse your custom format
        turns = []
        for turn_data in data["turns"]:
            prompt = Prompt(text=turn_data["text"])
            turn = ConversationTurn(
                prompt=prompt,
                input_token_count=tokenizer.count_tokens(prompt.text),
            )
            turns.append(turn)

        return Conversation(
            session_id=data["id"],
            turns=turns,
        )
```

**Usage in Composer**:

```python
# File: aiperf/dataset/composer/custom.py
class CustomComposer:
    async def compose(self) -> dict[str, Conversation]:
        if self.user_config.input.custom_dataset_type == "my_dataset":
            return await MyDatasetLoader.load(
                self.user_config.input.input_file,
                self.tokenizer,
            )
```

**Source**: `aiperf/dataset/loader/`, `aiperf/dataset/composer/`

### 4. Adding a New Service

**Steps**:

1. Create service class inheriting from `BaseComponentService`
2. Add service type to `ServiceType` enum
3. Register with `ServiceFactory`
4. Add to required services in `SystemController`
5. Implement lifecycle hooks and message handlers

**Example**:

```python
# 1. Add to ServiceType enum
# File: aiperf/common/enums/service_enums.py
class ServiceType(CaseInsensitiveStrEnum):
    MY_SERVICE = "my_service"

# 2. Create service implementation
# File: aiperf/my_service/my_service.py
@ServiceFactory.register(ServiceType.MY_SERVICE)
class MyService(BaseComponentService):
    def __init__(self, service_config, user_config, service_id=None):
        super().__init__(
            service_config=service_config,
            user_config=user_config,
            service_id=service_id,
        )

    @on_init
    async def _initialize_my_service(self):
        # Initialization logic
        pass

    @on_start
    async def _start_my_service(self):
        # Start logic
        pass

    @on_stop
    async def _cleanup_my_service(self):
        # Cleanup logic
        pass

    @on_command(CommandType.PROFILE_CONFIGURE)
    async def _configure(self, message):
        # Configuration logic
        pass

# 3. Add to SystemController required services
# File: aiperf/controller/system_controller.py
self.required_services = {
    ServiceType.MY_SERVICE: 1,
    # ... other services
}
```

**Source**: `aiperf/controller/system_controller.py`, template: any service in `aiperf/`

---

## Development Workflow

### Setting Up Development Environment

```bash
# 1. Clone repository
git clone https://github.com/ai-dynamo/aiperf.git
cd aiperf

# 2. Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# 3. Install in development mode with dev dependencies
pip install -e ".[dev]"

# 4. Install pre-commit hooks
pre-commit install

# 5. Run tests
pytest
```

### Code Style & Linting

AIPerf uses:
- **Black** for code formatting
- **Ruff** for linting
- **pre-commit** hooks for automatic checks

Configuration: `pyproject.toml`

Run manually:
```bash
black aiperf tests
ruff check aiperf tests
```

### Making Changes

1. **Create a branch**:
   ```bash
   git checkout -b feature/my-feature
   ```

2. **Make changes** following existing patterns

3. **Add tests** for new functionality

4. **Run tests**:
   ```bash
   pytest
   pytest -xvs  # Verbose, stop on first failure
   pytest tests/metrics/  # Specific directory
   ```

5. **Update documentation** if needed

6. **Commit** (pre-commit hooks run automatically):
   ```bash
   git add .
   git commit -m "feat: add new feature"
   ```

7. **Push and create PR**:
   ```bash
   git push origin feature/my-feature
   # Create PR on GitHub
   ```

### Debugging Tips

1. **Enable verbose logging**:
   ```bash
   aiperf profile --log-level DEBUG ...
   aiperf profile -vv ...  # TRACE level
   ```

2. **Enable developer mode**:
   ```bash
   export AIPERF_DEV_MODE=true
   aiperf profile ...
   ```

3. **Use simple UI for debugging**:
   ```bash
   aiperf profile --ui simple ...
   aiperf profile --ui none ...  # No UI
   ```

4. **Examine artifacts**:
   ```bash
   cat artifacts/<run_name>/logs/aiperf.log
   cat artifacts/<run_name>/profile_export_aiperf.json
   ```

5. **Python debugger**:
   ```python
   import pdb; pdb.set_trace()  # Set breakpoint
   ```

6. **Async debugging**:
   ```python
   import asyncio
   asyncio.get_event_loop().set_debug(True)
   ```

---

## Testing

### Test Organization

```
tests/
├── clients/          # HTTP client tests
├── common/           # Common infrastructure tests
├── config/           # Configuration tests
├── dataset/          # Dataset tests
├── metrics/          # Metric computation tests
├── parsers/          # Response parsing tests
├── post_processors/  # Results processing tests
├── timing/           # Timing strategy tests
├── workers/          # Worker tests
└── conftest.py       # Shared fixtures
```

### Test Types

1. **Unit Tests**: Test individual components in isolation
2. **Integration Tests**: Test component interactions
3. **End-to-End Tests**: Full benchmark runs (in `integration-tests/`)

### Writing Tests

**Example Unit Test**:

```python
# File: tests/metrics/test_my_metric.py
import pytest
from aiperf.metrics.types.my_metric import MyCustomLatencyMetric
from aiperf.common.models import ParsedResponseRecord, InferenceResponse

def test_my_custom_latency_metric():
    """Test that MyCustomLatencyMetric computes correctly."""
    # Arrange
    record = ParsedResponseRecord(
        start_perf_ns=0,
        responses=[
            InferenceResponse(perf_ns=1_000_000),  # 1ms
            InferenceResponse(perf_ns=5_000_000),  # 5ms
        ],
        valid=True,
    )
    metric = MyCustomLatencyMetric()

    # Act
    result = metric.compute(record)

    # Assert
    assert result == 4.0  # 4ms between first and last

def test_my_custom_latency_metric_insufficient_responses():
    """Test that metric raises NoMetricValue with < 2 responses."""
    record = ParsedResponseRecord(
        start_perf_ns=0,
        responses=[InferenceResponse(perf_ns=1_000_000)],
        valid=True,
    )
    metric = MyCustomLatencyMetric()

    with pytest.raises(NoMetricValue):
        metric.compute(record)
```

**Example Integration Test**:

```python
# File: tests/test_dataset_manager.py
import pytest
from aiperf.dataset.dataset_manager import DatasetManager

@pytest.mark.asyncio
async def test_dataset_manager_provides_conversations(user_config, service_config):
    """Test that DatasetManager provides conversations to workers."""
    # Arrange
    manager = DatasetManager(
        user_config=user_config,
        service_config=service_config,
    )
    await manager.initialize()

    # Act
    conversation = await manager.get_conversation()

    # Assert
    assert conversation is not None
    assert len(conversation.turns) > 0
```

### Running Tests

```bash
# Run all tests
pytest

# Run specific test file
pytest tests/metrics/test_my_metric.py

# Run tests matching pattern
pytest -k "test_latency"

# Run with coverage
pytest --cov=aiperf --cov-report=html

# Run in parallel
pytest -n auto
```

---

## Performance Considerations

### 1. Async/Await Best Practices

- **Always await** async operations
- Use `asyncio.gather()` for parallel operations
- Avoid blocking calls in async code
- Use `asyncio.to_thread()` for CPU-bound work

### 2. ZMQ Performance

- **High Water Mark (HWM)**: Controls message buffering
- **Batch Processing**: Process messages in batches when possible
- **Connection Pooling**: Reuse ZMQ sockets
- **Serialization**: Use efficient formats (currently JSON via orjson)

### 3. Memory Management

- **Streaming**: Use async iterators for large data
- **Generators**: Use generators to avoid loading everything into memory
- **Cleanup**: Always close resources in `@on_stop` hooks

### 4. Concurrency Limits

- `--workers-max`: Controls number of worker processes
- `AIPERF_HTTP_CONNECTION_LIMIT`: HTTP connection pool size
- `pull_client_max_concurrency`: Backpressure control

### 5. Profiling

Use Python profiling tools:

```python
import cProfile
import pstats

profiler = cProfile.Profile()
profiler.enable()
# ... code to profile
profiler.disable()
stats = pstats.Stats(profiler)
stats.sort_stats('cumulative')
stats.print_stats(20)
```

Or use `py-spy`:
```bash
py-spy record -o profile.svg -- aiperf profile ...
```

---

## Additional Resources

- **[Architecture Documentation](architecture.md)** - High-level architecture overview
- **[Metrics Reference](metrics_reference.md)** - Complete metrics documentation
- **[Terminology Glossary](terminology-glossary.md)** - All terminology definitions
- **[User Guide](user-guide.md)** - User-facing documentation
- **[CLI Options](cli_options.md)** - All command-line options
- **[Tutorial](tutorial.md)** - Getting started tutorial

---

## Contributing

We welcome contributions! Please follow:

1. **Code Style**: Follow existing patterns and use Black/Ruff
2. **Tests**: Add tests for new functionality
3. **Documentation**: Update docs for user-facing changes
4. **PR Process**: Create PRs with clear descriptions

For major changes, please open an issue first to discuss the proposed changes.

---

## Summary

This developer guide provides comprehensive technical documentation for working with the AIPerf codebase. Key takeaways:

- **Modular Architecture**: Service-based design with ZMQ messaging
- **Extensibility**: Factories, registries, and protocols enable easy extension
- **Type Safety**: Pydantic models and type hints throughout
- **Async-First**: Modern async/await concurrency
- **Well-Tested**: Comprehensive test suite

For questions or clarifications, please open an issue on GitHub or reach out to the development team.
