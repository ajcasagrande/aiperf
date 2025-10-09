<!--
# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
-->
# The Ultimate AIPerf User Guide
**A Comprehensive Guide to Benchmarking Generative AI Models**

---

## Table of Contents

1. [What is AIPerf?](#what-is-aiperf)
2. [Quick Start](#quick-start)
3. [Installation & Setup](#installation--setup)
4. [Core Concepts](#core-concepts)
5. [Common Use Cases](#common-use-cases)
6. [Benchmarking Modes](#benchmarking-modes)
7. [Dataset Options](#dataset-options)
8. [Understanding Metrics](#understanding-metrics)
9. [Advanced Features](#advanced-features)
10. [Interpreting Results](#interpreting-results)
11. [Troubleshooting](#troubleshooting)
12. [Best Practices](#best-practices)

---

## What is AIPerf?

AIPerf is a comprehensive benchmarking tool designed to measure the performance of generative AI models served through inference servers. Think of it as a sophisticated load testing tool specifically built for AI workloads.

### What AIPerf Does

- **Generates realistic load** against your AI inference server
- **Measures performance metrics** like latency, throughput, and token generation speed
- **Simulates production scenarios** with different traffic patterns
- **Validates service quality** under various conditions
- **Exports detailed reports** for analysis and optimization

### When to Use AIPerf

- **Before Production**: Validate your model can handle expected traffic
- **Performance Tuning**: Find optimal batch sizes, concurrency levels, or hardware configurations
- **A/B Testing**: Compare different models, frameworks, or deployment strategies
- **SLA Validation**: Ensure your service meets latency and throughput requirements
- **Regression Testing**: Verify updates don't degrade performance
- **Capacity Planning**: Determine infrastructure needs for scaling

### Who Should Use AIPerf

- **ML Engineers** optimizing model serving infrastructure
- **DevOps Engineers** planning deployment and scaling
- **Platform Engineers** evaluating inference frameworks
- **Product Teams** validating service performance requirements

---

## Quick Start

### Prerequisites

- Python 3.10 or higher
- An inference server running (vLLM, TensorRT-LLM, Triton, etc.)
- The model name your server is hosting

### Installation

```bash
pip install aiperf
```

### Your First Benchmark

Let's say you have vLLM running locally on port 8000 serving the Qwen/Qwen3-0.6B model:

```bash
aiperf profile \
  --model Qwen/Qwen3-0.6B \
  --url http://localhost:8000 \
  --endpoint-type chat \
  --streaming \
  --concurrency 10 \
  --request-count 100
```

**What this does:**
- Sends 100 requests to your server
- Maintains 10 concurrent requests at all times
- Uses streaming mode to measure token-by-token latency
- Targets the OpenAI-compatible chat endpoint
- Displays real-time progress and final metrics

### Understanding the Output

After running, you'll see a table like this:

```
NVIDIA AIPerf | LLM Metrics
┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━┳━━━━━━━┳━━━━━━━┓
┃ Metric                         ┃     avg ┃   p99 ┃   p90 ┃
┡━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━╇━━━━━━━╇━━━━━━━┩
│ Time to First Token (ms)       │   18.26 │ 68.82 │ 27.76 │
│ Request Latency (ms)           │  487.30 │715.99 │580.83 │
│ Output Token Throughput        │10944.03 │   N/A │   N/A │
│   (tokens/sec)                 │         │       │       │
│ Request Throughput             │  255.54 │   N/A │   N/A │
│   (requests/sec)               │         │       │       │
└────────────────────────────────┴─────────┴───────┴───────┘
```

**Key Metrics Explained:**
- **Time to First Token (TTFT)**: How long before the model starts generating (latency indicator)
- **Request Latency**: Total time for complete response (user experience metric)
- **Output Token Throughput**: Total tokens/sec your server can generate (capacity metric)
- **Request Throughput**: Requests/sec your server can handle (scalability metric)

---

## Installation & Setup

### Basic Installation

```bash
pip install aiperf
```

### Verify Installation

```bash
aiperf --help
```

You should see the command-line interface documentation.

### Setting Up Your Inference Server

AIPerf works with any OpenAI-compatible inference server. Here are common setups:

#### vLLM (Recommended for Quick Start)

```bash
# Using Docker
docker pull vllm/vllm-openai:latest
docker run --gpus all -p 8000:8000 vllm/vllm-openai:latest \
  --model Qwen/Qwen3-0.6B \
  --host 0.0.0.0 --port 8000

# Wait for server to be ready (check logs for "Application startup complete")
```

#### TensorRT-LLM via Triton

```bash
# Follow Triton + TensorRT-LLM setup documentation
# Ensure OpenAI compatibility layer is enabled
```

#### Custom Endpoints

AIPerf supports custom endpoint paths and headers:

```bash
aiperf profile \
  --model your-model \
  --url https://your-api.com \
  --custom-endpoint /custom/path \
  --header "Authorization:Bearer YOUR_TOKEN" \
  --endpoint-type chat
```

---

## Core Concepts

Understanding these concepts will help you design better benchmarks.

### 1. Benchmark Lifecycle

Every AIPerf benchmark follows this flow:

```
Configuration → Warmup → Profiling → Processing → Results
```

- **Configuration**: AIPerf validates settings and prepares services
- **Warmup**: Sends warmup requests to "prime" the model (excluded from metrics)
- **Profiling**: Actual benchmark runs, collecting performance data
- **Processing**: Computes metrics from collected data
- **Results**: Exports to console, JSON, and CSV files

### 2. Load Generation Modes

AIPerf offers three ways to generate load:

#### Concurrency Mode (Default)
Maintains a fixed number of concurrent requests:

```bash
--concurrency 10  # Always keep 10 requests in flight
```

**Use when:**
- Testing maximum sustained throughput
- Simulating fixed number of concurrent users
- Finding optimal concurrency level

#### Request Rate Mode
Sends requests at a specified rate (req/sec):

```bash
--request-rate 50  # Send 50 requests per second
```

**Use when:**
- Simulating predictable traffic patterns
- Testing service under controlled load
- Validating SLA at specific traffic levels

**Rate Distribution Options:**
- `--request-rate-mode constant`: Fixed intervals between requests
- `--request-rate-mode poisson`: Natural traffic variation (default, recommended)

#### Request Rate with Max Concurrency
Combines rate control with concurrency limits:

```bash
--request-rate 100 --concurrency 20
# Send 100 req/sec but never exceed 20 concurrent requests
```

**Use when:**
- Simulating rate-limited APIs
- Testing backpressure behavior
- Modeling real production constraints

### 3. Streaming vs Non-Streaming

#### Streaming Mode (`--streaming`)

**How it works:**
- Server sends tokens one-by-one via Server-Sent Events (SSE)
- AIPerf captures timestamp of each token arrival
- Enables detailed per-token metrics

**Available Metrics:**
- Time to First Token (TTFT)
- Time to Second Token (TTST)
- Inter-Token Latency (ITL)
- Per-token throughput

**Use for:** Chat models, conversational AI, LLMs

#### Non-Streaming Mode (default)

**How it works:**
- Server sends complete response in single HTTP reply
- AIPerf measures end-to-end latency only

**Available Metrics:**
- Request latency
- Request throughput
- Token counts (computed after response)

**Use for:** Embeddings, batch processing, simple completions

### 4. Datasets

AIPerf needs prompts to send. You can provide them in several ways:

#### Synthetic Data (Default)
AIPerf generates random prompts automatically:

```bash
--synthetic-input-tokens-mean 500   # Average prompt length
--synthetic-input-tokens-stddev 50  # Variation around mean
--output-tokens-mean 200            # Expected output length
```

**Pros:** Easy, reproducible, configurable
**Cons:** Not representative of real user prompts

#### Custom Datasets
Provide your own prompts from a file:

```bash
--input-file my_prompts.jsonl \
--custom-dataset-type single_turn
```

**Pros:** Realistic, domain-specific
**Cons:** Requires data preparation

#### Public Datasets
Use pre-existing datasets like ShareGPT:

```bash
--public-dataset sharegpt
```

**Pros:** Standard benchmarks, comparability
**Cons:** May not match your use case

### 5. Metrics Categories

AIPerf computes four categories of metrics:

#### Streaming Metrics
Only available with `--streaming`:
- Time to First Token (TTFT)
- Inter-Token Latency (ITL)
- Token-level timing details

#### Token Metrics
Available for text-generating endpoints:
- Input/Output token counts
- Token throughput
- Sequence lengths

#### Reasoning Metrics
For models with thinking/reasoning tokens:
- Reasoning token count
- Total reasoning output

#### General Metrics
Always available:
- Request latency
- Request throughput
- Error counts
- Benchmark duration

---

## Common Use Cases

### Use Case 1: "How fast is my model?"

**Scenario:** You deployed a model and want to know its baseline performance.

```bash
aiperf profile \
  --model your-model-name \
  --url http://localhost:8000 \
  --endpoint-type chat \
  --streaming \
  --concurrency 1 \
  --request-count 50 \
  --warmup-request-count 5
```

**Why these settings:**
- `--concurrency 1`: Isolates per-request latency without queuing effects
- `--warmup-request-count 5`: Primes caches and models
- `--request-count 50`: Enough samples for stable statistics

**Key metrics to check:**
- Time to First Token: How long before users see first response
- Request Latency: Total time to complete response
- Inter-Token Latency: Consistency of token generation

---

### Use Case 2: "What's my maximum throughput?"

**Scenario:** You need to know how many requests/sec your server can handle.

```bash
aiperf profile \
  --model your-model-name \
  --url http://localhost:8000 \
  --endpoint-type chat \
  --streaming \
  --concurrency 50 \
  --request-count 500 \
  --synthetic-input-tokens-mean 200 \
  --output-tokens-mean 100
```

**Why these settings:**
- `--concurrency 50`: High enough to saturate the server
- `--request-count 500`: Longer run for accurate throughput measurement
- Controlled token lengths: Consistent workload for fair comparison

**Key metrics to check:**
- Output Token Throughput: Maximum tokens/sec
- Request Throughput: Maximum requests/sec
- Request Latency p99: Ensure latency doesn't degrade too much

**Pro tip:** Gradually increase concurrency (10, 25, 50, 100) and plot throughput vs latency to find the optimal operating point.

---

### Use Case 3: "Can my service handle production load?"

**Scenario:** You expect 100 requests/sec with 200-token prompts and 300-token responses.

```bash
aiperf profile \
  --model your-model-name \
  --url http://localhost:8000 \
  --endpoint-type chat \
  --streaming \
  --request-rate 100 \
  --request-rate-mode poisson \
  --benchmark-duration 300 \
  --synthetic-input-tokens-mean 200 \
  --synthetic-input-tokens-stddev 20 \
  --output-tokens-mean 300 \
  --output-tokens-stddev 30
```

**Why these settings:**
- `--request-rate 100`: Matches expected production traffic
- `--request-rate-mode poisson`: Natural variation in arrival times
- `--benchmark-duration 300`: 5-minute sustained load test
- Token distributions: Match production characteristics

**Key metrics to check:**
- Request Latency p95/p99: Most users experience acceptable latency
- Error count: Zero errors under normal load
- Output Token Throughput: Server keeps up with demand

---

### Use Case 4: "Which model is faster for my use case?"

**Scenario:** Comparing Model A vs Model B with your actual prompts.

```bash
# Prepare your prompts in JSONL format
# my_prompts.jsonl:
# {"text": "Explain quantum computing"}
# {"text": "Write a Python function to sort a list"}

# Test Model A
aiperf profile \
  --model model-a \
  --url http://localhost:8000 \
  --endpoint-type chat \
  --streaming \
  --input-file my_prompts.jsonl \
  --custom-dataset-type single_turn \
  --concurrency 10 \
  --output-artifact-dir artifacts/model-a

# Test Model B (same settings, different model)
aiperf profile \
  --model model-b \
  --url http://localhost:8000 \
  --endpoint-type chat \
  --streaming \
  --input-file my_prompts.jsonl \
  --custom-dataset-type single_turn \
  --concurrency 10 \
  --output-artifact-dir artifacts/model-b

# Compare JSON outputs from both runs
```

**Key metrics to compare:**
- Time to First Token: Which feels faster to users
- Request Latency: Overall response time
- Output Token Throughput: Processing efficiency
- Inter-Token Latency: Smoothness of generation

---

### Use Case 5: "How does request cancellation affect performance?"

**Scenario:** Users often cancel requests (closing browser tab, navigating away). What's the impact?

```bash
aiperf profile \
  --model your-model-name \
  --url http://localhost:8000 \
  --endpoint-type chat \
  --streaming \
  --concurrency 20 \
  --request-count 200 \
  --request-cancellation-rate 25 \
  --request-cancellation-delay 2.0
```

**Why these settings:**
- `--request-cancellation-rate 25`: Cancel 25% of requests
- `--request-cancellation-delay 2.0`: Wait 2 seconds before canceling (simulate user waiting then giving up)

**Key metrics to check:**
- Effect on throughput: Does cancellation free up resources?
- Completed request latency: Are remaining requests faster?
- Error patterns: How does server handle cancellations?

---

### Use Case 6: "Stress testing: When does my service break?"

**Scenario:** Find the breaking point to understand failure modes.

```bash
# Gradually increase load until errors appear
for concurrency in 10 25 50 100 200 500; do
  aiperf profile \
    --model your-model-name \
    --url http://localhost:8000 \
    --endpoint-type chat \
    --streaming \
    --concurrency $concurrency \
    --request-count 100 \
    --output-artifact-dir artifacts/stress-test-c${concurrency}
done

# Review error_request_count in each run's JSON output
```

**Key metrics to check:**
- Error Request Count: When do errors start appearing?
- Request Latency p99: When does latency become unacceptable?
- Output Token Throughput: When does throughput stop increasing?

---

## Benchmarking Modes

### Concurrency Mode

**What it does:** Maintains a constant number of requests in flight simultaneously.

**Configuration:**
```bash
--concurrency 20 --request-count 100
# OR for time-based:
--concurrency 20 --benchmark-duration 60
```

**Behavior:**
1. AIPerf starts 20 requests immediately
2. As each request completes, a new one starts
3. Continues until reaching 100 total requests (or 60 seconds)
4. Keeps exactly 20 requests in flight at all times

**When to use:**
- Finding maximum throughput (use high concurrency)
- Measuring single-request latency (use concurrency=1)
- Simulating constant user load
- Testing queue behavior under sustained pressure

**Example scenarios:**
- "What's the latency if 50 users are always active?"
- "How many concurrent requests can my server handle?"
- "What's the optimal concurrency for this hardware?"

---

### Request Rate Mode

**What it does:** Sends requests at a specified rate, independent of completion time.

**Configuration:**
```bash
--request-rate 100 --request-count 1000
# OR time-based:
--request-rate 100 --benchmark-duration 60
```

**Rate Distribution:**
```bash
# Constant intervals (predictable)
--request-rate 100 --request-rate-mode constant
# Sends request every exactly 10ms (1/100 sec)

# Poisson distribution (realistic)
--request-rate 100 --request-rate-mode poisson
# Average 100 req/sec but with natural variation
```

**Behavior:**
1. AIPerf schedules requests based on target rate
2. Requests sent regardless of previous completions
3. Concurrency varies based on server response time
4. More realistic simulation of production traffic

**When to use:**
- Simulating production traffic patterns
- Testing specific throughput targets
- Validating SLAs at defined request rates
- Understanding behavior under controlled load

**Example scenarios:**
- "Can my service handle 500 requests/sec with acceptable latency?"
- "What happens when request rate exceeds processing capacity?"
- "How does the system behave with bursty vs steady traffic?"

---

### Request Rate with Max Concurrency

**What it does:** Sends requests at specified rate, but limits maximum concurrent requests.

**Configuration:**
```bash
--request-rate 200 --concurrency 50
```

**Behavior:**
1. Targets 200 requests/sec
2. But never exceeds 50 concurrent requests
3. If 50 concurrent limit reached, new requests wait
4. Simulates backpressure and queueing

**When to use:**
- Modeling rate-limited production systems
- Testing queue management
- Preventing server overload during benchmarking
- Simulating client-side connection pools

**Example scenarios:**
- "What if my load balancer limits connections to 100?"
- "How does the service respond to backpressure?"
- "Can I sustain 1000 req/sec with a 200-connection limit?"

---

### Fixed Schedule Mode

**What it does:** Replays requests at exact timestamps from a trace file.

**Configuration:**
```bash
--input-file trace.jsonl \
--custom-dataset-type single_turn \
--fixed-schedule \
--fixed-schedule-auto-offset
```

**Trace Format (JSONL):**
```json
{"timestamp": 0, "text": "First request"}
{"timestamp": 1500, "text": "Second request (1.5 sec later)"}
{"timestamp": 2000, "text": "Third request (0.5 sec after second)"}
```

**Behavior:**
1. AIPerf reads timestamps from dataset
2. Sends each request at its exact scheduled time
3. Maintains precise timing for deterministic replay
4. Can offset timestamps to start from t=0

**When to use:**
- Replaying production traffic patterns
- Regression testing (same load every time)
- Trace-based benchmarking
- A/B testing with identical workloads

**Example scenarios:**
- "Can my new deployment handle last week's peak traffic?"
- "How does configuration A compare to B with identical load?"
- "Replay production trace to debug performance issues"

**Advanced options:**
```bash
# Start replay from specific point in trace
--fixed-schedule-start-offset 60000  # Skip first 60 seconds

# End replay at specific point
--fixed-schedule-end-offset 300000   # Stop after 5 minutes

# Auto-offset timestamps (t=0 becomes first request time)
--fixed-schedule-auto-offset
```

---

### Time-Based Benchmarking

**What it does:** Run for a specific duration instead of request count.

**Configuration:**
```bash
--benchmark-duration 300 \
--benchmark-grace-period 30 \
--concurrency 10
```

**Behavior:**
1. Runs for exactly 300 seconds (5 minutes)
2. Sends requests continuously during this time
3. After 300 sec, stops sending new requests
4. Waits up to 30 seconds for in-flight requests to complete
5. Requests completing within grace period are included in metrics

**When to use:**
- Sustained performance testing
- Comparing different configurations fairly (same time window)
- Identifying performance degradation over time
- SLA validation over fixed periods

**Example scenarios:**
- "Can the service maintain 95th percentile latency under 100ms for 1 hour?"
- "How many requests can be processed in 10 minutes?"
- "Does performance degrade during extended operation?"

**Grace Period Options:**
```bash
# Allow in-flight requests to finish (default)
--benchmark-grace-period 30

# Force immediate stop (discard in-flight requests)
--benchmark-grace-period 0

# Extended grace period for long-running requests
--benchmark-grace-period 120
```

---

## Dataset Options

### Synthetic Datasets

**What they are:** AIPerf generates random prompts on-the-fly.

#### Text Generation

```bash
# Control prompt lengths
--synthetic-input-tokens-mean 500
--synthetic-input-tokens-stddev 50
# Prompts will average 500 tokens with ±50 variance

# Control expected output lengths
--output-tokens-mean 200
--output-tokens-stddev 20
# Influences max_tokens parameter sent to server
```

**Token Distribution:**
- Uses normal (Gaussian) distribution
- Mean: average token count
- Standard deviation: spread around mean
- Truncated to ensure positive values

**How prompts are generated:**
1. AIPerf loads a text corpus (Shakespeare by default)
2. Randomly samples token sequences of desired length
3. Decodes tokens back to text
4. Sends to server with appropriate max_tokens

**Pros:**
- No data preparation needed
- Deterministic with `--random-seed`
- Configurable distributions
- Fast dataset generation

**Cons:**
- Not representative of real use cases
- May not trigger domain-specific behaviors
- Generic content lacks context

**Best for:**
- Quick performance checks
- Hardware/infrastructure comparisons
- Reproducible benchmarks
- Finding optimal configurations

---

### Custom Datasets

Provide your own prompts from files.

#### Single-Turn Format

**Use case:** Each line is an independent prompt (no conversation context).

**File format (JSONL):**
```json
{"text": "Explain quantum entanglement in simple terms"}
{"text": "Write a Python function to reverse a string"}
{"text": "What are the benefits of meditation?"}
```

**Command:**
```bash
aiperf profile \
  --input-file my_prompts.jsonl \
  --custom-dataset-type single_turn \
  --model your-model \
  --url http://localhost:8000 \
  --endpoint-type chat
```

**Advanced features:**
```json
// Multi-modal with images
{"text": "What's in this image?", "image": "/path/to/image.jpg"}

// Multi-modal with audio
{"text": "Transcribe this audio", "audio": "/path/to/audio.mp3"}

// With fixed schedule
{"timestamp": 0, "text": "First request"}
{"timestamp": 5000, "text": "Second request 5 sec later"}
```

---

#### Multi-Turn Format

**Use case:** Conversational contexts with multiple back-and-forth turns.

**File format (JSONL):**
```json
{
  "session_id": "conversation_1",
  "turns": [
    {"text": "Hi, I need help with Python"},
    {"text": "Can you show me how to read a CSV file?"}
  ]
}
{
  "session_id": "conversation_2",
  "turns": [
    {"text": "What is machine learning?"},
    {"text": "Can you give me some examples?"},
    {"text": "How do I get started?"}
  ]
}
```

**Command:**
```bash
aiperf profile \
  --input-file conversations.jsonl \
  --custom-dataset-type multi_turn \
  --model your-model \
  --url http://localhost:8000 \
  --endpoint-type chat
```

**Advanced features:**
```json
{
  "session_id": "session_123",
  "turns": [
    {"text": "Hello", "delay": 0},
    {"text": "Follow up", "delay": 5000}  // Wait 5 sec before sending
  ]
}
```

---

#### Random Pool Format

**Use case:** Mix and match from separate data pools for varied prompts.

**File format (JSONL):**
```json
{"text": "Query from pool 1"}
{"text": "Another query"}
{"text": "More queries"}
```

**Command:**
```bash
aiperf profile \
  --input-file data_pool.jsonl \
  --custom-dataset-type random_pool \
  --conversation-num 500 \
  --model your-model \
  --url http://localhost:8000 \
  --endpoint-type chat
```

**How it works:**
1. AIPerf loads all entries from file(s)
2. Randomly samples to create 500 conversations
3. Each conversation is a random selection from the pool
4. Enables data reuse with variation

**Use for:**
- Limited source data that needs to generate many requests
- Creating diverse workloads from small datasets
- Testing with combinations of different prompt types

---

### Public Datasets

Pre-existing benchmark datasets.

#### ShareGPT Dataset

**What it is:** Real conversations from ChatGPT, multi-turn format.

**Command:**
```bash
aiperf profile \
  --public-dataset sharegpt \
  --model your-model \
  --url http://localhost:8000 \
  --endpoint-type chat
```

**How it works:**
1. AIPerf downloads ShareGPT dataset from HuggingFace
2. Caches locally (`.cache/aiperf/datasets/`)
3. Filters conversations by length and token counts
4. Uses first N conversations for benchmarking

**Configuration:**
```bash
# Control dataset filtering
--max-prompt-length 2048         # Skip prompts longer than this
--max-sequence-length 4096       # Skip total sequences longer than this
--conversation-num 100            # Use first 100 conversations
```

**Pros:**
- Real user conversations
- Standard benchmark for comparability
- Multi-turn conversational context
- No data preparation

**Cons:**
- Generic (not domain-specific)
- May not match your use case
- Fixed dataset (can't customize)

---

### Dataset Tips

**Choosing the right dataset:**

| Use Case | Recommended Dataset | Why |
|----------|---------------------|-----|
| Quick performance check | Synthetic | Fast, reproducible |
| Production validation | Custom single-turn | Your actual prompts |
| Conversational AI | Custom multi-turn | Realistic dialogue |
| Standard benchmark | Public ShareGPT | Comparability |
| Load testing | Random pool | Reuse limited data |
| Trace replay | Custom with timestamps | Exact production patterns |

**Dataset best practices:**

1. **Match production characteristics:**
   - Use similar prompt lengths
   - Include typical variation
   - Represent actual use cases

2. **Consider data volume:**
   - Synthetic: Unlimited
   - Custom: Prepare enough samples
   - Random pool: Small dataset, many conversations

3. **Validate your data:**
   - Test with small sample first
   - Check for formatting errors
   - Verify endpoints accept the format

4. **Use random seeds for reproducibility:**
   ```bash
   --random-seed 42  # Same data every run
   ```

---

## Understanding Metrics

AIPerf computes dozens of metrics. Here's what matters and when.

### Latency Metrics

#### Time to First Token (TTFT)

**What it measures:** Time from request start until first token arrives.

**Why it matters:**
- User's perceived responsiveness
- "How long until I see something happen?"
- Critical for interactive applications

**Typical values:**
- Good: < 100ms
- Acceptable: 100-500ms
- Poor: > 500ms

**What affects it:**
- Model size (larger = slower)
- Prompt length (longer = more processing)
- Batching strategy
- GPU memory bandwidth

**How to improve:**
- Reduce batch size for lower latency
- Use tensor parallelism
- Optimize KV cache
- Consider continuous batching

**When to focus on it:**
- Chat applications
- Interactive demos
- Real-time systems
- User-facing APIs

---

#### Request Latency

**What it measures:** Total time from request start to complete response.

**Why it matters:**
- End-to-end user experience
- "How long until my request is done?"
- SLA metric for batch processing

**Formula:**
```
Request Latency = Time to First Token + (Output Tokens × Inter-Token Latency)
```

**Typical values (for 100-token output):**
- Good: < 1 second
- Acceptable: 1-5 seconds
- Poor: > 5 seconds

**What affects it:**
- All factors affecting TTFT
- Output length
- Token generation speed
- Decoding strategy (greedy vs sampling)

**How to improve:**
- Everything that improves TTFT
- Optimize token generation kernel
- Use FP8/INT8 quantization
- Increase batch size (throughput vs latency trade-off)

---

#### Inter-Token Latency (ITL)

**What it measures:** Average time between consecutive tokens during generation.

**Why it matters:**
- Smoothness of generation
- Token generation efficiency
- Bottleneck identification

**Formula:**
```
ITL = (Request Latency - TTFT) / (Output Tokens - 1)
```

**Typical values:**
- Good: < 20ms (> 50 tokens/sec)
- Acceptable: 20-50ms (20-50 tokens/sec)
- Poor: > 50ms (< 20 tokens/sec)

**What affects it:**
- Model architecture
- Batch size
- GPU utilization
- Memory bandwidth

**How to interpret:**
- Low variance: Consistent generation
- High variance: Queuing or contention issues
- Increasing over time: Resource exhaustion

---

### Throughput Metrics

#### Output Token Throughput

**What it measures:** Total tokens generated per second across all requests.

**Why it matters:**
- System capacity
- Hardware efficiency
- Cost per token

**Formula:**
```
Output Token Throughput = Total Output Tokens / Benchmark Duration
```

**Typical values (single A100 GPU):**
- Small model (7B): 5,000-10,000 tokens/sec
- Medium model (13B): 2,000-5,000 tokens/sec
- Large model (70B): 500-2,000 tokens/sec

**What affects it:**
- Concurrency/batch size (primary factor)
- Model size
- Hardware (GPU model, memory)
- Framework optimizations

**How to improve:**
- Increase batch size (up to GPU memory limit)
- Use continuous batching
- Optimize kernels (FlashAttention, PagedAttention)
- Add more GPUs with tensor/pipeline parallelism

**When to focus on it:**
- Batch processing workloads
- Cost optimization
- Capacity planning
- Hardware evaluation

---

#### Request Throughput

**What it measures:** Requests completed per second.

**Why it matters:**
- System scalability
- User capacity
- Infrastructure sizing

**Formula:**
```
Request Throughput = Total Requests / Benchmark Duration
```

**What affects it:**
- Concurrency level
- Request latency
- Output length variation
- Error rate

**Relationship to token throughput:**
```
Requests/sec = Token Throughput / Average Output Length
```

**Example:**
- 10,000 tokens/sec ÷ 100 tokens/response = 100 requests/sec

---

### Statistical Metrics

AIPerf reports percentiles for most latency metrics:

- **Average (avg):** Mean value across all requests
- **Minimum (min):** Best-case scenario
- **Maximum (max):** Worst-case scenario
- **p50 (median):** 50% of requests are faster than this
- **p90:** 90% of requests are faster than this
- **p95:** 95% of requests are faster than this
- **p99:** 99% of requests are faster than this
- **Standard Deviation (std):** Variance in values

**Which percentile to use:**

| Percentile | Use Case |
|------------|----------|
| Average | General performance indicator |
| p50 | Typical user experience |
| p90 | Most users' experience |
| p95 | SLA target (e.g., "95% under 100ms") |
| p99 | Worst acceptable case |
| Max | Debugging outliers |

**SLA examples:**
- "95% of requests complete in under 500ms" = p95 < 500ms
- "99% of requests get first token in under 200ms" = TTFT p99 < 200ms

---

### Token Metrics

#### Input Sequence Length (ISL)

**What it measures:** Number of tokens in the prompt.

**Why it matters:**
- Influences latency
- Affects memory usage
- Determines context window utilization

**How to control it:**
```bash
--synthetic-input-tokens-mean 500
--synthetic-input-tokens-stddev 50
```

---

#### Output Sequence Length (OSL)

**What it measures:** Number of tokens in the response.

**Why it matters:**
- Directly impacts latency
- Affects cost (tokens = money)
- Determines throughput capacity

**Note:** AIPerf sets `max_tokens` but actual output may be shorter (EOS token).

**Formula:**
```
OSL = Output Token Count + Reasoning Token Count (if applicable)
```

---

### Error Metrics

#### Error Request Count

**What it measures:** Number of requests that failed.

**Types of errors:**
- HTTP errors (500, 503, etc.)
- Timeout errors
- Connection errors
- Malformed responses

**What to check:**
- Error types (see JSON export)
- When errors occurred (beginning vs end)
- Correlation with load level

**Acceptable levels:**
- Zero errors under normal load
- < 0.1% during stress testing
- > 1% indicates serious issues

---

### Metrics Decision Tree

**"Which metrics should I focus on?"**

```
Are you building a user-facing application?
├─ YES → Focus on latency metrics (TTFT, ITL, p95/p99)
└─ NO (batch processing) → Focus on throughput metrics

Is latency your main concern?
├─ YES → Measure with concurrency=1, optimize TTFT
└─ NO → Increase concurrency, maximize token throughput

Do you have SLA requirements?
├─ YES → Measure p95/p99, validate under max load
└─ NO → Focus on average performance

Are you comparing configurations?
└─ Use same dataset, random seed, and load pattern for fair comparison
```

---

## Advanced Features

### Request Cancellation Testing

**What it does:** Simulates users canceling requests mid-generation.

**Why it matters:**
- Real users close tabs, navigate away, refresh pages
- Cancellations affect resource utilization
- Tests server's graceful handling

**Configuration:**
```bash
--request-cancellation-rate 25.0      # Cancel 25% of requests
--request-cancellation-delay 2.0      # Wait 2 seconds before canceling
```

**How it works:**
1. AIPerf sends request normally
2. After 2 seconds, cancels 25% of requests (randomly selected)
3. Canceled requests use `asyncio.wait_for()` timeout
4. Server should receive cancellation signal
5. Metrics exclude canceled requests

**Use cases:**
- Model user behavior (impatient users)
- Test resource cleanup
- Validate graceful degradation
- Measure impact on non-canceled requests

**Metrics to watch:**
- Do non-canceled requests get faster?
- Does throughput increase?
- Are resources properly released?

**Example:**
```bash
# Baseline without cancellation
aiperf profile --concurrency 20 --request-count 200

# With 50% cancellation after 1 second
aiperf profile --concurrency 20 --request-count 200 \
  --request-cancellation-rate 50 \
  --request-cancellation-delay 1.0

# Compare throughput and latency of completed requests
```

---

### Multi-Modal Benchmarking

**What it supports:**
- Text prompts (always)
- Images (JPEG, PNG, etc.)
- Audio (WAV, MP3, etc.)

**Image benchmarking:**
```json
// Dataset format (JSONL)
{"text": "What's in this image?", "image": "/path/to/image.jpg"}
{"text": "Describe this photo", "image": "data:image/jpeg;base64,..."}
```

**Audio benchmarking:**
```json
// Dataset format (JSONL)
{"text": "Transcribe this audio", "audio": "/path/to/audio.wav"}
```

**Synthetic generation:**
```bash
# Generate random images
--synthetic-image-count-mean 1
--synthetic-image-width-mean 512
--synthetic-image-height-mean 512
--synthetic-image-format jpeg

# Generate random audio
--synthetic-audio-count-mean 1
--synthetic-audio-length-mean 5.0  # 5 seconds
--synthetic-audio-format wav
```

---

### Multiple Models

**What it does:** Benchmark multiple models in a single run.

**Configuration:**
```bash
--model-names model-a,model-b,model-c
--model-selection-strategy round-robin
```

**Selection strategies:**
- `round-robin`: Request 1→model-a, Request 2→model-b, Request 3→model-c, Request 4→model-a...
- `random`: Each request randomly assigned to a model

**Use cases:**
- Compare models fairly (same load pattern)
- A/B/C testing
- Load balancing simulation

**Metrics:**
- Separate metrics for each model
- Aggregated across all models

---

### Warmup Phase

**What it does:** Sends requests before actual benchmarking starts.

**Why it matters:**
- Cold start effects (model loading, cache warming)
- JIT compilation in some frameworks
- Connection pool initialization

**Configuration:**
```bash
--warmup-request-count 10
```

**How it works:**
1. AIPerf sends 10 warmup requests
2. Collects timing data but marks as warmup
3. Starts actual profiling phase
4. Warmup data excluded from final metrics

**Recommendation:**
- Always use 5-10 warmup requests
- More for cold-start testing
- Fewer for quick checks

---

### Custom HTTP Headers

**What it does:** Add authentication, tracing, or custom headers to requests.

**Configuration:**
```bash
# Single header
--header "Authorization:Bearer YOUR_TOKEN"

# Multiple headers
--header "Authorization:Bearer TOKEN" \
--header "X-Custom-Header:value" \
--header "X-Request-ID:benchmark-run-123"

# JSON format
--header '{"Authorization":"Bearer TOKEN","X-Custom":"value"}'
```

**Use cases:**
- Authentication (API keys, tokens)
- Distributed tracing (trace IDs)
- Custom routing (edge cases)
- Feature flags

---

### Extra Input Parameters

**What it does:** Pass additional parameters to the inference API.

**Configuration:**
```bash
# Single parameter
--extra-inputs "temperature:0.7"

# Multiple parameters
--extra-inputs "temperature:0.7" \
--extra-inputs "top_p:0.9" \
--extra-inputs "frequency_penalty:0.5"

# JSON format
--extra-inputs '{"temperature":0.7,"top_p":0.9}'
```

**Common parameters:**
- `temperature`: Sampling randomness (0.0-1.0)
- `top_p`: Nucleus sampling (0.0-1.0)
- `frequency_penalty`: Repetition penalty
- `presence_penalty`: Topic diversity
- `stop`: Stop sequences
- `ignore_eos`: Keep generating even after EOS
- `min_tokens`: Minimum output length

**Example:**
```bash
# Force consistent output lengths
--output-tokens-mean 100 \
--extra-inputs "min_tokens:100" \
--extra-inputs "ignore_eos:true"
```

---

### Kubernetes Deployment

**What it does:** Run AIPerf distributed across Kubernetes pods for massive scale.

**Why use it:**
- Scale beyond single machine limits
- Test distributed inference clusters
- Simulate geographically distributed load
- Achieve higher concurrency

**Configuration:**
```bash
--kubernetes-enable \
--kubernetes-namespace aiperf-benchmark \
--kubernetes-worker-count 10
```

**How it works:**
1. AIPerf creates Kubernetes resources:
   - SystemController pod (orchestrator)
   - Worker pods (send requests)
   - Service pods (dataset, timing, etc.)
2. Pods communicate via ZMQ over TCP
3. Results aggregated to SystemController
4. Cleanup on completion

**Architecture:**
```
                  ┌─────────────────┐
                  │ SystemController│
                  │      Pod        │
                  └────────┬────────┘
                           │
        ┌──────────────────┼──────────────────┐
        │                  │                  │
   ┌────▼────┐        ┌────▼────┐       ┌────▼────┐
   │ Worker  │        │ Worker  │  ...  │ Worker  │
   │  Pod 1  │        │  Pod 2  │       │  Pod N  │
   └─────────┘        └─────────┘       └─────────┘
        │                  │                  │
        └──────────────────┼──────────────────┘
                           │
                      ┌────▼────┐
                      │ Target  │
                      │ Service │
                      └─────────┘
```

**Requirements:**
- Kubernetes cluster access
- `kubectl` configured
- Docker image: `aiperf:latest`
- Sufficient cluster resources

**Advanced options:**
```bash
# Custom Docker image
--kubernetes-image my-registry/aiperf:v1.0

# Resource requests
--kubernetes-worker-cpu 2
--kubernetes-worker-memory 4Gi

# Node affinity (target specific nodes)
--kubernetes-node-selector "gpu:true"
```

---

### Environment Variables

**What it does:** Configure AIPerf via environment variables instead of CLI flags.

**Format:** `AIPERF_<OPTION_NAME>`

**Examples:**
```bash
# Set via environment
export AIPERF_MODEL="Qwen/Qwen3-0.6B"
export AIPERF_URL="http://localhost:8000"
export AIPERF_CONCURRENCY=10
export AIPERF_REQUEST_COUNT=100

# Run without flags
aiperf profile
```

**Use cases:**
- CI/CD pipelines
- Containerized environments
- Secrets management (API keys)
- Default configurations

**Precedence:**
1. CLI flags (highest priority)
2. Environment variables
3. Configuration file
4. Defaults (lowest priority)

---

## Interpreting Results

### Reading the Console Output

After a benchmark completes, AIPerf displays a metrics table:

```
NVIDIA AIPerf | LLM Metrics
┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━┳━━━━━━━┳━━━━━━━┳━━━━━━━┳━━━━━━━┓
┃ Metric                         ┃     avg ┃   min ┃   max ┃   p99 ┃   p90 ┃
┡━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━╇━━━━━━━╇━━━━━━━╇━━━━━━━╇━━━━━━━┩
│ Time to First Token (ms)       │   18.26 │ 11.22 │106.32 │ 68.82 │ 27.76 │
│ Request Latency (ms)           │  487.30 │267.07 │769.57 │715.99 │580.83 │
│ Inter Token Latency (ms)       │   11.23 │  8.80 │ 13.17 │ 12.48 │ 11.73 │
│ Output Token Throughput        │10944.03 │   N/A │   N/A │   N/A │   N/A │
│   (tokens/sec)                 │         │       │       │       │       │
│ Request Throughput             │  255.54 │   N/A │   N/A │   N/A │   N/A │
│   (requests/sec)               │         │       │       │       │       │
│ Output Sequence Length         │   42.83 │ 24.00 │ 65.00 │ 64.00 │ 52.00 │
│   (tokens)                     │         │       │       │       │       │
│ Request Count (requests)       │  711.00 │   N/A │   N/A │   N/A │   N/A │
│ Benchmark Duration (sec)       │    2.78 │   N/A │   N/A │   N/A │   N/A │
└────────────────────────────────┴─────────┴───────┴───────┴───────┴───────┘

CLI Command: aiperf profile --model Qwen/Qwen3-0.6B --url http://localhost:8000 ...
Benchmark Duration: 2.78 sec
JSON Export: /path/to/artifacts/profile_export_aiperf.json
CSV Export: /path/to/artifacts/profile_export_aiperf.csv
Log File: /path/to/artifacts/logs/aiperf.log
```

---

### Interpreting Key Patterns

#### Pattern 1: High TTFT, Low ITL

```
Time to First Token: 500ms (avg)
Inter Token Latency: 10ms (avg)
```

**What it means:**
- Long prefill time (processing the prompt)
- Fast token generation once started

**Likely causes:**
- Large prompt
- Small batch size (prefill not parallelized)
- CPU-bound prefill

**How to improve:**
- Increase batch size for better GPU utilization
- Optimize attention mechanism (FlashAttention)
- Use prompt caching if available

---

#### Pattern 2: Low TTFT, High ITL

```
Time to First Token: 50ms (avg)
Inter Token Latency: 100ms (avg)
```

**What it means:**
- Fast prompt processing
- Slow token generation

**Likely causes:**
- Memory-bound generation
- Small model on powerful GPU (underutilized)
- Inefficient decoding kernel

**How to improve:**
- Increase batch size to saturate GPU
- Check memory bandwidth utilization
- Optimize token generation kernel

---

#### Pattern 3: High Variance in Latency

```
Request Latency: 200ms (avg), 500ms (p99), 100ms (std)
```

**What it means:**
- Inconsistent performance
- Some requests much slower than others

**Likely causes:**
- Queuing effects (request batching)
- Memory allocation spikes
- Garbage collection pauses
- Network variability

**How to investigate:**
- Check latency distribution over time
- Monitor GPU utilization
- Review server logs
- Test with lower concurrency

---

#### Pattern 4: Throughput Plateaus with Increased Concurrency

```
Concurrency=10: 5000 tokens/sec
Concurrency=50: 8000 tokens/sec
Concurrency=100: 8000 tokens/sec (no improvement)
```

**What it means:**
- Hit hardware limit
- GPU fully saturated
- Memory bandwidth maxed out

**What to do:**
- This is your maximum capacity
- Adding concurrency beyond this hurts latency without improving throughput
- To scale further: add more GPUs or optimize model

---

### Exported Files

#### JSON Export

**Location:** `artifacts/<run-name>/profile_export_aiperf.json`

**Contents:**
```json
{
  "input_config": {
    "endpoint": { "model_names": ["Qwen/Qwen3-0.6B"], ... },
    "loadgen": { "concurrency": 10, ... },
    ...
  },
  "records": {
    "ttft": {
      "tag": "ttft",
      "avg": 18.26,
      "min": 11.22,
      "max": 106.32,
      "p50": 15.34,
      "p90": 27.76,
      "p95": 45.21,
      "p99": 68.82,
      "std": 12.07,
      "unit": "ms"
    },
    ...
  },
  "error_summary": [
    {
      "type": "TimeoutError",
      "message": "Request timeout after 600s",
      "count": 2
    }
  ],
  "was_cancelled": false,
  "start_time": "2025-10-03T10:30:00.000Z",
  "end_time": "2025-10-03T10:32:18.780Z"
}
```

**Use cases:**
- Programmatic analysis
- Automated reporting
- Time-series tracking
- CI/CD integration

---

#### CSV Export

**Location:** `artifacts/<run-name>/profile_export_aiperf.csv`

**Format:**
```csv
Metric,avg,min,max,p99,p90,p75,std
Time to First Token (ms),18.26,11.22,106.32,68.82,27.76,16.62,12.07
Request Latency (ms),487.30,267.07,769.57,715.99,580.83,536.17,79.60
...

Metric,Value
Output Token Throughput (tokens/sec),10944.03
Request Throughput (requests/sec),255.54
...
```

**Use cases:**
- Excel/spreadsheet analysis
- Plotting tools
- Data science notebooks
- Quick inspection

---

### Comparing Results

**Method 1: Side-by-side JSON comparison**

```python
import json

with open('artifacts/run-a/profile_export_aiperf.json') as f:
    run_a = json.load(f)
with open('artifacts/run-b/profile_export_aiperf.json') as f:
    run_b = json.load(f)

# Compare TTFT
ttft_a = run_a['records']['ttft']['avg']
ttft_b = run_b['records']['ttft']['avg']
improvement = ((ttft_a - ttft_b) / ttft_a) * 100
print(f"TTFT improvement: {improvement:.1f}%")
```

**Method 2: CSV in spreadsheet**

1. Open both CSV files in Excel/Sheets
2. Create comparison table
3. Calculate percentage differences
4. Generate charts

**Method 3: Time-series tracking**

```python
import pandas as pd
import matplotlib.pyplot as plt

# Track metrics over multiple runs
runs = []
for run_dir in sorted(Path('artifacts').iterdir()):
    with open(run_dir / 'profile_export_aiperf.json') as f:
        data = json.load(f)
        runs.append({
            'timestamp': data['start_time'],
            'ttft_p99': data['records']['ttft']['p99'],
            'throughput': data['records']['output_token_throughput']['avg']
        })

df = pd.DataFrame(runs)
df.plot(x='timestamp', y=['ttft_p99', 'throughput'])
plt.show()
```

---

## Troubleshooting

### Common Issues

#### Issue: "Connection refused"

**Symptoms:**
```
Error: Error connecting to http://localhost:8000
```

**Causes:**
- Server not running
- Wrong URL/port
- Firewall blocking connection

**Solutions:**
1. Verify server is running:
   ```bash
   curl http://localhost:8000/v1/models
   ```

2. Check server logs for errors

3. Try different URL:
   ```bash
   --url http://127.0.0.1:8000
   ```

4. Verify endpoint path:
   ```bash
   --custom-endpoint /v1/chat/completions
   ```

---

#### Issue: "Request timeout"

**Symptoms:**
```
Error Request Count: 45
Error: TimeoutError: Request timeout after 600s
```

**Causes:**
- Server overloaded
- Request timeout too short
- Model too slow for workload

**Solutions:**
1. Increase timeout:
   ```bash
   --request-timeout-seconds 1200  # 20 minutes
   ```

2. Reduce load:
   ```bash
   --concurrency 5  # Lower concurrency
   --output-tokens-mean 50  # Shorter outputs
   ```

3. Check server capacity:
   - Monitor GPU utilization
   - Check memory usage
   - Review server logs

---

#### Issue: "Out of memory" on server

**Symptoms:**
- Server crashes during benchmark
- "CUDA out of memory" errors
- Requests start failing mid-run

**Causes:**
- Batch size too large
- Prompt + output too long
- Memory leak

**Solutions:**
1. Reduce concurrency:
   ```bash
   --concurrency 5  # Start low
   ```

2. Shorter sequences:
   ```bash
   --synthetic-input-tokens-mean 200
   --output-tokens-mean 100
   ```

3. Check server configuration:
   - Max batch size
   - KV cache size
   - GPU memory allocation

---

#### Issue: "Port exhaustion"

**Symptoms:**
```
Error: Cannot create connection
OSError: [Errno 24] Too many open files
```

**Causes:**
- Very high concurrency (>10,000)
- System file descriptor limit
- Connection pool exhaustion

**Solutions:**
1. Increase file descriptor limit:
   ```bash
   ulimit -n 65536
   ```

2. Reduce concurrency:
   ```bash
   --concurrency 1000  # Lower value
   ```

3. Use request rate instead:
   ```bash
   --request-rate 500  # Controlled rate
   ```

---

#### Issue: "Invalid JSON in response"

**Symptoms:**
```
Error parsing response
JSONDecodeError: Expecting value: line 1 column 1
```

**Causes:**
- Server returned non-JSON
- Streaming mode mismatch
- Partial response

**Solutions:**
1. Verify endpoint supports your mode:
   ```bash
   # Try without streaming
   aiperf profile ... (remove --streaming)
   ```

2. Check server compatibility:
   ```bash
   curl -X POST http://localhost:8000/v1/chat/completions \
     -H "Content-Type: application/json" \
     -d '{"model":"your-model","messages":[{"role":"user","content":"test"}]}'
   ```

3. Review server logs for errors

---

#### Issue: "AIPerf hangs/freezes"

**Symptoms:**
- No progress after initialization
- UI stops updating
- Process doesn't respond

**Causes:**
- Invalid configuration
- Service startup failure
- Deadlock in communication

**Solutions:**
1. Check logs:
   ```bash
   tail -f artifacts/logs/aiperf.log
   ```

2. Enable verbose logging:
   ```bash
   --verbose
   ```

3. Try simpler configuration:
   ```bash
   aiperf profile \
     --model test \
     --url http://localhost:8000 \
     --endpoint-type chat \
     --request-count 10
   ```

4. If frozen, `Ctrl+C` to cancel, check for error messages

---

### Debugging Tips

**Enable verbose logging:**
```bash
--verbose  # Debug level
# or
--extra-verbose  # Trace level (very detailed)
```

**Check log file:**
```bash
cat artifacts/logs/aiperf.log
```

**Test connectivity manually:**
```bash
# Test basic connection
curl http://localhost:8000/v1/models

# Test chat endpoint
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "your-model",
    "messages": [{"role": "user", "content": "Hello"}],
    "max_tokens": 10
  }'
```

**Validate dataset:**
```bash
# Check JSON format
head -n 5 my_dataset.jsonl | python -m json.tool

# Test with small sample
--request-count 5
```

**Isolate issues:**
```bash
# Minimal configuration
aiperf profile --model test --url localhost:8000 --endpoint-type chat --request-count 1

# Add features incrementally
# ... + --streaming
# ... + --concurrency 10
# ... + --input-file dataset.jsonl
```

---

## Best Practices

### 1. Always Use Warmup

**Why:**
- Eliminates cold-start effects
- Primes caches and models
- Initializes connection pools

**Recommendation:**
```bash
--warmup-request-count 10  # Minimum
--warmup-request-count 50  # For large models
```

---

### 2. Match Production Characteristics

**Why:**
- Realistic performance predictions
- Identify actual bottlenecks
- Valid SLA validation

**How:**
```bash
# Analyze production traffic
# - Average prompt length: 450 tokens
# - Average output length: 200 tokens
# - Request rate: 50 req/sec during peak

# Configure AIPerf to match
--synthetic-input-tokens-mean 450 \
--synthetic-input-tokens-stddev 50 \
--output-tokens-mean 200 \
--output-tokens-stddev 20 \
--request-rate 50
```

---

### 3. Use Reproducible Settings

**Why:**
- Compare results across runs
- Debug regressions
- Share benchmarks with team

**How:**
```bash
--random-seed 42  # Same synthetic data every time
--input-file dataset.jsonl  # Fixed dataset
```

---

### 4. Test Multiple Scenarios

**Why:**
- Single scenario doesn't show full picture
- Different workloads stress different components
- Find edge cases and limits

**Scenarios to test:**

```bash
# 1. Minimum latency (single request)
aiperf profile --concurrency 1 ...

# 2. Maximum throughput (high concurrency)
aiperf profile --concurrency 100 ...

# 3. Expected production load
aiperf profile --request-rate 50 ...

# 4. Stress test (find breaking point)
aiperf profile --concurrency 500 ...

# 5. Sustained performance
aiperf profile --benchmark-duration 300 ...
```

---

### 5. Focus on Percentiles, Not Averages

**Why:**
- Averages hide outliers
- Real users experience the tail
- SLAs based on percentiles

**What to use:**
- p50: Typical experience
- p95: SLA target
- p99: Worst acceptable case

**Example:**
```
TTFT: 20ms (avg), 150ms (p99)
```
This means 99% of users wait < 150ms, but average is misleading.

---

### 6. Monitor Server-Side Metrics Too

**Why:**
- Understand bottlenecks
- Validate measurements
- Debug performance issues

**Server metrics to track:**
- GPU utilization
- GPU memory usage
- CPU usage
- Network bandwidth
- Queue depths
- Batch sizes

**Tools:**
- `nvidia-smi` (GPU stats)
- `htop` (CPU/memory)
- Server framework metrics (vLLM stats, etc.)

---

### 7. Iterate on Configuration

**Why:**
- Find optimal settings
- Understand trade-offs
- Validate assumptions

**Process:**
```bash
# Start simple
aiperf profile --concurrency 10 ...

# Analyze results
# - Low GPU utilization? Increase concurrency
# - High latency p99? Reduce concurrency
# - Want more throughput? Increase batch size

# Test hypothesis
aiperf profile --concurrency 25 ...

# Compare results, repeat
```

---

### 8. Document Your Benchmarks

**Why:**
- Reproduce results later
- Share with team
- Track changes over time

**What to save:**
```bash
# Save full command
echo "aiperf profile --model ... " > benchmark_notes.txt

# Save configuration
--output-artifact-dir artifacts/$(date +%Y%m%d-%H%M%S)-description

# Export results
cp artifacts/latest/profile_export_aiperf.json results/baseline.json
```

---

### 9. Understand Your Hardware

**Why:**
- Set realistic expectations
- Identify bottlenecks
- Choose appropriate configs

**Key factors:**
- GPU model and memory
- Number of GPUs
- CPU cores and memory
- Network bandwidth
- Storage speed (for model loading)

**Example:**
```
Single A100 (80GB):
- Max throughput: ~10,000 tokens/sec (7B model)
- Max concurrency: ~500 (depends on sequence lengths)
- TTFT: 20-100ms (depends on prompt length)
```

---

### 10. Validate Before Deploying

**Why:**
- Avoid production surprises
- Ensure SLA compliance
- Identify issues early

**Pre-deployment checklist:**

- [ ] Baseline performance measured
- [ ] Maximum throughput determined
- [ ] Latency p95/p99 acceptable
- [ ] Tested at 2x expected load
- [ ] Zero errors under normal load
- [ ] < 1% errors under stress
- [ ] Sustained performance validated (30+ min run)
- [ ] Warmup time acceptable
- [ ] Memory usage stable
- [ ] Request cancellation handled gracefully

---

## Summary

### Quick Reference Card

**Common Commands:**

```bash
# Quick performance check
aiperf profile --model MODEL --url URL --endpoint-type chat --streaming --concurrency 10 --request-count 100

# Find maximum throughput
aiperf profile --model MODEL --url URL --endpoint-type chat --streaming --concurrency 100 --request-count 500

# Production validation
aiperf profile --model MODEL --url URL --endpoint-type chat --streaming --request-rate 50 --benchmark-duration 300

# Custom dataset
aiperf profile --model MODEL --url URL --endpoint-type chat --streaming --input-file data.jsonl --custom-dataset-type single_turn

# Stress test
aiperf profile --model MODEL --url URL --endpoint-type chat --streaming --concurrency 500 --request-count 1000
```

**Key Metrics:**

| Metric | What It Measures | Good Value |
|--------|------------------|------------|
| TTFT | Perceived responsiveness | < 100ms |
| Request Latency | Total response time | < 5s |
| ITL | Generation smoothness | < 20ms |
| Output Token Throughput | System capacity | Depends on HW |
| Error Count | Reliability | 0 errors |

**Decision Tree:**

```
What do you want to know?
├─ "Is my model fast?" → Use concurrency=1, measure TTFT and latency
├─ "How much load can it handle?" → Use high concurrency, measure throughput
├─ "Will it meet SLAs?" → Use expected request rate, check p95/p99
├─ "Which config is better?" → Test both with same dataset and random seed
└─ "When does it break?" → Gradually increase load until errors appear
```

---

## Getting Help

- **Documentation**: https://github.com/ai-dynamo/aiperf
- **CLI Help**: `aiperf profile --help`
- **Issues**: Report bugs on GitHub Issues
- **Discord**: Join community discussions

---

**Happy Benchmarking! 🚀**

