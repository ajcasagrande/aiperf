<!--
# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
-->
# AIPerf Architecture Diagrams

Visual representations of AIPerf's architecture and data flows.

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         System Controller                           │
│  (Central orchestrator, service lifecycle, command distribution)    │
└──────┬──────────────────┬──────────────────┬────────────────────────┘
       │                  │                  │
       │                  │                  │
   ┌───▼────┐        ┌────▼────┐       ┌────▼─────┐
   │Timing  │        │Dataset  │       │Worker    │
   │Manager │        │Manager  │       │Manager   │
   └───┬────┘        └────┬────┘       └────┬─────┘
       │                  │                  │
       │ Credits          │ Data             │ Health
       │                  │                  │
   ┌───▼──────────────────▼──────────────────▼─────┐
   │             Workers (Processes 1...N)          │
   │  (Execute requests, measure timing, collect    │
   │   responses, return credits, send results)     │
   └───┬────────────────────────────────────────────┘
       │
       │ Inference Results
       │
   ┌───▼────────────────────────────────────────────┐
   │      Record Processors (Processes 1...M)       │
   │  (Parse responses, compute metrics,            │
   │   aggregate partial results)                   │
   └───┬────────────────────────────────────────────┘
       │
       │ Metric Records
       │
   ┌───▼────────────────────────────────────────────┐
   │             Records Manager                     │
   │  (Aggregate results, finalize metrics,         │
   │   detect completion, export)                   │
   └───┬────────────────────────────────────────────┘
       │
       │ Final Results
       │
   ┌───▼────────────────────────────────────────────┐
   │            Exporters                            │
   │  (Console, CSV, JSON)                          │
   └─────────────────────────────────────────────────┘
```

## Service Communication Architecture

```
                     ┌─────────────────────┐
                     │  System Controller  │
                     └──────────┬──────────┘
                                │
                    ┌───────────▼───────────┐
                    │   ZMQ Proxy Manager   │
                    │  (3 Proxies)          │
                    └───┬───────┬───────┬───┘
                        │       │       │
           ┌────────────┘       │       └────────────┐
           │                    │                    │
      ┌────▼────┐          ┌────▼────┐         ┌────▼────┐
      │ XPub/   │          │ Push/   │         │ Dealer/ │
      │ XSub    │          │ Pull    │         │ Router  │
      │ Proxy   │          │ Proxy   │         │ Proxy   │
      └────┬────┘          └────┬────┘         └────┬────┘
           │                    │                    │
    Event Bus             Result Flow           Data Requests
    (Commands,           (Inference            (Conversations,
     Status,              Results,              Timing Data)
     Progress)            Metrics)
```

## Credit Flow Architecture

```
┌───────────────────────────────────────────────────────────────┐
│                      Timing Manager                           │
│  - Calculates issue rate based on mode                        │
│  - Issues credits according to schedule                       │
│  - Tracks issued and returned credits                         │
└────┬──────────────────────────────────────────────┬───────────┘
     │                                              │
     │ PUSH (Credit Drop)                          │ PULL (Credit Return)
     │                                              │
┌────▼──────────────────────────────────────────────▼───────────┐
│                    Workers (N processes)                       │
│                                                                │
│  ┌──────────────────────────────────────────────────────┐     │
│  │  Credit Processing Loop:                             │     │
│  │  1. PULL credit from Timing Manager                  │     │
│  │  2. Acquire semaphore (enforce concurrency limit)    │     │
│  │  3. REQUEST conversation from Dataset Manager        │     │
│  │  4. SEND HTTP request to inference endpoint          │     │
│  │  5. RECEIVE and parse response                       │     │
│  │  6. PUSH results to Record Processor                 │     │
│  │  7. PUSH credit return to Timing Manager (finally)   │     │
│  │  8. Release semaphore                                │     │
│  └──────────────────────────────────────────────────────┘     │
└────────────────────────────────────────────────────────────────┘
```

## Data Flow Architecture

```
┌──────────────┐
│   Dataset    │
│   Manager    │
│              │
│ - Loads data │
│ - Serves on  │
│   request    │
└──────┬───────┘
       │
       │ REQ/REPLY
       │ (Conversation Request)
       │
   ┌───▼──────────────────┐
   │    Workers           │
   │                      │
   │ ┌─────────────────┐  │
   │ │ Build Request   │  │
   │ │   Payload       │  │
   │ └────────┬────────┘  │
   │          │           │
   │          │ HTTP POST │
   │          │           │
   │ ┌────────▼────────┐  │
   │ │   Inference     │  │
   │ │    Endpoint     │  │
   │ └────────┬────────┘  │
   │          │           │
   │          │ Response  │
   │          │           │
   │ ┌────────▼────────┐  │
   │ │ Parse Response  │  │
   │ │ Timestamp Data  │  │
   │ └────────┬────────┘  │
   └──────────┼───────────┘
              │
              │ PUSH
              │ (Inference Results)
              │
   ┌──────────▼───────────┐
   │  Record Processors   │
   │                      │
   │ - Parse responses    │
   │ - Tokenize text      │
   │ - Compute metrics    │
   └──────────┬───────────┘
              │
              │ PUSH
              │ (Metric Records)
              │
   ┌──────────▼───────────┐
   │  Records Manager     │
   │                      │
   │ - Aggregate metrics  │
   │ - Detect completion  │
   │ - Export results     │
   └──────────┬───────────┘
              │
              ▼
         ┌─────────┐
         │Exporters│
         └─────────┘
