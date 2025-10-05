# Chapter 42: Performance Profiling

<!--
# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
-->

## Overview

This chapter covers performance profiling and optimization strategies for AIPerf. Learn how to analyze performance bottlenecks, optimize resource usage, and maximize benchmarking throughput. Whether you're optimizing AIPerf itself or analyzing benchmark performance, this chapter provides the tools and techniques you need.

## Table of Contents

- [Understanding Performance](#understanding-performance)
- [Profiling Tools](#profiling-tools)
- [CPU Profiling](#cpu-profiling)
- [Memory Profiling](#memory-profiling)
- [I/O Profiling](#io-profiling)
- [Async Performance](#async-performance)
- [Network Performance](#network-performance)
- [Benchmark Performance Analysis](#benchmark-performance-analysis)
- [Optimization Strategies](#optimization-strategies)
- [Performance Testing](#performance-testing)
- [Benchmarking AIPerf Itself](#benchmarking-aiperf-itself)
- [Best Practices](#best-practices)

---

## Understanding Performance

### Performance Dimensions

**AIPerf Performance Metrics:**

1. **Throughput**: Requests processed per second
2. **Latency**: Time to complete individual requests
3. **Resource Usage**: CPU, memory, network utilization
4. **Scalability**: Performance with increasing load
5. **Efficiency**: Resource usage per request

### Performance Goals

**Different Perspectives:**

```
┌─────────────────────────────────────────────────────────────┐
│                    Performance Goals                         │
├─────────────────────────────────────────────────────────────┤
│ AIPerf Developer:                                            │
│   - Minimize overhead                                        │
│   - Maximize throughput                                      │
│   - Efficient resource usage                                 │
│                                                              │
│ Benchmark User:                                              │
│   - Accurate measurements                                    │
│   - Consistent results                                       │
│   - Minimal impact on target system                          │
│                                                              │
│ System Administrator:                                        │
│   - Predictable resource consumption                         │
│   - Stable under load                                        │
│   - Efficient multi-tenant usage                             │
└─────────────────────────────────────────────────────────────┘
```

### Performance Baseline

**Establish Baseline:**
```bash
# Minimal overhead test
aiperf profile \
  --model test \
  --url http://localhost:8000 \
  --endpoint-type chat \
  --request-count 1000 \
  --concurrency 10 \
  --ui none \
  --output-file baseline.json
```

**Key Baseline Metrics:**
- Cold start time
- Warm start time
- Request processing rate
- Memory footprint
- Network bandwidth usage

---

## Profiling Tools

### Python Profilers

**1. cProfile (Standard Library)**

Built-in profiler for function-level performance:

```bash
# Profile AIPerf execution
python -m cProfile -o aiperf.prof -m aiperf.cli profile \
  --model Qwen/Qwen3-0.6B \
  --url http://localhost:8000 \
  --endpoint-type chat \
  --request-count 100

# Analyze results
python -m pstats aiperf.prof
```

**Interactive Analysis:**
```python
import pstats

# Load profile
p = pstats.Stats('aiperf.prof')

# Sort by cumulative time
p.sort_stats('cumulative')
p.print_stats(20)

# Sort by internal time
p.sort_stats('time')
p.print_stats(20)

# Filter by module
p.print_stats('aiperf')

# Show callers
p.print_callers(20)
```

**2. line_profiler**

Line-by-line profiling:

```bash
# Install
pip install line_profiler

# Decorate functions to profile
```

```python
# In source code: /home/anthony/nvidia/projects/aiperf/aiperf/workers/inference_worker.py
@profile  # line_profiler decorator
async def process_request(self, request):
    # Function implementation
    pass
```

```bash
# Run profiler
kernprof -l -v aiperf/cli.py profile [options...]
```

**Output Example:**
```
Line #  Hits    Time    Per Hit   % Time  Line Contents
===========================================================
    42                                      @profile
    43                                      async def process_request(self, request):
    44  1000    250.0    0.3       2.5         payload = await format_request(request)
    45  1000   8500.0    8.5      85.0        response = await send_request(payload)
    46  1000   1250.0    1.3      12.5        return parse_response(response)
```

**3. py-spy**

Low-overhead sampling profiler (no code changes needed):

```bash
# Install
pip install py-spy

# Record profile
py-spy record -o profile.svg -- python -m aiperf.cli profile [options...]

# Top view (real-time)
py-spy top --pid $(pgrep -f aiperf)

# Dump current stack
py-spy dump --pid $(pgrep -f aiperf)
```

**Flame Graph:**
```bash
# Generate interactive flame graph
py-spy record -o profile.svg --format speedscope -- \
  python -m aiperf.cli profile [options...]

# Open in browser
firefox profile.svg
```

**4. scalene**

Combined CPU, memory, and GPU profiler:

```bash
# Install
pip install scalene

# Profile with all metrics
scalene aiperf/cli.py profile [options...]

# HTML report
scalene --html --outfile profile.html aiperf/cli.py profile [options...]
```

### Visualization Tools

**snakeviz** - Interactive cProfile viewer:

```bash
# Install
pip install snakeviz

# Visualize profile
snakeviz aiperf.prof
```

**gprof2dot** - Call graph visualization:

```bash
# Install
pip install gprof2dot

# Generate graph
gprof2dot -f pstats aiperf.prof | dot -Tpng -o callgraph.png
```

---

## CPU Profiling

### Identify CPU Bottlenecks

**Hot Path Analysis:**
```bash
# Profile with cProfile
python -m cProfile -o cpu.prof -s cumulative -m aiperf.cli profile [options...]

# Analyze hot functions
python -c "
import pstats
p = pstats.Stats('cpu.prof')
p.sort_stats('cumulative').print_stats(10)
"
```

**Common CPU Bottlenecks:**

1. **Metric Computation**: Heavy mathematical operations
2. **Serialization**: JSON encoding/decoding
3. **Logging**: Excessive string formatting
4. **Request Formatting**: Payload construction

### CPU Profiling Example

**Profile Metric Computation:**

```python
import cProfile
import pstats
from aiperf.metrics.metric_registry import MetricRegistry
from aiperf.common.models import ParsedResponseRecord

# Create test data
records = [
    ParsedResponseRecord(
        request_start_time=0.0,
        request_end_time=1.0,
        valid=True,
        input_token_count=100,
        output_token_count=200
    )
    for _ in range(1000)
]

# Profile metric computation
profiler = cProfile.Profile()
profiler.enable()

for tag in MetricRegistry.all_tags():
    metric = MetricRegistry.get_instance(tag)
    try:
        for record in records:
            value = metric._parse_record(record, {})
    except:
        pass

profiler.disable()

# Print results
stats = pstats.Stats(profiler)
stats.sort_stats('cumulative')
stats.print_stats(20)
```

### Optimization: Lazy Evaluation

**Before:**
```python
# Always formats string
self.debug(f"Processing record {record.id} with {len(record.tokens)} tokens")
```

**After:**
```python
# Only formats if DEBUG enabled
self.debug(lambda: f"Processing record {record.id} with {len(record.tokens)} tokens")
```

**Benchmark:**
```python
import time

# Without lazy evaluation
start = time.time()
for i in range(100000):
    # logger.debug disabled, but still formats
    msg = f"Iteration {i}"
elapsed = time.time() - start
print(f"Without lazy: {elapsed:.3f}s")

# With lazy evaluation
start = time.time()
for i in range(100000):
    # Never formats the string
    msg = lambda i=i: f"Iteration {i}"
elapsed = time.time() - start
print(f"With lazy: {elapsed:.3f}s")
```

---

## Memory Profiling

### Memory Usage Analysis

**memory_profiler** - Line-by-line memory usage:

```bash
# Install
pip install memory_profiler

# Decorate function
```

```python
from memory_profiler import profile

@profile
def create_dataset(config):
    # Function implementation
    pass
```

```bash
# Run profiler
python -m memory_profiler aiperf/cli.py profile [options...]
```

**Output:**
```
Line #    Mem usage    Increment  Occurrences   Line Contents
=============================================================
    10    125.0 MiB    125.0 MiB           1   @profile
    11                                         def create_dataset(config):
    12    250.0 MiB    125.0 MiB           1       data = load_large_file()
    13    375.0 MiB    125.0 MiB           1       processed = process_data(data)
    14    375.0 MiB      0.0 MiB           1       return processed
```

### Memory Leak Detection

**tracemalloc** (Standard Library):

```python
import tracemalloc
import time

# Start tracing
tracemalloc.start()

# Take initial snapshot
snapshot1 = tracemalloc.take_snapshot()

# Run benchmark
run_system_controller(user_config, service_config)

# Take final snapshot
snapshot2 = tracemalloc.take_snapshot()

# Compare snapshots
top_stats = snapshot2.compare_to(snapshot1, 'lineno')

print("Top 10 memory increases:")
for stat in top_stats[:10]:
    print(stat)
```

**Output:**
```
/home/anthony/nvidia/projects/aiperf/aiperf/workers/inference_worker.py:42:
  size=1.2 MiB (+1.2 MiB), count=1000 (+1000), average=1.2 KiB
```

### Memory Optimization

**1. Generator Usage:**

**Before (List):**
```python
def process_records(records: list) -> list:
    results = []
    for record in records:
        results.append(compute_metric(record))
    return results
```

**After (Generator):**
```python
def process_records(records: list) -> Iterator:
    for record in records:
        yield compute_metric(record)
```

**2. Object Pooling:**

```python
from collections import deque

class ObjectPool:
    def __init__(self, factory, max_size=100):
        self.factory = factory
        self.pool = deque(maxlen=max_size)

    def acquire(self):
        return self.pool.pop() if self.pool else self.factory()

    def release(self, obj):
        self.pool.append(obj)

# Usage
request_pool = ObjectPool(lambda: InferenceRequest())

# Acquire from pool
request = request_pool.acquire()
# ... use request ...
request_pool.release(request)
```

**3. Weak References:**

```python
import weakref

class MetricCache:
    def __init__(self):
        self._cache = weakref.WeakValueDictionary()

    def get(self, key):
        return self._cache.get(key)

    def set(self, key, value):
        self._cache[key] = value
```

### Memory Profiling Tools

**objgraph** - Object graph analysis:

```bash
pip install objgraph
```

```python
import objgraph

# Show most common types
objgraph.show_most_common_types(limit=10)

# Show growth between snapshots
objgraph.show_growth(limit=10)

# Find backreferences
objgraph.show_backrefs(obj, max_depth=3)
```

**pympler** - Memory usage tracking:

```bash
pip install pympler
```

```python
from pympler import asizeof, tracker

# Size of object
size = asizeof.asizeof(large_object)
print(f"Object size: {size / 1024 / 1024:.2f} MB")

# Track memory usage
tr = tracker.SummaryTracker()

# ... run code ...

tr.print_diff()
```

---

## I/O Profiling

### File I/O Performance

**Profile File Operations:**

```python
import time

def profile_file_io(filename, iterations=100):
    # Read performance
    start = time.time()
    for _ in range(iterations):
        with open(filename, 'r') as f:
            data = f.read()
    read_time = time.time() - start
    print(f"Read: {read_time:.3f}s ({iterations/read_time:.1f} ops/sec)")

    # Write performance
    start = time.time()
    for i in range(iterations):
        with open(f'test_{i}.json', 'w') as f:
            f.write(data)
    write_time = time.time() - start
    print(f"Write: {write_time:.3f}s ({iterations/write_time:.1f} ops/sec)")
```

**Optimization: Buffered I/O**

```python
# Default buffering
with open('data.json', 'r') as f:
    data = f.read()

# Custom buffer size
with open('data.json', 'r', buffering=1024*1024) as f:
    data = f.read()

# Line buffering for logs
with open('output.log', 'w', buffering=1) as f:
    f.write(log_message)
```

### Dataset Loading Performance

**Profile Custom Dataset Loading:**

```python
import time
from aiperf.dataset.loader import SingleTurnLoader

# Profile loading
start = time.time()
loader = SingleTurnLoader(filename='dataset.jsonl')
dataset = loader.load_dataset()
load_time = time.time() - start

print(f"Loaded {len(dataset)} records in {load_time:.3f}s")
print(f"Rate: {len(dataset)/load_time:.1f} records/sec")

# Memory usage
import sys
dataset_size = sys.getsizeof(dataset) / 1024 / 1024
print(f"Dataset size: {dataset_size:.2f} MB")
```

**Optimization: Streaming Loading**

```python
from typing import Iterator

def load_dataset_streaming(filename: str) -> Iterator:
    """Load dataset line by line instead of all at once"""
    with open(filename, 'r') as f:
        for line in f:
            yield parse_line(line)

# Usage
for record in load_dataset_streaming('large_dataset.jsonl'):
    process_record(record)
```

---

## Async Performance

### Async Profiling

**aiomonitor** - Real-time async monitoring:

```bash
pip install aiomonitor
```

```python
import asyncio
import aiomonitor

async def main():
    with aiomonitor.start_monitor(loop=asyncio.get_event_loop()):
        await run_benchmark()

asyncio.run(main())
```

**Access console:**
```bash
# Connect to monitoring console
nc localhost 50101

# Available commands:
# ps - list tasks
# where <task_id> - show task stack
# signal <task_id> - send signal
# cancel <task_id> - cancel task
```

### Detect Blocking Code

**Identify Blocking Operations:**

```python
import asyncio
import warnings

# Enable debug mode
asyncio.run(main(), debug=True)
```

**Output:**
```
/path/to/file.py:42: RuntimeWarning: coroutine 'slow_function' took 0.250 seconds
```

**Profile Async Functions:**

```python
import asyncio
import time
from functools import wraps

def async_profile(func):
    @wraps(func)
    async def wrapper(*args, **kwargs):
        start = time.time()
        result = await func(*args, **kwargs)
        elapsed = time.time() - start
        print(f"{func.__name__}: {elapsed:.3f}s")
        return result
    return wrapper

@async_profile
async def process_request(request):
    # Implementation
    pass
```

### Async Performance Patterns

**Pattern 1: Concurrent Requests**

```python
# Bad: Sequential requests
async def send_requests_sequential(requests):
    results = []
    for request in requests:
        result = await send_request(request)
        results.append(result)
    return results

# Good: Concurrent requests
async def send_requests_concurrent(requests):
    tasks = [send_request(req) for req in requests]
    return await asyncio.gather(*tasks)
```

**Benchmark:**
```python
import asyncio
import time

# Sequential: 10 requests × 0.1s = 1.0s
start = time.time()
results = await send_requests_sequential(requests)
print(f"Sequential: {time.time() - start:.3f}s")

# Concurrent: max(0.1s) = 0.1s
start = time.time()
results = await send_requests_concurrent(requests)
print(f"Concurrent: {time.time() - start:.3f}s")
```

**Pattern 2: Semaphore for Concurrency Control**

```python
async def bounded_send_requests(requests, max_concurrent=100):
    semaphore = asyncio.Semaphore(max_concurrent)

    async def send_with_semaphore(request):
        async with semaphore:
            return await send_request(request)

    tasks = [send_with_semaphore(req) for req in requests]
    return await asyncio.gather(*tasks)
```

---

## Network Performance

### HTTP Client Performance

**Profile Request Latency:**

```python
import time
import asyncio
from aiperf.clients.http.aiohttp_client import AIOHttpClient

async def profile_http_client(url, num_requests=100):
    client = AIOHttpClient(url)

    latencies = []
    for _ in range(num_requests):
        start = time.time()
        response = await client.post("/v1/chat/completions", json={...})
        latency = time.time() - start
        latencies.append(latency)

    print(f"Mean latency: {sum(latencies)/len(latencies)*1000:.2f}ms")
    print(f"P99 latency: {sorted(latencies)[int(len(latencies)*0.99)]*1000:.2f}ms")

asyncio.run(profile_http_client("http://localhost:8000"))
```

**Connection Pool Tuning:**

```python
import aiohttp

# Default: 100 connections
connector = aiohttp.TCPConnector(limit=100)

# Increased pool size
connector = aiohttp.TCPConnector(limit=1000)

# Per-host limit
connector = aiohttp.TCPConnector(
    limit=1000,
    limit_per_host=100
)

# Custom timeouts
timeout = aiohttp.ClientTimeout(
    total=60.0,
    connect=10.0,
    sock_read=30.0
)

session = aiohttp.ClientSession(
    connector=connector,
    timeout=timeout
)
```

### Network Monitoring

**Track Network Usage:**

```bash
# Monitor bandwidth
iftop -i lo

# Track connections
netstat -an | grep ESTABLISHED | grep 8000 | wc -l

# Monitor with sar
sar -n DEV 1 10
```

**Application-Level Monitoring:**

```python
import time

class NetworkMonitor:
    def __init__(self):
        self.bytes_sent = 0
        self.bytes_received = 0
        self.start_time = time.time()

    def record_request(self, request_size, response_size):
        self.bytes_sent += request_size
        self.bytes_received += response_size

    def get_stats(self):
        elapsed = time.time() - self.start_time
        return {
            'bytes_sent': self.bytes_sent,
            'bytes_received': self.bytes_received,
            'bandwidth_sent': self.bytes_sent / elapsed,
            'bandwidth_received': self.bytes_received / elapsed
        }
```

---

## Benchmark Performance Analysis

### Throughput Analysis

**Measure Effective Throughput:**

```python
from aiperf.common.models import BenchmarkResults

def analyze_throughput(results: BenchmarkResults):
    # Request throughput
    total_requests = len(results.records)
    duration = results.benchmark_duration
    throughput = total_requests / duration

    print(f"Total requests: {total_requests}")
    print(f"Duration: {duration:.2f}s")
    print(f"Throughput: {throughput:.2f} req/s")

    # Token throughput
    total_tokens = sum(r.output_token_count for r in results.records)
    token_throughput = total_tokens / duration

    print(f"Total tokens: {total_tokens}")
    print(f"Token throughput: {token_throughput:.2f} tok/s")

    # Efficiency
    concurrency = results.config.loadgen.concurrency
    theoretical_max = concurrency / results.metrics['request_latency']['avg']
    efficiency = (throughput / theoretical_max) * 100

    print(f"Concurrency: {concurrency}")
    print(f"Efficiency: {efficiency:.1f}%")
```

### Latency Analysis

**Percentile Analysis:**

```python
import numpy as np

def analyze_latency(latencies):
    percentiles = [50, 90, 95, 99, 99.9]

    print("Latency Distribution:")
    for p in percentiles:
        value = np.percentile(latencies, p)
        print(f"  P{p}: {value:.2f}ms")

    # Outlier detection
    q1 = np.percentile(latencies, 25)
    q3 = np.percentile(latencies, 75)
    iqr = q3 - q1
    outliers = [l for l in latencies if l > q3 + 1.5*iqr]

    print(f"Outliers: {len(outliers)} ({len(outliers)/len(latencies)*100:.1f}%)")
```

**Latency Over Time:**

```python
import matplotlib.pyplot as plt

def plot_latency_over_time(results):
    timestamps = [r.request_start_time for r in results.records]
    latencies = [r.latency for r in results.records]

    plt.figure(figsize=(12, 6))
    plt.scatter(timestamps, latencies, alpha=0.5)
    plt.xlabel('Time (s)')
    plt.ylabel('Latency (ms)')
    plt.title('Request Latency Over Time')
    plt.savefig('latency_over_time.png')
```

### Resource Utilization

**Monitor During Benchmark:**

```bash
# CPU usage
mpstat 1 60 > cpu_usage.log &

# Memory usage
free -s 1 -c 60 > memory_usage.log &

# Network usage
sar -n DEV 1 60 > network_usage.log &

# Run benchmark
aiperf profile [options...]

# Stop monitoring
pkill -f mpstat
pkill -f sar
```

---

## Optimization Strategies

### Worker Optimization

**Optimal Worker Count:**

```python
import multiprocessing

# CPU-bound: number of cores
optimal_workers_cpu = multiprocessing.cpu_count()

# I/O-bound: 2-4x cores
optimal_workers_io = multiprocessing.cpu_count() * 2

# Test different configurations
for num_workers in [1, 2, 4, 8, 16]:
    print(f"\nTesting with {num_workers} workers:")
    # Run benchmark with num_workers
    # Measure throughput
```

**Worker Configuration Example:**

```bash
# Test worker scaling
for workers in 1 2 4 8 16; do
  echo "Workers: $workers"
  aiperf profile \
    --model Qwen/Qwen3-0.6B \
    --url http://localhost:8000 \
    --endpoint-type chat \
    --request-count 1000 \
    --concurrency 100 \
    --num-workers $workers \
    --ui none \
    --output-file "results_${workers}w.json"
done
```

### Request Batching

**Batch Requests for Efficiency:**

```python
async def send_requests_batched(requests, batch_size=10):
    results = []
    for i in range(0, len(requests), batch_size):
        batch = requests[i:i+batch_size]
        tasks = [send_request(req) for req in batch]
        batch_results = await asyncio.gather(*tasks)
        results.extend(batch_results)
    return results
```

### Caching Strategies

**Metric Caching:**

```python
from functools import lru_cache

class OptimizedMetric:
    @lru_cache(maxsize=1000)
    def compute(self, record_id, value):
        # Expensive computation
        return expensive_calculation(value)
```

**Configuration Caching:**

```python
from functools import cached_property

class CachedConfig:
    @cached_property
    def parsed_config(self):
        # Expensive parsing
        return parse_configuration(self.raw_config)
```

---

## Performance Testing

### Load Testing

**Stress Test AIPerf:**

```bash
# Gradually increase load
for concurrency in 10 50 100 500 1000; do
  echo "Testing concurrency: $concurrency"
  aiperf profile \
    --model Qwen/Qwen3-0.6B \
    --url http://localhost:8000 \
    --endpoint-type chat \
    --request-count 1000 \
    --concurrency $concurrency \
    --ui none
done
```

**Monitor System Resources:**

```bash
# Create monitoring script
cat > monitor.sh << 'EOF'
#!/bin/bash
while true; do
  echo "=== $(date) ==="
  ps aux | grep aiperf | awk '{print $2, $3, $4, $11}'
  free -h | grep Mem
  netstat -an | grep ESTABLISHED | wc -l
  sleep 1
done
EOF

chmod +x monitor.sh

# Run monitoring
./monitor.sh > monitor.log &
MONITOR_PID=$!

# Run benchmark
aiperf profile [options...]

# Stop monitoring
kill $MONITOR_PID
```

### Performance Regression Testing

**Automated Performance Tests:**

```python
import pytest
import time

@pytest.mark.performance
def test_benchmark_throughput():
    """Ensure throughput meets minimum threshold"""
    start = time.time()

    # Run benchmark
    results = run_benchmark(
        request_count=1000,
        concurrency=10
    )

    elapsed = time.time() - start
    throughput = 1000 / elapsed

    # Assert minimum throughput
    assert throughput >= 50.0, f"Throughput {throughput:.1f} below threshold"

@pytest.mark.performance
def test_memory_usage():
    """Ensure memory usage stays within bounds"""
    import tracemalloc

    tracemalloc.start()

    # Run benchmark
    run_benchmark(request_count=100)

    current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    # Assert memory usage
    assert peak / 1024 / 1024 < 500, f"Peak memory {peak/1024/1024:.1f}MB exceeds 500MB"
```

**Run Performance Tests:**

```bash
# Run performance test suite
pytest -m performance -v

# With benchmarking
pytest -m performance --benchmark-only
```

---

## Benchmarking AIPerf Itself

### Measuring AIPerf Overhead

**Compare with Direct Requests:**

```python
import asyncio
import time
import aiohttp

async def direct_requests(url, num_requests):
    """Measure performance of direct HTTP requests"""
    async with aiohttp.ClientSession() as session:
        start = time.time()

        tasks = []
        for _ in range(num_requests):
            tasks.append(session.post(url, json={...}))

        await asyncio.gather(*tasks)

        elapsed = time.time() - start
        print(f"Direct: {num_requests/elapsed:.1f} req/s")

async def aiperf_requests(url, num_requests):
    """Measure performance through AIPerf"""
    start = time.time()

    # Run AIPerf
    run_system_controller(
        user_config=UserConfig(...),
        service_config=ServiceConfig(...)
    )

    elapsed = time.time() - start
    print(f"AIPerf: {num_requests/elapsed:.1f} req/s")

# Compare
asyncio.run(direct_requests("http://localhost:8000/v1/chat/completions", 1000))
asyncio.run(aiperf_requests("http://localhost:8000", 1000))
```

### Profiling AIPerf Components

**Profile Service Communication:**

```python
import cProfile

def profile_message_bus():
    profiler = cProfile.Profile()
    profiler.enable()

    # Test message bus
    asyncio.run(test_message_bus_performance())

    profiler.disable()
    profiler.print_stats(sort='cumulative')
```

### Optimization Targets

**High-Impact Areas:**

1. **Message Serialization**: ~15% of overhead
2. **Metric Computation**: ~25% of overhead
3. **Request Formatting**: ~10% of overhead
4. **Result Aggregation**: ~20% of overhead
5. **Logging**: ~5% of overhead (DEBUG mode)

---

## Best Practices

### Profiling Best Practices

1. **Profile Representative Workloads**: Use realistic data and configurations
2. **Profile in Production-Like Environment**: Match CPU, memory, network conditions
3. **Multiple Runs**: Average results across multiple runs
4. **Warm-Up Period**: Exclude initial startup time
5. **Isolate Variables**: Change one thing at a time
6. **Document Baseline**: Track performance over time

### Optimization Best Practices

1. **Measure First**: Profile before optimizing
2. **Focus on Bottlenecks**: Optimize high-impact areas first
3. **Trade-offs**: Balance performance vs. readability
4. **Test Performance**: Add regression tests
5. **Document Changes**: Explain optimization rationale

### Performance Testing Best Practices

1. **Automated Tests**: Include in CI/CD
2. **Performance Budget**: Set thresholds
3. **Track Metrics**: Monitor over time
4. **Regression Detection**: Alert on degradation
5. **Optimization Validation**: Verify improvements

---

## Performance Checklist

- [ ] Profile with representative workload
- [ ] Identify top CPU hotspots
- [ ] Check memory usage and leaks
- [ ] Analyze async performance
- [ ] Monitor network utilization
- [ ] Test with various worker counts
- [ ] Measure AIPerf overhead
- [ ] Optimize hot paths
- [ ] Add performance tests
- [ ] Document optimizations
- [ ] Verify improvements
- [ ] Track performance over time

---

## Key Takeaways

1. **Profile First**: Measure before optimizing
2. **Use Appropriate Tools**: Choose the right profiler for the job
3. **Focus on Impact**: Optimize bottlenecks, not everything
4. **Test Continuously**: Include performance in testing
5. **Monitor Production**: Track real-world performance
6. **Document Changes**: Explain optimizations
7. **Balance Trade-offs**: Performance vs. maintainability
8. **Validate Results**: Ensure optimizations work

---

## Navigation

- [Previous Chapter: Chapter 41 - Debugging Techniques](chapter-41-debugging-techniques.md)
- [Next Chapter: Chapter 43 - Common Patterns](chapter-43-common-patterns.md)
- [Return to Index](INDEX.md)

---

**Document Information**
- **File**: `/home/anthony/nvidia/projects/aiperf/guidebook/chapter-42-performance-profiling.md`
- **Purpose**: Performance profiling and optimization guide for AIPerf
- **Target Audience**: Developers optimizing AIPerf or analyzing benchmark performance
- **Related Files**:
  - `/home/anthony/nvidia/projects/aiperf/aiperf/workers/`
  - `/home/anthony/nvidia/projects/aiperf/aiperf/metrics/`
  - `/home/anthony/nvidia/projects/aiperf/tests/metrics/`
