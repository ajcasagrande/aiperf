<!--
# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
-->
# AIPerf Metrics Reference

Complete reference of all built-in metrics with formulas, units, and interpretation guidance.

## Latency Metrics

All latency metrics measure time intervals with nanosecond precision internally, displayed in milliseconds.

### Time to First Token (TTFT)

**Tag**: `ttft`
**Type**: Record Metric
**Unit**: Milliseconds (ms)
**Applies To**: Streaming endpoints only
**Direction**: Lower is better

**Formula**:
```
TTFT = timestamp_first_response - timestamp_request_start
```

**Interpretation**:
- Measures prefill/prompt processing time
- Includes model loading time on first request
- Critical for user-perceived responsiveness
- Typical values: 10-500ms depending on model size and prompt length

**Optimization**:
- Reduce input token count
- Use smaller models
- Enable Flash Attention
- Optimize batch size

---

### Time to Second Token (TTST)

**Tag**: `ttst`
**Type**: Record Metric
**Unit**: Milliseconds (ms)
**Applies To**: Streaming endpoints only
**Direction**: Lower is better

**Formula**:
```
TTST = timestamp_second_response - timestamp_request_start
```

**Interpretation**:
- Measures time until decode starts
- Useful for understanding prefill + first decode latency
- Should be close to TTFT + one ITL

---

### Inter-Token Latency (ITL)

**Tag**: `inter_token_latency`
**Type**: Record Metric
**Unit**: Milliseconds (ms)
**Applies To**: Streaming endpoints only
**Direction**: Lower is better

**Formula**:
```
intervals = [resp[i+1].timestamp - resp[i].timestamp for i in range(len(responses)-1)]
ITL = mean(intervals)
```

**Interpretation**:
- Measures decode speed (tokens per second = 1000/ITL)
- Should be consistent across tokens
- High variance indicates performance instability

**Optimization**:
- Use quantization
- Enable continuous batching
- Optimize decode kernels
- Check GPU utilization

---

### Request Latency

**Tag**: `request_latency`
**Type**: Record Metric
**Unit**: Milliseconds (ms)
**Applies To**: All endpoints
**Direction**: Lower is better

**Formula**:
```
Request Latency = timestamp_final_response - timestamp_request_start
```

**Interpretation**:
- Total end-to-end time
- Includes network, prefill, and all decode time
- Used for SLA validation

---

## Throughput Metrics

### Request Throughput

**Tag**: `request_throughput`
**Type**: Derived Metric
**Unit**: Requests per second (req/s)
**Applies To**: All endpoints
**Direction**: Higher is better

**Formula**:
```
Request Throughput = valid_request_count / benchmark_duration
```

**Interpretation**:
- Overall system throughput
- Includes time between requests
- Lower than request rate if system can't keep up

---

### Output Token Throughput

**Tag**: `output_token_throughput`
**Type**: Derived Metric
**Unit**: Tokens per second (tokens/s)
**Applies To**: Token-producing endpoints
**Direction**: Higher is better

**Formula**:
```
Output Token Throughput = total_output_tokens / benchmark_duration
```

**Interpretation**:
- Aggregate token generation rate
- Key metric for batch inference efficiency
- Scales with concurrency up to GPU saturation

---

### Output Token Throughput Per User

**Tag**: `output_token_throughput_per_user`
**Type**: Record Metric
**Unit**: Tokens per second per user (tokens/s/user)
**Applies To**: Streaming, token-producing endpoints
**Direction**: Higher is better

**Formula**:
```
Output TPS Per User = output_token_count / (request_latency - ttft)
```

For streaming: Equivalent to `1000 / ITL`

**Interpretation**:
- Per-request generation speed
- Independent of system load
- Measures decode efficiency

---

## Token Count Metrics

### Input Sequence Length

**Tag**: `input_sequence_length`
**Type**: Record Metric
**Unit**: Tokens
**Direction**: Neutral (depends on use case)

**Interpretation**:
- Actual input prompt length
- Affects TTFT (longer input = longer prefill)
- Affects GPU memory usage

---

### Output Sequence Length

**Tag**: `output_sequence_length`
**Type**: Record Metric
**Unit**: Tokens
**Direction**: Neutral (depends on use case)

**Interpretation**:
- Total output tokens (including reasoning if applicable)
- Affects request latency
- Affects GPU memory usage

---

### Output Token Count

**Tag**: `output_token_count`
**Type**: Record Metric
**Unit**: Tokens
**Direction**: Neutral

**Interpretation**:
- Output tokens excluding reasoning tokens
- Used for billing calculations
- Used for throughput calculations

---

### Reasoning Token Count

**Tag**: `reasoning_token_count`
**Type**: Record Metric
**Unit**: Tokens
**Direction**: Neutral

