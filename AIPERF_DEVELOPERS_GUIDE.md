<!--
# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
-->
# AIPerf Developer's Guidebook
## The Complete Guide to AIPerf Architecture, Design, and Development

**Version:** 1.0
**Last Updated:** 2025-10-04
**Authors:** AIPerf Development Team

---

## Table of Contents

1. [Introduction](#1-introduction)
2. [Getting Started](#2-getting-started)
3. [Architecture Overview](#3-architecture-overview)
4. [Core Subsystems](#4-core-subsystems)
5. [Configuration System](#5-configuration-system)
6. [Communication Architecture](#6-communication-architecture)
7. [Metrics System](#7-metrics-system)
8. [Development Guidelines](#8-development-guidelines)
9. [Testing Strategies](#9-testing-strategies)
10. [Common Patterns](#10-common-patterns)
11. [Troubleshooting Guide](#11-troubleshooting-guide)
12. [Glossary](#12-glossary)
13. [Keywords and Concepts](#13-keywords-and-concepts)
14. [Appendix: File Reference](#14-appendix-file-reference)

---

## 1. Introduction

### 1.1 What is AIPerf?

AIPerf is a comprehensive benchmarking tool designed to measure the performance of generative AI models served by any inference solution. It provides detailed metrics through command-line displays and extensive benchmark performance reports.

**Key Capabilities:**
- Multi-process distributed architecture for scalability
- Multiple benchmarking modes (concurrency, request-rate, trace replay, fixed schedule)
- Comprehensive metrics (TTFT, ITL, throughput, latency, goodput)
- Multi-modal support (text, images, audio)
- Real-time dashboard UI with live metrics
- Support for multiple endpoint types (OpenAI chat, completions, embeddings, rankings)

### 1.2 Design Philosophy

AIPerf is built on several core principles:

1. **Separation of Concerns**: Clear boundaries between subsystems
2. **Type Safety**: Full Pydantic validation and Python type hints throughout
3. **Extensibility**: Factory patterns and protocols for easy extension
4. **Performance**: Async/await, connection pooling, efficient data structures
5. **Observability**: Comprehensive logging, tracing, and real-time metrics
6. **Reliability**: Graceful error handling and resource cleanup

### 1.3 Who Should Read This Guide?

This guide is intended for:
- **New Contributors**: Understanding the codebase architecture
- **Core Developers**: Deep technical reference for subsystems
- **Integration Engineers**: Adding new endpoints, metrics, or features
- **Performance Engineers**: Optimizing bottlenecks
- **DevOps Engineers**: Deployment and operational concerns

### 1.4 Document Structure

This guide is organized into major sections:
- **Chapters 1-3**: Overview and architecture
- **Chapters 4-7**: Deep dives into core subsystems
- **Chapters 8-9**: Development and testing practices
- **Chapters 10-11**: Patterns and troubleshooting
- **Chapters 12-14**: Reference materials

---

## 2. Getting Started

### 2.1 Development Environment Setup

#### Prerequisites
```bash
# Python 3.10 or higher
python --version  # Should be >= 3.10

# Install AIPerf in development mode
pip install -e ".[dev]"

# Install pre-commit hooks
pre-commit install

# Run tests to verify setup
pytest
```

#### Recommended Tools
- **IDE**: PyCharm, VS Code with Python extensions
- **Debugger**: Built-in Python debugger or `ipdb`
- **Profiler**: `yappi` (enable with `AIPERF_DEV_MODE=1 --enable-yappi-profiling`)
- **Network Inspector**: Wireshark for ZMQ debugging

### 2.2 Project Structure

```
aiperf/
├── aiperf/                     # Main package
│   ├── cli.py                  # CLI entry point
│   ├── cli_runner.py           # System controller bootstrap
│   ├── clients/                # HTTP and OpenAI clients
│   ├── common/                 # Shared utilities and base classes
│   │   ├── config/             # Configuration system
│   │   ├── enums/              # Enumerations
│   │   ├── messages/           # Message types
│   │   ├── mixins/             # Reusable mixins
│   │   ├── models/             # Data models
│   │   └── protocols.py        # Protocol definitions
│   ├── controller/             # System controller and service managers
│   ├── dataset/                # Dataset loaders, composers, generators
│   ├── exporters/              # Results exporters (console, CSV, JSON)
│   ├── metrics/                # Metrics system
│   │   └── types/              # Metric implementations
│   ├── parsers/                # Response parsers
│   ├── post_processors/        # Metrics processors
│   ├── records/                # Records management
│   ├── timing/                 # Timing and credit management
│   ├── ui/                     # UI implementations
│   │   └── dashboard/          # Textual-based dashboard
│   ├── workers/                # Worker processes
│   └── zmq/                    # ZMQ communication layer
├── tests/                      # Test suite
├── integration-tests/          # Integration tests with mock server
├── docs/                       # Documentation
├── tools/                      # Development tools
└── pyproject.toml              # Project configuration
```

### 2.3 Running AIPerf

#### Basic Usage
```bash
# Simple benchmark
aiperf profile \
  --model Qwen/Qwen3-0.6B \
  --url http://localhost:8000 \
  --endpoint-type chat \
  --request-count 100 \
  --concurrency 10 \
  --streaming
```

#### Developer Mode
```bash
# Enable developer features
export AIPERF_DEV_MODE=1

aiperf profile \
  --model Qwen/Qwen3-0.6B \
  --url http://localhost:8000 \
  --endpoint-type chat \
  --show-internal-metrics \
  --enable-yappi-profiling
```

### 2.4 First Contribution Workflow

1. **Find an Issue**: Browse [GitHub Issues](https://github.com/ai-dynamo/aiperf/issues)
2. **Create Branch**: `git checkout -b feature/my-feature`
3. **Make Changes**: Follow coding guidelines (Section 8)
4. **Write Tests**: Add tests for new functionality
5. **Run Linters**: `pre-commit run --all-files`
6. **Run Tests**: `pytest tests/`
7. **Commit**: Follow commit message conventions
8. **Push**: `git push origin feature/my-feature`
9. **Create PR**: Open pull request with description

### 2.5 Key Concepts for New Developers

Before diving into the code, understand these core concepts:

1. **Services**: Independent processes coordinated by SystemController
2. **Credits**: Token-based flow control for request rate management
3. **Phases**: Warmup and Profiling phases in benchmark lifecycle
4. **Records**: Data structure tracking request/response metadata
5. **Metrics**: Computed statistics from records (record, aggregate, derived types)
6. **ZMQ**: Zero-copy messaging library for inter-process communication
7. **Hooks**: Decorator-based lifecycle event handlers
8. **Mixins**: Composable functionality via multiple inheritance

---

## 3. Architecture Overview

### 3.1 High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                      System Controller                          │
│  (Orchestrates services, manages lifecycle, handles commands)   │
└───────┬────────────────────────┬────────────────────────────────┘
        │                        │
        ├─ Timing Manager         ├─ Dataset Manager
        │  (Credit issuance)      │  (Data loading)
        │                         │
        ├─ Worker Manager         ├─ Records Manager
        │  (Health monitoring)    │  (Results aggregation)
        │                         │
        └─ Workers (1...N)        └─ Record Processors (1...M)
           (Request execution)       (Metrics computation)
                   │
                   ▼
            Inference Endpoint
```

**Data Flow:**
```
Dataset → Timing Manager → Workers → Inference API → Workers →
Record Processors → Records Manager → Metrics Processors → Exporters
```

### 3.2 Service Architecture

AIPerf uses a **microservices-inspired architecture** where each service:
- Runs in its own process (true parallelism, no GIL)
- Communicates via ZMQ message bus
- Has its own lifecycle (initialize, start, run, stop)
- Registers with SystemController
- Responds to commands

**Core Services:**
1. **SystemController**: Central orchestrator
2. **DatasetManager**: Serves dataset requests
3. **TimingManager**: Issues request credits on schedule
4. **WorkerManager**: Monitors worker health
5. **Workers (N)**: Execute inference requests
6. **RecordProcessor (M)**: Compute per-record metrics
7. **RecordsManager**: Aggregate results and finalize metrics

### 3.3 Communication Patterns

AIPerf uses **three ZMQ communication patterns**:

#### Pub/Sub (Event Bus)
```
Services → PUB → XPubXSub Proxy → SUB → Services
```
- Broadcasting: Commands, status updates, heartbeats
- One-to-many or many-to-many

#### Push/Pull (Work Distribution)
```
Timing Manager → PUSH → PushPull Proxy → PULL → Workers
Workers → PUSH → PushPull Proxy → PULL → Record Processors
```
- Credit drops, inference results
- Round-robin load balancing

#### Dealer/Router (Request/Reply)
```
Workers → DEALER → DealerRouter Proxy → ROUTER → Dataset Manager
```
- Conversation requests
- Async request-response

### 3.4 Lifecycle States

All services follow a common lifecycle:

```
CREATED → INITIALIZING → INITIALIZED → STARTING → RUNNING → STOPPING → STOPPED
```

**State Transitions:**
- **CREATED**: Instance created, fields initialized
- **INITIALIZING**: `@on_init` hooks execute (sockets, clients created)
- **INITIALIZED**: Ready to start
- **STARTING**: `@on_start` hooks execute (background tasks start)
- **RUNNING**: Normal operation
- **STOPPING**: `@on_stop` hooks execute (cleanup)
- **STOPPED**: All resources released

**Critical Rules:**
- Communication clients must be created in `__init__` or `@on_init`
- Background tasks start in `@on_start`
- Always cleanup resources in `@on_stop`
- Never block in lifecycle hooks (use async/await)

### 3.5 Credit-Based Flow Control

AIPerf uses a **credit system** for precise request rate control:

```
┌─────────────┐
│ Credit Pool │ (Based on request_rate, concurrency, duration)
└──────┬──────┘
       │ Issue credits at target rate
       ▼
┌──────────────┐
│ Credit Drops │ (PUSH to workers)
└──────┬───────┘
       │
       ▼
┌──────────────┐
│   Workers    │ (Semaphore limits concurrency)
└──────┬───────┘
       │ Execute request
       ▼
┌──────────────┐
│ Credit Return│ (PUSH to timing manager)
└──────────────┘
```

**Key Insight**: Credits are issued at target rate, semaphores enforce concurrency limit. This decouples rate generation from execution, allowing precise control.

---

## 4. Core Subsystems

### 4.1 Workers and Worker Manager

#### 4.1.1 Worker Architecture

Workers are independent processes that:
1. Receive credit drops via ZMQ PULL
2. Request conversation data from DatasetManager
3. Send HTTP requests to inference endpoints
4. Parse and timestamp responses
5. Return credits to TimingManager
6. Push results to RecordProcessor

**Key Files:**
- `/aiperf/workers/worker.py`: Main worker implementation
- `/aiperf/workers/worker_manager.py`: Worker orchestration

#### 4.1.2 Worker Lifecycle

```python
class Worker(PullClientMixin, BaseComponentService, ProcessHealthMixin):
    @on_pull_message(MessageType.CREDIT_DROP)
    async def _credit_drop_callback(self, message: CreditDropMessage):
        """Entry point for credit processing."""
        await self._process_credit_drop_internal(message)
```

**Critical Pattern**: Credit return in `finally` block ensures no credit leaks:

```python
try:
    await self._execute_single_credit_internal(message)
finally:
    # ALWAYS return credit, even on error
    await self.credit_return_push_client.push(
        CreditReturnMessage(...)
    )
```

#### 4.1.3 Timing Precision

Workers use **dual timestamp system**:
- `time.time_ns()`: Absolute wall-clock time (for logging)
- `time.perf_counter_ns()`: Monotonic high-resolution timer (for latency)

```python
drop_perf_ns = time.perf_counter_ns()  # Start timing
# ... make request ...
first_response_perf_ns = time.perf_counter_ns()  # First token
end_perf_ns = time.perf_counter_ns()  # Request complete

ttft = first_response_perf_ns - drop_perf_ns
latency = end_perf_ns - drop_perf_ns
```

#### 4.1.4 Worker Auto-Scaling

WorkerManager computes optimal worker count:

```python
max_workers = min(
    int(cpu_count * 0.75) - 1,  # Leave headroom
    concurrency or sys.maxsize,  # Respect concurrency limit
    32  # Hard cap
)
max_workers = max(max_workers, workers_config.min or 1)
```

**Rationale**: 75% CPU utilization leaves room for system processes. Subtract 1 for other AIPerf services.

#### 4.1.5 Connection Pooling

Workers use **shared TCP connector** for HTTP connection reuse:

```python
self.tcp_connector = create_tcp_connector(
    limit=AIPERF_HTTP_CONNECTION_LIMIT,  # 2500
    ttl_dns_cache=300,
    keepalive_timeout=300,
)

# Reused across all requests
async with aiohttp.ClientSession(
    connector=self.tcp_connector,
    connector_owner=False  # Don't close on session exit
) as session:
    await session.request(...)
```

### 4.2 Dataset Manager and Timing Manager

#### 4.2.1 Dataset Manager Architecture

DatasetManager serves data via three paths:

1. **Public Datasets**: ShareGPT from HuggingFace
2. **Custom Datasets**: User-provided files (single turn, multi turn, trace, random pool)
3. **Synthetic Datasets**: Generated on-the-fly

**Key Files:**
- `/aiperf/dataset/dataset_manager.py`: Main service
- `/aiperf/dataset/loader/`: Dataset loaders
- `/aiperf/dataset/composer/`: Composers (orchestrate loaders)
- `/aiperf/dataset/generator/`: Data generators (prompts, images, audio)

#### 4.2.2 Dataset Types

| Type | Use Case | Features |
|------|----------|----------|
| **Single Turn** | Simple Q&A | One turn per conversation |
| **Multi Turn** | Dialogues | Multiple turns with delays |
| **Mooncake Trace** | Trace replay | Timestamps, hash_ids for KV cache |
| **Random Pool** | Diverse sampling | Random selection with replacement |
| **ShareGPT** | Public benchmark | Filtered by token lengths |
| **Synthetic** | Generated data | Configurable distributions |

#### 4.2.3 Timing Manager Strategies

**Three timing strategies:**

1. **Request Rate** (`RequestRateStrategy`)
   - **Constant**: Fixed inter-arrival time (1/rate)
   - **Poisson**: Exponentially distributed (realistic traffic)
   - **Concurrency Burst**: No delay, rely on semaphore

2. **Fixed Schedule** (`FixedScheduleStrategy`)
   - Loads (timestamp, conversation_id) tuples
   - Waits until scheduled time
   - Deterministic trace replay

3. **Credit Issuing** (Base class)
   - Sequential phase execution (warmup → profiling)
   - Grace period handling
   - Timeout detection

#### 4.2.4 Phase Lifecycle

```
Warmup Phase Start → Issue Credits → Sending Complete → All Returned → Complete
Profiling Phase Start → Issue Credits → Sending Complete → All Returned → Complete
Credits Complete
```

**Grace Period**: Extra time after duration expires to allow in-flight requests to complete.

```python
timeout = remaining_duration + grace_period
try:
    await asyncio.wait_for(phase_complete_event.wait(), timeout=timeout)
except asyncio.TimeoutError:
    # Force completion, mark timeout_triggered=True
```

#### 4.2.5 Request Cancellation

Optional feature to test timeout behavior:

```python
class RequestCancellationStrategy:
    def should_cancel_request(self) -> bool:
        return self._rng.random() < self._cancellation_rate

    def get_cancellation_delay_ns(self) -> int:
        return self._cancellation_delay_ns
```

Workers handle cancellation using `asyncio.wait_for()`:

```python
try:
    response = await asyncio.wait_for(
        session.request(...),
        timeout=cancel_after_ns / NANOS_PER_SECOND
    )
except asyncio.TimeoutError:
    # Mark request as cancelled
    record.was_cancelled = True
    record.error = ErrorDetails(code=499, message="Client Closed Request")
```

### 4.3 Records Processing Pipeline

#### 4.3.1 Pipeline Stages

```
RequestRecord (raw) → InferenceResultParser → ParsedResponseRecord →
MetricRecordProcessor (distributed) → MetricRecordDict →
MetricResultsProcessor (centralized) → MetricResultsDict →
Exporters → Console/CSV/JSON
```

#### 4.3.2 Parsing Stage

**InferenceResultParser** transforms raw responses:

```python
async def parse_request_record(
    self, request_record: RequestRecord
) -> ParsedResponseRecord:
    # Extract responses using endpoint-specific extractor
    responses = await self.extractor.extract(request_record.responses)

    # Tokenize input/output
    input_tokens = self.tokenizer.encode(input_text)
    output_tokens = self.tokenizer.encode(output_text)

    return ParsedResponseRecord(
        request=request_record,
        responses=responses,
        input_token_count=len(input_tokens),
        output_token_count=len(output_tokens),
        reasoning_token_count=reasoning_tokens,
    )
```

#### 4.3.3 Metric Processing Stage

**MetricRecordProcessor** (distributed):

```python
async def process_record(
    self, record: ParsedResponseRecord
) -> MetricRecordDict:
    record_metrics = MetricRecordDict()

    # Process metrics in dependency order
    for tag, parse_func in self.parse_funcs:
        try:
            record_metrics[tag] = parse_func(record, record_metrics)
        except NoMetricValue:
            pass  # Metric not applicable

    return record_metrics
```

#### 4.3.4 Results Aggregation Stage

**MetricResultsProcessor** (centralized):

```python
async def process_result(self, incoming_metrics: MetricRecordDict):
    for tag, value in incoming_metrics.items():
        if metric_type == MetricType.RECORD:
            # Append to array
            self._results[tag].append(value)
        elif metric_type == MetricType.AGGREGATE:
            # Update aggregate value
            metric.aggregate_value(value)
            self._results[tag] = metric.current_value

async def update_derived_metrics(self):
    """Called once after all records processed."""
    for tag, derive_func in self.derive_funcs.items():
        self._results[tag] = derive_func(self._results)
```

#### 4.3.5 MetricArray Optimization

**NumPy-backed dynamic array**:

```python
class MetricArray:
    def __init__(self, initial_capacity=10000):
        self._data = np.empty(initial_capacity)
        self._size = 0
        self._sum = 0  # Running sum for O(1) average

    def append(self, value):
        self._resize_if_needed(1)
        self._data[self._size] = value
        self._sum += value
        self._size += 1

    def to_result(self, tag, header, unit) -> MetricResult:
        arr = self.data  # Zero-copy view
        percentiles = np.percentile(arr, [1, 5, 25, 50, 75, 90, 95, 99])
        return MetricResult(
            tag=tag, unit=unit, header=header,
            min=np.min(arr), max=np.max(arr),
            avg=self._sum / self._size,
            std=float(np.std(arr)),
            p1=percentiles[0], ..., p99=percentiles[7],
        )
```

**Performance**: Percentile computation on 100K values takes ~10ms.

### 4.4 HTTP and OpenAI Clients

#### 4.4.1 AioHttpClientMixin

High-performance HTTP client optimized for benchmarking:

```python
class AioHttpClientMixin:
    async def _request(self, method, url, **kwargs) -> RequestRecord:
        start_perf_ns = time.perf_counter_ns()

        async with aiohttp.ClientSession(...) as session:
            start_perf_ns = time.perf_counter_ns()  # Re-capture

            async with session.request(method, url, **kwargs) as response:
                recv_start_perf_ns = time.perf_counter_ns()

                if response.content_type == "text/event-stream":
                    # SSE handling
                    responses = await AioHttpSSEStreamReader(response).read()
                else:
                    # Regular response
                    text = await response.text()
                    responses = [TextResponse(perf_ns=end_ns, text=text)]

                end_perf_ns = time.perf_counter_ns()

        return RequestRecord(
            start_perf_ns=start_perf_ns,
            recv_start_perf_ns=recv_start_perf_ns,
            end_perf_ns=end_perf_ns,
            responses=responses,
        )
```

#### 4.4.2 SSE Stream Reading

**First-byte timestamp capture**:

```python
# Read first byte immediately
first_byte = await response.content.read(1)
chunk_ns_first_byte = time.perf_counter_ns()

# Read rest of chunk
chunk = await response.content.readuntil(b"\n\n")
full_chunk = first_byte + chunk

# Parse SSE fields
message = SSEMessage(perf_ns=chunk_ns_first_byte, packets=fields)
```

#### 4.4.3 TCP Socket Optimizations

```python
def create_socket(af, socktype, proto, address):
    sock = socket.socket(af, socktype, proto)
    sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_QUICKACK, 1)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
    sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPIDLE, 60)
    sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPINTVL, 30)
    sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPCNT, 1)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 10 * 1024 * 1024)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 10 * 1024 * 1024)
    return sock
```

**Why?**
- `TCP_NODELAY`: Disable Nagle's algorithm for low latency
- `TCP_QUICKACK`: Reduce ACK delay
- Large buffers: Handle streaming responses efficiently
- Keepalive: Maintain long-lived connections

### 4.5 ZMQ Communication Layer

#### 4.5.1 Socket Types and Patterns

| Pattern | Sockets | Use Case |
|---------|---------|----------|
| **Pub/Sub** | PUB → SUB | Event bus, broadcasting |
| **Push/Pull** | PUSH → PULL | Work distribution |
| **Dealer/Router** | DEALER ↔ ROUTER | Async request-response |

#### 4.5.2 Proxy Architecture

**Three proxies** enable many-to-many communication:

```
XPubXSub Proxy (Event Bus):
  Frontend: XSUB (clients PUB here)
  Backend: XPUB (services SUB here)

PushPull Proxy (Inference Results):
  Frontend: PULL (workers PUSH here)
  Backend: PUSH (processors PULL here)

DealerRouter Proxy (Dataset Requests):
  Frontend: ROUTER (workers DEALER here)
  Backend: DEALER (dataset manager ROUTER here)
```

**Critical**: Proxies run in separate threads via `asyncio.to_thread()` to avoid blocking event loop.

#### 4.5.3 Pull Client Semaphore Pattern

**Why acquire before recv?**

```python
# CORRECT - ZMQ load balancing works
await self.semaphore.acquire()  # Block if at limit
message = await socket.recv_string()  # Receive work
# ... process ...
self.semaphore.release()

# WRONG - Breaks load balancing
message = await socket.recv_string()  # Receive regardless
await self.semaphore.acquire()  # Block after receiving
```

If semaphore is acquired after `recv`, the socket will still receive messages even when the worker is at capacity, causing those messages to queue up locally instead of being distributed to other workers.

#### 4.5.4 Topic-Based Pub/Sub

**Topic structure**:
```
{message_type}$
{message_type}.{service_id}$
{message_type}.{service_type}$
```

**Examples**:
- `command$`: All commands
- `command.worker_123$`: Commands for worker_123
- `command.WORKER$`: Commands for all workers
- `status$`: All status messages

**Why the `$` suffix?** Prevents prefix matching issues:
- Without: `command` subscription also receives `command_response`
- With: `command$` only receives `command`, not `command_response$`

### 4.6 UI and Dashboard

#### 4.6.1 UI Architecture

Three UI modes:

1. **Dashboard** (Textual-based): Rich TUI with live updates
2. **Simple** (tqdm): Progress bars only
3. **NoUI**: Headless mode

**Base abstraction**:

```python
class BaseAIPerfUI(ProgressTrackerMixin, WorkerTrackerMixin, RealtimeMetricsMixin):
    """Mixins provide hook-based event handling."""
```

#### 4.6.2 Dashboard Components

```
┌─────────────────────────────────────────────────┐
│ Progress Header (warmup/profiling status)      │
├──────────────────────┬──────────────────────────┤
│ Progress Dashboard   │ Realtime Metrics Table  │
│ (phases, stats)      │ (TTFT, ITL, throughput) │
├──────────────────────┴──────────────────────────┤
│ Worker Dashboard (status, CPU, memory, tasks)  │
├─────────────────────────────────────────────────┤
│ Log Viewer (color-coded, scrollable)           │
└─────────────────────────────────────────────────┘
```

#### 4.6.3 Log Integration

**Dashboard Mode**: Logs go to queue, consumed by UI

```python
if ui_type == AIPerfUIType.DASHBOARD:
    handler = MultiProcessLogHandler(log_queue, service_id)
    logger.addHandler(handler)
```

**Other Modes**: Logs go directly to Rich console

```python
else:
    handler = RichHandler(console=console, ...)
    logger.addHandler(handler)
```

**Log Consumer** polls queue at 10 FPS:

```python
@background_task(immediate=True, interval=0.1)
async def _consume_logs(self):
    while not self.log_queue.empty():
        record = self.log_queue.get_nowait()
        self.app.log_viewer.write(self._format_log(record))
```

---

## 5. Configuration System

### 5.1 Configuration Architecture

AIPerf uses **Pydantic v2** for configuration with **Cyclopts** for CLI integration.

**Two-tier system**:
1. **UserConfig**: Benchmarking parameters (exposed to users)
2. **ServiceConfig**: Runtime parameters (internal)

### 5.2 Configuration Hierarchy

```
UserConfig
├── endpoint: EndpointConfig (model, URL, streaming, timeout)
├── input: InputConfig (file, dataset type, random seed)
│   ├── audio: AudioConfig
│   ├── image: ImageConfig
│   ├── prompt: PromptConfig
│   │   ├── input_tokens: InputTokensConfig
│   │   ├── output_tokens: OutputTokensConfig
│   │   └── prefix_prompt: PrefixPromptConfig
│   └── conversation: ConversationConfig
│       └── turn: TurnConfig
├── output: OutputConfig (artifact directory)
├── tokenizer: TokenizerConfig (HuggingFace tokenizer)
└── loadgen: LoadGeneratorConfig (rate, concurrency, duration)

ServiceConfig
├── service_run_type: ServiceRunType (process, k8s)
├── zmq_tcp / zmq_ipc: Communication configs
├── workers: WorkersConfig
├── log_level: AIPerfLogLevel
├── ui_type: AIPerfUIType
└── developer: DeveloperConfig (dev-only settings)
```

### 5.3 CLI Integration Pattern

```python
# Configuration field with CLI mapping
request_rate: Annotated[
    float | None,
    Field(
        gt=0,  # Pydantic validation
        description="Request rate in requests/second",
    ),
    CLIParameter(
        name=("--request-rate",),  # CLI flag
        group=Groups.LOAD_GENERATOR,  # Help grouping
    ),
] = LoadGeneratorDefaults.REQUEST_RATE  # Default value
```

**Cyclopts** inspects Pydantic models and automatically generates CLI:

```python
@app.command(name="profile")
def profile(
    user_config: UserConfig,  # Auto-parsed from CLI
    service_config: ServiceConfig | None = None,
):
    run_system_controller(user_config, service_config)
```

### 5.4 Validation Patterns

#### Field-Level Validation
```python
Field(gt=0)  # Greater than
Field(ge=0)  # Greater than or equal
Field(lt=100)  # Less than
Field(le=100)  # Less than or equal
Field(min_length=1)  # String/list minimum length
```

#### BeforeValidator (Input Transformation)
```python
model_names: Annotated[
    list[str],
    BeforeValidator(parse_str_or_list),  # "a,b,c" → ["a","b","c"]
]
```

#### Model Validator (Cross-Field Validation)
```python
@model_validator(mode="after")
def validate_benchmark_mode(self) -> Self:
    if ("benchmark_duration" in self.loadgen.model_fields_set and
        "request_count" in self.loadgen.model_fields_set):
        raise ValueError("Cannot use both duration and count-based modes")
    return self
```

### 5.5 Adding New Configuration Options

**Step 1**: Add field to config class
```python
class MyConfig(BaseConfig):
    my_field: Annotated[
        int,
        Field(gt=0, description="My new field"),
        CLIParameter(name=("--my-field",), group=Groups.MY_GROUP),
    ] = MyDefaults.MY_FIELD
```

**Step 2**: Add default
```python
@dataclass(frozen=True)
class MyDefaults:
    MY_FIELD = 42
```

**Step 3**: Add validator if needed
```python
@model_validator(mode="after")
def validate_my_field(self) -> Self:
    if self.my_field > 1000:
        raise ValueError("my_field too large")
    return self
```

**Step 4**: Add tests
```python
def test_my_field_default():
    config = MyConfig()
    assert config.my_field == MyDefaults.MY_FIELD

def test_my_field_validation():
    with pytest.raises(ValidationError):
        MyConfig(my_field=-1)
```

---

## 6. Communication Architecture

### 6.1 Message Types

All messages inherit from `Message` base class:

```python
class Message(AIPerfBaseModel):
    message_type: MessageTypeT
    request_ns: int | None
    request_id: str | None

    @classmethod
    def from_json(cls, json_str: str) -> "Message":
        # Auto-detects type and deserializes
```

**Message Categories**:

1. **Service Messages**: Status, registration, heartbeat
2. **Command Messages**: Commands and responses
3. **Data Messages**: Inference results, metric records
4. **Progress Messages**: Phase progress, worker status
5. **Error Messages**: Error propagation

### 6.2 Command Pattern

```python
class CommandMessage(TargetedServiceMessage):
    command: CommandTypeT
    command_id: str  # UUID for tracking

    # Specific commands
    class ProfileStartCommand(CommandMessage): ...
    class SpawnWorkersCommand(CommandMessage): ...
```

**Command Response**:

```python
class CommandResponse(TargetedServiceMessage):
    command: CommandTypeT
    command_id: str  # Matches request
    status: CommandResponseStatus

    # Response types
    class CommandSuccessResponse: status = SUCCESS
    class CommandErrorResponse: status = FAILURE, error = ErrorDetails
```

**Async Command-Response**:

```python
# Send command, get response
response = await self.send_command_and_wait_for_response(
    ProfileStartCommand(service_id=self.id, ...),
    timeout=30.0
)

# Send command to all, wait for all responses
responses = await self.send_command_and_wait_for_all_responses(
    ProfileConfigureCommand(service_id=self.id, config=...),
    service_ids=["worker_1", "worker_2", "worker_3"],
    timeout=60.0
)
```

### 6.3 Message Bus Client Mixin

Auto-subscribes based on `@on_message` decorators:

```python
class MyService(MessageBusClientMixin, BaseService):
    @on_message(MessageType.STATUS)
    async def handle_status(self, message: StatusMessage):
        # Automatically subscribed to "status$" topic
        self.info(f"Received status from {message.service_id}")
```

### 6.4 Pull Client Mixin

Auto-registers callbacks based on `@on_pull_message` decorators:

```python
class Worker(PullClientMixin, BaseService):
    def __init__(self, ...):
        super().__init__(
            pull_client_address=CommAddress.CREDIT_DROP,
            max_pull_concurrency=10  # Semaphore limit
        )

    @on_pull_message(MessageType.CREDIT_DROP)
    async def process_credit(self, message: CreditDropMessage):
        # Automatically registered as pull callback
        await self.handle_credit(message)
```

### 6.5 Reply Client Mixin

Auto-registers request handlers based on `@on_request` decorators:

```python
class DatasetManager(ReplyClientMixin, BaseService):
    def __init__(self, ...):
        super().__init__(
            reply_client_address=CommAddress.DATASET_MANAGER_BACKEND,
            reply_client_bind=True
        )

    @on_request(MessageType.CONVERSATION_REQUEST)
    async def handle_request(
        self, message: ConversationRequestMessage
    ) -> ConversationResponseMessage:
        conversation = self.get_conversation(message.conversation_id)
        return ConversationResponseMessage(conversation=conversation)
```

---

## 7. Metrics System

### 7.1 Metric Type Hierarchy

```
BaseMetric[ValueType]
├── BaseRecordMetric[ValueType] (per-request values)
│   └── Examples: TTFTMetric, RequestLatencyMetric, InputSequenceLengthMetric
├── BaseAggregateMetric[ValueType] (running aggregations)
│   ├── BaseAggregateCounterMetric[int] (simple counters)
│   │   └── Examples: RequestCountMetric, ErrorRequestCountMetric
│   └── Examples: MaxResponseTimestampMetric, MinRequestTimestampMetric
└── BaseDerivedMetric[ValueType] (computed from other metrics)
    ├── DerivedSumMetric[ValueType, SourceMetric] (auto-sum)
    │   └── Examples: TotalInputSequenceLengthMetric
    └── Examples: RequestThroughputMetric, GoodputMetric
```

### 7.2 Adding a New Metric

#### Record Metric (Per-Request)

```python
# File: aiperf/metrics/types/my_latency_metric.py

from aiperf.common.enums import MetricFlags, MetricTimeUnit
from aiperf.metrics import BaseRecordMetric
from aiperf.metrics.metric_dicts import MetricRecordDict
from aiperf.common.models import ParsedResponseRecord

class MyLatencyMetric(BaseRecordMetric[int]):
    """My custom latency metric.

    Formula: (Last response - first response) / 2
    """

    # Required fields
    tag = "my_latency"
    header = "My Latency"
    unit = MetricTimeUnit.NANOSECONDS
    display_unit = MetricTimeUnit.MILLISECONDS
    display_order = 250
    flags = MetricFlags.STREAMING_ONLY

    # Optional dependencies
    required_metrics = {"request_latency"}

    def _parse_record(
        self,
        record: ParsedResponseRecord,
        record_metrics: MetricRecordDict,
    ) -> int:
        if len(record.responses) < 2:
            raise NoMetricValue("Need at least 2 responses")

        first = record.responses[0].perf_ns
        last = record.responses[-1].perf_ns
        return (last - first) // 2
```

#### Derived Metric (From Other Metrics)

```python
# File: aiperf/metrics/types/my_throughput_metric.py

from aiperf.metrics import BaseDerivedMetric
from aiperf.metrics.metric_dicts import MetricResultsDict
from aiperf.metrics.types.request_count_metric import RequestCountMetric
from aiperf.metrics.types.my_latency_metric import MyLatencyMetric

class MyThroughputMetric(BaseDerivedMetric[float]):
    """Average throughput based on my latency."""

    tag = "my_throughput"
    header = "My Throughput"
    unit = MetricOverTimeUnit.REQUESTS_PER_SECOND
    display_order = 850
    flags = MetricFlags.LARGER_IS_BETTER

    required_metrics = {
        MyLatencyMetric.tag,
        RequestCountMetric.tag,
    }

    def _derive_value(self, metric_results: MetricResultsDict) -> float:
        count = metric_results.get_or_raise(RequestCountMetric)

        # For record metrics, get MetricArray
        my_latency_array = metric_results.get_or_raise(MyLatencyMetric)
        avg_latency_ns = my_latency_array.sum / my_latency_array.count
        avg_latency_s = avg_latency_ns / NANOS_PER_SECOND

        return count / avg_latency_s
```

### 7.3 Metric Flags

```python
class MetricFlags(Flag):
    NONE = 0
    STREAMING_ONLY = 1 << 0        # Only for streaming
    ERROR_ONLY = 1 << 1            # Only for errors
    PRODUCES_TOKENS_ONLY = 1 << 2  # Only for token endpoints
    NO_CONSOLE = 1 << 3            # Hidden from console
    LARGER_IS_BETTER = 1 << 4      # Higher = better (default: lower)
    INTERNAL = 1 << 5              # Internal metric
    EXPERIMENTAL = 1 << 6          # Experimental
```

**Usage**:

```python
# Check if metric has flag
if metric.flags.has_flags(MetricFlags.STREAMING_ONLY):
    # Only compute for streaming

# Check if ANY flag present
if metric.flags.has_any_flags(MetricFlags.INTERNAL | MetricFlags.EXPERIMENTAL):
    # Internal or experimental

# Check if flag MISSING
if metric.flags.missing_flags(MetricFlags.NO_CONSOLE):
    # Display in console
```

### 7.4 Unit Conversion System

```python
# Metric stored in nanoseconds
class TTFTMetric(BaseRecordMetric[int]):
    unit = MetricTimeUnit.NANOSECONDS
    display_unit = MetricTimeUnit.MILLISECONDS

# Convert during computation
ttft_ms = record_metrics.get_converted_or_raise(
    TTFTMetric,
    MetricTimeUnit.MILLISECONDS
)

# Automatic conversion during export
result = to_display_unit(metric_result, MetricRegistry)
```

### 7.5 Metric Registry

Auto-registration via `__init_subclass__`:

```python
class BaseMetric:
    def __init_subclass__(cls, **kwargs):
        if not inspect.isabstract(cls):
            MetricRegistry.register_metric(cls)
```

**Usage**:

```python
# Get metric class
metric_class = MetricRegistry.get_class("ttft")

# Get all metric tags
tags = MetricRegistry.all_tags()

# Filter by type and flags
tags = MetricRegistry.tags_applicable_to(
    required_flags=MetricFlags.STREAMING_ONLY,
    disallowed_flags=MetricFlags.ERROR_ONLY,
    MetricType.RECORD
)

# Topological sort (dependency order)
ordered = MetricRegistry.topological_sort(tags)
```

---

## 8. Development Guidelines

### 8.1 Code Style

#### Type Hints
```python
# Always use type hints
def process_record(record: ParsedResponseRecord) -> MetricRecordDict:
    ...

# Use | for unions (Python 3.10+)
def get_value(x: int | None) -> str:
    ...

# Use Annotated for field metadata
field: Annotated[int, Field(gt=0), CLIParameter(...)]
```

#### Async/Await
```python
# Use async/await consistently
async def fetch_data(self) -> Data:
    result = await self.client.request(...)
    return result

# Don't mix sync and async
# ❌ BAD
def process(self):
    asyncio.run(self.async_process())

# ✅ GOOD
async def process(self):
    await self.async_process()
```

#### Error Handling
```python
# Catch specific exceptions
try:
    result = await operation()
except ValueError as e:
    logger.error(f"Invalid value: {e}")
except Exception as e:
    logger.exception("Unexpected error")
    raise

# Use context managers for cleanup
async with self.try_operation_or_stop("Operation Name"):
    await risky_operation()
```

#### Logging
```python
# Use lazy logging for expensive operations
self.debug(lambda: f"Processing {len(large_list)} items")

# Use appropriate levels
self.debug("Detailed info")
self.info("Important milestones")
self.warning("Potential issues")
self.error("Errors")
self.exception("Errors with traceback")
```

### 8.2 Naming Conventions

#### Variables
```python
# snake_case for variables and functions
request_count = 10
async def process_record(record): ...

# UPPER_CASE for constants
DEFAULT_TIMEOUT = 60.0
MAX_RETRIES = 3
```

#### Classes
```python
# PascalCase for classes
class RequestProcessor: ...
class HTTPClient: ...

# Suffix for types
class MyProtocol(Protocol): ...
class MyMixin: ...
class MyFactory: ...
```

#### Files
```python
# snake_case for files
aiperf/workers/worker.py
aiperf/metrics/types/ttft_metric.py
```

#### Private Members
```python
# Single underscore for internal
def _internal_method(self): ...
self._cache = {}

# Double underscore for name mangling (rare)
def __private_method(self): ...
```

### 8.3 Documentation

#### Docstrings
```python
def process_request(
    self,
    request: RequestRecord,
    timeout: float = 30.0,
) -> ProcessedRecord:
    """Process a single request record.

    This method validates the request, sends it to the endpoint,
    and parses the response into a structured format.

    Args:
        request: The request record to process
        timeout: Maximum time to wait for response in seconds

    Returns:
        Processed record with parsed responses

    Raises:
        ValueError: If request is invalid
        TimeoutError: If request exceeds timeout

    Example:
        >>> record = RequestRecord(...)
        >>> result = processor.process_request(record)
        >>> print(result.status)
        'success'
    """
```

#### Comments
```python
# Use comments for WHY, not WHAT
# ✅ GOOD
# Acquire semaphore before recv to enable ZMQ load balancing
await semaphore.acquire()
message = await socket.recv_string()

# ❌ BAD
# Acquire semaphore
await semaphore.acquire()
# Receive message
message = await socket.recv_string()
```

### 8.4 Best Practices

#### Immutability
```python
# Prefer immutable defaults
# ❌ BAD
def process(items=[]):
    items.append(1)
    return items

# ✅ GOOD
def process(items: list | None = None):
    items = items or []
    items.append(1)
    return items
```

#### Context Managers
```python
# Use context managers for resource management
async with self.processing_lock:
    self.counter += 1

with suppress(KeyError):
    del self.cache[key]
```

#### Early Returns
```python
# Use early returns for clarity
def process(value: int | None) -> str:
    if value is None:
        return "none"
    if value < 0:
        return "negative"
    return f"positive: {value}"
```

#### Composition Over Inheritance
```python
# ✅ GOOD - Use mixins for composition
class MyService(MessageBusClientMixin, PullClientMixin, BaseService):
    pass

# ❌ AVOID - Deep inheritance hierarchies
class BaseService: ...
class IntermediateService(BaseService): ...
class MyService(IntermediateService): ...
```

---

## 9. Testing Strategies

### 9.1 Test Structure

```
tests/
├── conftest.py                 # Shared fixtures
├── clients/                    # Client tests
├── common/                     # Common utilities tests
├── config/                     # Configuration tests
├── dataset/                    # Dataset tests
├── metrics/                    # Metric tests
├── parsers/                    # Parser tests
├── post_processors/            # Processor tests
├── records/                    # Records tests
├── timing/                     # Timing tests
├── ui/                         # UI tests
└── workers/                    # Worker tests
```

### 9.2 Test Patterns

#### Unit Tests
```python
import pytest
from aiperf.metrics.types.ttft_metric import TTFTMetric

def test_ttft_computation():
    """Test TTFT metric computation."""
    record = create_parsed_record(
        start_perf_ns=1000,
        responses=[
            create_response(perf_ns=1100),
            create_response(perf_ns=1200),
        ]
    )

    metric = TTFTMetric()
    result = metric.parse_record(record, MetricRecordDict())

    assert result == 100  # 1100 - 1000

def test_ttft_missing_responses():
    """Test TTFT with no responses."""
    record = create_parsed_record(responses=[])

    metric = TTFTMetric()
    with pytest.raises(NoMetricValue):
        metric.parse_record(record, MetricRecordDict())
```

#### Parametrized Tests
```python
@pytest.mark.parametrize(
    "input,expected",
    [
        ("a,b,c", ["a", "b", "c"]),
        (["a", "b"], ["a", "b"]),
        ("single", ["single"]),
    ],
)
def test_parse_str_or_list(input, expected):
    result = parse_str_or_list(input)
    assert result == expected
```

#### Async Tests
```python
@pytest.mark.asyncio
async def test_worker_credit_processing():
    """Test worker processes credit drops."""
    worker = Worker(...)
    await worker.initialize()

    credit = CreditDropMessage(request_id="test-1", ...)
    await worker._credit_drop_callback(credit)

    # Verify credit returned
    assert len(worker.returned_credits) == 1
```

#### Mocking
```python
from unittest.mock import MagicMock, patch

def test_http_client_retry(mocker):
    """Test HTTP client retries on failure."""
    mock_session = mocker.patch("aiohttp.ClientSession")
    mock_session.request.side_effect = [
        aiohttp.ClientError(),
        MagicMock(status=200),
    ]

    client = HTTPClient()
    response = await client.request("GET", "http://test")

    assert mock_session.request.call_count == 2
```

### 9.3 Fixtures

#### Common Fixtures
```python
# tests/conftest.py

@pytest.fixture
def user_config():
    """Standard user config for tests."""
    return UserConfig(
        endpoint=EndpointConfig(
            model_names=["test-model"],
            url="http://localhost:8000",
        ),
        loadgen=LoadGeneratorConfig(
            request_count=10,
        ),
    )

@pytest.fixture
def parsed_record():
    """Sample parsed response record."""
    return ParsedResponseRecord(
        request=RequestRecord(...),
        responses=[...],
        input_token_count=10,
        output_token_count=20,
    )
```

### 9.4 Test Coverage

```bash
# Run tests with coverage
pytest --cov=aiperf --cov-report=html tests/

# View coverage report
open htmlcov/index.html

# Check coverage percentage
pytest --cov=aiperf --cov-fail-under=80 tests/
```

### 9.5 Integration Tests

```bash
# Run integration tests with mock server
cd integration-tests
make test

# Run specific integration test
pytest integration-tests/test_chat_completions.py
```

---

## 10. Common Patterns

### 10.1 Service Pattern

```python
@ServiceFactory.register(ServiceType.MY_SERVICE)
class MyService(MessageBusClientMixin, BaseComponentService):
    def __init__(self, service_config, user_config, service_id=None):
        # Create clients BEFORE super().__init__
        self.pub_client = self.comms.create_pub_client(...)
        self.sub_client = self.comms.create_sub_client(...)

        super().__init__(
            service_config=service_config,
            user_config=user_config,
            service_id=service_id,
        )

    @on_init
    async def _initialize(self):
        """Initialize resources."""
        self.debug("Initializing MyService")
        # Setup state, load data, etc.

    @on_start
    async def _start(self):
        """Start service operation."""
        self.info("Starting MyService")
        # Start background tasks

    @on_message(MessageType.COMMAND)
    async def _handle_command(self, message: CommandMessage):
        """Handle commands."""
        # Process command

    @on_stop
    async def _stop(self):
        """Cleanup resources."""
        self.debug("Stopping MyService")
        # Close connections, cancel tasks, etc.
```

### 10.2 Background Task Pattern

```python
class MyService(BaseService):
    @background_task(immediate=True, interval=1.0)
    async def _periodic_task(self):
        """Runs every 1 second."""
        # Do periodic work
        await self.publish_status()

    @background_task(immediate=False, interval=lambda self: self.interval)
    async def _configurable_task(self):
        """Interval determined at runtime."""
        # Do work
```

### 10.3 Hook Pattern

```python
# Define hook
@provides_hooks(AIPerfHook.ON_CUSTOM_EVENT)
class MyMixin:
    async def trigger_custom_event(self, data):
        await self.trigger_hook(AIPerfHook.ON_CUSTOM_EVENT, data)

# Use hook
class MyService(MyMixin, BaseService):
    @on_custom_event
    async def handle_event(self, data):
        # Handle event
```

### 10.4 Factory Pattern

```python
class MyFactory(AIPerfSingletonFactory[MyType, MyProtocol]):
    """Factory for creating MyProtocol instances."""

@MyFactory.register(MyType.OPTION_A)
class OptionA(MyProtocol):
    ...

@MyFactory.register(MyType.OPTION_B)
class OptionB(MyProtocol):
    ...

# Usage
instance = MyFactory.create_instance(MyType.OPTION_A, **kwargs)
```

### 10.5 Context Manager Pattern

```python
class MyService(BaseService):
    @asynccontextmanager
    async def try_operation_or_stop(self, operation_name: str):
        """Execute operation or stop service on failure."""
        try:
            yield
        except Exception as e:
            self.error(f"{operation_name} failed: {e}")
            await self.stop()
            raise

# Usage
async with self.try_operation_or_stop("Initialize Database"):
    await self.db.connect()
```

### 10.6 Lazy Initialization Pattern

```python
class MyService(BaseService):
    def __init__(self):
        self._cache = None

    async def get_cache(self):
        if self._cache is None:
            self._cache = await self._build_cache()
        return self._cache
```

### 10.7 Batch Update Pattern

```python
# Textual UI batch updates
async with self.widget.batch():
    self.widget.update_field1(value1)
    self.widget.update_field2(value2)
    self.widget.update_field3(value3)
# All updates rendered in single pass
```

---

## 11. Troubleshooting Guide

### 11.1 Common Issues

#### Issue: Port Already in Use

**Symptom**: `Address already in use` error on startup

**Causes**:
- Previous AIPerf instance still running
- Another application using the port

**Solutions**:
```bash
# Find and kill process
lsof -ti:5555 | xargs kill -9

# Or use different ports
aiperf profile --zmq-tcp-event-bus-proxy-frontend-port 6666 ...
```

#### Issue: Worker Stalls

**Symptom**: Workers report STALE status, no progress

**Causes**:
- Network connectivity issues
- Inference server not responding
- Request timeout too short

**Solutions**:
```bash
# Increase timeout
aiperf profile --timeout-seconds 1200 ...

# Check connectivity
curl http://localhost:8000/v1/models

# Check worker logs
tail -f artifacts/*/logs/aiperf.log | grep -i worker
```

#### Issue: Metric Not Showing

**Symptom**: Expected metric missing from output

**Causes**:
- Metric filtered by flags (streaming-only, etc.)
- Metric marked NO_CONSOLE
- Metric computation failed

**Solutions**:
```bash
# Enable internal metrics
aiperf profile --show-internal-metrics ...

# Check metric flags
python -c "from aiperf.metrics.metric_registry import MetricRegistry; print(MetricRegistry.get_class('your_metric').flags)"

# Check logs for errors
grep -i "error.*metric" artifacts/*/logs/aiperf.log
```

#### Issue: Dashboard Crashes

**Symptom**: Terminal becomes unusable, corrupted display

**Causes**:
- Terminal compatibility issues (macOS)
- ANSI sequence corruption

**Solutions**:
```bash
# Restore terminal
reset

# Use simple UI instead
aiperf profile --ui simple ...

# Or no UI
aiperf profile --ui no-ui ...
```

#### Issue: High Memory Usage

**Symptom**: AIPerf consuming excessive memory

**Causes**:
- Large dataset loaded into memory
- Too many workers
- Metric arrays growing unbounded

**Solutions**:
```bash
# Reduce workers
aiperf profile --workers-max 8 ...

# Use smaller dataset
aiperf profile --request-count 1000 ...

# Monitor memory
watch -n 1 'ps aux | grep aiperf'
```

### 11.2 Debugging Techniques

#### Enable Debug Logging
```bash
export AIPERF_DEV_MODE=1

aiperf profile \
  --verbose \
  --debug-services WORKER DATASET_MANAGER \
  ...
```

#### Enable Trace Logging
```bash
aiperf profile \
  --extra-verbose \
  --trace-services TIMING_MANAGER \
  ...
```

#### Profile Performance
```bash
export AIPERF_DEV_MODE=1

aiperf profile \
  --enable-yappi-profiling \
  ...

# View profile results
python -m yappi
```

#### Inspect ZMQ Messages
```bash
# Use tcpdump to capture ZMQ traffic
sudo tcpdump -i lo -X port 5555

# Or use wireshark with ZMQ dissector
wireshark
```

#### Attach Debugger
```python
# Add breakpoint in code
import ipdb; ipdb.set_trace()

# Or use built-in
breakpoint()
```

### 11.3 Performance Optimization

#### Optimize Worker Count
```bash
# Start with CPU count * 0.75
WORKERS=$(python -c "import os; print(int(os.cpu_count() * 0.75))")
aiperf profile --workers-max $WORKERS ...
```

#### Optimize Concurrency
```bash
# Start conservative, increase gradually
aiperf profile --concurrency 10 ...   # Good for initial testing
aiperf profile --concurrency 50 ...   # Moderate load
aiperf profile --concurrency 100 ...  # High load
```

#### Optimize Request Rate
```bash
# Use POISSON for realistic traffic
aiperf profile --request-rate 100 --request-rate-mode poisson ...

# Use CONSTANT for predictable load
aiperf profile --request-rate 100 --request-rate-mode constant ...

# Use CONCURRENCY_BURST for max throughput
aiperf profile --request-rate-mode concurrency_burst --concurrency 50 ...
```

#### Optimize Dataset Loading
```bash
# Use smaller datasets for testing
aiperf profile --request-count 100 ...

# Cache public datasets
# ShareGPT cached in ~/.cache/aiperf/datasets/

# Use random pool for fast sampling
aiperf profile --custom-dataset-type random_pool --file prompts.jsonl ...
```

---

## 12. Glossary

**Aggregate Metric**: Metric that accumulates values across multiple requests (e.g., RequestCountMetric)

**Background Task**: Coroutine that runs periodically in the background, managed by lifecycle system

**BaseConfig**: Pydantic-based configuration base class with YAML serialization

**BaseService**: Abstract base class for all AIPerf services with lifecycle management

**Benchmark Duration**: Time-based benchmarking mode (alternative to request count)

**CLI Parameter**: Cyclopts annotation mapping Pydantic fields to CLI flags

**Command**: Message type for service control (e.g., ProfileStartCommand)

**Composer**: Orchestrates loaders to create datasets

**Concurrency**: Maximum number of simultaneous in-flight requests

**Credit**: Token representing permission to send one request

**Credit Drop**: Message from TimingManager to Worker granting permission to send request

**Credit Phase**: Warmup or Profiling phase of benchmark

**Credit Return**: Message from Worker to TimingManager indicating request complete

**Custom Dataset**: User-provided dataset file (vs. public or synthetic)

**DEALER**: ZMQ socket type for async request (client-side of request/reply)

**Derived Metric**: Metric computed from other metrics (e.g., RequestThroughputMetric)

**Display Unit**: Unit for user-facing display (may differ from storage unit)

**Endpoint Type**: Type of API endpoint (chat, completions, embeddings, etc.)

**Error Details**: Structured error information (code, type, message)

**Event Bus**: Pub/Sub message bus for broadcasting events

**Exporter**: Component that outputs results (console, CSV, JSON)

**Factory**: Pattern for registering and creating instances based on type

**Fixed Schedule**: Trace replay mode with precise timestamp-based execution

**Generator**: Component that generates synthetic data (prompts, images, audio)

**Goodput**: Metric measuring successful requests meeting SLO thresholds

**Grace Period**: Extra time after benchmark duration for in-flight requests

**Hook**: Decorator-based lifecycle event handler (@on_init, @on_start, etc.)

**Inference Client**: HTTP client for sending requests to inference endpoints

**Inference Result**: Response from inference endpoint with timing metadata

**Inter Token Latency (ITL)**: Average time between output tokens

**IPC**: Inter-Process Communication (Unix domain sockets)

**Lifecycle**: Service state machine (CREATED → INITIALIZED → RUNNING → STOPPED)

**Loader**: Component that loads datasets from files or APIs

**Metric Array**: NumPy-backed dynamic array for efficient metric storage

**Metric Flag**: Enum indicating when/how metric should be computed

**Metric Record**: Per-request metric values computed by RecordProcessor

**Metric Registry**: Singleton managing metric registration and discovery

**Mixin**: Composable functionality via multiple inheritance

**Mooncake Trace**: Trace format for KV cache simulation

**Multi-Turn**: Conversation with multiple request/response exchanges

**Parser**: Component that parses inference responses into structured format

**Phase**: Benchmark lifecycle stage (Warmup, Profiling)

**Poisson**: Request rate mode with exponentially distributed inter-arrival times

**Post-Processor**: Component that processes metrics after collection

**Prefix Prompt**: Reused prompt prefix for KV cache testing

**Protocol**: Python protocol defining interface (duck typing)

**Proxy**: ZMQ device enabling many-to-many communication

**PUB**: ZMQ socket type for publishing messages (many subscribers)

**PULL**: ZMQ socket type for receiving work (round-robin from multiple senders)

**PUSH**: ZMQ socket type for sending work (distributed to multiple receivers)

**Record**: Data structure tracking request/response with timing metadata

**Record Metric**: Metric computed independently for each request

**Records Manager**: Central service aggregating results from all processors

**Request Cancellation**: Feature to test timeout behavior by cancelling requests

**Request Rate**: Target rate for issuing requests (requests per second)

**ROUTER**: ZMQ socket type for routing replies (server-side of request/reply)

**Semaphore**: Async concurrency limit (asyncio.Semaphore)

**Service**: Independent process in AIPerf architecture

**Service Config**: Runtime configuration for internal services

**Service Factory**: Factory for creating services based on ServiceType

**ServiceType**: Enum identifying service type (WORKER, DATASET_MANAGER, etc.)

**ShareGPT**: Public dataset of chat conversations

**Single Turn**: Conversation with one request/response exchange

**SSE**: Server-Sent Events (streaming HTTP protocol)

**SUB**: ZMQ socket type for subscribing to published messages

**Synthetic Dataset**: Generated dataset (not from file or API)

**System Controller**: Central orchestrator managing all services

**TCP**: Transmission Control Protocol (network sockets)

**Time to First Token (TTFT)**: Latency until first output token (streaming)

**Timing Manager**: Service issuing request credits on schedule

**Timing Mode**: Strategy for issuing credits (REQUEST_RATE, FIXED_SCHEDULE)

**Tokenizer**: HuggingFace tokenizer for counting tokens

**Trace Replay**: Benchmarking mode replaying recorded traffic traces

**Turn**: Single request/response in conversation

**UI Type**: Dashboard, Simple (tqdm), or NoUI

**User Config**: Benchmarking parameters exposed to users

**Warmup**: Initial phase to stabilize system before profiling

**Worker**: Process executing inference requests

**Worker Manager**: Service monitoring worker health and status

**XPUB**: ZMQ extended PUB socket (proxy frontend)

**XSUB**: ZMQ extended SUB socket (proxy backend)

**ZMQ**: Zero-copy messaging library for IPC

---

## 13. Keywords and Concepts

### 13.1 Architecture Keywords

- **Microservices**: Independent processes communicating via messages
- **Distributed Pipeline**: Work distributed across multiple workers
- **Credit-Based Flow Control**: Token system for rate limiting
- **Event-Driven**: Services react to messages/events
- **Async/Await**: Non-blocking I/O throughout
- **Protocol-Based**: Duck-typed interfaces via Python protocols
- **Factory Pattern**: Dynamic registration and instantiation
- **Mixin Composition**: Functionality composed via multiple inheritance
- **Lifecycle Management**: Standardized initialization, startup, shutdown
- **Hook System**: Decorator-based event handling

### 13.2 Performance Keywords

- **Zero-Copy**: ZMQ and NumPy minimize data copying
- **Connection Pooling**: Reuse HTTP connections
- **TCP Optimizations**: TCP_NODELAY, large buffers, keepalive
- **Dynamic Arrays**: Efficient metric storage with O(1) ops
- **Batch Updates**: Group UI updates to minimize flicker
- **Lazy Initialization**: Defer expensive operations
- **Concurrency Limits**: Semaphores prevent overload
- **Round-Robin**: ZMQ load balancing
- **Topological Sort**: Dependency-ordered metric computation

### 13.3 Data Flow Keywords

- **Pipeline**: Dataset → Credits → Workers → Results → Metrics → Export
- **Pull-Based**: Workers pull data on demand (not pushed)
- **Push Results**: Workers push results asynchronously
- **Aggregate**: Results aggregated centrally
- **Derive**: Final metrics derived from aggregated data
- **Filter**: Metrics filtered by flags and configuration
- **Transform**: Data transformed at each pipeline stage
- **Parse**: Responses parsed into structured format
- **Tokenize**: Text tokenized for metrics
- **Export**: Results exported to multiple formats

### 13.4 Testing Keywords

- **Unit Tests**: Test individual components in isolation
- **Integration Tests**: Test component interactions
- **Mocking**: Replace dependencies with mocks
- **Fixtures**: Reusable test data and setup
- **Parametrized**: Run same test with multiple inputs
- **Coverage**: Measure code coverage percentage
- **Async Tests**: Test async functions with pytest-asyncio
- **Test Doubles**: Mocks, stubs, fakes, spies

### 13.5 Communication Keywords

- **Message Bus**: Central pub/sub communication
- **Command Pattern**: Request-response commands
- **Targeted Messaging**: Direct messages to specific service
- **Broadcasting**: One-to-many message distribution
- **Work Distribution**: Round-robin work assignment
- **Request/Reply**: Async request-response pattern
- **Topic-Based**: Pub/sub with topic filtering
- **Proxy**: Many-to-many communication enabler
- **Routing Envelope**: ZMQ routing metadata
- **Serialization**: JSON-based message encoding

---

## 14. Appendix: File Reference

### 14.1 Core Entry Points

| File | Description |
|------|-------------|
| `aiperf/cli.py` | CLI entry point (cyclopts) |
| `aiperf/cli_runner.py` | SystemController bootstrap |
| `aiperf/__init__.py` | Package initialization |

### 14.2 Controllers and Managers

| File | Description |
|------|-------------|
| `aiperf/controller/system_controller.py` | Central orchestrator |
| `aiperf/controller/system_mixins.py` | Signal handling mixin |
| `aiperf/controller/proxy_manager.py` | ZMQ proxy management |
| `aiperf/controller/multiprocess_service_manager.py` | Process spawning |
| `aiperf/controller/base_service_manager.py` | Service manager base |

### 14.3 Workers

| File | Description |
|------|-------------|
| `aiperf/workers/worker.py` | Worker process |
| `aiperf/workers/worker_manager.py` | Worker orchestration |

### 14.4 Dataset System

| File | Description |
|------|-------------|
| `aiperf/dataset/dataset_manager.py` | Dataset service |
| `aiperf/dataset/loader/single_turn.py` | Single turn loader |
| `aiperf/dataset/loader/multi_turn.py` | Multi turn loader |
| `aiperf/dataset/loader/mooncake_trace.py` | Trace loader |
| `aiperf/dataset/loader/random_pool.py` | Random pool loader |
| `aiperf/dataset/loader/sharegpt.py` | ShareGPT loader |
| `aiperf/dataset/composer/synthetic.py` | Synthetic composer |
| `aiperf/dataset/composer/custom.py` | Custom composer |
| `aiperf/dataset/generator/prompt.py` | Prompt generator |
| `aiperf/dataset/generator/image.py` | Image generator |
| `aiperf/dataset/generator/audio.py` | Audio generator |

### 14.5 Timing System

| File | Description |
|------|-------------|
| `aiperf/timing/timing_manager.py` | Timing service |
| `aiperf/timing/credit_manager.py` | Credit management |
| `aiperf/timing/request_rate_strategy.py` | Request rate strategy |
| `aiperf/timing/fixed_schedule_strategy.py` | Fixed schedule strategy |
| `aiperf/timing/credit_issuing_strategy.py` | Base strategy |
| `aiperf/timing/request_cancellation_strategy.py` | Cancellation logic |

### 14.6 Records System

| File | Description |
|------|-------------|
| `aiperf/records/records_manager.py` | Records service |
| `aiperf/records/record_processor_service.py` | Record processor |
| `aiperf/records/phase_completion.py` | Completion detection |

### 14.7 Metrics System

| File | Description |
|------|-------------|
| `aiperf/metrics/base_metric.py` | Base metric class |
| `aiperf/metrics/base_record_metric.py` | Record metric base |
| `aiperf/metrics/base_aggregate_metric.py` | Aggregate metric base |
| `aiperf/metrics/base_derived_metric.py` | Derived metric base |
| `aiperf/metrics/metric_registry.py` | Metric registry |
| `aiperf/metrics/metric_dicts.py` | Metric data structures |
| `aiperf/metrics/types/ttft_metric.py` | TTFT metric |
| `aiperf/metrics/types/inter_token_latency_metric.py` | ITL metric |
| `aiperf/metrics/types/request_latency_metric.py` | Latency metric |
| `aiperf/metrics/types/request_throughput_metric.py` | Throughput metric |
| `aiperf/metrics/types/goodput_metric.py` | Goodput metric |

### 14.8 Post-Processors

| File | Description |
|------|-------------|
| `aiperf/post_processors/base_metrics_processor.py` | Base processor |
| `aiperf/post_processors/metric_record_processor.py` | Record processor |
| `aiperf/post_processors/metric_results_processor.py` | Results processor |

### 14.9 Exporters

| File | Description |
|------|-------------|
| `aiperf/exporters/exporter_manager.py` | Export orchestration |
| `aiperf/exporters/console_metrics_exporter.py` | Console metrics |
| `aiperf/exporters/console_error_exporter.py` | Console errors |
| `aiperf/exporters/csv_exporter.py` | CSV export |
| `aiperf/exporters/json_exporter.py` | JSON export |
| `aiperf/exporters/display_units_utils.py` | Unit conversion |

### 14.10 Clients

| File | Description |
|------|-------------|
| `aiperf/clients/http/aiohttp_client.py` | HTTP client |
| `aiperf/clients/http/tcp_connector.py` | TCP connector |
| `aiperf/clients/http/sse_utils.py` | SSE parsing |
| `aiperf/clients/openai/openai_aiohttp.py` | OpenAI client |
| `aiperf/clients/model_endpoint_info.py` | Endpoint info |

### 14.11 Parsers

| File | Description |
|------|-------------|
| `aiperf/parsers/inference_result_parser.py` | Main parser |
| `aiperf/parsers/openai_parsers.py` | OpenAI parsers |

### 14.12 ZMQ Communication

| File | Description |
|------|-------------|
| `aiperf/zmq/zmq_comms.py` | ZMQ communication |
| `aiperf/zmq/zmq_base_client.py` | Base ZMQ client |
| `aiperf/zmq/pub_client.py` | PUB client |
| `aiperf/zmq/sub_client.py` | SUB client |
| `aiperf/zmq/push_client.py` | PUSH client |
| `aiperf/zmq/pull_client.py` | PULL client |
| `aiperf/zmq/dealer_request_client.py` | DEALER client |
| `aiperf/zmq/router_reply_client.py` | ROUTER client |
| `aiperf/zmq/zmq_proxy_base.py` | Base proxy |
| `aiperf/zmq/zmq_proxy_sockets.py` | Proxy implementations |

### 14.13 Configuration

| File | Description |
|------|-------------|
| `aiperf/common/config/__init__.py` | Config exports |
| `aiperf/common/config/user_config.py` | User configuration |
| `aiperf/common/config/service_config.py` | Service configuration |
| `aiperf/common/config/endpoint_config.py` | Endpoint config |
| `aiperf/common/config/input_config.py` | Input config |
| `aiperf/common/config/loadgen_config.py` | Load generator config |
| `aiperf/common/config/prompt_config.py` | Prompt config |
| `aiperf/common/config/config_validators.py` | Validators |
| `aiperf/common/config/config_defaults.py` | Default values |

### 14.14 UI System

| File | Description |
|------|-------------|
| `aiperf/ui/base_ui.py` | Base UI class |
| `aiperf/ui/no_ui.py` | Headless mode |
| `aiperf/ui/tqdm_ui.py` | Progress bars |
| `aiperf/ui/dashboard/aiperf_dashboard_ui.py` | Dashboard wrapper |
| `aiperf/ui/dashboard/aiperf_textual_app.py` | Textual app |
| `aiperf/ui/dashboard/progress_dashboard.py` | Progress display |
| `aiperf/ui/dashboard/realtime_metrics_dashboard.py` | Metrics display |
| `aiperf/ui/dashboard/worker_dashboard.py` | Worker display |
| `aiperf/ui/dashboard/rich_log_viewer.py` | Log viewer |

### 14.15 Common Utilities

| File | Description |
|------|-------------|
| `aiperf/common/base_service.py` | Service base class |
| `aiperf/common/base_component_service.py` | Component service |
| `aiperf/common/bootstrap.py` | Service bootstrap |
| `aiperf/common/protocols.py` | Protocol definitions |
| `aiperf/common/factories.py` | Factory classes |
| `aiperf/common/logging.py` | Logging setup |
| `aiperf/common/constants.py` | Constants |
| `aiperf/common/enums/` | Enumerations |
| `aiperf/common/messages/` | Message types |
| `aiperf/common/mixins/` | Reusable mixins |
| `aiperf/common/models/` | Data models |

---

## End of Developer's Guidebook

This comprehensive guide covers the essential architecture, patterns, and practices for developing with AIPerf. For additional information:

- **Documentation**: See `/docs/` directory
- **Examples**: See `/integration-tests/` for working examples
- **Issues**: [GitHub Issues](https://github.com/ai-dynamo/aiperf/issues)
- **Discussions**: [GitHub Discussions](https://github.com/ai-dynamo/aiperf/discussions)
- **Discord**: [AIPerf Discord Server](https://discord.gg/D92uqZRjCZ)

**Contributing**: We welcome contributions! Please read this guide thoroughly before submitting PRs.

**Questions?** Open a discussion or reach out on Discord.

---

**Document Version**: 1.0
**Last Updated**: 2025-10-04
**Maintainers**: AIPerf Development Team
**License**: Apache 2.0
