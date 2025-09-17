<!--
# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
-->
## Release Highlights:

The initial release of AIPerf, the successor to GenAI-Perf, created to deliver extensive benchmarking capabilities.
AIPerf is written entirely in Python offering an easy installation with a modular design for user extensibility.

## Major Features of AIPerf

### Comprehensive Benchmarking
  - Measures throughput, latency, and comprehensive token-level metrics for generative AI models
  - Supports both synthetic and dataset-driven input modes

### Scalable Load Generation
  - Multiprocess support for local scaling
  - High concurrency and request-rate modes with configurable patterns

### Trace Replay
  - Reproduce real-world or synthetic workload traces for validation and stress testing
  - Supports MoonCake trace format and custom JSONL datasets

### Flexible Model and Endpoint Support
  - Works with OpenAI-compatible APIs including vLLM, AI Dynamo, and other compatible services
  - Supports chat completions, completions, embeddings and rankings endpoints
  - Easily configurable for different model backends and custom endpoints

### Advanced Input and Output Configuration
  - Fine-grained control over input/output token counts and streaming
  - Pass extra inputs and custom payloads to endpoints

### Rich Reporting and Export
  - Console, CSV, and JSON output formats for results
  - Artifact directory support for saving logs and metrics

### Extensible and Modular Design
  - Easy to modify and extend for custom benchmarking scenarios
  - Plugin architecture for new components and metrics

### Automation and Integration
  - CLI-first workflow for scripting and automation
  - Compatible with containerized and cloud environments

### Security and Customization
  - Support for custom headers, authentication, and advanced API options
  - Random seed and reproducibility controls

### Console UI Options
  - Real-time metrics dashboard with live progress tracking and worker status monitoring
  - Simple UI mode for streamlined monitoring and headless mode for automated environments

## Key Improvements Over GenAI-Perf

AIPerf introduces several enhancements over GenAI-Perf:

### Performance & Scaling
- **Distributed Architecture**: Scalable service-oriented design built for horizontal scaling and distributed deployments
- **Python Multiprocessing**: Native multiprocessing implementation with automatic worker provisioning and lifecycle management, enabling true parallel load generation
- **Request-Rate with Max Concurrency**: Combine request-rate control with concurrency limits to throttle requests or provide controlled ramp-up to prevent burst traffic

### User Experience
- **Live Dashboard**: Interactive terminal-based UI with real-time metrics visualization, progress tracking, and worker status monitoring
- **Multiple UI Modes**: Dashboard mode for interactive use, simple mode for streamlined monitoring, and headless mode for automation

### Observability & Control
- **API Error Analytics**: Comprehensive tracking and categorization of request failures with detailed error summaries grouped by failure reason
- **Early Termination Support**: Cancel benchmarks mid-run while preserving all completed results and metrics

### Extensibility & Development
- **Pure Python Architecture**: Eliminates complex mixed-language dependencies for simpler installation, deployment, and customization
- **Plugin Framework**: Simple registration system for custom metrics, data exporters, dataset loaders, and API clients with extensive lifecycle hooks enabling advanced customization
- **ShareGPT Integration**: Automatic download, caching, and conversation processing of public datasets

## Installation
```bash
pip install aiperf
```

## Migration from GenAI-Perf

AIPerf is designed to be a drop-in replacement for GenAI-Perf for currently supported features. To migrate your existing GenAI-Perf commands, please refer to the [Migrating from GenAI-Perf](docs/migrating.md) documentation.


## Tutorials

Please refer to the [Tutorials](docs/tutorial.md) documentation for information on how to use AIPerf.

## Additional Information

### Known Issues
- When setting the OSL via the `--output-tokens-mean` option, if `--extra-inputs ignore_eos:true` is not set, AIPerf cannot guarantee a given OSL constraint.
- A couple of options in the documentation are inconsistent in their usage of an underscore instead of a hyphen.
