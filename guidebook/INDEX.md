<!--
# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
-->
# AIPerf Developer's Guidebook
## Complete Technical Reference and Development Guide

Version 1.0 | Last Updated: 2025-10-04

---

## About This Guide

This comprehensive guidebook provides complete technical documentation for AIPerf, NVIDIA's AI inference benchmarking tool. Each chapter covers specific aspects of the system in extreme detail, with architecture explanations, code examples, and best practices.

---

## Complete Chapter List

### Part I: Foundation (Chapters 1-5)

**[Chapter 1: Introduction and Overview](chapter-01-introduction.md)**
Introduction to AIPerf, design philosophy, use cases, and getting started guide.

**[Chapter 2: Installation and Setup](chapter-02-installation-setup.md)**
Complete installation instructions, environment setup, dependencies, and verification procedures.

**[Chapter 3: Quick Start Guide](chapter-03-quick-start.md)**
Hands-on tutorial for running your first benchmarks with detailed explanations.

**[Chapter 4: Core Concepts](chapter-04-core-concepts.md)**
Fundamental concepts including services, credits, phases, records, and metrics.

**[Chapter 5: Architecture Fundamentals](chapter-05-architecture-fundamentals.md)**
High-level architecture, service model, data flow, and communication patterns.

### Part II: Core Systems Deep Dive (Chapters 6-15)

**[Chapter 6: System Controller](chapter-06-system-controller.md)**
Central orchestrator architecture, service lifecycle management, and command handling.

**[Chapter 7: Workers Architecture](chapter-07-workers-architecture.md)**
Worker process design, credit processing, timing precision, and performance.

**[Chapter 8: Worker Manager](chapter-08-worker-manager.md)**
Worker orchestration, health monitoring, auto-scaling, and status tracking.

**[Chapter 9: Dataset Manager](chapter-09-dataset-manager.md)**
Dataset service architecture, data serving patterns, and request handling.

**[Chapter 10: Timing Manager](chapter-10-timing-manager.md)**
Credit issuance, timing strategies, phase management, and scheduling.

**[Chapter 11: Credit System](chapter-11-credit-system.md)**
Credit-based flow control, semaphore patterns, and rate limiting.

**[Chapter 12: Records Manager](chapter-12-records-manager.md)**
Results aggregation, phase completion, error tracking, and filtering.

**[Chapter 13: Record Processors](chapter-13-record-processors.md)**
Distributed metric computation, parsing pipeline, and aggregation.

**[Chapter 14: ZMQ Communication](chapter-14-zmq-communication.md)**
ZMQ architecture, socket patterns, proxies, and performance tuning.

**[Chapter 15: Message System](chapter-15-message-system.md)**
Message types, command pattern, serialization, and routing.

### Part III: Data and Metrics (Chapters 16-22)

**[Chapter 16: Dataset Types](chapter-16-dataset-types.md)**
Single turn, multi turn, trace, random pool, and synthetic datasets.

**[Chapter 17: Dataset Loaders](chapter-17-dataset-loaders.md)**
Loader architecture, file formats, validation, and error handling.

**[Chapter 18: Dataset Composers](chapter-18-dataset-composers.md)**
Composer pattern, data transformation, and pipeline orchestration.

**[Chapter 19: Data Generators](chapter-19-data-generators.md)**
Prompt, image, and audio generation with caching strategies.

**[Chapter 20: Metrics Foundation](chapter-20-metrics-foundation.md)**
Metrics architecture, type hierarchy, and registry system.

**[Chapter 21: Record Metrics](chapter-21-record-metrics.md)**
Per-request metrics, computation patterns, and statistical analysis.

**[Chapter 22: Aggregate and Derived Metrics](chapter-22-aggregate-derived-metrics.md)**
Aggregation strategies, derived computation, and dependencies.

### Part IV: Communication and Clients (Chapters 23-28)

**[Chapter 23: HTTP Client Architecture](chapter-23-http-client-architecture.md)**
AioHttpClientMixin design, connection pooling, and timing precision.

**[Chapter 24: OpenAI Client](chapter-24-openai-client.md)**
OpenAI integration, endpoint types, and authentication.

**[Chapter 25: SSE Stream Handling](chapter-25-sse-stream-handling.md)**
Server-Sent Events parsing, first-byte timing, and error handling.

**[Chapter 26: TCP Optimizations](chapter-26-tcp-optimizations.md)**
Socket tuning, TCP options, buffer sizing, and keepalive.

**[Chapter 27: Request Converters](chapter-27-request-converters.md)**
Payload formatting, multimodal support, and endpoint adapters.

**[Chapter 28: Response Parsers](chapter-28-response-parsers.md)**
Response parsing, tokenization, and data extraction.

