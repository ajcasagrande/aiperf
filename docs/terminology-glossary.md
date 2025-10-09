<!--
SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
SPDX-License-Identifier: Apache-2.0
-->

# AIPerf Terminology Glossary

This comprehensive glossary defines all key terminologies, concepts, and technical terms used throughout the AIPerf codebase and documentation. Terms are organized by category for easy reference.

---

## Core Concepts

### AIPerf
The complete benchmarking framework for performance testing generative AI models. AIPerf provides a command-line interface, multiprocess architecture, and comprehensive metrics collection for evaluating inference servers.

### Benchmark / Profiling
The process of measuring and evaluating the performance of an AI inference server under controlled load conditions. In AIPerf, these terms are used interchangeably to describe a performance test run.

### Benchmark Run
A complete execution of AIPerf from initialization through results collection and export. Each run produces artifacts including logs, metrics, and exported data files.

---

## Architecture Components

### System Controller
The central orchestration service that manages the lifecycle of all other components. The System Controller:
- Initializes and starts all required services
- Coordinates configuration and profiling commands
- Handles graceful shutdown and error recovery
- Manages the overall benchmark execution flow

Source: `aiperf/controller/system_controller.py`

### Dataset Manager
The service responsible for managing benchmark input data. Functions include:
- Loading datasets from files (JSONL, ShareGPT, traces) or generating synthetic data
- Providing conversations and turns to workers on-demand
- Managing tokenization of input prompts
- Generating `inputs.json` file for reproducibility

Source: `aiperf/dataset/dataset_manager.py`

### Timing Manager
Controls the timing and scheduling of requests during benchmarking. Responsibilities:
- Issuing timing credits according to the selected benchmarking mode
- Managing request rate, concurrency, or fixed schedule timing
- Coordinating with the Dataset Manager for trace-based benchmarking
- Supporting warmup and profiling phases

Source: `aiperf/timing/timing_manager.py`

### Worker
Individual processes that execute benchmarking tasks. Each worker:
- Receives timing credits from the Timing Manager
- Requests conversation data from the Dataset Manager
- Sends HTTP/API requests to the inference server
- Records timestamps and collects response data
- Reports results to Record Processors

Source: `aiperf/workers/worker.py`

### Worker Manager
Orchestrates the pool of worker processes. Functions:
- Spawning and managing worker processes
- Monitoring worker health and performance
- Tracking worker status and resource usage
- Coordinating worker lifecycle events

Source: `aiperf/workers/worker_manager.py`

### Record Processor
Services that process raw inference results. Responsibilities:
- Parsing responses from the inference server
- Computing per-request metrics (latency, token counts, etc.)
- Validating and normalizing data
- Sending processed records to the Records Manager

Source: `aiperf/records/record_processor_service.py`

### Records Manager
Central repository for all benchmarking results. Functions:
- Collecting processed records from Record Processors
- Aggregating metrics across all requests
- Managing phase completion detection
- Generating final results and statistics
- Providing real-time metrics updates

Source: `aiperf/records/records_manager.py`

---

## Service Infrastructure

### Service
A component in the AIPerf system that runs independently (either as a process or Kubernetes pod). All services inherit from `BaseService` or `BaseComponentService` and follow a common lifecycle pattern.

### Service Type
Enumeration defining the types of services in AIPerf:
- `SYSTEM_CONTROLLER` - Central orchestrator
- `DATASET_MANAGER` - Data management
- `TIMING_MANAGER` - Request timing
- `WORKER` - Request execution
- `WORKER_MANAGER` - Worker orchestration
- `RECORD_PROCESSOR` - Result processing
- `RECORDS_MANAGER` - Result aggregation

Source: `aiperf/common/enums/service_enums.py:32`

### Service Run Type
Defines how services are deployed:
- `MULTIPROCESSING` (process) - Each service runs as a separate process (default for single-node)
- `KUBERNETES` (k8s) - Each service runs as a Kubernetes pod (for multi-node)

Source: `aiperf/common/enums/service_enums.py:7`

### Lifecycle State
The state of a service during its lifecycle:
- `CREATED` - Service instantiated
- `INITIALIZING` - Running initialization logic
- `INITIALIZED` - Initialization complete
- `STARTING` - Starting service operations
- `RUNNING` - Active and operational
- `STOPPING` - Shutting down
- `STOPPED` - Fully stopped
- `FAILED` - Service encountered an error