```

## Metrics Processing Pipeline

```
┌─────────────────────────────────────────────────────────────────────┐
│                     Metrics Processing Pipeline                     │
└─────────────────────────────────────────────────────────────────────┘

Stage 1: Record Processing (Distributed across Record Processors)
┌─────────────────────────────────────────────────────────────────────┐
│  ParsedResponseRecord                                               │
│         │                                                            │
│         ├─► TTFT Metric ────────────► value: 50 (ms)                │
│         ├─► Request Latency Metric ─► value: 487 (ms)               │
│         ├─► Input Seq Length ───────► value: 512 (tokens)           │
│         ├─► Output Seq Length ──────► value: 256 (tokens)           │
│         └─► Request Count ──────────► value: 1                      │
│                                                                      │
│  Output: MetricRecordDict {tag: value}                              │
└──────────────────────────────────┬──────────────────────────────────┘
                                   │
                    ┌──────────────▼──────────────┐
                    │   PUSH to Records Manager   │
                    └──────────────┬──────────────┘
                                   │
Stage 2: Aggregation (Centralized in Records Manager)
┌──────────────────────────────────▼──────────────────────────────────┐
│  MetricResultsProcessor                                             │
│                                                                      │
│  Record Metrics (append to MetricArray):                            │
│    ttft: [50, 45, 60, 48, ...] ──► Compute percentiles later       │
│    request_latency: [487, 490, ...] ──► Statistical summary        │
│                                                                      │
│  Aggregate Metrics (update running value):                          │
│    request_count: 1 + 1 + 1 + ... = 100                            │
│    good_request_count: 1 + 0 + 1 + ... = 95                        │
│                                                                      │
└──────────────────────────────────┬──────────────────────────────────┘
                                   │
Stage 3: Derivation (After all records processed)
┌──────────────────────────────────▼──────────────────────────────────┐
│  Compute Derived Metrics                                            │
│                                                                      │
│  request_throughput = request_count / benchmark_duration            │
│  goodput = good_request_count / benchmark_duration                  │
│  output_token_throughput = total_output_tokens / benchmark_duration │
│                                                                      │
│  Output: Complete MetricResultsDict                                 │
└──────────────────────────────────┬──────────────────────────────────┘
                                   │
                                   ▼
                              ┌─────────┐
                              │Exporters│
                              └─────────┘
```

## ZMQ Communication Patterns

### Pub/Sub (Event Bus)

```
┌──────────────────────────────────────────────────────────────┐
│                    Publishers (Any Service)                  │
└───┬──────────────────────────────────────────────────────┬───┘
    │ PUB                                                   │ PUB
    │                                                       │
    ▼                                                       ▼
┌────────────────────────────────────────────────────────────────┐
│                      XSUB (Frontend)                           │
│                     XPub/XSub Proxy                            │
│                      XPUB (Backend)                            │
└────────┬─────────────────────────────────────────────┬─────────┘
         │ SUB                                         │ SUB
         ▼                                             ▼
    ┌─────────┐                                   ┌─────────┐
    │Service 1│                                   │Service N│
    └─────────┘                                   └─────────┘
