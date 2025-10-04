<!--
# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
-->
# AIPerf Examples

This directory contains complete, runnable examples demonstrating various AIPerf features and use cases.

## Directory Structure

- **basic/** - Simple benchmarking examples for getting started
- **advanced/** - Advanced benchmarking scenarios and configurations
- **custom-metrics/** - Examples of creating custom metrics
- **custom-datasets/** - Examples of custom dataset loaders and formats
- **integration/** - Integration examples with various inference servers
- **performance/** - Performance optimization examples

## Running Examples

Each example includes:
- Complete source code
- README with instructions
- Sample data files (where applicable)
- Expected output

### Prerequisites

```bash
# Install AIPerf
pip install aiperf

# Or install from source
pip install -e .
```

### Basic Usage

```bash
cd examples/basic
python simple_benchmark.py
```

## Example Index

### Basic Examples
- `basic/simple_benchmark.py` - Minimal benchmarking example
- `basic/streaming_benchmark.py` - Streaming API benchmark
- `basic/concurrency_test.py` - Concurrency-based benchmarking
- `basic/request_rate_test.py` - Request rate benchmarking

### Advanced Examples
- `advanced/trace_replay.py` - Trace replay benchmarking
- `advanced/multi_turn_conversation.py` - Multi-turn dialogue benchmarking
- `advanced/request_cancellation.py` - Request cancellation testing
- `advanced/goodput_measurement.py` - Goodput metrics with SLOs
- `advanced/fixed_schedule.py` - Fixed schedule trace replay

### Custom Metrics Examples
- `custom-metrics/custom_record_metric.py` - Creating per-request metrics
- `custom-metrics/custom_aggregate_metric.py` - Creating aggregate metrics
- `custom-metrics/custom_derived_metric.py` - Creating derived metrics
- `custom-metrics/latency_percentile_metric.py` - Custom percentile metric

### Custom Datasets Examples
- `custom-datasets/custom_single_turn.py` - Custom single-turn dataset
- `custom-datasets/custom_multi_turn.py` - Custom multi-turn dataset
- `custom-datasets/synthetic_generator.py` - Synthetic data generation
- `custom-datasets/custom_loader.py` - Custom dataset loader

### Integration Examples
- `integration/vllm_integration.py` - vLLM server integration
- `integration/tgi_integration.py` - Text Generation Inference integration
- `integration/openai_compatible.py` - OpenAI-compatible endpoints
- `integration/custom_endpoint.py` - Custom endpoint integration

### Performance Examples
- `performance/optimizing_workers.py` - Worker count optimization
- `performance/connection_pooling.py` - Connection pool tuning
- `performance/memory_optimization.py` - Memory usage optimization
- `performance/high_throughput.py` - High throughput configuration

## Example Templates

See `templates/` directory for boilerplate code to start your own examples.

## Contributing Examples

To contribute an example:
1. Create a new directory under the appropriate category
2. Include complete, runnable code
3. Add README.md with clear instructions
4. Include sample data if needed
5. Document expected output
6. Submit a pull request

## Support

For questions about examples:
- Open an issue on GitHub
- Ask in the Discord community
- Refer to the Developer's Guidebook