Source: `aiperf/common/enums/service_enums.py:19`

---

## Communication & Messaging

### ZMQ (ZeroMQ)
The messaging library used for inter-service communication in AIPerf. Provides high-performance asynchronous messaging patterns.

### Communication Address (CommAddress)
Named endpoints for ZMQ communication channels. Examples:
- `CREDIT_DROP` - Timing credits to workers
- `CREDIT_RETURN` - Credits returned from workers
- `RAW_INFERENCE_PROXY_FRONTEND` - Inference results from workers
- `RECORDS` - Processed records to Records Manager
- `MESSAGE_BUS` - Broadcast messages to all services

Source: `aiperf/common/enums/communication_enums.py`

### Message Types
Categories of messages exchanged between services:
- `COMMAND` - Control messages (configure, start, stop, cancel)
- `STATUS` - Service status updates
- `HEARTBEAT` - Keep-alive signals
- `CREDIT_DROP` - Timing credit distribution
- `METRIC_RECORDS` - Processed benchmark results
- `INFERENCE_RESULT` - Raw inference responses
- And many more specific types

Source: `aiperf/common/enums/message_enums.py`

### Proxy
ZMQ proxy services that forward messages between services. Used to enable many-to-many communication patterns:
- `DATASET_MANAGER_PROXY` - Routes dataset requests
- `RAW_INFERENCE_PROXY` - Forwards inference results
- `RECORDS_PROXY` - Routes processed records

Source: `aiperf/controller/proxy_manager.py`

---

## Timing & Load Generation

### Timing Mode
The strategy used to generate request timing:
- `FIXED_SCHEDULE` - Requests sent according to predetermined timestamps (trace replay)
- `REQUEST_RATE` - Requests generated at a specified rate (QPS)

Source: `aiperf/common/enums/timing_enums.py:7`

### Request Rate Mode
How requests are distributed over time when using request rate:
- `CONSTANT` - Evenly spaced requests
- `POISSON` - Poisson-distributed inter-arrival times (default)
- `CONCURRENCY_BURST` - Send requests as fast as possible up to concurrency limit

Source: `aiperf/common/enums/timing_enums.py:19`

### Concurrency
The number of simultaneous in-flight requests. This is a key load parameter that determines how many requests can be active at any given time.

### Request Rate
The target number of requests per second (QPS - Queries Per Second). Can be combined with a maximum concurrency limit.

### Credit / Timing Credit
A token issued by the Timing Manager that authorizes a worker to send one request. Credits implement the timing strategy and control the rate/schedule of requests.

### Credit Phase
The phase of benchmarking a credit belongs to:
- `WARMUP` - Requests sent before measurement begins
- `PROFILING` - Requests that count toward final metrics

Source: `aiperf/common/enums/timing_enums.py:32`

### Credit Issuing Strategy
The algorithm that determines when and how credits are issued. Implementations include:
- `FixedScheduleStrategy` - Issues credits based on predetermined timestamps
- `RequestRateStrategy` - Issues credits at a target rate
- `RequestCancellationStrategy` - Wraps other strategies to add cancellation behavior

Source: `aiperf/timing/credit_issuing_strategy.py`

---

## Datasets & Data Generation

### Dataset
A collection of conversations used as input for benchmarking. Can be synthetic, loaded from files, or from public datasets.

### Composer / Dataset Composer
Component that creates or loads datasets:
- `SyntheticComposer` - Generates synthetic data
- `CustomComposer` - Loads user-provided data files
- `PublicDatasetComposer` - Downloads and loads public datasets

Source: `aiperf/dataset/composer/`

### Composer Type
The type of dataset source:
- `SYNTHETIC` - Generated data
- `CUSTOM` - User-provided files
- `PUBLIC_DATASET` - Public dataset repositories

Source: `aiperf/common/enums/dataset_enums.py:11`

### Custom Dataset Type
Format of user-provided dataset files:
- `SINGLE_TURN` - One prompt-response pair per conversation
- `MULTI_TURN` - Multiple turns within conversations
- `RANDOM_POOL` - Random selection from a pool of prompts
- `MOONCAKE_TRACE` - Mooncake trace file format for replay

Source: `aiperf/common/enums/dataset_enums.py:17`

