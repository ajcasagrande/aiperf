<!--
# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
-->
# Chapter 3: Quick Start Guide

## Table of Contents
- [Prerequisites](#prerequisites)
- [Your First Benchmark](#your-first-benchmark)
- [Understanding the Output](#understanding-the-output)
- [Basic CLI Options](#basic-cli-options)
- [Common Scenarios](#common-scenarios)
- [Interpreting Results](#interpreting-results)
- [Troubleshooting](#troubleshooting)
- [Next Steps](#next-steps)
- [Key Takeaways](#key-takeaways)

## Prerequisites

Before running your first benchmark, ensure you have:

1. **AIPerf Installed**: Follow Chapter 2 to install AIPerf
2. **Python 3.10+**: Verify with `python --version`
3. **Virtual Environment**: Activated and AIPerf installed in it
4. **Inference Server Running**: A target endpoint to benchmark
5. **Network Connectivity**: Can reach the inference server

### Quick Environment Check

```bash
# Activate your virtual environment
source aiperf-env/bin/activate

# Verify AIPerf is installed
aiperf --version

# Check Python version
python --version

# Verify you can reach your endpoint
curl http://localhost:8000/v1/models  # Example for OpenAI-compatible endpoint
```

## Your First Benchmark

Let's run a simple benchmark against a chat completions endpoint. This example assumes you have a vLLM or similar OpenAI-compatible server running on `localhost:8000`.

### Example 1: Simplest Possible Benchmark

```bash
aiperf profile \
    --model Qwen/Qwen3-0.6B \
    --url localhost:8000 \
    --endpoint-type chat
```

This minimal command will:
- Target the model `Qwen/Qwen3-0.6B`
- Connect to `localhost:8000`
- Use the chat completions endpoint
- Run with default settings (100 requests, concurrency of 1)

### Example 2: Basic Benchmark with Key Parameters

```bash
aiperf profile \
    --model Qwen/Qwen3-0.6B \
    --url localhost:8000 \
    --endpoint-type chat \
    --streaming \
    --concurrency 10 \
    --request-count 100 \
    --warmup-request-count 10
```

**What this does**:
- `--streaming`: Enables streaming responses (SSE)
- `--concurrency 10`: Maintains 10 concurrent requests
- `--request-count 100`: Sends 100 total requests
- `--warmup-request-count 10`: Sends 10 warmup requests first (not measured)

### Example 3: Controlled Input/Output Lengths

```bash
aiperf profile \
    --model Qwen/Qwen3-0.6B \
    --url localhost:8000 \
    --endpoint-type chat \
    --streaming \
    --concurrency 10 \
    --request-count 100 \
    --synthetic-input-tokens-mean 100 \
    --synthetic-input-tokens-stddev 10 \
    --output-tokens-mean 200 \
    --output-tokens-stddev 20 \
    --extra-inputs min_tokens:200 \
    --extra-inputs ignore_eos:true
```

**What this does**:
- Generates synthetic prompts with ~100 tokens (±10 stddev)
- Requests ~200 output tokens (±20 stddev)
- Uses `min_tokens:200` to enforce minimum output length
- Uses `ignore_eos:true` to prevent early stopping

### Watching It Run

When you execute the command, you'll see:

1. **Initialization Phase**:
```
INFO     AIPerf System is CONFIGURING
INFO     Configuring tokenizer(s) for dataset manager
INFO     Tokenizer(s) configured in 2.34 seconds
INFO     Dataset configured in 0.15 seconds
```

2. **Progress Dashboard** (default UI):
```
┌─────────────────────────────────────────────────────────────┐
│                    AIPerf Profiling                         │
├─────────────────────────────────────────────────────────────┤
│ Phase: PROFILING                                            │
│ Progress: ████████████░░░░░░░░ 65/100 (65%)                │
│ Request Rate: 45.3 req/s                                    │
│ Workers: 8 active                                           │
└─────────────────────────────────────────────────────────────┘
```

3. **Completion and Results** (see next section)

## Understanding the Output

After the benchmark completes, AIPerf displays comprehensive results.

### Console Output Structure

```
NVIDIA AIPerf | LLM Metrics
┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━┳━━━━━━━━┳━━━━━━━━┳━━━━━━━━┳━━━━━━━━┳━━━━━━━━┳━━━━━━━┓
┃                               Metric ┃       avg ┃    min ┃    max ┃    p99 ┃    p90 ┃    p75 ┃   std ┃
┡━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━╇━━━━━━━━╇━━━━━━━━╇━━━━━━━━╇━━━━━━━━╇━━━━━━━━╇━━━━━━━┩
│             Time to First Token (ms) │     18.26 │  11.22 │ 106.32 │  68.82 │  27.76 │  16.62 │ 12.07 │
│            Time to Second Token (ms) │     11.40 │   0.02 │  85.91 │  34.54 │  12.59 │  11.65 │  7.01 │
│                 Request Latency (ms) │    487.30 │ 267.07 │ 769.57 │ 715.99 │ 580.83 │ 536.17 │ 79.60 │
│             Inter Token Latency (ms) │     11.23 │   8.80 │  13.17 │  12.48 │  11.73 │  11.37 │  0.45 │
│     Output Token Throughput Per User │     89.23 │  75.93 │ 113.60 │ 102.28 │  90.91 │  90.29 │  3.70 │
│                    (tokens/sec/user) │           │        │        │        │        │        │       │
│      Output Sequence Length (tokens) │     42.83 │  24.00 │  65.00 │  64.00 │  52.00 │  47.00 │  7.21 │
│       Input Sequence Length (tokens) │     10.00 │  10.00 │  10.00 │  10.00 │  10.00 │  10.00 │  0.00 │
│ Output Token Throughput (tokens/sec) │ 10,944.03 │    N/A │    N/A │    N/A │    N/A │    N/A │   N/A │
│    Request Throughput (requests/sec) │    255.54 │    N/A │    N/A │    N/A │    N/A │    N/A │   N/A │
│             Request Count (requests) │    711.00 │    N/A │    N/A │    N/A │    N/A │    N/A │   N/A │
└──────────────────────────────────────┴───────────┴────────┴────────┴────────┴────────┴────────┴───────┘

CLI Command: aiperf profile --model Qwen/Qwen3-0.6B --url localhost:8000 --endpoint-type chat --streaming --concurrency 10 --request-count 100
Benchmark Duration: 2.78 seconds
CSV: /home/user/artifacts/results/profile_export.csv
JSON: /home/user/artifacts/results/profile_export.json
Log File: /home/user/artifacts/logs/aiperf.log
```

### Key Metrics Explained

#### Time to First Token (TTFT)
- **What it measures**: Time from request sent to first token received
- **Why it matters**: User-perceived latency, "thinking time"
- **Good values**: < 100ms for fast responses, < 500ms acceptable
- **In the example**: 18.26ms average, 106.32ms worst case (p99: 68.82ms)

#### Time to Second Token (TTST)
- **What it measures**: Time from first token to second token
- **Why it matters**: Indicates when generation actually starts
- **Use case**: Helpful for diagnosing scheduling delays

#### Request Latency
- **What it measures**: Total time from request start to completion
- **Why it matters**: Overall user experience
- **In the example**: 487.30ms average for complete response

#### Inter Token Latency (ITL)
- **What it measures**: Average time between consecutive tokens
- **Why it matters**: Streaming experience smoothness
- **Good values**: Consistent, low values (< 50ms ideal)
- **In the example**: 11.23ms - very consistent (low stddev)

#### Output Token Throughput Per User
- **What it measures**: Tokens/second per concurrent user
- **Why it matters**: Individual user experience
- **In the example**: ~89 tokens/second per user

#### Output Token Throughput (System)
- **What it measures**: Total system throughput
- **Why it matters**: System capacity
- **In the example**: 10,944 tokens/second across all concurrent requests

#### Request Throughput
- **What it measures**: Completed requests per second
- **Why it matters**: System capacity metric
- **In the example**: 255.54 requests/second

### Output Files

AIPerf creates several output files in the artifacts directory:

#### 1. CSV Export (`profile_export.csv`)
```csv
model_name,timestamp_ns,start_perf_ns,end_perf_ns,request_latency,...
Qwen/Qwen3-0.6B,1234567890,1234567891,1234567892,487300000,...
```
- Machine-readable results
- One row per request
- All metrics included
- Import into pandas, Excel, etc.

#### 2. JSON Export (`profile_export.json`)
```json
{
  "results": {
    "records": [...],
    "metrics": {...},
    "error_summary": {}
  },
  "config": {...}
}
```
- Complete benchmark data
- Structured format
- Programmatic access
- Configuration included

#### 3. Inputs File (`inputs.json`)
```json
{
  "data": [
    {
      "session_id": "uuid-here",
      "payloads": [
        {
          "model": "Qwen/Qwen3-0.6B",
          "messages": [...]
        }
      ]
    }
  ]
}
```
- Exact payloads sent
- Reproducibility
- Debugging aid

#### 4. Log File (`aiperf.log`)
```
2025-01-15 10:30:45.123 | INFO     | System Controller starting
2025-01-15 10:30:45.456 | DEBUG    | Worker worker_1 initialized
...
```
- Detailed execution log
- Debugging information
- Timestamps for everything
- Multiple log levels

## Basic CLI Options

Here are the essential options you'll use most frequently.

### Required Options

```bash
--model MODEL_NAME              # Model name to benchmark
--url URL                       # Server URL (host:port or full URL)
--endpoint-type TYPE            # Endpoint type: chat, completions, embeddings, etc.
```

### Connection Options

```bash
--endpoint ENDPOINT             # API endpoint path (default: /v1/chat/completions)
--streaming                     # Enable streaming responses (SSE)
--service-kind SERVICE          # Service type: openai (default), triton, etc.
```

### Load Generation Options

```bash
# Concurrency mode (default)
--concurrency N                 # Number of concurrent requests (default: 1)
--request-count N               # Total requests to send (default: 100)

# Request rate mode
--request-rate RATE             # Target requests per second
--request-count N               # Total requests to send

# Combined mode
--request-rate RATE             # Target requests per second
--request-rate-max-concurrency N  # Max concurrent requests
```

### Dataset Options

```bash
# Synthetic generation (default)
--synthetic-input-tokens-mean N       # Mean input tokens (default: 550)
--synthetic-input-tokens-stddev N     # Stddev input tokens (default: 0)
--output-tokens-mean N                # Mean output tokens (default: 150)
--output-tokens-stddev N              # Stddev output tokens (default: 0)
--conversation-num N                  # Number of unique conversations (default: 1)

# Custom dataset
--input-file PATH                     # Path to input file (JSONL, CSV)
--custom-dataset-type TYPE            # Dataset type: single_turn, multi_turn, etc.
```

### Timing Options

```bash
--warmup-request-count N        # Warmup requests before profiling (default: 0)
--benchmark-duration SECONDS    # Run for specific duration instead of request count
--benchmark-grace-period SECONDS # Grace period after duration (default: 5.0)
--request-timeout-seconds SECONDS # Request timeout (default: None)
```

### Output Options

```bash
--output-dir PATH               # Output directory (default: ./artifacts)
--ui TYPE                       # UI type: dashboard (default), simple, none
```

### Advanced Options

```bash
--extra-inputs KEY:VALUE        # Pass additional parameters to endpoint
--random-seed SEED              # Random seed for reproducibility (default: 0)
--tokenizer NAME                # Tokenizer to use (default: model name)
```

## Common Scenarios

### Scenario 1: Quick Performance Check

"I just want to see if my server is working and get basic metrics."

```bash
aiperf profile \
    --model my-model \
    --url localhost:8000 \
    --endpoint-type chat \
    --request-count 20 \
    --concurrency 2
```

Fast, minimal benchmark for sanity checking.

### Scenario 2: Concurrency Stress Test

"I want to test how my server handles 50 concurrent users."

```bash
aiperf profile \
    --model my-model \
    --url localhost:8000 \
    --endpoint-type chat \
    --streaming \
    --concurrency 50 \
    --request-count 500 \
    --warmup-request-count 50
```

Tests behavior under sustained concurrent load.

### Scenario 3: Request Rate Testing

"I need to hit exactly 100 requests per second."

```bash
aiperf profile \
    --model my-model \
    --url localhost:8000 \
    --endpoint-type chat \
    --request-rate 100 \
    --request-count 1000
```

Precise rate targeting for capacity testing.

### Scenario 4: Long-Running Stress Test

"I want to test stability over 5 minutes."

```bash
aiperf profile \
    --model my-model \
    --url localhost:8000 \
    --endpoint-type chat \
    --streaming \
    --concurrency 20 \
    --benchmark-duration 300 \
    --benchmark-grace-period 30
```

Time-based testing for stability validation.

### Scenario 5: Controlled Input/Output Testing

"I want to test with specific sequence lengths."

```bash
aiperf profile \
    --model my-model \
    --url localhost:8000 \
    --endpoint-type chat \
    --streaming \
    --concurrency 10 \
    --request-count 100 \
    --synthetic-input-tokens-mean 512 \
    --synthetic-input-tokens-stddev 50 \
    --output-tokens-mean 1024 \
    --output-tokens-stddev 100 \
    --extra-inputs min_tokens:1024 \
    --extra-inputs ignore_eos:true
```

Precise control over sequence characteristics.

### Scenario 6: Custom Dataset Testing

"I want to use my own prompts from a file."

```bash
aiperf profile \
    --model my-model \
    --url localhost:8000 \
    --endpoint-type chat \
    --streaming \
    --input-file my-prompts.jsonl \
    --custom-dataset-type single_turn \
    --concurrency 10
```

Test with realistic, production-like data.

### Scenario 7: Timeout Testing

"I want to test how my system handles timeouts."

```bash
aiperf profile \
    --model my-model \
    --url localhost:8000 \
    --endpoint-type chat \
    --streaming \
    --concurrency 20 \
    --request-count 200 \
    --request-timeout-seconds 10.0
```

Validate timeout behavior and SLA compliance.

### Scenario 8: Embeddings Benchmarking

"I want to benchmark an embeddings endpoint."

```bash
aiperf profile \
    --model my-embedding-model \
    --url localhost:8000 \
    --endpoint-type embeddings \
    --endpoint /v1/embeddings \
    --concurrency 50 \
    --request-count 1000 \
    --synthetic-input-tokens-mean 256
```

Test non-generative endpoints.

## Interpreting Results

### Reading the Metrics Table

**Look for**:
1. **P99 Latencies**: These show worst-case user experience
2. **Standard Deviation**: Low stddev = consistent performance
3. **Throughput**: Compare against your requirements
4. **Error Count**: Should be zero or very low

**Red Flags**:
- High P99 (> 10x average)
- High standard deviation (> 50% of mean)
- Low throughput vs. expectations
- Any errors

### Performance Patterns

#### Good Performance
```
Time to First Token (ms)  avg: 50   p99: 75   std: 10
Inter Token Latency (ms)  avg: 20   p99: 30   std: 5
Request Latency (ms)      avg: 500  p99: 650  std: 80
```
- Consistent metrics
- Low standard deviation
- Reasonable P99 values

#### Problematic Performance
```
Time to First Token (ms)  avg: 150  p99: 2000  std: 400
Inter Token Latency (ms)  avg: 50   p99: 500   std: 100
Request Latency (ms)      avg: 2000 p99: 8000  std: 1500
```
- High variance
- P99 much worse than average
- Suggests scheduling issues or resource contention

### Comparing Results

When comparing benchmarks:
1. **Same Configuration**: Use identical settings
2. **Same Seed**: Use `--random-seed` for reproducibility
3. **Same Hardware**: Run on consistent infrastructure
4. **Same Load**: Match concurrency/request rate
5. **Multiple Runs**: Run 3-5 times and average

## Troubleshooting

### Problem: Connection Refused

```
Error: Connection refused to localhost:8000
```

**Solutions**:
1. Verify server is running: `curl http://localhost:8000/v1/models`
2. Check correct port
3. Check firewall rules
4. Verify endpoint path

### Problem: Timeouts

```
Warning: 50% of requests timed out
```

**Solutions**:
1. Increase `--request-timeout-seconds`
2. Reduce concurrency
3. Check server resources
4. Verify server can handle load

### Problem: Invalid Model Name

```
Error: Model 'wrong-name' not found
```

**Solutions**:
1. List available models: `curl http://localhost:8000/v1/models`
2. Use exact model name from server
3. Check spelling and case

### Problem: Tokenizer Download Fails

```
Error: Cannot download tokenizer 'model-name'
```

**Solutions**:
1. Check internet connection
2. Verify HuggingFace model name
3. Use `--tokenizer` to specify alternative
4. Check HuggingFace credentials if needed

### Problem: Out of Memory

```
Error: Cannot allocate memory
```

**Solutions**:
1. Reduce `--concurrency`
2. Reduce worker count (service config)
3. Use simpler UI (`--ui simple`)
4. Increase system memory

### Problem: Poor Performance

```
Throughput much lower than expected
```

**Debugging Steps**:
1. Check AIPerf system resources (shouldn't be bottleneck)
2. Monitor server resources
3. Check network latency
4. Try lower concurrency to establish baseline
5. Review logs for errors

## Next Steps

Now that you've run your first benchmarks, here's how to level up:

### 1. Explore Advanced Features
- Try trace replay (Chapter 4)
- Test request cancellation
- Use fixed schedules
- Test multi-turn conversations

### 2. Automate Testing
- Integrate into CI/CD pipelines
- Script multiple test scenarios
- Set up automated regression testing

### 3. Understand Architecture
- Read Chapters 4-5 for core concepts
- Learn how AIPerf works internally
- Understand when to use which mode

### 4. Customize and Extend
- Add custom metrics
- Implement custom exporters
- Support new endpoint types
- Contribute back to the project

### 5. Best Practices
- Always use warmup phases
- Run multiple iterations for statistical significance
- Document your test configurations
- Keep results for trend analysis

## Key Takeaways

1. **Getting Started Is Easy**: A minimal benchmark needs just model, URL, and endpoint type.

2. **Defaults Are Sensible**: AIPerf's defaults work for most cases, but customization is available.

3. **Multiple Modes Available**: Choose concurrency, request rate, or time-based depending on your goals.

4. **Rich Output**: Detailed metrics, multiple formats, and comprehensive logging provide full visibility.

5. **Common Scenarios Covered**: From quick checks to long stress tests, AIPerf handles diverse use cases.

6. **Metrics Tell a Story**: Learn to read P99s, standard deviation, and throughput patterns.

7. **Troubleshooting Is Systematic**: Most issues have clear solutions - check connections, resources, and configuration.

8. **Reproducibility Matters**: Use seeds, save configurations, and run multiple iterations.

9. **Output Files Are Valuable**: CSV and JSON exports enable deeper analysis and tracking over time.

10. **Next Level Awaits**: Basic benchmarking is just the start - advanced features enable sophisticated testing.

You now have hands-on experience with AIPerf benchmarking. The following chapters dive deeper into concepts, architecture, and advanced usage patterns.

---

Next: [Chapter 4: Core Concepts](chapter-04-core-concepts.md)
