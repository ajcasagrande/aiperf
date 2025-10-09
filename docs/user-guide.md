<!--
SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
SPDX-License-Identifier: Apache-2.0
-->

# AIPerf User Guide

This guide explains AIPerf in accessible terms for users who want to understand and use the tool effectively, without needing deep technical knowledge. It covers what AIPerf does, why it's useful, and how to use it for your benchmarking needs.

---

## Table of Contents

- [What is AIPerf?](#what-is-aiperf)
- [Why Use AIPerf?](#why-use-aiperf)
- [How AIPerf Works](#how-aiperf-works)
- [Getting Started](#getting-started)
- [Understanding the Results](#understanding-the-results)
- [Common Use Cases](#common-use-cases)
- [Configuration Guide](#configuration-guide)
- [Troubleshooting](#troubleshooting)
- [FAQ](#faq)

---

## What is AIPerf?

**AIPerf** is a tool that measures how fast and efficiently AI models respond to requests. Think of it like a stress test or performance benchmark for AI services.

### Simple Analogy

Imagine you want to test how well a restaurant can handle customers:
- How long does it take to serve the first dish?
- How many customers can they serve at once?
- What happens when the restaurant gets really busy?
- How consistent is the service quality?

AIPerf does the same thing for AI models - it sends many requests and measures response times, throughput, and quality under different load conditions.

### What AIPerf Measures

AIPerf tracks important performance metrics like:
- **Response Time**: How long it takes to get an answer
- **Throughput**: How many requests can be handled per second
- **Token Generation Speed**: How fast the AI generates text
- **Consistency**: How much performance varies between requests
- **Reliability**: How many requests succeed vs. fail

---

## Why Use AIPerf?

### 1. **Performance Validation**

Before deploying an AI service to production, you need to know:
- Can it handle the expected number of users?
- Will response times be acceptable?
- Are there performance bottlenecks?

AIPerf answers these questions with concrete data.

### 2. **Capacity Planning**

Understand how much hardware you need:
- How many requests per second can your current setup handle?
- What happens when you add more resources?
- Where should you invest to improve performance?

### 3. **Optimization**

Identify performance issues:
- Is the model slow at starting to generate responses?
- Does performance degrade under load?
- Which configuration provides the best performance?

### 4. **Comparison**

Compare different:
- Models (which performs better?)
- Serving solutions (vLLM, Triton, TensorRT-LLM, etc.)
- Hardware configurations (GPUs, CPUs, memory)
- Optimization techniques (quantization, batching, etc.)

### 5. **Regression Testing**

Ensure performance doesn't degrade:
- Test after code changes
- Validate after infrastructure updates
- Track performance trends over time

---

## How AIPerf Works

### High-Level Overview

AIPerf simulates real-world usage by:

1. **Generating or Loading Test Data**: Creates prompts that resemble real user requests
2. **Sending Requests**: Sends many requests to your AI service
3. **Collecting Responses**: Records when responses arrive and what they contain
4. **Measuring Performance**: Calculates metrics like latency and throughput
5. **Reporting Results**: Displays easy-to-understand performance statistics

### The AIPerf Architecture (Simplified)

```
┌─────────────────────────────────────────────┐
│          AIPerf Benchmarking Tool           │
│                                             │
│  ┌─────────────┐        ┌───────────────┐  │
│  │ Test Data   │        │ Test          │  │
│  │ Generator   │───────▶│ Coordinator   │  │
│  └─────────────┘        └───────┬───────┘  │
│                                  │          │
│                         ┌────────▼────────┐ │
│                         │  Request        │ │
│                         │  Executors      │ │
│                         │  (Workers)      │ │
│                         └────────┬────────┘ │
│                                  │          │
└──────────────────────────────────┼──────────┘
                                   │
                       HTTP Requests
                                   │
                                   ▼
                    ┌──────────────────────────┐
                    │   Your AI Service        │
                    │   (vLLM, Triton, etc.)   │
                    └──────────────────────────┘
                                   │
                       HTTP Responses
                                   │
                                   ▼
┌─────────────────────────────────────────────┐
│              AIPerf Results                 │
│  ┌──────────────────────────────────────┐   │
│  │ • Response times                     │   │
│  │ • Throughput metrics                 │   │
│  │ • Token generation speed             │   │
│  │ • Error rates                        │   │
│  │ • Detailed statistics                │   │
│  └──────────────────────────────────────┘   │
└─────────────────────────────────────────────┘
```

### Key Components Explained

**1. Test Data Generator**
- Creates realistic prompts for your AI to respond to
- Can generate synthetic data or use your own custom datasets
- Ensures consistent, reproducible tests

**2. Test Coordinator**
- Controls when requests are sent (how fast, how many at once)
- Manages the overall benchmark execution
- Ensures proper timing and load distribution

**3. Request Executors (Workers)**
- Multiple workers send requests in parallel
- Simulates many users accessing your AI service simultaneously
- Records precise timing information for each request

**4. Your AI Service**
- This is what you're testing (e.g., a model served with vLLM)
- Receives requests just like it would from real users
- AIPerf measures how well it performs

**5. Results Collection & Analysis**
- Gathers all timing and response data
- Calculates performance metrics
- Generates reports and visualizations

---

## Getting Started

### Installation

```bash
# Install AIPerf using pip
pip install aiperf
```

### Basic Usage

The simplest way to run AIPerf:

```bash
aiperf profile \
  --model your_model_name \
  --url http://localhost:8000 \
  --endpoint-type chat \
  --streaming
```

This command:
- Tests a chat model
- Sends requests to `http://localhost:8000`
- Uses streaming responses (gets tokens as they're generated)
- Uses default settings for everything else

### Example: Testing a Local Model

Let's say you're running a model with vLLM on your local machine:

```bash
# Step 1: Start your model server (in another terminal)
vllm serve Qwen/Qwen3-0.6B --port 8000

# Step 2: Run AIPerf
aiperf profile \
  --model Qwen/Qwen3-0.6B \
  --url http://localhost:8000 \
  --endpoint-type chat \
  --streaming \
  --concurrency 10 \
  --request-count 100
```

This sends 100 requests with 10 happening concurrently (at the same time).

### What You'll See

While AIPerf runs, you'll see a dashboard showing:
- **Progress**: How many requests have been sent/completed
- **Live Metrics**: Current performance statistics
- **Worker Status**: Health of the request executors
- **Errors**: Any problems encountered

When finished, you'll get a summary table like:

```
NVIDIA AIPerf | LLM Metrics
┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━┳━━━━━━━━┳━━━━━━━━┓
┃                               Metric ┃       avg ┃    p90 ┃    p99 ┃
┡━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━╇━━━━━━━━╇━━━━━━━━┩
│             Time to First Token (ms) │     18.26 │  27.76 │  68.82 │
│                 Request Latency (ms) │    487.30 │ 580.83 │ 715.99 │
│             Inter Token Latency (ms) │     11.23 │  11.73 │  12.48 │
│ Output Token Throughput (tokens/sec) │ 10,944.03 │    N/A │    N/A │
│    Request Throughput (requests/sec) │    255.54 │    N/A │    N/A │
└──────────────────────────────────────┴───────────┴────────┴────────┘
```

---

## Understanding the Results

### Key Metrics Explained

#### **Time to First Token (TTFT)**
**What it means**: How long until you see the first word of the response.

**Why it matters**: This is what users perceive as "responsiveness". Lower is better.

**Real-world impact**:
- 100ms = feels instant
- 500ms = noticeable delay
- 2000ms = frustrating wait

---

#### **Request Latency**
**What it means**: Total time from sending a request to receiving the complete response.

**Why it matters**: Affects overall user experience and system throughput.

**What's considered good**: Depends on your use case
- Chatbots: 1-3 seconds for short responses
- Content generation: 5-10 seconds acceptable
- Real-time systems: < 500ms critical

---

#### **Inter Token Latency (ITL)**
**What it means**: Average time between each word/token during generation.

**Why it matters**: Affects how smoothly text "flows" to users.

**Reading experience**:
- 10ms = smooth, natural reading
- 50ms = slightly choppy
- 100ms+ = noticeably slow

---

#### **Output Token Throughput**
**What it means**: How many tokens (words) your system generates per second, total.

**Why it matters**: Indicates system capacity and efficiency.

**Example**: If you get 1000 tokens/sec:
- At 20 tokens per response, you can serve 50 requests/sec
- At 100 tokens per response, you can serve 10 requests/sec

---

#### **Request Throughput**
**What it means**: How many requests your system completes per second.

**Why it matters**: Direct measure of system capacity.

**Capacity planning**: If you expect 100 users making 1 request/minute each:
- You need ~2 requests/sec capacity
- Add headroom for peak times (3-5x)

---

#### **Percentiles (p90, p99)**
**What it means**:
- p90: 90% of requests were faster than this
- p99: 99% of requests were faster than this

**Why it matters**: Shows consistency and worst-case performance.

**Example interpretation**:
- Average latency: 100ms
- p90 latency: 150ms (most users experience this or better)
- p99 latency: 500ms (1 in 100 users see this delay)

If p99 is much higher than average, you have consistency problems.

---

### Reading the Results Table

Results include several statistical measures:

- **avg**: Average value across all requests
- **min**: Best (fastest) observed value
- **max**: Worst (slowest) observed value
- **p50** (median): Middle value - half were faster, half slower
- **p90**: 90th percentile
- **p99**: 99th percentile
- **std**: Standard deviation (how much values vary)

**Focus on percentiles over averages** - they better represent user experience.

---

## Common Use Cases

### 1. Load Testing

**Goal**: Determine maximum capacity

**Configuration**:
```bash
aiperf profile \
  --model your_model \
  --url http://your-server:8000 \
  --endpoint-type chat \
  --streaming \
  --concurrency 50 \        # Start with 50 concurrent users
  --benchmark-duration 300   # Run for 5 minutes
```

**What to look for**:
- When does latency start increasing?
- When do errors start appearing?
- What's the maximum stable throughput?

**Tip**: Gradually increase concurrency in separate runs (10, 25, 50, 100, 200) to find the breaking point.

---

### 2. Performance Comparison

**Goal**: Compare different models or configurations

**Approach**:
```bash
# Test Model A
aiperf profile --model model-a --url http://server:8000 \
  --concurrency 10 --request-count 100 \
  --output-artifact-dir artifacts/model-a

# Test Model B
aiperf profile --model model-b --url http://server:8000 \
  --concurrency 10 --request-count 100 \
  --output-artifact-dir artifacts/model-b

# Compare the results from both artifact directories
```

**Important**: Keep all other parameters the same for fair comparison.

---

### 3. Real-World Simulation

**Goal**: Test with realistic traffic patterns

**Configuration**:
```bash
aiperf profile \
  --model your_model \
  --url http://your-server:8000 \
  --endpoint-type chat \
  --streaming \
  --request-rate 10 \              # 10 requests per second
  --request-rate-mode poisson \    # Realistic random distribution
  --benchmark-duration 600         # Run for 10 minutes
```

**Realistic Settings**:
- Use `--request-rate` instead of `--concurrency`
- Use `--request-rate-mode poisson` for realistic variability
- Run for longer durations (5-30 minutes) to capture system behavior

---

### 4. Trace Replay

**Goal**: Test with actual production traffic

**Configuration**:
```bash
aiperf profile \
  --model your_model \
  --url http://your-server:8000 \
  --endpoint-type chat \
  --input-file production_trace.jsonl \
  --custom-dataset-type mooncake_trace \
  --fixed-schedule \
  --fixed-schedule-auto-offset
```

**Use when**:
- You have production logs
- Need exact reproducibility
- Testing regression or comparing changes

---

### 5. Stress Testing

**Goal**: Test system behavior under extreme load

**Configuration**:
```bash
aiperf profile \
  --model your_model \
  --url http://your-server:8000 \
  --endpoint-type chat \
  --streaming \
  --concurrency 200 \              # Very high concurrency
  --benchmark-duration 60 \        # Short duration
  --request-timeout-seconds 30     # Aggressive timeout
```

**What to observe**:
- Does the system crash or gracefully degrade?
- How many errors occur?
- How long does recovery take after test ends?

---

## Configuration Guide

### Load Control

**Concurrency Mode** (fixed number of simultaneous requests):
```bash
--concurrency 50
```
Best for: Understanding capacity limits, max throughput testing

**Request Rate Mode** (fixed requests per second):
```bash
--request-rate 100               # Target 100 req/sec
--request-rate-mode poisson      # Realistic distribution
```
Best for: Real-world simulation, capacity planning

**Combined Mode** (rate with concurrency limit):
```bash
--request-rate 100
--concurrency 50                 # But never exceed 50 concurrent
```
Best for: Controlled stress testing

---

### Test Duration

**Fixed Request Count** (default):
```bash
--request-count 1000            # Send exactly 1000 requests
--warmup-request-count 100      # Plus 100 warmup requests
```

**Time-Based**:
```bash
--benchmark-duration 300        # Run for 5 minutes
--benchmark-grace-period 30     # Wait 30s for in-flight requests
```

---

### Input Data

**Synthetic** (default):
```bash
--prompt-input-tokens-mean 550  # Average prompt length
--prompt-output-tokens-mean 150 # Expected response length
--conversation-num 100           # Number of unique prompts
```

**Custom File**:
```bash
--input-file my_prompts.jsonl
--custom-dataset-type single_turn
```

**Public Dataset**:
```bash
--public-dataset sharegpt       # Use ShareGPT conversations
```

---

### Output Configuration

```bash
--output-artifact-dir results/my-test   # Where to save results
--ui-type dashboard                      # dashboard, simple, or none
--log-level info                         # debug, info, warning, error
```

---

## Troubleshooting

### Common Issues

#### **Error: Connection Refused**
```
Problem: Cannot connect to http://localhost:8000
```

**Solution**:
- Verify your model server is running
- Check the URL and port are correct
- Test with `curl http://localhost:8000/v1/models`

---

#### **Very High Latency**
```
Problem: Request latency is in the 10,000ms+ range
```

**Possible Causes**:
- Server overloaded (reduce concurrency)
- Model too large for hardware
- Network issues
- Request timeout too aggressive

**Solution**:
- Start with low concurrency (5-10)
- Monitor GPU/CPU usage on server
- Increase timeout: `--request-timeout-seconds 120`

---

#### **Many Errors**
```
Problem: High error_request_count in results
```

**Check**:
- Server logs for error details
- Are you exceeding server capacity?
- Is authentication required? (use `--api-key`)
- Correct endpoint type? (`--endpoint-type chat` vs `completions`)

---

#### **Results Look Wrong**
```
Problem: Metrics seem inconsistent or unexpected
```

**Verify**:
- Did warmup complete? (use `--warmup-request-count 50`)
- Is server stable? (check server resource usage)
- Are you comparing apples-to-apples? (same settings across tests)
- Run multiple times to confirm reproducibility

---

#### **AIPerf Crashes or Hangs**
```
Problem: AIPerf stops responding
```

**Try**:
- Reduce workers: `--workers-max 16`
- Reduce concurrency: `--concurrency 10`
- Use simpler UI: `--ui simple` or `--ui none`
- Check available system resources (RAM, CPU)
- Enable debug logs: `--log-level debug`

---

#### **Dashboard UI Corrupted**
```
Problem: Terminal shows garbled text
```

**Solution**:
- Switch to simple UI: `--ui simple`
- Or no UI: `--ui none`
- Reset terminal: run `reset` command
- This is a known issue on some macOS terminals

---

## FAQ

### General Questions

**Q: How long should I run a benchmark?**

A: Depends on your goal:
- Quick test: 100 requests or 30 seconds
- Reliable results: 1000 requests or 5 minutes
- Production validation: 10,000 requests or 30 minutes

**Q: What concurrency should I use?**

A: Start low and increase:
- Development: 1-10
- Testing: 10-50
- Production sizing: Match expected peak load + 50% headroom

**Q: How do I know if my results are good?**

A: Compare against requirements:
- TTFT < 500ms for interactive applications
- ITL < 30ms for smooth reading experience
- Error rate < 1% under normal load
- p99 < 2x average (good consistency)

**Q: Can AIPerf test non-OpenAI APIs?**

A: Currently only OpenAI-compatible APIs. Support for other protocols is planned.

**Q: Does AIPerf support multi-modal models (images, audio)?**

A: Yes! Use:
- `--image-batch-size` for image inputs
- `--audio-batch-size` for audio inputs
- Chat endpoint supports multi-modal content

**Q: How is AIPerf different from other benchmarking tools?**

A: Key differences:
- Designed specifically for LLM inference
- Multiprocess architecture for high scale
- Rich metrics (TTFT, ITL, token throughput, etc.)
- Supports trace replay for reproducibility
- Active development and community

---

### Performance Questions

**Q: Why is my throughput lower than expected?**

A: Common reasons:
- Model too large for GPU memory
- Insufficient batch size on server
- Network bottleneck
- AIPerf workers limited (increase `--workers-max`)

**Q: What's the difference between output token throughput and output token throughput per user?**

A:
- **System throughput**: Total tokens/sec across all requests (measures capacity)
- **Per-user throughput**: Tokens/sec for a single request (measures experience)

**Q: How do I interpret ITL (Inter Token Latency)?**

A:
- 10ms = ~100 tokens/sec per request = excellent
- 20ms = ~50 tokens/sec per request = good
- 50ms = ~20 tokens/sec per request = acceptable
- 100ms+ = ~10 tokens/sec per request = slow

**Q: What if p99 latency is much higher than p50?**

A: You have a "tail latency" problem:
- Some requests are much slower than others
- Could indicate scheduling issues, garbage collection, or resource contention
- Consider request cancellation to manage worst cases

---

### Configuration Questions

**Q: Should I use synthetic or custom data?**

A:
- **Synthetic**: Quick tests, consistency, reproducibility
- **Custom**: Realistic workload, production validation
- **Recommendation**: Start synthetic, validate with custom

**Q: What's the difference between request rate and concurrency?**

A:
- **Request rate**: "Send X requests per second"
  - More realistic for production modeling
  - Concurrency varies based on latency
- **Concurrency**: "Always have X requests in-flight"
  - Good for finding capacity limits
  - Send next request immediately when one completes

**Q: When should I use trace replay?**

A: Use trace replay when:
- You have production traffic logs
- You need exact reproducibility
- You're doing before/after comparisons (A/B testing)
- You want deterministic benchmarking

**Q: How many warmup requests do I need?**

A:
- Minimum: 50-100 requests
- Typical: Match 10% of main request count
- Cold start testing: 0 warmup requests
- Production validation: 200-500 warmup requests

---

### Results Questions

**Q: Where are my results saved?**

A: Default location: `artifacts/<model>-<endpoint>-<config>/`

Contains:
- `profile_export_aiperf.json` - Complete results
- `profile_export_aiperf.csv` - Tabular metrics
- `inputs_aiperf.json` - Request payloads used
- `logs/` - Detailed logs

**Q: How do I compare results from multiple runs?**

A:
1. Save each run to a different output directory:
   ```bash
   --output-artifact-dir results/run1
   --output-artifact-dir results/run2
   ```
2. Compare the JSON or CSV files
3. Focus on p50, p90, p99 values for fairness

**Q: Can I export results to my monitoring system?**

A: JSON export is available. You can parse it and send to your system:
```bash
python process_results.py artifacts/my-test/profile_export_aiperf.json
```

**Q: What do I do with the inputs.json file?**

A: This file contains all the prompts used in your test:
- Enables reproducibility (run same test again)
- Helps debug issues (see what was sent)
- Validate test realism (review prompts)
- Share benchmarks with others

---

## Next Steps

### Learning More

- **[Tutorial](tutorial.md)**: Step-by-step examples
- **[Metrics Reference](metrics_reference.md)**: Detailed metric definitions
- **[CLI Options](cli_options.md)**: Complete option reference
- **[Advanced Features](tutorials/)**: Request cancellation, trace replay, etc.

### Getting Help

- **Documentation**: https://docs.claude.com/en/docs/claude-code/
- **GitHub Issues**: https://github.com/ai-dynamo/aiperf/issues
- **Discord Community**: https://discord.gg/D92uqZRjCZ

### Contributing

AIPerf is open source! Contributions welcome:
- Report bugs or request features on GitHub
- Share your use cases and benchmarks
- Contribute code improvements

---

## Summary

AIPerf is a powerful yet accessible tool for measuring AI model performance. Key takeaways:

- **Start Simple**: Begin with basic commands and default settings
- **Understand Metrics**: Focus on TTFT, latency, and throughput for most use cases
- **Match Reality**: Configure tests to resemble your actual workload
- **Use Percentiles**: P90/P99 are more meaningful than averages
- **Iterate**: Run multiple tests with different configurations
- **Validate**: Always verify results make sense for your system

With AIPerf, you can confidently deploy AI services knowing exactly how they'll perform under real-world conditions.

Happy benchmarking!