### Conversation / Session
A sequence of turns between a user and the AI model. Each conversation has a unique session ID and contains one or more turns.

### Turn
A single request-response interaction within a conversation. For multi-turn conversations, turns are executed sequentially with optional delays.

### Prompt
The input text sent to the model for a single turn. May include system messages, user messages, and assistant messages for chat endpoints.

### Payload
The formatted request body sent to the inference server, including the prompt, parameters, and endpoint-specific fields.

---

## Endpoints & Protocols

### Endpoint Type
The type of API endpoint being benchmarked:
- `CHAT` - Chat completions (OpenAI `/v1/chat/completions`)
- `COMPLETIONS` - Text completions (OpenAI `/v1/completions`)
- `EMBEDDINGS` - Text embeddings (OpenAI `/v1/embeddings`)
- `RANKINGS` - Text rankings (NIM `/v1/ranking`)
- `RESPONSES` - Response generation (OpenAI `/v1/responses`)

Source: `aiperf/common/enums/endpoints_enums.py:36`

### Endpoint Service Kind
The API protocol/format of the endpoint:
- `OPENAI` - OpenAI-compatible API format

Source: `aiperf/common/enums/endpoints_enums.py:15`

### Streaming
A mode where the inference server sends responses incrementally as Server-Sent Events (SSE) rather than as a single response. Enables metrics like TTFT and ITL.

### Server-Sent Events (SSE)
The HTTP protocol used for streaming responses. The server sends multiple `data:` messages over a single connection.

### Inference Client
Component that sends HTTP requests to the inference server and handles responses. Different implementations exist for different endpoint types.

Source: `aiperf/clients/`

### Request Converter
Component that formats conversation turns into endpoint-specific payloads. Handles differences in request structure across endpoint types.

Source: `aiperf/common/factories.py`

---

## Metrics & Measurements

### Metric
A measured or calculated performance indicator. AIPerf computes three types of metrics: Record, Aggregate, and Derived.

### Metric Type
The computation category of a metric:
- `RECORD` - Computed per-request, produces distributions (e.g., latency)
- `AGGREGATE` - Accumulated across all requests, produces single values (e.g., request count)
- `DERIVED` - Computed from other metrics using formulas (e.g., throughput)

Source: `aiperf/common/enums/metric_enums.py:287`

### Metric Tag
A unique string identifier for a metric (e.g., `request_latency`, `ttft`, `output_token_throughput`). Used for programmatic access and export.

### Metric Unit
The unit of measurement for a metric value:
- **Time Units**: `ns`, `us`, `ms`, `sec`
- **Generic Units**: `tokens`, `requests`, `count`, `ratio`, `user`
- **Rate Units**: `requests/sec`, `tokens/sec`, `tokens/sec/user`
- **Size Units**: `B`, `KB`, `MB`, `GB`, `TB`

Source: `aiperf/common/enums/metric_enums.py`

### Metric Flags
Attributes that control metric behavior:
- `STREAMING_ONLY` - Only for streaming endpoints
- `PRODUCES_TOKENS_ONLY` - Only for token-generating endpoints
- `HIDDEN` - Not displayed in UI
- `INTERNAL` - System metric, not user-facing
- `EXPERIMENTAL` - Experimental, subject to change
- `ERROR_ONLY` - Only computed for error records
- `LARGER_IS_BETTER` - Higher values are better (default: lower is better)

Source: `aiperf/common/enums/metric_enums.py:379`

### Record Metric
A metric computed individually for each request. Produces a distribution with statistics (min, max, mean, median, p90, p99, std). Examples: request latency, TTFT, ITL, token counts.

Source: `aiperf/metrics/base_record_metric.py`

### Aggregate Metric
A metric that tracks or accumulates values across all requests in real-time. Produces a single value. Examples: request count, error count, min/max timestamps.

Source: `aiperf/metrics/base_aggregate_metric.py`

### Derived Metric
A metric computed from other metrics using formulas. Not computed per-request. Examples: request throughput, output token throughput, benchmark duration.

Source: `aiperf/metrics/base_derived_metric.py`

---

## Key Performance Metrics

### Request Latency
Total time from sending a request to receiving the final response. For streaming, this is until the last chunk.

Formula: `final_response_timestamp - request_start_timestamp`