```

**Use Cases**: Commands, status updates, heartbeats, progress notifications

---

### Push/Pull (Work Distribution)

```
┌─────────────────┐
│ Timing Manager  │
└────────┬────────┘
         │ PUSH (Credit Drop)
         ▼
    ┌─────────────────┐
    │ PULL (Frontend) │
    │ Push/Pull Proxy │
    │ PUSH (Backend)  │
    └────────┬────────┘
             │ PULL (Round-robin)
     ┌───────┼───────┬───────┐
     ▼       ▼       ▼       ▼
┌────────┐ ┌────────┐ ... ┌────────┐
│Worker 1│ │Worker 2│     │Worker N│
└────────┘ └────────┘     └────────┘
```

**Use Cases**: Credit distribution, result collection

---

### Dealer/Router (Request/Reply)

```
┌────────┐ ┌────────┐     ┌────────┐
│Worker 1│ │Worker 2│ ... │Worker N│
└────┬───┘ └────┬───┘     └────┬───┘
     │ DEALER   │ DEALER        │ DEALER
     │          │               │
     ▼          ▼               ▼
┌──────────────────────────────────────┐
│      ROUTER (Frontend)               │
│      Dealer/Router Proxy             │
│      DEALER (Backend)                │
└──────────────────┬───────────────────┘
                   │ ROUTER
                   ▼
           ┌────────────────┐
           │Dataset Manager │
           └────────────────┘
```

**Use Cases**: Dataset requests, timing data requests

---

## Lifecycle State Machine

```
┌─────────┐
│ CREATED │ (Instance created, __init__ called)
└────┬────┘
     │ initialize()
     ▼
┌─────────────┐
│INITIALIZING │ (@on_init hooks execute)
└────┬────────┘
     │
     ▼
┌────────────┐
│INITIALIZED │ (Ready to start)
└────┬───────┘
     │ start()
     ▼
┌──────────┐
│ STARTING │ (@on_start hooks execute, background tasks start)
└────┬─────┘
     │
     ▼
┌─────────┐
│ RUNNING │ (Normal operation, processing requests)
└────┬────┘
     │ stop()
     ▼
┌──────────┐
│ STOPPING │ (@on_stop hooks execute, cleanup)
└────┬─────┘
     │
     ▼
┌─────────┐
│ STOPPED │ (All resources released, process can exit)
└─────────┘
```

**Key Rules**:
- Communication clients created in CREATED or INITIALIZING
- Background tasks started in STARTING
- Cleanup happens in STOPPING
- Never block in lifecycle hooks (use async/await)

---

## Benchmark Execution Flow

```
┌─────────────────────────────────────────────────────────────────┐
│ User runs: aiperf profile --model X --url Y ...                │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
                 ┌─────────────────────┐
                 │ Parse CLI Arguments │
                 │ Create UserConfig   │
                 └──────────┬──────────┘
                            │
                            ▼
              ┌──────────────────────────┐
              │ Bootstrap System         │
              │ Controller               │
              └──────────┬───────────────┘
                         │
                         ▼
         ┌────────────────────────────────────┐
         │ Start Services:                    │
         │ - Proxy Manager (first!)           │
         │ - Dataset Manager                  │
         │ - Timing Manager                   │
         │ - Worker Manager                   │
         │ - Records Manager                  │
         └──────────┬─────────────────────────┘
                    │
                    ▼
        ┌─────────────────────────────────────┐
        │ Wait for Service Registration       │
        └──────────┬──────────────────────────┘
                   │
                   ▼
       ┌──────────────────────────────────────┐
       │ CONFIGURE Phase                      │
       │ - Send ProfileConfigureCommand       │
       │ - Services load datasets, setup      │
       │ - Workers spawn                      │
       └──────────┬───────────────────────────┘
                  │
                  ▼
       ┌──────────────────────────────────────┐
       │ START Phase                          │
       │ - Send ProfileStartCommand           │
       │ - Timing Manager begins issuing      │
       │   credits                            │
       └──────────┬───────────────────────────┘
                  │
                  ▼
       ┌──────────────────────────────────────┐
       │ WARMUP Phase (if configured)         │
       │ - Issue warmup credits               │
       │ - Wait for all returns               │
       └──────────┬───────────────────────────┘
                  │
                  ▼
       ┌──────────────────────────────────────┐
       │ PROFILING Phase                      │
       │ - Issue profiling credits            │
       │ - Workers execute requests           │
       │ - Results flow to processors         │
       │ - Metrics aggregated                 │
       └──────────┬───────────────────────────┘
                  │
                  ▼
       ┌──────────────────────────────────────┐
       │ PROCESSING Phase                     │
       │ - Wait for all records processed     │
       │ - Finalize metrics                   │
       │ - Detect completion                  │
       └──────────┬───────────────────────────┘
                  │
                  ▼
       ┌──────────────────────────────────────┐
       │ EXPORT Phase                         │
       │ - Export to console                  │
       │ - Export to CSV                      │
       │ - Export to JSON                     │
       └──────────┬───────────────────────────┘
                  │
                  ▼
       ┌──────────────────────────────────────┐
       │ SHUTDOWN Phase                       │
       │ - Stop all services                  │
       │ - Cleanup resources                  │
       │ - Exit                               │
       └──────────────────────────────────────┘
