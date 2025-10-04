<!--
# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
-->
# AIPerf Quick Reference

Quick reference guide for common AIPerf commands, configurations, and metrics.

## Common Commands

### Basic Benchmarking

```bash
# Simple benchmark
aiperf profile --model MODEL_NAME --url http://localhost:8000

# Streaming benchmark
aiperf profile -m MODEL_NAME --url localhost:8000 --streaming

# With concurrency
aiperf profile -m MODEL_NAME --url localhost:8000 --concurrency 10 --request-count 100

# With request rate
aiperf profile -m MODEL_NAME --url localhost:8000 --request-rate 50 --request-count 500
```

### Advanced Benchmarking

```bash
# Time-based benchmark (run for 5 minutes)
aiperf profile -m MODEL_NAME --url localhost:8000 \
  --benchmark-duration 300 --benchmark-grace-period 30

# Trace replay
aiperf profile -m MODEL_NAME --url localhost:8000 \
  --file trace.jsonl --custom-dataset-type mooncake_trace \
  --fixed-schedule --fixed-schedule-auto-offset

# Request cancellation testing
aiperf profile -m MODEL_NAME --url localhost:8000 \
  --request-cancellation-rate 20 --request-cancellation-delay 5.0

# Goodput measurement
aiperf profile -m MODEL_NAME --url localhost:8000 \
  --goodput ttft:100 --goodput request_latency:1000
```

### Custom Datasets

```bash
# Single-turn dataset
aiperf profile -m MODEL_NAME --url localhost:8000 \
  --file prompts.jsonl --custom-dataset-type single_turn

# Multi-turn conversations
aiperf profile -m MODEL_NAME --url localhost:8000 \
  --file conversations.jsonl --custom-dataset-type multi_turn

# Random pool sampling
aiperf profile -m MODEL_NAME --url localhost:8000 \
  --file prompts_dir/ --custom-dataset-type random_pool
```

### Output and Artifacts

```bash
# Specify output directory
aiperf profile -m MODEL_NAME --url localhost:8000 \
  --artifact-directory ./my_results

# Results are saved to:
#   <artifact-directory>/
#     ├── logs/aiperf.log
#     ├── profile_results.json
#     └── profile_results.csv
```

### Debugging

```bash
# Enable debug logging
aiperf profile -m MODEL_NAME --url localhost:8000 --verbose

# Trace logging for specific services
aiperf profile -m MODEL_NAME --url localhost:8000 \
  --trace-services worker --debug-services dataset_manager

# Simple UI (no dashboard)
aiperf profile -m MODEL_NAME --url localhost:8000 --ui simple

# No UI (headless)
aiperf profile -m MODEL_NAME --url localhost:8000 --ui no-ui
```

## Configuration Matrix

### Load Generation Modes

| Mode | Config | Use Case |
|------|--------|----------|
| **Fixed Concurrency** | `--concurrency N` | Test max capacity |
| **Request Rate (Constant)** | `--request-rate X --request-rate-mode constant` | Predictable load |
| **Request Rate (Poisson)** | `--request-rate X --request-rate-mode poisson` | Realistic traffic |
| **Concurrency Burst** | `--concurrency N --request-rate-mode concurrency_burst` | Max throughput |
| **Fixed Schedule** | `--file trace.jsonl --fixed-schedule` | Trace replay |

### Benchmark Duration

| Option | Config | Behavior |
|--------|--------|----------|
| **Count-Based** | `--request-count N` | Stop after N requests |
| **Time-Based** | `--benchmark-duration S` | Run for S seconds |
| **Grace Period** | `--benchmark-grace-period S` | Extra time for stragglers |

### Warmup

| Config | Purpose |
|--------|---------|
| `--warmup-request-count N` | Send N warmup requests before profiling |

## Metrics Reference

### Latency Metrics (Lower is Better)

| Metric | Unit | Description |
|--------|------|-------------|
| **TTFT** | ms | Time to first token (streaming only) |
| **ITL** | ms | Inter-token latency (streaming only) |
| **Request Latency** | ms | Total request duration |

### Throughput Metrics (Higher is Better)

| Metric | Unit | Description |
|--------|------|-------------|
| **Request Throughput** | req/s | Valid requests per second |
| **Output Token Throughput** | tokens/s | Output tokens per second |
| **Output TPS Per User** | tokens/s/user | Per-request throughput |

### Token Metrics

| Metric | Unit | Description |
|--------|------|-------------|
| **Input Sequence Length** | tokens | Input tokens per request |
| **Output Sequence Length** | tokens | Output tokens per request |
| **Output Token Count** | tokens | Output tokens (excludes reasoning) |
| **Reasoning Token Count** | tokens | Reasoning tokens only |

### Count Metrics

| Metric | Unit | Description |
|--------|------|-------------|
| **Request Count** | requests | Total valid requests |
| **Error Request Count** | requests | Total error requests |
| **Good Request Count** | requests | Requests meeting SLOs |

### Derived Metrics

