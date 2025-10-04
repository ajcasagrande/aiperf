# AIPerf ReadMe

This document outlines the high-level design and detailed evaluation for implementing AIPerf—a modular, high-throughput benchmarking tool designed to drive load for large-scale inference infrastructure such as Dynamo. The design emphasizes developer experience and throughput, ensuring that architectural and infrastructure decisions (including coding standards, testing, logging, and design patterns) remain a top priority.

---

## Table of Contents

- [AIPerf ReadMe](#aiperf-readme)
  - [Table of Contents](#table-of-contents)
  - [Overview](#overview)
  - [Goals & Non-Goals](#goals--non-goals)
    - [Goals](#goals)
    - [Non-Goals](#non-goals)
  - [Requirements](#requirements)
  - [High-Level Architecture](#high-level-architecture)
  - [Implementation Details](#implementation-details)
    - [System Sequence](#system-sequence)
    - [Detailed Component Evaluations](#detailed-component-evaluations)
  - [Developer Considerations](#developer-considerations)
  - [Next Steps](#next-steps)

---

## Overview

AIPerf is intended as a single, unified benchmarking solution that meets the needs of various teams working on inference servers. The project aims to consolidate previously fragmented tools (GenAI-Perf and PCA loadgen) into a more modular and maintainable platform that scales at the datacenter level.

---

## Goals & Non-Goals

### Goals
- **Datacenter Scalability:** Support for load testing at deployment scales.
- **Modular Architecture:** Clear separation of concerns allows for customization and independent updates.
- **Flexible API Support:** Easily integrate additional APIs with minimal code changes.
- **Comprehensive Metrics:** Out-of-the-box support for detailed performance metrics.
- **Developer Focus:** Emphasis on ease of code modification, robust testing, and detailed debugging.

### Non-Goals
- Real-time monitoring features.
- Generic orchestration for Dynamo (focus is solely on performance measurement).

---

## Requirements

AIPerf is designed around several core requirements, such as:
- **REQ 1:** Support for Dynamo use cases.
- **REQ 2:** Handling both single and multi-turn conversations.
- **REQ 3:** Extensive in-code and generated documentation.
- **REQ 4:** Seamless integration of new datasets.
- **REQ 5:** Out-of-the-box support for multiple modalities.
- **REQ 6:** Dual HTTP and gRPC interfaces.
- **REQ 7:** Synthetic data generation.
- **REQ 8:** Multiple endpoint support using different distribution strategies.
- **REQ 9:** Extensible custom API support.
- **REQ 10:** Comprehensive out-of-the-box metric collection.
- **REQ 11:** Extensibility for custom metric definitions.
- **REQ 12:** Robust debugging and logging tools.
- **REQ 13:** Thorough testing with automated CI integration.
- **REQ 14:** Basic system visibility for resource usage.
- **REQ 15-21:** Additional features including dataset and timing management, deterministic behavior, progress profiling, raw token support, beam search load generation, and server-side metric collection.

---

## High-Level Architecture

The architecture of AIPerf is built upon a series of interconnected components:

- **System Controller:** Orchestrates the entire system, ensuring that all components are ready, healthy, and coordinated.
- **Dataset Manager:** Handles data acquisition and synthetic data generation.
- **Timing Manager:** Creates and issues timing credits for request scheduling.
- **Worker Manager:** Manages workers that translate credits and data into actual requests.
- **Worker:** Formats requests according to the chosen interface and manages multi-turn conversations.
- **Records Manager:** Stores results from benchmarking operations.
- **Post Processors:** Analyzes records to generate detailed performance reports and custom metrics.

---

## Implementation Details

### System Sequence

1. **Bringup Phase:**
    - Components (System Controller, Dataset Manager, Timing Manager, Worker Manager, Records Manager, and Post Processors) start and publish their presence to a central publishing socket.
    - A "ready" check is performed; if all components respond, the system transitions to the READY state.
    - A timeout and retry mechanism ensures that if any component fails to respond, the system gracefully shuts down with an error.

2. **Profile Execution:**
    - A configuration is provided by the user, which the System Controller disburses to all components.
    - The Timing Manager generates a schedule based on the profile.
    - The Dataset Manager collects or generates the necessary dataset.
    - The Worker Manager starts and assigns workers based on available credits.
    - Workers convert data into required formats and issue requests.
    - Conversation results are aggregated in the Records Manager.
    - Post Processors generate performance metrics and reports.

3. **Shutdown Phase:**
    - The System Controller initiates shutdown by sending commands over a dedicated control channel.
    - Each component performs a graceful shutdown and confirms its successful termination.

### Detailed Component Evaluations

- **System Controller:**  
  *Implementation Tip:* Use an event-driven or asynchronous approach to monitor readiness and coordinate commands.  
  *Evaluation:* Ensure robust handling of late or missing component initialization.

- **Dataset Manager:**  
  *Implementation Tip:* Leverage modular code to support both synthetic and real data; consider extending an interface for external dataset plugins.  
  *Evaluation:* Maintain a clear separation between data acquisition and preprocessing to facilitate future dataset integrations.

- **Timing Manager:**  
  *Implementation Tip:* Apply stateful design to generate timing credits; incorporate well-known distributions (Poisson, normal, uniform) for accurate scheduling.  
  *Evaluation:* Test timing intervals extensively to minimize jitter and ensure deterministic behavior where possible.

- **Worker Manager & Worker:**  
  *Implementation Tip:* Implement a dynamic scaling mechanism (hysteresis-based) to adjust the number of active workers based on the load.  
  *Evaluation:* Optimize request processing to isolate measurement overhead from actual server performance.

- **Records Manager & Post Processors:**  
  *Implementation Tip:* Use a database or in-memory store for aggregating records; design post processors as plug-in modules to add or update metric calculations with minimal disruption.  
  *Evaluation:* Ensure that the aggregation and processing pipeline can handle high data volumes without affecting live performance measurements.

---

## Developer Considerations

- **Coding Standards & Modularity:**  
  Structure the codebase to enforce low cyclomatic complexity, and integrate static analysis and linting tools into CI/CD pipelines.
  
- **Testing:**  
  Develop a comprehensive testing matrix covering unit tests, integration tests, performance benchmarks, and documentation generation. Automate test coverage reports.
  
- **Debuggability:**  
  Integrate robust logging mechanisms (with adjustable verbosity) and include features such as curl command generation for error replication.
  
- **Documentation:**  
  Treat documentation as a living document, using tools (e.g., pydoc) that auto-generate docs from inline docstrings. Maintain extensive tutorials and usage examples.

---

## Next Steps

1. **Define and Scaffold Components:**  
    Create minimal viable implementations of the System Controller, Dataset Manager, Timing Manager, and Worker Manager.
    
2. **Integration and CI/CD Pipeline:**  
    Integrate coding standards, comprehensive testing, and automated documentation generation into the development workflow.
    
3. **MVP Specification:**  
    Outline a phased MVP that can be delivered in iterations, starting with the core orchestration and basic load generation, then gradually integrate advanced features like custom metrics and multi-turn conversation support.

4. **Performance & Scalability Tests:**  
    Plan for extensive performance testing to ensure that the tool does not introduce overhead that could be mistaken as performance issues on the target inference server.

---

This document serves as both an architectural blueprint and a guideline for developers. Each component’s detailed implementation evaluation is intended to ensure that engineering effort is aligned with the dual objectives of maintaining developer experience while achieving high throughput. Further iterations and feedback cycles will refine the tool’s design as research and testing reveal new insights.