### Part V: Configuration (Chapters 29-33)

**[Chapter 29: Configuration Architecture](chapter-29-configuration-architecture.md)**
Configuration system design, Pydantic integration, and hierarchy.

**[Chapter 30: UserConfig Deep Dive](chapter-30-userconfig-deep-dive.md)**
Complete UserConfig reference with all nested configurations.

**[Chapter 31: ServiceConfig Deep Dive](chapter-31-serviceconfig-deep-dive.md)**
Runtime configuration, environment variables, and service parameters.

**[Chapter 32: CLI Integration](chapter-32-cli-integration.md)**
Cyclopts integration, parameter mapping, and command structure.

**[Chapter 33: Validation System](chapter-33-validation-system.md)**
Field validation, model validators, custom validators, and error handling.

### Part VI: UI and Output (Chapters 34-37)

**[Chapter 34: UI Architecture](chapter-34-ui-architecture.md)**
UI abstraction, protocol design, and mode selection.

**[Chapter 35: Dashboard Implementation](chapter-35-dashboard-implementation.md)**
Textual-based dashboard, widgets, real-time updates, and interaction.

**[Chapter 36: Exporters System](chapter-36-exporters-system.md)**
Export architecture, console formatting, CSV and JSON export.

**[Chapter 37: Log Management](chapter-37-log-management.md)**
Logging architecture, log routing, queue handling, and formatting.

### Part VII: Development (Chapters 38-43)

**[Chapter 38: Development Environment](chapter-38-development-environment.md)**
IDE setup, debugging tools, profilers, and workflow optimization.

**[Chapter 39: Code Style Guide](chapter-39-code-style-guide.md)**
Coding conventions, naming standards, documentation, and formatting.

**[Chapter 40: Testing Strategies](chapter-40-testing-strategies.md)**
Unit testing, integration testing, mocking, fixtures, and coverage.

**[Chapter 41: Debugging Techniques](chapter-41-debugging-techniques.md)**
Debugging strategies, tools, common issues, and solutions.

**[Chapter 42: Performance Profiling](chapter-42-performance-profiling.md)**
Profiling tools, performance analysis, optimization strategies.

**[Chapter 43: Common Patterns](chapter-43-common-patterns.md)**
Design patterns, idioms, best practices, and reusable solutions.

### Part VIII: Advanced Topics (Chapters 44-48)

**[Chapter 44: Custom Metrics Development](chapter-44-custom-metrics-development.md)**
Creating custom metrics, registration, testing, and deployment.

**[Chapter 45: Custom Dataset Development](chapter-45-custom-dataset-development.md)**
Custom loaders, composers, validation, and integration.

**[Chapter 46: Custom Endpoints](chapter-46-custom-endpoints.md)**
Supporting new endpoint types, parsers, and converters.

**[Chapter 47: Extending AIPerf](chapter-47-extending-aiperf.md)**
Extension points, plugin architecture, and integration patterns.

**[Chapter 48: Plugin Architecture](chapter-48-plugin-architecture.md)**
Plugin system design, loading, registration, and lifecycle.

### Part IX: Operations and Reference (Chapters 49-50)

**[Chapter 49: Deployment Guide](chapter-49-deployment-guide.md)**
Deployment patterns, Docker, Kubernetes, monitoring, and operations.

**[Chapter 50: Troubleshooting Guide](chapter-50-troubleshooting-guide.md)**
Common problems, diagnostic procedures, solutions, and prevention.

---

## Reading Paths

### Beginner Path
Chapters 1 → 2 → 3 → 4 → 5 → 38 → 39 → 40

### Architecture Path
Chapters 5 → 6 → 7 → 9 → 10 → 12 → 14 → 15

### Development Path
Chapters 38 → 39 → 40 → 41 → 42 → 43

### Metrics Path
Chapters 20 → 21 → 22 → 44

### Configuration Path
Chapters 29 → 30 → 31 → 32 → 33

### Advanced Path
Chapters 44 → 45 → 46 → 47 → 48

---

## Navigation

- Each chapter begins with an overview and objectives
- Each chapter ends with key takeaways and link to next chapter
- Cross-references link to related chapters
- Code examples are provided throughout
- All examples are in the /examples directory

---

## Document Conventions

**File Paths**: Absolute paths from project root
**Code Blocks**: Language-specific syntax highlighting
**Cross-References**: [Chapter X: Title](filename.md)
**Important Notes**: Callout blocks for critical information
**Examples**: Runnable code with expected output

---

## Contributing

This guidebook is maintained alongside the AIPerf codebase. Contributions welcome via pull requests.

---

## License

Apache 2.0 License - See LICENSE file for details

---

**Start Reading: [Chapter 1: Introduction and Overview](chapter-01-introduction.md)**