Tag: `request_latency`

Source: `docs/metrics_reference.md:54`

### Time to First Token (TTFT)
Time from sending a request to receiving the first token/chunk. Critical for perceived responsiveness in streaming scenarios.

Formula: `first_response_timestamp - request_start_timestamp`

Tag: `ttft`

Source: `docs/metrics_reference.md:68`

### Time to Second Token (TTST)
Time between the first and second token/chunk. Helps identify generation startup overhead.

Formula: `second_response_timestamp - first_response_timestamp`

Tag: `ttst`

Source: `docs/metrics_reference.md:82`

### Inter Token Latency (ITL)
Average time between consecutive tokens during generation, excluding TTFT overhead. Represents steady-state generation rate.

Formula: `(request_latency - ttft) / (output_sequence_length - 1)`

Tag: `inter_token_latency`

Source: `docs/metrics_reference.md:94`

### Inter Chunk Latency (ICL)
Distribution of time gaps between all consecutive response chunks. Unlike ITL (an average), ICL provides the full distribution.

Formula: `[response[i].timestamp - response[i-1].timestamp for i in 1..N]`

Tag: `inter_chunk_latency`

Source: `docs/metrics_reference.md:110`

### Input Sequence Length (ISL)
Number of input/prompt tokens for a request.

Tag: `input_sequence_length`

Source: `docs/metrics_reference.md:185`

### Output Sequence Length (OSL)
Total completion tokens (output + reasoning) generated for a request.

Formula: `output_token_count + reasoning_token_count`

Tag: `output_sequence_length`

Source: `docs/metrics_reference.md:166`

### Output Token Count
Number of visible output tokens (excluding reasoning tokens).

Tag: `output_token_count`

Source: `docs/metrics_reference.md:134`

### Reasoning Token Count
Number of reasoning tokens used for chain-of-thought reasoning (models like OpenAI o1).

Tag: `reasoning_token_count`

Source: `docs/metrics_reference.md:150`

### Request Throughput
Rate of completed requests per second across the entire benchmark.

Formula: `request_count / benchmark_duration_seconds`

Tag: `request_throughput`

Source: `docs/metrics_reference.md:282`

### Output Token Throughput
System-level token generation rate across all concurrent requests.

Formula: `total_output_sequence_length / benchmark_duration_seconds`

Tag: `output_token_throughput`

Source: `docs/metrics_reference.md:300`

### Output Token Throughput Per User
Token generation rate from an individual user's perspective (single-request streaming performance).

Formula: `1.0 / inter_token_latency_seconds`

Tag: `output_token_throughput_per_user`

Source: `docs/metrics_reference.md:323`

### Request Count
Total number of successfully completed requests.

Tag: `request_count`

Source: `docs/metrics_reference.md:349`

### Error Request Count
Total number of failed/error requests.

Tag: `error_request_count`

Source: `docs/metrics_reference.md:358`

### Benchmark Duration
Total elapsed time from first request to last response.

Formula: `max_response_timestamp - min_request_timestamp`

Tag: `benchmark_duration`

Source: `docs/metrics_reference.md:388`

---

## Results Processing

### Parsed Response Record
A processed inference result containing:
- Request metadata (timestamps, session ID, turn index)
- Response data (content, token counts, timestamps)
- Validity flag indicating success/failure
- Error details if applicable

Source: `aiperf/common/models/record_models.py`

### Metric Record
Per-request metric values computed by Record Processors. Stored as a dictionary mapping metric tags to values.

Source: `aiperf/metrics/metric_dicts.py`

### Metric Result
Aggregate or derived metric values, including:
- Single values for aggregate/derived metrics
- Statistical distributions (min, max, mean, percentiles) for record metrics

Source: `aiperf/common/models/record_models.py`

### Profile Results
The complete output of a benchmark run, including:
- All metric results
- Processing statistics
- Error summary
- Performance data for export

Source: `aiperf/common/models/`

### Results Processor
Component that processes collected records to generate final results. Types include:
- `MetricRecordProcessor` - Computes per-request metrics
- `MetricResultsProcessor` - Aggregates metrics and computes statistics

Source: `aiperf/post_processors/`

---

## Tokenization

### Tokenizer
A Hugging Face tokenizer used to count tokens in prompts and responses. Necessary for token-based metrics.