| Metric | Unit | Formula |
|--------|------|---------|
| **Goodput** | req/s | Good requests / duration |
| **Benchmark Duration** | s | End time - start time |

## Configuration Patterns

### Prompt Configuration

```bash
# Synthetic prompts with specific token distribution
aiperf profile -m MODEL \
  --input-tokens-mean 500 --input-tokens-stddev 100 \
  --output-tokens-mean 200 --output-tokens-stddev 50

# Prefix prompts for KV cache testing
aiperf profile -m MODEL \
  --prefix-prompt-length 100 --prefix-prompt-pool-size 10
```

### Multimodal Configuration

```bash
# Images
aiperf profile -m MODEL \
  --image-width-mean 512 --image-height-mean 512 \
  --image-format png

# Audio
aiperf profile -m MODEL \
  --audio-length-mean 10.0 --audio-format wav \
  --audio-sample-rates 16000
```

### Advanced Configuration

```bash
# Multiple models (round-robin selection)
aiperf profile --model-names model1 model2 model3 \
  --model-selection-strategy round_robin

# Custom endpoint path
aiperf profile -m MODEL --url localhost:8000 \
  --custom-endpoint /v1/custom/completions

# Extra request parameters
aiperf profile -m MODEL --url localhost:8000 \
  --extra-inputs top_p:0.9 --extra-inputs temperature:0.7
```

## File Formats

### Single-Turn Dataset (JSONL)

```json
{"text_input": "What is AI?", "max_tokens": 100}
{"text_input": "Explain ML", "max_tokens": 150}
```

### Multi-Turn Dataset (JSONL)

```json
{
  "session_id": "conv_001",
  "turns": [
    {"text_input": "Hello", "delay": 0, "role": "user"},
    {"text_input": "How are you?", "delay": 2000, "role": "user"}
  ]
}
```

### Trace Dataset (JSONL)

```json
{"timestamp": 1000, "text_input": "Query 1"}
{"timestamp": 1500, "text_input": "Query 2"}
{"timestamp": 2200, "text_input": "Query 3"}
```

## Environment Variables

```bash
# Developer mode
export AIPERF_DEV_MODE=1

# Custom connection limit
export AIPERF_HTTP_CONNECTION_LIMIT=5000

# Service configuration
export AIPERF_LOG_LEVEL=DEBUG
export AIPERF_UI_TYPE=dashboard
```

## Quick Troubleshooting

| Issue | Solution |
|-------|----------|
| No output appearing | Add `--verbose` or `--log-level DEBUG` |
| Connection refused | Check server URL and port |
| OOM errors | Reduce `--concurrency` or token lengths |
| Slow performance | Increase `--workers-max` |
| Dashboard broken | Try `--ui simple` or `--ui no-ui` |
| Tests failing | Reduce `--request-count` |

## Performance Tuning

### Optimal Worker Count

```bash
# Auto-calculated: min(CPU_count * 0.75 - 1, concurrency, 32)
# Override with:
--workers-max 16
```

### Concurrency Guidelines

| Scenario | Concurrency | Reasoning |
|----------|-------------|-----------|
| Single GPU | 10-20 | Avoid OOM |
| Multi GPU | 50-100 | Utilize capacity |
| CPU inference | 5-10 | CPU bottleneck |
| High latency | 20-50 | Keep workers busy |

### Request Rate Guidelines

| Scenario | Rate | Mode |
|----------|------|------|
| Stress test | None | Use concurrency only |
| Realistic load | 10-100 | Poisson |
| Precise timing | 10-100 | Constant |
| Trace replay | N/A | Fixed schedule |

## Common Patterns

### Load Testing

```bash
# Find maximum throughput
aiperf profile -m MODEL --url localhost:8000 \
  --concurrency 50 --request-count 1000
```

### SLA Validation

```bash
# Verify 99th percentile < 500ms
aiperf profile -m MODEL --url localhost:8000 \
  --request-rate 20 --request-count 500
# Check p99 in results
```

### A/B Testing

```bash
# Benchmark setup A
aiperf profile -m MODEL_V1 --url localhost:8000 \
  --file dataset.jsonl --random-seed 42 --custom-dataset-type single_turn

# Benchmark setup B (same dataset, different model/config)
aiperf profile -m MODEL_V2 --url localhost:8001 \
  --file dataset.jsonl --random-seed 42 --custom-dataset-type single_turn

# Compare results
```

### Production Simulation

```bash
# Replay production trace
aiperf profile -m MODEL --url localhost:8000 \
  --file prod_trace.jsonl --custom-dataset-type mooncake_trace \
  --fixed-schedule --fixed-schedule-auto-offset
```

## See Also

- **[Complete Developer's Guidebook](../guidebook/INDEX.md)** - Full technical reference
- **[Examples](../examples/README.md)** - Runnable code examples
- **[CLI Options](cli_options.md)** - Complete CLI reference
- **[Architecture](architecture.md)** - System design
- **[Troubleshooting](../guidebook/chapter-50-troubleshooting-guide.md)** - Problem solving