**Interpretation**:
- Reasoning tokens for models with chain-of-thought
- Excluded from output token count
- Useful for reasoning model analysis

---

## Count Metrics

### Request Count

**Tag**: `request_count`
**Type**: Aggregate Counter Metric
**Unit**: Requests
**Direction**: Higher is better

**Interpretation**:
- Total valid (non-error) requests
- Used in throughput calculations
- Excludes cancelled and failed requests

---

### Error Request Count

**Tag**: `error_request_count`
**Type**: Aggregate Counter Metric
**Unit**: Requests
**Direction**: Lower is better

**Interpretation**:
- Total failed requests
- Includes timeouts, cancellations, HTTP errors
- Check error summary for breakdown

---

### Good Request Count

**Tag**: `good_request_count`
**Type**: Aggregate Counter Metric
**Unit**: Requests
**Applies To**: When goodput SLOs are configured
**Direction**: Higher is better

**Interpretation**:
- Requests meeting ALL configured SLOs
- Used in goodput calculation
- Ratio to request_count indicates SLO compliance rate

---

## Specialized Metrics

### Goodput

**Tag**: `goodput`
**Type**: Derived Metric
**Unit**: Requests per second (req/s)
**Applies To**: When goodput SLOs are configured
**Direction**: Higher is better

**Formula**:
```
Goodput = good_request_count / benchmark_duration
```

**Interpretation**:
- Rate of requests meeting SLO targets
- More meaningful than raw throughput for SLA validation
- Goodput < Request Throughput indicates SLO violations

**Configuration**:
```bash
--goodput ttft:100 --goodput request_latency:500
```

---

### Benchmark Duration

**Tag**: `benchmark_duration`
**Type**: Derived Metric
**Unit**: Seconds (s)
**Direction**: Neutral

**Formula**:
```
Benchmark Duration = max_response_timestamp - min_request_timestamp
```

**Interpretation**:
- Actual profiling duration
- May differ from configured duration due to grace period
- Used in throughput calculations

---

## Statistics Explained

AIPerf reports comprehensive statistics for each metric:

| Statistic | Symbol | Description |
|-----------|--------|-------------|
| **Average** | avg | Mean value across all requests |
| **Minimum** | min | Best (lowest) value observed |
| **Maximum** | max | Worst (highest) value observed |
| **1st Percentile** | p1 | 1% of requests were better than this |
| **50th Percentile** | p50 | Median value (half better, half worse) |
| **90th Percentile** | p90 | 90% of requests were better than this |
| **99th Percentile** | p99 | 99% of requests were better than this (SLA threshold) |
| **Standard Deviation** | std | Measure of variability/consistency |

### Interpreting Percentiles

**p50 (Median)**:
- Typical user experience
- Not affected by outliers
- Good baseline metric

**p90**:
- 90% of users get this performance or better
- Reasonable SLA target

**p99**:
- 99% of users get this performance or better
- Common SLA target for customer-facing services
- Captures tail latency

**p99 vs Average**:
- Large difference indicates inconsistent performance
- Investigate causes of high p99 values

## Metric Flags

Metrics have flags controlling when they're computed:

| Flag | Description |
|------|-------------|
| `STREAMING_ONLY` | Only for streaming endpoints (e.g., TTFT, ITL) |
| `PRODUCES_TOKENS_ONLY` | Only for token-producing endpoints (exclude embeddings) |
| `ERROR_ONLY` | Only for error requests |
| `NO_CONSOLE` | Hidden from console output (internal use) |
| `LARGER_IS_BETTER` | Higher values are better (throughput, counts) |
| `EXPERIMENTAL` | Experimental metric (may change) |

## Using Metrics in Analysis

### Identify Bottlenecks

```
High TTFT, Low ITL → Prefill bottleneck (increase batch size)
Low TTFT, High ITL → Decode bottleneck (optimize kernels)
High p99 vs avg → Variance issue (check GPU scheduling)
```

### Capacity Planning

```
Request Throughput = achievable sustained load
Output Token Throughput = billing/cost estimation
p99 Latency = SLA target for customer guarantees
```

### Performance Comparison

```
# Export to JSON for analysis
# Results in <artifact-dir>/profile_results.json

# Compare metrics across configurations
# Look at: TTFT, ITL, throughput, p99 values
```

## See Also

- **[Complete Metrics System](../guidebook/chapter-20-metrics-foundation.md)** - Architecture and internals
- **[Custom Metrics](../guidebook/chapter-44-custom-metrics-development.md)** - Creating your own
- **[Record Metrics](../guidebook/chapter-21-record-metrics.md)** - Per-request metrics deep dive
- **[Aggregate/Derived Metrics](../guidebook/chapter-22-aggregate-derived-metrics.md)** - Computed metrics
