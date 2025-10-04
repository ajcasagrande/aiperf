<!--
# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
-->
# Chapter 4: Core Concepts

## Table of Contents
- [Services and Processes](#services-and-processes)
- [Credits and Flow Control](#credits-and-flow-control)
- [Phases: Warmup and Profiling](#phases-warmup-and-profiling)
- [Records and Metrics](#records-and-metrics)
- [Communication Patterns](#communication-patterns)
- [Lifecycle Management](#lifecycle-management)
- [Key Takeaways](#key-takeaways)

## Services and Processes

AIPerf is built on a **service-oriented architecture** where each major component runs as an independent service, typically in its own process. Understanding this architecture is fundamental to working with AIPerf.

### What is a Service?

A service in AIPerf is a self-contained component that:
- Runs in its own process (true multiprocessing)
- Has a well-defined lifecycle (initialize → start → run → stop)
- Communicates via message passing (not shared memory)
- Manages its own state
- Has a unique service ID
- Implements a specific responsibility

### Core Services

AIPerf consists of these primary services:

#### 1. System Controller
- **Role**: Orchestrator and coordinator
- **Process Count**: 1
- **Key Responsibilities**:
  - Start and stop all other services
  - Coordinate lifecycle transitions
  - Handle commands and responses
  - Aggregate final results
  - Display UI and output

Location: `/home/anthony/nvidia/projects/aiperf/aiperf/controller/system_controller.py`

#### 2. Timing Manager
- **Role**: Request scheduling and timing control
- **Process Count**: 1
- **Key Responsibilities**:
  - Issue timing credits to workers
  - Implement load generation strategies (concurrency, request rate, etc.)
  - Manage warmup and profiling phases
  - Track in-flight requests
  - Handle credit returns

Location: `/home/anthony/nvidia/projects/aiperf/aiperf/timing/timing_manager.py`

#### 3. Dataset Manager
- **Role**: Data provisioning
- **Process Count**: 1
- **Key Responsibilities**:
  - Load and manage datasets
  - Generate synthetic data
  - Serve conversation data to workers
  - Support trace replay
  - Maintain conversation context

Location: `/home/anthony/nvidia/projects/aiperf/aiperf/dataset/dataset_manager.py`

#### 4. Worker Manager
- **Role**: Worker lifecycle orchestration
- **Process Count**: 1
- **Key Responsibilities**:
  - Monitor worker health
  - Track worker statistics
  - Coordinate worker spawning/shutdown
  - Report worker status
  - Auto-scaling (future)

Location: `/home/anthony/nvidia/projects/aiperf/aiperf/workers/worker_manager.py`

#### 5. Workers
- **Role**: Request execution
- **Process Count**: Multiple (1-32+ typically)
- **Key Responsibilities**:
  - Pull timing credits
  - Fetch conversation data
  - Send HTTP requests to inference server
  - Measure timing precisely
  - Return results
  - Handle errors

Location: `/home/anthony/nvidia/projects/aiperf/aiperf/workers/worker.py`

#### 6. Record Processor(s)
- **Role**: Result processing pipeline
- **Process Count**: Multiple (auto-scaled with workers)
- **Key Responsibilities**:
  - Parse inference responses
  - Extract metrics
  - Compute per-request metrics
  - Forward to Records Manager
  - Handle streaming responses

Location: `/home/anthony/nvidia/projects/aiperf/aiperf/records/record_processor_service.py`

#### 7. Records Manager
- **Role**: Result aggregation
- **Process Count**: 1
- **Key Responsibilities**:
  - Collect all processed records
  - Aggregate statistics
  - Track completion
  - Build error summaries
  - Provide real-time metrics
  - Signal completion

Location: `/home/anthony/nvidia/projects/aiperf/aiperf/records/records_manager.py`

### Service Lifecycle

Every service follows a standardized lifecycle:

```
┌─────────────┐
│   Created   │  Constructor called, basic initialization
└──────┬──────┘
       │
       v
┌─────────────┐
│ Initialized │  @on_init hooks run, resources allocated
└──────┬──────┘
       │
       v
┌─────────────┐
│   Started   │  @on_start hooks run, background tasks begin
└──────┬──────┘
       │
       v
┌─────────────┐
│   Running   │  Service performs its main function
└──────┬──────┘
       │
       v
┌─────────────┐
│   Stopping  │  @on_stop hooks run, cleanup begins
└──────┬──────┘
       │
       v
┌─────────────┐
│   Stopped   │  All resources released, process exits
└─────────────┘
```

### Process Model

AIPerf uses **true multiprocessing** (not just asyncio threads):

```
┌─────────────────────────────────────────────────────────────┐
│                  System Controller Process                  │
│  - Orchestration                                            │
│  - UI                                                       │
│  - Result Export                                            │
└─────────────────────────────────────────────────────────────┘
              │
              ├──────────────┬────────────┬──────────────────────┐
              │              │            │                      │
              v              v            v                      v
┌──────────────────┐  ┌─────────────┐  ┌──────────────┐  ┌──────────────┐
│ Timing Manager   │  │  Dataset    │  │   Worker     │  │   Records    │
│  Process         │  │  Manager    │  │   Manager    │  │   Manager    │
│                  │  │  Process    │  │   Process    │  │   Process    │
└──────────────────┘  └─────────────┘  └──────────────┘  └──────────────┘
                                                │                   │
                                                v                   v
                              ┌────────────────────────────┐  ┌────────────┐
                              │  Worker Processes (N)      │  │  Record    │
                              │  - Worker 1                │  │  Processors│
                              │  - Worker 2                │  │  (M)       │
                              │  - ...                     │  │            │
                              │  - Worker N                │  │            │
                              └────────────────────────────┘  └────────────┘
```

**Benefits**:
- True parallelism across CPU cores
- Process isolation (crash containment)
- No GIL limitations
- Better resource utilization

**Trade-offs**:
- Higher memory usage than threads
- Inter-process communication overhead
- More complex coordination

## Credits and Flow Control

AIPerf uses a **credit-based system** to control the flow of requests. This is one of its most important and innovative design patterns.

### What is a Credit?

A **credit** is a permission token that allows a worker to execute one request. Think of it like a ticket system:
- The Timing Manager issues credits based on the load generation strategy
- Workers pull credits when ready
- Each credit represents authorization to make one request
- Workers return credits after completing requests
- The system tracks in-flight credits

### Credit Flow

```
┌──────────────────┐
│ Timing Manager   │  Issues credits according to strategy
│                  │
│ [Credit Pool]    │
└────────┬─────────┘
         │ Drop Credit
         │ (via ZMQ PUSH)
         v
┌────────────────────┐
│  Credit Drop       │  ZMQ Proxy buffers credits
│  Proxy/Buffer      │
└────────┬───────────┘
         │
         │ Pull Credit (when ready)
         │ (via ZMQ PULL with max concurrency)
         v
┌───────────────────┐
│  Worker Process   │
│                   │  1. Pull credit
│  [Semaphore]      │  2. Request data
│                   │  3. Execute request
│                   │  4. Process response
│                   │  5. Return credit
└────────┬──────────┘
         │ Return Credit
         │ (via ZMQ PUSH)
         v
┌──────────────────┐
│ Timing Manager   │  Receives credit return
│                  │  Updates tracking
└──────────────────┘
```

### Credit Phases

Credits have a `phase` attribute indicating their purpose:

#### Warmup Phase
```python
CreditPhase.WARMUP
```
- Sent first (if warmup requested)
- Not included in metrics
- Warms up server caches, JIT compilation, etc.
- Helps stabilize performance before measurement

#### Profiling Phase
```python
CreditPhase.PROFILING
```
- Main measurement phase
- All results counted in metrics
- This is what you're actually benchmarking

### Credit Properties

A credit drop message contains:

```python
class CreditDropMessage:
    service_id: str              # Timing Manager ID
    phase: CreditPhase           # WARMUP or PROFILING
    request_id: str              # Unique credit ID (X-Correlation-ID)
    credit_drop_ns: int | None   # Expected execution time (nanoseconds)
    conversation_id: str | None  # Specific conversation to use
    should_cancel: bool          # Enable cancellation
    cancel_after_ns: int         # Cancellation timeout
```

### Why Use Credits?

**Flow Control**:
- Prevents overwhelming workers
- Enables precise rate limiting
- Supports backpressure

**Precise Timing**:
- Credits can specify exact execution times
- Enables deterministic replay
- Supports complex scheduling

**Resource Management**:
- Credits act as semaphores
- Limits concurrent requests
- Prevents resource exhaustion

**Flexibility**:
- Different strategies (concurrency, rate, schedule)
- Phase-based execution
- Conditional features (cancellation)

### Load Generation Strategies

The Timing Manager implements different credit issuing strategies:

#### Concurrency Strategy
Maintains fixed number of in-flight requests:
```python
target_concurrency = 10
while not complete:
    if in_flight < target_concurrency:
        drop_credit()
    await credit_return()
```

#### Request Rate Strategy
Issues credits at specific rate:
```python
target_rate = 100  # req/s
interval = 1.0 / target_rate
while not complete:
    await asyncio.sleep(interval)
    drop_credit()
```

#### Fixed Schedule Strategy
Issues credits at predetermined times:
```python
for timestamp, conversation_id in schedule:
    wait_until(timestamp)
    drop_credit(conversation_id=conversation_id)
```

## Phases: Warmup and Profiling

AIPerf benchmarks execute in distinct **phases** to ensure measurement accuracy.

### Why Phases?

Initial requests often show different performance characteristics:
- **Cold Start Effects**: JIT compilation, model loading, cache warming
- **Connection Establishment**: TCP handshakes, SSL negotiation
- **Queue Warmup**: Scheduler optimization, batch assembly
- **GPU Kernel Launch**: CUDA kernel compilation

These can skew results if included in measurements.

### Warmup Phase

**Purpose**: Stabilize the system before measurement

**Configuration**:
```bash
--warmup-request-count 50
```

**Characteristics**:
- Executes first
- Uses same load pattern as profiling
- Results discarded (not in metrics)
- No separate statistics

**Best Practices**:
- Use 10-20% of total request count
- More warmup for cold starts
- Less for hot systems
- Required for accurate comparisons

### Profiling Phase

**Purpose**: Actual measurement phase

**Configuration**:
```bash
# Request-count based
--request-count 1000

# Time-based
--benchmark-duration 300  # 5 minutes
--benchmark-grace-period 30  # Wait 30s for in-flight requests
```

**Characteristics**:
- All results counted
- Can be count-based or time-based
- Supports grace periods
- Full metrics collection

### Phase Transitions

```
System Start
     │
     v
┌─────────────────┐
│ Configuration   │  Services configure
└────────┬────────┘
         │
         v
┌─────────────────┐
│ Warmup Phase    │  If warmup-request-count > 0
│ (Optional)      │
│                 │  - Issue warmup credits
│ [Not Measured]  │  - Wait for completion
│                 │  - Discard results
└────────┬────────┘
         │
         v
┌─────────────────┐
│ Profiling Phase │  Main measurement
│                 │
│ [Measured]      │  - Issue profiling credits
│                 │  - Collect metrics
│                 │  - Track progress
└────────┬────────┘
         │
         v
┌─────────────────┐
│ Grace Period    │  If time-based benchmark
│ (Optional)      │
│                 │  - Wait for in-flight
│ [Measured]      │  - Or timeout
└────────┬────────┘
         │
         v
┌─────────────────┐
│ Results Export  │  Final processing
└─────────────────┘
```

### Phase Messages

Services communicate phase transitions via messages:

```python
# Phase start
CreditPhaseStartMessage(
    phase=CreditPhase.PROFILING,
    start_ns=time.time_ns(),
    expected_requests=1000,
    expected_duration_sec=None
)

# Phase sending complete
CreditPhaseSendingCompleteMessage(
    phase=CreditPhase.PROFILING,
    sent_end_ns=time.time_ns(),
    sent_count=1000
)

# Phase complete
CreditPhaseCompleteMessage(
    phase=CreditPhase.PROFILING,
    completed_count=1000,
    end_ns=time.time_ns()
)
```

## Records and Metrics

AIPerf's data flow follows a **records → metrics → results** pipeline.

### Request Records

The fundamental data unit is a `RequestRecord`:

```python
class RequestRecord:
    # Identification
    model_name: str
    conversation_id: str
    turn_index: int
    credit_phase: CreditPhase

    # Timing (nanosecond precision)
    timestamp_ns: int           # Wall clock time
    start_perf_ns: int          # Monotonic start time
    end_perf_ns: int            # Monotonic end time
    credit_drop_latency: int    # Scheduling overhead

    # Request/Response Data
    turn: Turn                  # Input data
    response: InferenceServerResponse  # Server response

    # Streaming Timing
    first_token_ns: int | None
    second_token_ns: int | None
    token_timestamps: list[int]

    # Cancellation
    was_cancelled: bool
    cancel_after_ns: int

    # Tracing
    x_request_id: str
    x_correlation_id: str

    # Errors
    error: ErrorDetails | None
```

### Record Flow

```
Worker
  │ Execute Request
  │ Measure Timing
  │ Capture Response
  v
RequestRecord
  │
  │ (via ZMQ)
  v
Record Processor
  │ Parse Response
  │ Extract Metrics
  │ Compute Values
  v
MetricRecordsMessage
  │ contains: list[dict[MetricTag, MetricValue]]
  │
  │ (via ZMQ)
  v
Records Manager
  │ Aggregate
  │ Track Statistics
  │ Build Summaries
  v
ProfileResults
  │
  │ Export
  v
CSV / JSON / Console
```

### Metric Types

AIPerf computes multiple metric categories:

#### 1. Record Metrics (Per-Request)
Computed from individual records:
- Request Latency
- Time to First Token
- Time to Second Token
- Inter Token Latency
- Input/Output Sequence Lengths

Location: `/home/anthony/nvidia/projects/aiperf/aiperf/metrics/base_record_metric.py`

#### 2. Aggregate Metrics
Computed across all records:
- Request Throughput (req/s)
- Token Throughput (tokens/s)
- Statistics (min, max, avg, percentiles)

Location: `/home/anthony/nvidia/projects/aiperf/aiperf/metrics/base_aggregate_metric.py`

#### 3. Counter Metrics
Count-based metrics:
- Request Count
- Error Count
- Good Request Count

Location: `/home/anthony/nvidia/projects/aiperf/aiperf/metrics/base_aggregate_counter_metric.py`

#### 4. Derived Metrics
Computed from other metrics:
- Goodput (% within SLA)
- Token Throughput Per User

Location: `/home/anthony/nvidia/projects/aiperf/aiperf/metrics/base_derived_metric.py`

### Metric Tags

Metrics are identified by tags:

```python
class MetricTag(str, Enum):
    REQUEST_LATENCY = "request_latency"
    TIME_TO_FIRST_TOKEN = "time_to_first_token"
    INTER_TOKEN_LATENCY = "inter_token_latency"
    OUTPUT_TOKEN_THROUGHPUT = "output_token_throughput"
    # ... many more
```

These tags enable:
- Type-safe metric access
- Consistent naming
- Easy filtering
- Programmatic queries

## Communication Patterns

AIPerf uses ZeroMQ for inter-process communication with several patterns.

### ZeroMQ Patterns Used

#### 1. PUB/SUB (Publish/Subscribe)
**Use Case**: Broadcasting messages to all services

```
┌──────────────┐
│ Publisher    │─────┐
└──────────────┘     │
                     ├──→ [Message Bus] ───┬──→ Subscriber 1
                     │                      ├──→ Subscriber 2
                     │                      └──→ Subscriber 3
```

**Examples**:
- System Controller broadcasting shutdown commands
- Timing Manager announcing phase changes
- Worker health updates

**Pattern**:
```python
# Publish
await service.publish(ShutdownCommand(...))

# Subscribe
@on_message(MessageType.SHUTDOWN)
async def handle_shutdown(self, msg: ShutdownCommand):
    ...
```

#### 2. PUSH/PULL (Pipeline)
**Use Case**: Work distribution, load balancing

```
┌──────────┐     ┌───────┐     ┌──────────┐
│ PUSH     │────→│ Proxy │────→│ PULL     │
│ (Timing) │     │       │     │ (Worker) │
└──────────┘     └───────┘     └──────────┘
```

**Examples**:
- Credit drops (Timing Manager → Workers)
- Credit returns (Workers → Timing Manager)
- Inference results (Workers → Record Processors)
- Metric records (Record Processors → Records Manager)

**Characteristics**:
- Load balanced automatically
- First available worker gets the message
- Back-pressure support via max concurrency

**Pattern**:
```python
# Push
await push_client.push(CreditDropMessage(...))

# Pull (with max concurrency)
@on_pull_message(MessageType.CREDIT_DROP)
async def handle_credit(self, msg: CreditDropMessage):
    # Semaphore automatically limits concurrency
    ...
```

#### 3. DEALER/ROUTER (Request/Reply)
**Use Case**: Request-response pattern

```
┌──────────┐     ┌────────┐     ┌──────────┐
│ DEALER   │────→│ ROUTER │────→│ DEALER   │
│ (Client) │     │ (Proxy)│     │ (Server) │
└──────────┘     └────────┘     └──────────┘
      ↑                               │
      └───────── Response ────────────┘
```

**Examples**:
- Workers requesting conversation data from Dataset Manager
- Timing Manager requesting timing data for fixed schedules

**Pattern**:
```python
# Request
response = await request_client.request(
    ConversationRequestMessage(...)
)

# Reply
@on_request(MessageType.CONVERSATION_REQUEST)
async def handle_request(self, msg):
    return ConversationResponseMessage(...)
```

### Proxy Architecture

AIPerf uses ZeroMQ proxies to decouple services:

```
Services → Frontend Socket → PROXY → Backend Socket → Services
```

**Benefits**:
- Services don't need to know each other's addresses
- Centralized routing
- Simplifies service spawning
- Enables monitoring and logging

**Proxies**:
- PUB/SUB Proxy (broadcast)
- PUSH/PULL Credit Drop Proxy
- PUSH/PULL Credit Return Proxy
- DEALER/ROUTER Request/Reply Proxies

### Message Bus

All pub/sub messages flow through a central message bus:

```
                        ┌──────────────────┐
        ┌───────────────│   Message Bus    │──────────────┐
        │               │   (PUB/SUB)      │              │
        │               └──────────────────┘              │
        │                                                 │
        v                                                 v
┌───────────────┐                                 ┌──────────────┐
│ All Services  │                                 │ All Services │
│ Can Publish   │                                 │ Can Subscribe│
└───────────────┘                                 └──────────────┘
```

### Communication Addresses

Services communicate via well-defined addresses:

```python
class CommAddress(str, Enum):
    MESSAGE_BUS = "inproc://message_bus"
    CREDIT_DROP = "inproc://credit_drop"
    CREDIT_RETURN = "inproc://credit_return"
    DATASET_MANAGER_PROXY_FRONTEND = "inproc://dataset_request_frontend"
    DATASET_MANAGER_PROXY_BACKEND = "inproc://dataset_request_backend"
    # ... more addresses
```

**Why inproc://**?
- Fastest ZeroMQ transport (shared memory)
- No network overhead
- Suitable for single-machine deployment

**Future**: Could use tcp:// for distributed deployment

## Lifecycle Management

AIPerf provides sophisticated lifecycle management to ensure clean startup and shutdown.

### Lifecycle States

```python
class LifecycleState(str, Enum):
    CREATED = "created"
    INITIALIZING = "initializing"
    INITIALIZED = "initialized"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    STOPPED = "stopped"
    FAILED = "failed"
```

### State Transitions

```
CREATED → INITIALIZING → INITIALIZED → STARTING → RUNNING → STOPPING → STOPPED
                                                      │
                                                      v
                                                   FAILED
```

### Lifecycle Hooks

Services use decorators for lifecycle events:

```python
class MyService(BaseService):

    @on_init
    async def initialize_resources(self):
        """Called during initialization phase"""
        self.data = await load_data()

    @on_start
    async def start_tasks(self):
        """Called when service starts"""
        self.execute_async(self.background_task())

    @background_task(interval=5.0)
    async def background_task(self):
        """Runs every 5 seconds"""
        await self.do_work()

    @on_command(CommandType.PROFILE_CONFIGURE)
    async def configure(self, msg: ProfileConfigureCommand):
        """Handle configuration command"""
        self.config = msg.config

    @on_stop
    async def cleanup(self):
        """Called during shutdown"""
        await self.close_connections()
```

### Graceful Shutdown

AIPerf ensures clean shutdown:

1. **Signal Handling**: Catches SIGINT, SIGTERM
2. **Cascade Shutdown**: System Controller stops children
3. **Resource Cleanup**: All services clean up resources
4. **Credit Draining**: Wait for in-flight requests
5. **Result Export**: Save all data before exit
6. **Log Flushing**: Ensure logs are written

### Error Handling

```python
# Try-operation pattern
async with self.try_operation_or_stop("Initialize Database"):
    await self.db.connect()
    # If this fails, service stops gracefully
```

**Benefits**:
- Exceptions don't crash the system
- Clean error messages
- Proper cleanup even on error
- Context captured for debugging

### Health Monitoring

Workers report health metrics:

```python
class ProcessHealth:
    cpu_usage: float
    memory_mb: float
    io_read_mb: float
    io_write_mb: float
    cpu_times: CPUTimes
    ctx_switches: CtxSwitches
```

Worker Manager tracks:
- Worker status (healthy, error, high load, idle, stale)
- Task statistics (total, in progress, completed, failed)
- Last update timestamps
- Error recovery windows

## Key Takeaways

1. **Service-Oriented Architecture**: AIPerf is built from independent, communicating services, each with a specific responsibility.

2. **True Multiprocessing**: Services run in separate processes for true parallelism and isolation.

3. **Credit-Based Flow Control**: The credit system enables precise load generation and prevents resource exhaustion.

4. **Phase-Based Execution**: Warmup and profiling phases ensure accurate measurements by isolating cold-start effects.

5. **Records → Metrics Pipeline**: Data flows through a well-defined pipeline from raw records to aggregated metrics.

6. **Multiple Metric Types**: Record, aggregate, counter, and derived metrics provide comprehensive performance visibility.

7. **ZeroMQ Communication**: PUB/SUB, PUSH/PULL, and DEALER/ROUTER patterns enable flexible, high-performance IPC.

8. **Proxy Architecture**: Proxies decouple services and simplify addressing.

9. **Lifecycle Hooks**: Decorator-based hooks provide clean, testable service behavior.

10. **Robust Error Handling**: Comprehensive error handling, health monitoring, and graceful shutdown ensure reliability.

Understanding these core concepts is essential for effective use of AIPerf and serves as the foundation for the architectural deep-dives in the following chapters.

---

Next: [Chapter 5: Architecture Fundamentals](chapter-05-architecture-fundamentals.md)