Source: `aiperf/common/tokenizer.py`

### Token
The basic unit of text processed by language models. Models typically measure performance in tokens per second.

### Input Tokens / Prompt Tokens
Tokens in the input prompt sent to the model.

### Output Tokens / Completion Tokens
Tokens generated by the model in response (excluding reasoning tokens).

### Reasoning Tokens
Tokens used for internal "thinking" or chain-of-thought reasoning before generating the final output. Only available for certain models (e.g., OpenAI o1).

---

## Configuration

### User Config (UserConfig)
Configuration parameters provided by the user via CLI or config files. Includes:
- Endpoint configuration (URL, model, endpoint type)
- Load generation settings (concurrency, request rate)
- Input/output parameters (ISL, OSL, dataset)
- Tokenizer settings
- Output options

Source: `aiperf/common/config/user_config.py`

### Service Config (ServiceConfig)
Internal configuration for service management:
- Service run type (process, k8s)
- Logging level
- UI type
- Record processor count
- Worker settings

Source: `aiperf/common/config/service_config.py`

### CLI Parameter
A command-line option accepted by the `aiperf profile` command. CLI parameters map to UserConfig fields.

Source: `aiperf/common/config/cli_parameter.py`

---

## Warmup & Phases

### Warmup Phase
An initial period where requests are sent but not measured. Used to ensure the inference server is warmed up and ready for profiling.

Configured via: `--warmup-request-count`

### Profiling Phase
The main measurement phase where all requests contribute to the final metrics and results.

### Phase Completion
The mechanism for detecting when a phase (warmup or profiling) has finished. Tracks credits issued, credits returned, and records processed.

Source: `aiperf/records/phase_completion.py`

---

## Advanced Features

### Fixed Schedule / Trace Replay
A benchmarking mode where requests are sent at exact predetermined timestamps, typically from a trace file. Used for deterministic workload replay.

Source: `docs/tutorials/trace-benchmarking.md`, `docs/benchmark_modes/trace_replay.md`

### Request Cancellation
A feature that cancels a percentage of in-flight requests to test timeout behavior and service resilience.

Configuration:
- `--request-cancellation-rate` - Percentage of requests to cancel (0-100)
- `--request-cancellation-delay` - Delay before cancelling (seconds)

Source: `docs/tutorials/request-cancellation.md`

### Benchmark Duration
A mode where profiling runs for a specified duration rather than a fixed request count.

Configuration:
- `--benchmark-duration` - Duration in seconds
- `--benchmark-grace-period` - Grace period for in-flight requests after duration ends

Source: `docs/tutorials/time-based-benchmarking.md`

### Grace Period
The time to wait for in-flight requests to complete after the benchmark duration ends. Responses received within the grace period are included in metrics.

### Multi-turn Conversations
Conversations with multiple turns (back-and-forth exchanges). Turns are executed sequentially with optional delays.

Configuration:
- `--conversation-turn-mean` - Average number of turns
- `--conversation-turn-delay-mean` - Average delay between turns (ms)

---

## User Interface

### UI Type
The type of user interface displayed during benchmarking:
- `DASHBOARD` - Rich textual UI with real-time metrics and worker status
- `SIMPLE` - Simple progress bar with basic statistics
- `NONE` - No UI, only log output

Configured via: `--ui-type`

Source: `aiperf/common/enums/ui_enums.py`

### Real-time Metrics
Live metric updates displayed in the UI during profiling. Updated at regular intervals (default: 5 seconds).

### Worker Status
Information about worker health, task statistics, and resource usage displayed in the dashboard UI.

---

## Output & Artifacts

### Artifact Directory
The directory where all output files are written. Default: `artifacts/`

Configured via: `--output-artifact-dir`

### Profile Export
JSON and CSV files containing the complete benchmark results and metrics.

Files:
- `profile_export_aiperf.json` - Complete results in JSON format
- `profile_export_aiperf.csv` - Tabular metrics in CSV format

### Inputs File (inputs.json)
A JSON file containing all the request payloads used during benchmarking. Enables reproducibility and debugging.

Path: `<artifact_dir>/inputs_aiperf.json`

Source: `aiperf/dataset/dataset_manager.py:136`

### Console Export
Human-readable metrics table displayed in the terminal after profiling completes.

Source: `aiperf/exporters/console_metrics_exporter.py`