```

## Worker Process Detail

```
┌─────────────────────────────────────────────────────────────────┐
│                       Worker Process                            │
└─────────────────────────────────────────────────────────────────┘

┌──────────────┐
│ Pull Client  │ ◄─────────── PULL credit from Timing Manager
└──────┬───────┘
       │ CreditDropMessage received
       │
       ▼
┌────────────────────────┐
│ Acquire Semaphore      │ ◄─── Enforce max concurrency
└──────┬─────────────────┘
       │
       ▼
┌────────────────────────┐
│ Request Client (DEALER)│ ◄─── REQUEST conversation
│ → Dataset Manager      │
└──────┬─────────────────┘
       │ Conversation received
       │
       ▼
┌────────────────────────┐
│ HTTP Client (aiohttp)  │ ◄─── POST to inference endpoint
│ → Inference Endpoint   │
└──────┬─────────────────┘
       │ Response received (streaming or complete)
       │
       ▼
┌────────────────────────┐
│ Parse & Timestamp      │ ◄─── Extract tokens, compute latencies
└──────┬─────────────────┘
       │
       ▼
┌────────────────────────┐
│ Push Client            │ ◄─── PUSH results to Record Processor
│ → Record Processor     │
└──────┬─────────────────┘
       │
       ▼
┌────────────────────────┐
│ Push Client (finally)  │ ◄─── PUSH credit return (ALWAYS)
│ → Timing Manager       │
└──────┬─────────────────┘
       │
       ▼
┌────────────────────────┐
│ Release Semaphore      │ ◄─── Allow next credit processing
└────────────────────────┘
```

## Configuration Hierarchy

```
UserConfig (CLI-facing)
├── endpoint: EndpointConfig
│   ├── model_names: list[str]
│   ├── url: str
│   ├── type: EndpointType
│   ├── streaming: bool
│   └── timeout_seconds: float
│
├── input: InputConfig
│   ├── file: Path
│   ├── custom_dataset_type: CustomDatasetType
│   ├── prompt: PromptConfig
│   │   ├── input_tokens: InputTokensConfig
│   │   ├── output_tokens: OutputTokensConfig
│   │   └── prefix_prompt: PrefixPromptConfig
│   ├── conversation: ConversationConfig
│   ├── image: ImageConfig
│   ├── audio: AudioConfig
│   └── goodput: dict[str, float]
│
├── output: OutputConfig
│   └── artifact_directory: Path
│
├── tokenizer: TokenizerConfig
│   └── name: str
│
└── loadgen: LoadGeneratorConfig
    ├── request_rate: float
    ├── request_rate_mode: RequestRateMode
    ├── concurrency: int
    ├── request_count: int
    ├── benchmark_duration: float
    └── benchmark_grace_period: float

ServiceConfig (Runtime config)
├── service_run_type: ServiceRunType
├── zmq_tcp / zmq_ipc: ZMQConfig
├── workers: WorkersConfig
├── log_level: AIPerfLogLevel
├── ui_type: AIPerfUIType
└── developer: DeveloperConfig
```

## See Also

- **[Architecture Overview](architecture.md)** - Detailed architecture description
- **[Developer's Guidebook Chapter 5](../guidebook/chapter-05-architecture-fundamentals.md)** - Architecture fundamentals
- **[Developer's Guidebook Chapter 14](../guidebook/chapter-14-zmq-communication.md)** - ZMQ patterns
- **[Developer's Guidebook Chapter 7](../guidebook/chapter-07-workers-architecture.md)** - Worker internals
