<!--
# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
-->
## Release Highlights:

The initial release of AIPerf, the successor to GenAI-Perf, created to deliver extensive benchmarking capabilities.
AIPerf is written entirely in Python offering an easy installation with a modular design for user extensibility.

## Major Features of AIPerf

### Comprehensive Benchmarking
- **Detailed Performance Metrics**: Measures throughput, latency, and comprehensive token-level metrics for generative AI models
- **Flexible Data Sources**: Supports both synthetic and dataset-driven input modes

### Scalable Load Generation
- **Parallel Processing**: Multiprocess support for local scaling
- **Configurable Load Patterns**: High concurrency and request-rate modes with configurable patterns

### Trace Replay
- **Production Workload Simulation**: Reproduce real-world or synthetic workload traces for validation and stress testing
- **Industry Standard Formats**: Supports Mooncake trace format and custom JSONL datasets when using the `--fixed-schedule` option.

### Flexible Model and Endpoint Support
- **Universal Compatibility**: Works with OpenAI-compatible APIs including vLLM, Dynamo, and other compatible services
- **OpenAI APIs**: Chat completions, completions, and embeddings supported.

### Advanced Input and Output Configuration
- **Granular Token Control**: Fine-grained control over input/output token counts and streaming
- **Extended Request Support**: Pass extra inputs and custom payloads to endpoints

### Rich Reporting and Export
- **Multiple Export Options**: Console, CSV, and JSON output formats for results
- **Artifact Management**: Artifact directory support for saving logs and metrics

### Automation and Integration
- **CLI-First Design**: CLI-first workflow for scripting and automation
- **Deployment Flexibility**: Compatible with containerized and cloud environments

### Security and Customization
- **Security and Authentication**: Support for custom headers, authentication, and advanced API options
- **Deterministic Testing**: Random seed and reproducibility controls

### Console UI Options
- **Real-Time Monitoring**: Real-time metrics dashboard with live progress tracking and worker status monitoring
- **Multiple UI Modes**: Simple UI mode for streamlined monitoring and headless mode for automated environments

## Key Improvements Over GenAI-Perf

AIPerf introduces several enhancements over GenAI-Perf:

### Performance & Scaling
- **Distributed Architecture**: Scalable service-oriented design built for horizontal scalability
- **Python Multiprocessing**: Native multiprocessing implementation with automatic worker provisioning and lifecycle management, enabling true parallel load generation from a single node.
- **Request-Rate with Max Concurrency**: Combine request-rate control with concurrency limits to throttle requests or provide controlled ramp-up to prevent burst traffic

### User Experience
- **Live Dashboard**: Interactive terminal-based UI with real-time metrics visualization, progress tracking, and worker status monitoring
- **Multiple UI Modes**: Dashboard mode for interactive use, simple mode for streamlined monitoring, and headless mode for automation

### Observability & Control
- **API Error Analytics**: Comprehensive tracking and categorization of request failures with detailed error summaries grouped by failure reason
- **Early Termination Support**: Cancel benchmarks mid-run while preserving all completed results and metrics

### Extensibility & Integration
- **Pure Python Architecture**: Eliminates complex mixed-language dependencies for simpler installation, deployment, and customization
- **ShareGPT Integration**: Automatic download, caching, and conversation processing of public datasets

## Installation
```bash
pip install aiperf
```

## Migration from GenAI-Perf

AIPerf is designed to be a drop-in replacement of GenAI-Perf _for currently supported features_. To migrate your existing GenAI-Perf commands, please refer to the [Migrating from GenAI-Perf](docs/migrating.md) documentation.

## Getting Started

Please refer to the [Tutorials](docs/tutorial.md) documentation for information on how to use AIPerf.

## Additional Information

### Known Issues
- When setting the OSL via the `--output-tokens-mean` option, if `--extra-inputs ignore_eos:true` is not set, AIPerf cannot guarantee a given OSL constraint.
- A couple of options in the CLI help text are inconsistent in their usage of an underscore instead of a hyphen.
- Very high concurrency settings (typically >15,000 concurrency) may lead to port exhaustion on some systems, causing connection failures during benchmarking. Consider adjusting system limits or reducing concurrency if encountered.
- Startup errors caused by invalid configuration settings can cause AIPerf to hang indefinitely. If AIPerf appears to freeze during initialization, terminate the process and check configuration settings.
- Mooncake trace format currently requires the `--fixed-schedule` option to be set.
- Dashboard UI may cause corrupted ANSI sequences on macOS or certain terminal environments, making the terminal unusable. Run `reset` command to restore normal terminal functionality, or switch to `--ui simple` for a lightweight progress bar interface.