### Exporter
Component that formats and outputs metrics in various formats:
- `ConsoleMetricsExporter` - Terminal table output
- `CSVExporter` - CSV file export
- `JSONExporter` - JSON file export

Source: `aiperf/exporters/`

---

## Error Handling

### Error Details
Information about a request failure, including:
- Error message
- Error type (HTTP error, timeout, connection error, etc.)
- Stack trace (if applicable)

Source: `aiperf/common/models/error_models.py`

### Error Summary
Aggregated count of errors by error type. Displayed after profiling completes.

### Timeout
A request that exceeds the configured timeout duration.

Configured via: `--request-timeout-seconds` (default: 600.0)

### Grace Period Timeout
A request that completes after the benchmark duration + grace period. These requests are excluded from metrics.

---

## System & Infrastructure

### Mixin
A class that provides reusable functionality to services through multiple inheritance. Examples:
- `PullClientMixin` - Adds ZMQ PULL client functionality
- `PushClientMixin` - Adds ZMQ PUSH client functionality
- `ReplyClientMixin` - Adds ZMQ REP client functionality
- `ProcessHealthMixin` - Adds process health monitoring

Source: `aiperf/common/mixins/`

### Hook
A decorator that registers a method to be called at specific lifecycle points or in response to messages/commands.

Examples:
- `@on_init` - Called during initialization
- `@on_start` - Called when starting
- `@on_stop` - Called when stopping
- `@on_command(CommandType.X)` - Called for specific command types
- `@on_message(MessageType.X)` - Called for specific message types
- `@background_task` - Runs as a background task

Source: `aiperf/common/hooks.py`

### Factory
A class that creates instances of components based on a type identifier. Uses the Factory pattern for extensibility.

Examples:
- `ServiceFactory` - Creates service instances
- `ComposerFactory` - Creates dataset composers
- `InferenceClientFactory` - Creates inference clients
- `MetricRegistry` - Registers and creates metrics

Source: `aiperf/common/factories.py`

### Protocol
A Python typing Protocol that defines an interface. Used for type checking and dependency injection.

Examples:
- `ServiceProtocol` - Interface for services
- `ServiceManagerProtocol` - Interface for service managers
- `AIPerfUIProtocol` - Interface for UI implementations

Source: `aiperf/common/protocols.py`

---

## Developer & Debugging

### Developer Mode (AIPERF_DEV_MODE)
An environment variable that enables additional debug features and warnings.

Set via: `export AIPERF_DEV_MODE=true`

Source: `aiperf/common/constants.py:60`

### Logging
Structured logging with multiple levels:
- `TRACE` - Most verbose, includes message details
- `DEBUG` - Development information
- `INFO` - General information (default)
- `WARNING` - Warning messages
- `ERROR` - Error messages
- `CRITICAL` - Critical failures

Configured via: `--log-level` or `-v` (DEBUG) or `-vv` (TRACE)

Source: `aiperf/common/logging.py`

### Service ID
A unique identifier for each service instance, typically formatted as `<ServiceType>-<UUID>`.

Example: `worker-a1b2c3d4-e5f6-7890-abcd-ef1234567890`

---

## Performance & Optimization

### Max Workers
Maximum number of worker processes to spawn. Auto-calculated based on CPU cores and concurrency, or explicitly set.

Configured via: `--workers-max`

Default formula: `min(concurrency, (num_CPUs * 0.75) - 1)` with a cap of 32

Source: `aiperf/common/config/worker_config.py`

### Record Processor Scale Factor
The ratio of workers to record processors. Default: 1 record processor per 4 workers.

Configured via: `--record-processor-service-count`

Source: `aiperf/common/constants.py:95`

### Connection Limit
Maximum number of concurrent HTTP connections per worker.

Environment variable: `AIPERF_HTTP_CONNECTION_LIMIT` (default: 2500)

Source: `aiperf/common/constants.py:106`

### Pull Client Max Concurrency
Maximum number of concurrent pulls from a ZMQ PULL socket. Controls backpressure.

Source: `aiperf/common/constants.py:27`

---

## Synthetic Data Generation

### Prompt Source
The source of prompt text for synthetic data:
- `SYNTHETIC` - Generated from Shakespeare text
- `FILE` - Loaded from a file
- `PAYLOAD` - Provided directly

