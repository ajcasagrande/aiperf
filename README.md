# AIPerf

AIPerf is a highly modular performance benchmarking tool for AI inference systems, designed to measure and characterize the performance of large-scale deployments like Dynamo.

## Key Features

- **Datacenter Level Scalability**: Designed to drive load for large-scale inference deployments
- **Modular Architecture**: Easily extensible for customization and new features
- **Flexible API Support**: Works with OpenAI, Huggingface TGI/TEI, KServe, and custom APIs
- **Multi-Modal Support**: Benchmarks text, image, audio, and video processing
- **Conversation Support**: Handles single-turn and multi-turn conversations
- **Comprehensive Metrics**: Collects a wide range of performance metrics
- **Deterministic Behavior**: Provides reproducible benchmarking results

## Architecture

AIPerf consists of several key components:

- **System Controller**: Orchestrates the entire system
- **Dataset Manager**: Manages data generation and acquisition
- **Timing Manager**: Controls request timing and scheduling
- **Worker Manager**: Manages workers that issue requests
- **Records Manager**: Stores and organizes results
- **Post Processors**: Analyze results and generate metrics

## Installation

```bash
# Clone the repository
git clone https://github.com/nvidia/aiperf.git
cd aiperf

# Install dependencies
pip install -e .
```

## Quick Start

1. Create a configuration file (see `aiperf/config/examples/` for examples)
2. Run a benchmark profile:

```bash
python -m aiperf.cli.aiperf_cli run path/to/config.yaml
```

## Configuration

AIPerf uses YAML or JSON configuration files to define benchmark profiles. Key configuration sections include:

- **Endpoints**: The API endpoints to benchmark
- **Dataset**: Data source configuration (synthetic, remote, or local)
- **Timing**: Request scheduling parameters
- **Workers**: Worker pool configuration
- **Metrics**: Metrics collection and reporting configuration

See the `aiperf/config/examples/` directory for sample configurations.

## Extending AIPerf

AIPerf is designed to be modular and extensible:

- **Add New API Types**: Implement a new client class that inherits from `BaseClient`
- **Create Custom Metrics**: Extend the `PostProcessor` class to add custom metrics
- **Add Data Sources**: Implement custom data providers by extending the `DatasetManager`

## License

NVIDIA Proprietary

## Acknowledgments

AIPerf is developed by the NVIDIA Dynamo team. 