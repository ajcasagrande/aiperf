# Chapter 1: Introduction and Overview

<!--
SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
SPDX-License-Identifier: Apache-2.0
-->

## Table of Contents
- [What is AIPerf?](#what-is-aiperf)
- [Why AIPerf Exists](#why-aiperf-exists)
- [Design Philosophy and Principles](#design-philosophy-and-principles)
- [Use Cases and Scenarios](#use-cases-and-scenarios)
- [Who Should Use AIPerf](#who-should-use-aiperf)
- [Key Features and Capabilities](#key-features-and-capabilities)
- [Comparison with Other Tools](#comparison-with-other-tools)
- [Getting Oriented in the Codebase](#getting-oriented-in-the-codebase)
- [Key Takeaways](#key-takeaways)

## What is AIPerf?

AIPerf is a comprehensive, production-grade benchmarking framework specifically designed for evaluating the performance of generative AI models and their inference serving solutions. Developed by NVIDIA, AIPerf provides a robust, scalable, and extensible platform for measuring critical performance metrics of AI inference endpoints.

At its core, AIPerf is a distributed system built on modern Python async/await patterns, leveraging ZeroMQ for inter-process communication and multiprocessing for horizontal scalability. The framework orchestrates multiple worker processes that generate load against target inference endpoints while precisely measuring latency, throughput, and other critical performance indicators.

AIPerf is not just a simple load testing tool - it's a sophisticated benchmarking framework that understands the unique characteristics of generative AI workloads, including streaming responses, token-by-token generation, multi-turn conversations, and the nuanced timing requirements of LLM inference.

## Why AIPerf Exists

The landscape of AI inference serving has evolved rapidly, with numerous solutions emerging including vLLM, TensorRT-LLM, Triton Inference Server, and proprietary offerings. Each solution makes performance claims, but comparing them objectively has been challenging due to:

1. **Lack of Standardized Benchmarking**: Different tools use different methodologies, making apples-to-apples comparisons difficult.

2. **Complexity of AI Workloads**: Generative AI models have unique characteristics like streaming outputs, variable response lengths, and multi-turn conversations that traditional HTTP load testing tools don't handle well.

3. **Precision Timing Requirements**: Measuring time-to-first-token (TTFT), inter-token latency (ITL), and other LLM-specific metrics requires specialized instrumentation.

4. **Scalability Challenges**: Testing at realistic concurrency levels (hundreds or thousands of concurrent users) requires efficient multiprocessing and resource management.

5. **Reproducibility**: Research and production teams need reproducible benchmarks for regression testing, A/B testing, and capacity planning.

AIPerf was created to solve these problems by providing:
- A standardized, open-source benchmarking framework
- Deep understanding of LLM inference patterns
- Precise, microsecond-level timing measurements
- Scalable multiprocess architecture
- Reproducible, traceable results

## Design Philosophy and Principles

AIPerf's architecture and implementation are guided by several core principles:

### 1. Modularity and Extensibility
Every major component is designed as an independent service with well-defined interfaces. This allows users to:
- Extend or replace components without affecting the rest of the system
- Add support for new endpoint types
- Implement custom metrics and exporters
- Integrate with existing infrastructure

### 2. Precision Over Convenience
AIPerf prioritizes measurement accuracy:
- Uses `time.perf_counter_ns()` for nanosecond-precision timing
- Minimizes overhead in measurement paths
- Distinguishes between system time and monotonic time
- Tracks credit drop latency to account for scheduling overhead

### 3. Scalability Through Multiprocessing
Rather than trying to squeeze maximum performance from a single process:
- Uses true multiprocessing (not just asyncio)
- Distributes work across multiple CPU cores
- Scales worker count based on available resources
- Handles thousands of concurrent requests efficiently

### 4. Explicit State Management
- All services have clearly defined lifecycle states
- Phase-based execution (warmup, profiling)
- Credit-based flow control prevents resource exhaustion
- Graceful shutdown and error handling

### 5. Observability
- Comprehensive logging at multiple levels
- Real-time progress tracking
- Detailed error reporting with context
- Health monitoring for all services

### 6. Reproducibility
- Deterministic random seeding
- Trace replay capabilities
- Fixed schedule support
- Complete configuration capture

## Use Cases and Scenarios

AIPerf is designed to support a wide range of benchmarking scenarios:

### Performance Characterization
Understand how your inference endpoint performs under various conditions:
- Measure baseline latency and throughput
- Identify performance bottlenecks
- Characterize behavior under load
- Test scaling characteristics

### Regression Testing
Ensure performance doesn't degrade over time:
- Automated benchmarking in CI/CD pipelines
- Compare performance across code versions
- Detect performance regressions early
- Track performance trends

### Capacity Planning
Determine infrastructure requirements:
- Test maximum sustainable load
- Measure resource utilization
- Identify breaking points
- Plan for traffic growth

### A/B Testing
Compare different configurations or implementations:
- Test different model quantizations
- Compare inference backends
- Evaluate optimization techniques
- Validate hardware choices

### SLA Validation
Verify service level agreements:
- Test timeout behavior
- Measure P99 latencies
- Validate throughput guarantees
- Test under realistic traffic patterns

### Research and Development
Support AI systems research:
- Benchmark new serving techniques
- Evaluate scheduling algorithms
- Test memory management strategies
- Compare architectural choices

### Production Readiness
Validate systems before deployment:
- Stress testing
- Sustained load testing
- Failure scenario testing
- Recovery testing

## Who Should Use AIPerf

AIPerf is designed for several key audiences:

### ML Engineers and Researchers
- Benchmark model performance
- Compare inference solutions
- Optimize serving configurations
- Publish reproducible results

### Platform Engineers
- Validate infrastructure
- Perform capacity planning
- Test auto-scaling behavior
- Monitor production readiness

### DevOps and SRE Teams
- Integrate into CI/CD pipelines
- Monitor performance trends
- Validate SLAs
- Troubleshoot performance issues

### Product Teams
- Understand user experience implications
- Validate latency requirements
- Test at scale
- Plan for growth

### Enterprise IT
- Evaluate vendor solutions
- Compare deployment options
- Validate performance claims
- Plan infrastructure investments

## Key Features and Capabilities

### Comprehensive Metrics
AIPerf measures everything that matters for LLM inference:
- **Latency Metrics**: Request latency, time-to-first-token, time-to-second-token, inter-token latency
- **Throughput Metrics**: Requests per second, tokens per second (both input and output)
- **Sequence Metrics**: Input/output sequence lengths, token counts
- **Quality Metrics**: Error rates, cancellation rates, timeout rates
- **Goodput Metrics**: Successful requests within SLA thresholds

All metrics support statistical analysis with min, max, mean, median, percentiles (P75, P90, P99), and standard deviation.

### Flexible Load Generation
Multiple modes to match your testing needs:
- **Concurrency Mode**: Maintain fixed concurrent requests
- **Request Rate Mode**: Target specific requests per second
- **Request Rate with Max Concurrency**: Combine both approaches
- **Trace Replay**: Replay captured production traffic
- **Fixed Schedule**: Execute requests at precise timestamps

### Dataset Support
Multiple data sources for realistic testing:
- **Synthetic Generation**: Generate random prompts with controlled characteristics
- **Public Datasets**: Built-in support for ShareGPT and other formats
- **Custom Datasets**: JSONL, CSV, and custom formats
- **Trace Files**: Replay MoonCake and other trace formats
- **Multi-turn Conversations**: Test conversational workflows

### Endpoint Support
Comprehensive API compatibility:
- OpenAI Chat Completions
- OpenAI Completions
- OpenAI Embeddings
- OpenAI Audio APIs
- OpenAI Images APIs
- NIM Rankings APIs
- Custom endpoint support through extensibility

### Advanced Features
- **Request Cancellation**: Test timeout behavior and service resilience
- **Streaming Support**: Full SSE (Server-Sent Events) support for streaming responses
- **Multi-turn Conversations**: Maintain conversation context across turns
- **Token Counting**: Precise token counting with HuggingFace tokenizers
- **Custom Headers**: Support for tracing headers (X-Request-ID, X-Correlation-ID)
- **Warmup Phases**: Separate warmup from profiling
- **Time-based Benchmarking**: Run for specific durations with grace periods

### Output and Reporting
- **Rich Terminal UI**: Real-time progress dashboard
- **Console Tables**: Formatted metric tables
- **CSV Export**: Machine-readable results
- **JSON Export**: Complete data export
- **Inputs File**: Reproducible request payloads
- **Comprehensive Logging**: Detailed operation logs

### Scalability
- **Multiprocess Architecture**: Leverage all CPU cores
- **Auto-scaling Workers**: Automatic worker process management
- **Connection Pooling**: Efficient HTTP connection reuse
- **Resource Monitoring**: Track CPU, memory, and I/O
- **Health Checking**: Monitor worker health and status

## Comparison with Other Tools

### vs. Apache Bench / wrk / hey
Traditional HTTP benchmarking tools lack LLM-specific features:
- No streaming response support
- No token-level timing
- No multi-turn conversation support
- Limited metric collection
- No LLM-aware dataset generation

AIPerf provides all of these plus native understanding of OpenAI API formats.

### vs. Locust / JMeter
General-purpose load testing tools are flexible but require significant customization:
- Complex scripting for LLM workloads
- Manual metric instrumentation
- Less precise timing
- No built-in LLM metrics
- More operational overhead

AIPerf is purpose-built for LLM inference with batteries included.

### vs. GenAI-Perf (Predecessor)
AIPerf is the evolution of GenAI-Perf with significant improvements:
- **Architecture**: Complete rewrite with modular service architecture
- **Scalability**: True multiprocessing vs. single-process asyncio
- **Extensibility**: Plugin system for metrics, exporters, and endpoints
- **Observability**: Better logging, health monitoring, and progress tracking
- **Features**: Request cancellation, fixed schedules, goodput metrics
- **Stability**: More robust error handling and recovery

### vs. OpenAI's Loadgen
While OpenAI provides internal tools, they're not generally available:
- AIPerf is open-source and community-supported
- Works with any OpenAI-compatible endpoint
- More extensive metric collection
- Better documentation and examples

### vs. vLLM Benchmarking Tools
Framework-specific tools are optimized for one backend:
- AIPerf is backend-agnostic
- Enables fair comparisons across solutions
- More comprehensive metrics
- Better suited for production validation

## Getting Oriented in the Codebase

Understanding AIPerf's codebase structure will help you navigate, extend, and troubleshoot the system.

### Repository Structure

```
/home/anthony/nvidia/projects/aiperf/
├── aiperf/                          # Main package directory
│   ├── cli.py                       # CLI entry point
│   ├── cli_runner.py                # CLI execution logic
│   ├── clients/                     # HTTP clients and endpoint implementations
│   │   ├── http/                    # Core HTTP client (aiohttp-based)
│   │   └── openai/                  # OpenAI-specific client implementations
│   ├── common/                      # Shared infrastructure
│   │   ├── config/                  # Configuration management
│   │   ├── enums/                   # Type-safe enumerations
│   │   ├── messages/                # Message definitions for IPC
│   │   ├── mixins/                  # Reusable behavior mixins
│   │   ├── models/                  # Pydantic data models
│   │   ├── base_service.py          # Base class for all services
│   │   ├── factories.py             # Factory pattern implementations
│   │   ├── hooks.py                 # Decorator-based lifecycle hooks
│   │   └── protocols.py             # Type protocols for duck typing
│   ├── controller/                  # System orchestration
│   │   └── system_controller.py     # Main controller service
│   ├── dataset/                     # Dataset management
│   │   ├── composer/                # Dataset composition
│   │   ├── generator/               # Synthetic data generation
│   │   └── dataset_manager.py       # Dataset service
│   ├── exporters/                   # Result exporters
│   ├── metrics/                     # Metric definitions and computation
│   │   └── types/                   # Individual metric implementations
│   ├── records/                     # Record processing
│   │   ├── record_processor_service.py  # Record processing service
│   │   └── records_manager.py       # Record aggregation service
│   ├── timing/                      # Timing and scheduling
│   │   ├── credit_issuing_strategy.py   # Base credit issuing
│   │   ├── request_rate_strategy.py     # Request rate implementation
│   │   ├── fixed_schedule_strategy.py   # Fixed schedule implementation
│   │   └── timing_manager.py        # Timing service
│   ├── ui/                          # User interface
│   ├── workers/                     # Worker processes
│   │   ├── worker.py                # Worker implementation
│   │   └── worker_manager.py        # Worker lifecycle management
│   └── zmq/                         # ZeroMQ communication layer
├── tests/                           # Test suite
├── docs/                            # Documentation
├── examples/                        # Example configurations
└── integration-tests/               # Integration tests
```

### Key Concepts in the Code

#### Services
All major components inherit from `BaseService` or `BaseComponentService`:
- Located in `/home/anthony/nvidia/projects/aiperf/aiperf/common/base_service.py`
- Provides lifecycle management (initialize, start, stop)
- Handles message bus communication
- Implements health monitoring
- Uses decorator-based hooks for clean event handling

#### Messages
Inter-process communication uses strongly-typed message classes:
- Located in `/home/anthony/nvidia/projects/aiperf/aiperf/common/messages/`
- All inherit from `BaseMessage`
- Three categories: Commands, Messages, and Responses
- Serialized with Pydantic for type safety

#### Factories
The factory pattern enables extensibility:
- Located in `/home/anthony/nvidia/projects/aiperf/aiperf/common/factories.py`
- `ServiceFactory`: Creates service instances by type
- `InferenceClientFactory`: Creates endpoint-specific clients
- `ComposerFactory`: Creates dataset composers
- `ResultsProcessorFactory`: Creates result processors

#### Hooks
Lifecycle hooks provide clean event handling:
- Located in `/home/anthony/nvidia/projects/aiperf/aiperf/common/hooks.py`
- `@on_init`: Called during initialization
- `@on_start`: Called when starting
- `@on_stop`: Called during shutdown
- `@on_command`: Handle specific command types
- `@on_message`: Handle specific message types
- `@background_task`: Define recurring background tasks

### Finding Your Way Around

#### To Understand Core Architecture
Start with these files:
1. `/home/anthony/nvidia/projects/aiperf/aiperf/controller/system_controller.py` - System orchestration
2. `/home/anthony/nvidia/projects/aiperf/aiperf/common/base_service.py` - Service foundation
3. `/home/anthony/nvidia/projects/aiperf/docs/architecture.md` - Architecture overview

#### To Add a New Endpoint Type
Key files to modify:
1. `/home/anthony/nvidia/projects/aiperf/aiperf/clients/` - Add client implementation
2. `/home/anthony/nvidia/projects/aiperf/aiperf/common/factories.py` - Register with factory
3. `/home/anthony/nvidia/projects/aiperf/aiperf/common/enums/` - Add endpoint enum

#### To Add a New Metric
Key locations:
1. `/home/anthony/nvidia/projects/aiperf/aiperf/metrics/types/` - Create metric class
2. `/home/anthony/nvidia/projects/aiperf/aiperf/metrics/metric_registry.py` - Register metric
3. `/home/anthony/nvidia/projects/aiperf/aiperf/metrics/base_metric.py` - Base classes

#### To Modify Load Generation
Key files:
1. `/home/anthony/nvidia/projects/aiperf/aiperf/timing/timing_manager.py` - Main timing logic
2. `/home/anthony/nvidia/projects/aiperf/aiperf/timing/credit_issuing_strategy.py` - Strategy base
3. `/home/anthony/nvidia/projects/aiperf/aiperf/timing/request_rate_strategy.py` - Request rate mode

#### To Change Worker Behavior
Key files:
1. `/home/anthony/nvidia/projects/aiperf/aiperf/workers/worker.py` - Worker implementation
2. `/home/anthony/nvidia/projects/aiperf/aiperf/workers/worker_manager.py` - Worker lifecycle

### Development Guidelines

When working with the codebase:

1. **Follow the Service Pattern**: New major components should inherit from `BaseService` and use the lifecycle hooks system.

2. **Use Factories**: Register new implementations with the appropriate factory rather than hardcoding dependencies.

3. **Type Everything**: Use Pydantic models for data, Protocols for interfaces, and type hints everywhere.

4. **Test Your Changes**: Add unit tests in `tests/` and integration tests in `integration-tests/`.

5. **Follow Async Conventions**: Use `async`/`await` properly, avoid blocking calls, use `execute_async()` for fire-and-forget tasks.

6. **Add Logging**: Use the logger methods (`debug`, `info`, `warning`, `error`) with appropriate levels and lambda expressions for expensive string formatting.

7. **Handle Errors Gracefully**: Use the lifecycle's error handling mechanisms, never let exceptions escape service boundaries unhandled.

8. **Document Your Code**: Add docstrings to classes and methods, update relevant documentation files.

## Key Takeaways

1. **AIPerf is a Production-Grade Framework**: Not just a simple script, it's a fully-featured, distributed benchmarking system designed for serious performance evaluation.

2. **Purpose-Built for LLM Inference**: Unlike general HTTP load testers, AIPerf understands streaming responses, token-level timing, and conversational patterns.

3. **Scalable and Extensible**: The multiprocess architecture and modular design support both large-scale benchmarking and custom extensions.

4. **Measurement Precision Matters**: Nanosecond-level timing, careful overhead accounting, and LLM-specific metrics provide accurate, actionable data.

5. **Comprehensive Feature Set**: From basic throughput testing to complex trace replay, AIPerf covers a wide range of benchmarking scenarios.

6. **Open and Standardized**: As an open-source tool with reproducible results, AIPerf enables fair comparisons and community collaboration.

7. **Well-Architected Codebase**: The service-based architecture, factory pattern, and hook system create a maintainable and extensible foundation.

8. **Production-Ready**: With features like health monitoring, graceful shutdown, comprehensive error handling, and extensive logging, AIPerf is ready for production use.

Understanding these fundamentals will help you make the most of AIPerf, whether you're running simple benchmarks or extending the framework for custom use cases. The following chapters will dive deep into installation, usage, and the internal architecture that makes all of this possible.

---

Next: [Chapter 2: Installation and Setup](chapter-02-installation-setup.md)