Source: `aiperf/common/enums/dataset_enums.py:35`

### Prompt Generator
Component that generates synthetic text prompts of specified token lengths.

Source: `aiperf/dataset/generator/prompt.py`

### Audio Generator
Component that generates synthetic audio samples with configurable properties (length, format, sample rate, bit depth).

Source: `aiperf/dataset/generator/audio.py`

### Image Generator
Component that generates synthetic images with configurable dimensions and formats.

Source: `aiperf/dataset/generator/image.py`

---

## Mooncake Trace Format

### Mooncake Trace
A trace file format containing timestamped request information for trace replay benchmarking.

Format: JSONL file with fields:
- `timestamp` - Unix timestamp in seconds (float)
- `prompt` - Input text
- `num_output_tokens` (optional) - Expected output length

Source: `docs/benchmark_modes/trace_replay.md`

### Fixed Schedule Auto Offset
A flag that automatically offsets timestamps in a trace so the first timestamp is 0 and others are shifted accordingly.

Configured via: `--fixed-schedule-auto-offset`

### Fixed Schedule Start/End Offset
Timestamp boundaries (in milliseconds) for selecting a subset of a trace file to replay.

Configured via:
- `--fixed-schedule-start-offset`
- `--fixed-schedule-end-offset`

---

## Public Datasets

### ShareGPT
A public dataset of multi-turn conversations from ShareGPT, available from Hugging Face.

Usage: `--public-dataset sharegpt`

Source: `docs/benchmark_datasets.md`

### Public Dataset Loader
Component that downloads and loads public datasets from repositories.

Source: `aiperf/dataset/loader/`

---

## Additional Terms

### Inference Server
The AI model serving system being benchmarked (e.g., vLLM, Triton, TensorRT-LLM, NIM, etc.).

### Model Name
The identifier of the AI model being benchmarked. Passed to the inference server in requests.

Configured via: `--model-names` or `-m`

### Model Selection Strategy
When multiple models are specified, determines how models are assigned to prompts:
- `ROUND_ROBIN` - Cycle through models in order
- `RANDOM` - Random uniform selection

Configured via: `--model-selection-strategy`

Source: `aiperf/common/enums/model_enums.py`

### API Key
Authentication token sent with requests to the inference server.

Configured via: `--api-key`

### Extra Inputs
Additional key-value pairs included in every request payload.

Configured via: `--extra-inputs`

### Header
Custom HTTP headers to include with every request.

Configured via: `--header`

### Batch Size
Number of items (texts, images, audio) included in a single request. Supported for embeddings, rankings, and multi-modal endpoints.

Configured via:
- `--prompt-batch-size` - Text batch size
- `--audio-batch-size` - Audio batch size
- `--image-batch-size` - Image batch size

### Prefix Prompt
A prompt prepended to all requests, useful for testing KV cache performance.

Configured via:
- `--prompt-prefix-pool-size` - Number of prefix prompts to generate
- `--prompt-prefix-length` - Token length of each prefix

---

## Abbreviations

- **API** - Application Programming Interface
- **CLI** - Command Line Interface
- **CSV** - Comma-Separated Values
- **HTTP** - Hypertext Transfer Protocol
- **ICL** - Inter Chunk Latency
- **ISL** - Input Sequence Length
- **ITL** - Inter Token Latency
- **JSON** - JavaScript Object Notation
- **JSONL** - JSON Lines (newline-delimited JSON)
- **K8s** - Kubernetes
- **LLM** - Large Language Model
- **NIM** - NVIDIA Inference Microservices
- **OSL** - Output Sequence Length
- **QPS** - Queries Per Second (Request Rate)
- **SSE** - Server-Sent Events
- **TTFT** - Time to First Token
- **TTST** - Time to Second Token
- **UI** - User Interface
- **URL** - Uniform Resource Locator
- **UUID** - Universally Unique Identifier
- **ZMQ** - ZeroMQ

---

## Summary

This glossary provides comprehensive definitions of all major terms used in AIPerf. For more detailed technical information, see the Developer Guide. For high-level usage information, see the User Guide.

**Cross-References:**
- [Architecture Documentation](architecture.md)
- [Metrics Reference](metrics_reference.md)
- [CLI Options](cli_options.md)
- [Tutorial](tutorial.md)
