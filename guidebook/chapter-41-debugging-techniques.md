# Chapter 41: Debugging Techniques

<!--
# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
-->

## Overview

This chapter provides comprehensive debugging strategies, tools, and techniques for diagnosing and resolving issues in AIPerf. Whether you're troubleshooting configuration errors, investigating performance problems, or tracking down runtime failures, this chapter equips you with the knowledge and tools to debug effectively.

## Table of Contents

- [Debugging Philosophy](#debugging-philosophy)
- [Logging and Verbosity](#logging-and-verbosity)
- [Common Debugging Scenarios](#common-debugging-scenarios)
- [Debugging Tools](#debugging-tools)
- [Service Debugging](#service-debugging)
- [Communication Debugging](#communication-debugging)
- [Worker Debugging](#worker-debugging)
- [Configuration Debugging](#configuration-debugging)
- [Performance Debugging](#performance-debugging)
- [Error Analysis](#error-analysis)
- [Testing and Validation](#testing-and-validation)
- [Best Practices](#best-practices)

---

## Debugging Philosophy

### Understanding AIPerf Architecture

Before debugging, understand AIPerf's multi-service architecture:

```
┌─────────────────────────────────────────────────────────────┐
│                     System Controller                        │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │   Workers    │  │  Load Gen    │  │   Results    │     │
│  │   Manager    │  │   Service    │  │  Processor   │     │
│  └──────────────┘  └──────────────┘  └──────────────┘     │
│         │                  │                  │             │
│         └──────────────────┼──────────────────┘             │
│                            │                                │
│                     Message Bus (ZMQ)                       │
└─────────────────────────────────────────────────────────────┘
```

**Key Debugging Targets:**
- **System Controller**: Orchestration and lifecycle management
- **Worker Manager**: Worker processes and distribution
- **Load Generator**: Request generation and rate control
- **Results Processor**: Metric computation and reporting
- **Message Bus**: Inter-service communication

### Debugging Principles

1. **Start Simple**: Begin with the most basic configuration
2. **Isolate Components**: Test services independently
3. **Use Logging Strategically**: Increase verbosity only where needed
4. **Reproduce Consistently**: Create minimal reproducible examples
5. **Check Dependencies**: Verify endpoints, files, and network connectivity

---

## Logging and Verbosity

### Log Levels

AIPerf uses a custom logger (`AIPerfLogger`) with extended log levels:

```python
# From /home/anthony/nvidia/projects/aiperf/aiperf/common/aiperf_logger.py

Log Levels (lowest to highest):
- TRACE    (5):  Most verbose, includes all internal operations
- DEBUG    (10): Detailed debugging information
- INFO     (20): General informational messages
- NOTICE   (25): Important notices
- WARNING  (30): Warning messages
- SUCCESS  (35): Success messages
- ERROR    (40): Error messages
- CRITICAL (50): Critical failures
```

### Setting Log Levels

**Via Command Line:**
```bash
# Set global log level
aiperf profile --log-level DEBUG [options...]

# Set specific service log level
aiperf profile --service-log-level DEBUG [options...]
```

**Via Environment Variable:**
```bash
export AIPERF_LOG_LEVEL=DEBUG
aiperf profile [options...]
```

**Via Configuration:**
```python
from aiperf.common.config import ServiceConfig
from aiperf.common.enums import LogLevel

service_config = ServiceConfig(
    log_level=LogLevel.DEBUG
)
```

### Lazy Logging

AIPerf supports lazy evaluation to avoid expensive string formatting:

```python
from aiperf.common.aiperf_logger import AIPerfLogger

logger = AIPerfLogger(__name__)

# Expensive operation - only evaluated if DEBUG is enabled
logger.debug(lambda: f"Processing {large_data_structure}")

# Simple string - always formatted
logger.info("Starting benchmark")

# With loop variables - bind to lambda
for i in range(10):
    logger.debug(lambda i=i: f"Iteration {i}")
```

### Trace vs Debug Logging

Use `trace_or_debug()` for conditional verbosity:

```python
logger.trace_or_debug(
    lambda: f"Full request data: {request}",      # TRACE level
    lambda: f"Request ID: {request.id}"           # DEBUG level
)
```

### Log Output Control

**Console Output:**
```bash
# Minimal output
aiperf profile --ui simple [options...]

# No UI (logs only)
aiperf profile --ui none [options...]

# Redirect logs
aiperf profile [options...] 2> aiperf.log
```

**Filtering Logs:**
```bash
# Filter by service
aiperf profile [options...] 2>&1 | grep "WorkerManager"

# Filter by level
aiperf profile [options...] 2>&1 | grep "ERROR"

# Multiple filters
aiperf profile [options...] 2>&1 | grep -E "(ERROR|WARNING)"
```

---

## Common Debugging Scenarios

### Scenario 1: Connection Refused

**Symptoms:**
```
ERROR: Connection refused at http://localhost:8000
ERROR: Failed to send request
```

**Debug Steps:**

1. **Verify Endpoint Availability:**
```bash
# Test endpoint directly
curl http://localhost:8000/v1/models

# Check if service is running
netstat -an | grep 8000
```

2. **Check AIPerf Configuration:**
```bash
# Enable debug logging
aiperf profile \
  --model Qwen/Qwen3-0.6B \
  --url http://localhost:8000 \
  --endpoint-type chat \
  --log-level DEBUG
```

3. **Verify Network Connectivity:**
```bash
# Ping the host
ping localhost

# Test with netcat
nc -zv localhost 8000
```

**Solution:**
- Ensure the inference server is running
- Verify URL is correct (check protocol, host, port)
- Check firewall rules
- Use `--url` without trailing slash

### Scenario 2: Timeout Errors

**Symptoms:**
```
WARNING: Request timeout after 60.0 seconds
ERROR: Timeout waiting for response
```

**Debug Steps:**

1. **Increase Timeout:**
```bash
aiperf profile \
  --request-timeout-seconds 120.0 \
  [other options...]
```

2. **Check Server Performance:**
```bash
# Monitor server logs during benchmark
tail -f /path/to/server/logs
```

3. **Reduce Load:**
```bash
# Lower concurrency
aiperf profile --concurrency 1 [options...]

# Reduce request count
aiperf profile --request-count 10 [options...]
```

**Solution:**
- Adjust `--request-timeout-seconds` based on server performance
- Check server capacity and resource utilization
- Consider reducing request rate or concurrency

### Scenario 3: Service Hang

**Symptoms:**
```
INFO: Starting services...
[No further output, process hangs]
```

**Debug Steps:**

1. **Enable Debug Logging:**
```bash
aiperf profile --log-level DEBUG --service-log-level DEBUG [options...]
```

2. **Check Service State:**
```bash
# In another terminal, check process state
ps aux | grep aiperf

# Check for stuck processes
pstree -p | grep aiperf
```

3. **Kill and Retry:**
```bash
# Force kill if needed
pkill -9 -f aiperf

# Retry with minimal configuration
aiperf profile --model test --url http://localhost:8000 --endpoint-type chat --request-count 1
```

**Solution:**
- Verify configuration is valid
- Check for missing required parameters
- Look for errors in the last log messages before hang
- Check system resources (memory, file descriptors)

### Scenario 4: Invalid Configuration

**Symptoms:**
```
ERROR: ValidationError: Invalid configuration
ERROR: ConfigurationError: Missing required field
```

**Debug Steps:**

1. **Validate Configuration:**
```python
from aiperf.common.config import UserConfig, EndpointConfig, LoadGeneratorConfig

# Test configuration programmatically
endpoint_config = EndpointConfig(
    model_names=["Qwen/Qwen3-0.6B"],
    url="http://localhost:8000",
    type="chat"
)

loadgen_config = LoadGeneratorConfig(
    request_count=10,
    concurrency=1
)

user_config = UserConfig(
    endpoint=endpoint_config,
    loadgen=loadgen_config
)
```

2. **Check Field Values:**
```bash
# Enable validation logging
aiperf profile --log-level DEBUG [options...]
```

**Solution:**
- Verify all required fields are present
- Check field types match expected types
- Ensure enums use valid values
- Review configuration schema

### Scenario 5: Worker Failures

**Symptoms:**
```
ERROR: Worker worker_0 failed
ERROR: WorkerManager shutting down due to worker failure
```

**Debug Steps:**

1. **Check Worker Logs:**
```bash
# Enable worker debugging
aiperf profile --log-level DEBUG --service-log-level DEBUG [options...]
```

2. **Test with Single Worker:**
```bash
# Reduce to one worker for debugging
aiperf profile --num-workers 1 [options...]
```

3. **Check Worker State:**
```python
# From logs, identify worker failure reason
# Look for messages like:
# ERROR: Worker exception: [exception details]
# ERROR: Failed to send request: [error details]
```

**Solution:**
- Check endpoint health and capacity
- Verify dataset format is correct
- Ensure sufficient system resources
- Check for memory leaks or resource exhaustion

---

## Debugging Tools

### Built-in Debugging

**Verbose Mode:**
```bash
# Maximum verbosity
aiperf profile --log-level TRACE --service-log-level TRACE [options...]
```

**Simple UI for Log Visibility:**
```bash
# Disable dashboard to see logs clearly
aiperf profile --ui simple [options...]
```

**Configuration Dump:**
```python
from aiperf.common.config import UserConfig
import json

# Print configuration as JSON
config = UserConfig(...)
print(json.dumps(config.model_dump(), indent=2))
```

### Python Debugger (pdb)

**Interactive Debugging:**
```python
import pdb

# In your code, add breakpoint
pdb.set_trace()

# Or use built-in breakpoint()
breakpoint()
```

**Remote Debugging with pdb:**
```python
import pdb
import sys

# Debug in multiprocess environment
if __name__ == "__main__":
    pdb.set_trace()
    from aiperf.cli_runner import run_system_controller
    run_system_controller(user_config, service_config)
```

### Advanced Debugging with pdb++

Install enhanced debugger:
```bash
pip install pdbpp
```

**Features:**
- Syntax highlighting
- Tab completion
- Better stack trace
- Sticky mode (shows code context)

### IDE Debugging

**VS Code Configuration:**
```json
{
  "version": "0.2.0",
  "configurations": [
    {
      "name": "Debug AIPerf",
      "type": "python",
      "request": "launch",
      "module": "aiperf.cli",
      "args": [
        "profile",
        "--model", "Qwen/Qwen3-0.6B",
        "--url", "http://localhost:8000",
        "--endpoint-type", "chat",
        "--request-count", "10",
        "--log-level", "DEBUG"
      ],
      "console": "integratedTerminal",
      "justMyCode": false
    }
  ]
}
```

**PyCharm Configuration:**
1. Run → Edit Configurations
2. Add Python configuration
3. Script path: `aiperf/cli.py`
4. Parameters: `profile --model ... --url ...`
5. Environment: `PYTHONPATH=/path/to/aiperf`

### System Monitoring Tools

**Process Monitoring:**
```bash
# Watch AIPerf processes
watch -n 1 'ps aux | grep aiperf'

# Monitor with htop
htop -p $(pgrep -f aiperf | tr '\n' ',')
```

**Network Monitoring:**
```bash
# Monitor connections
watch -n 1 'netstat -an | grep 8000'

# Track network traffic
iftop -i lo

# Monitor with tcpdump
tcpdump -i lo -A 'port 8000'
```

**File Descriptor Monitoring:**
```bash
# Check open files
lsof -p $(pgrep -f aiperf)

# Count file descriptors
ls -l /proc/$(pgrep -f aiperf)/fd | wc -l
```

### Logging to File

**Capture Complete Logs:**
```bash
# Redirect stderr to file
aiperf profile [options...] 2> aiperf_debug.log

# Redirect both stdout and stderr
aiperf profile [options...] &> aiperf_full.log

# Append to file
aiperf profile [options...] 2>> aiperf_debug.log
```

**Structured Log Analysis:**
```bash
# Extract errors
grep ERROR aiperf_debug.log

# Count errors by type
grep ERROR aiperf_debug.log | cut -d':' -f3 | sort | uniq -c

# Timeline of errors
grep ERROR aiperf_debug.log | cut -d' ' -f1,2

# Service-specific logs
grep "WorkerManager" aiperf_debug.log
```

### Custom Debugging Utilities

**Create Debug Script:**
```python
#!/usr/bin/env python3
"""
Debug script for AIPerf issues
File: /home/anthony/nvidia/projects/aiperf/debug_aiperf.py
"""

import sys
import logging
from aiperf.common.config import UserConfig, EndpointConfig, LoadGeneratorConfig
from aiperf.cli_runner import run_system_controller
from aiperf.common.config import load_service_config

# Enable all logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

def main():
    # Minimal configuration for debugging
    endpoint_config = EndpointConfig(
        model_names=["Qwen/Qwen3-0.6B"],
        url="http://localhost:8000",
        type="chat",
        streaming=True
    )

    loadgen_config = LoadGeneratorConfig(
        request_count=5,
        concurrency=1
    )

    user_config = UserConfig(
        endpoint=endpoint_config,
        loadgen=loadgen_config
    )

    service_config = load_service_config()

    try:
        print("Starting AIPerf with debug configuration...")
        run_system_controller(user_config, service_config)
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
```

**Run Debug Script:**
```bash
python debug_aiperf.py 2>&1 | tee debug_output.log
```

---

## Service Debugging

### System Controller Debugging

**Enable Detailed Logging:**
```python
from aiperf.common.aiperf_logger import AIPerfLogger

logger = AIPerfLogger("SystemController")
logger.set_level("DEBUG")
```

**Check Controller State:**
```python
# Add debugging to controller lifecycle
@on_state_change
async def _debug_state_change(self, old_state, new_state):
    self.info(f"State transition: {old_state} -> {new_state}")
```

**Monitor Service Lifecycle:**
```bash
# Look for lifecycle messages
aiperf profile [options...] 2>&1 | grep -E "(INIT|START|STOP|FAILED)"
```

### Worker Manager Debugging

**Worker State Tracking:**
```python
from aiperf.common.mixins import WorkerTrackerMixin

@on_worker_status_summary
def _debug_worker_status(self, worker_statuses):
    for worker_id, status in worker_statuses.items():
        self.debug(f"Worker {worker_id}: {status}")
```

**Worker Communication:**
```bash
# Monitor worker messages
aiperf profile --log-level DEBUG [options...] 2>&1 | grep "Worker"
```

**Test Worker Isolation:**
```bash
# Run with single worker
aiperf profile --num-workers 1 --log-level DEBUG [options...]
```

### Load Generator Debugging

**Request Rate Analysis:**
```python
@on_profiling_progress
def _debug_profiling_progress(self, profiling_stats):
    self.debug(f"Requests sent: {profiling_stats.request_count}")
    self.debug(f"Current rate: {profiling_stats.throughput}")
```

**Request Timing:**
```bash
# Enable timing logs
aiperf profile --log-level DEBUG [options...] 2>&1 | grep "timing"
```

### Results Processor Debugging

**Metric Computation:**
```python
from aiperf.metrics.metric_registry import MetricRegistry

# List available metrics
print("Available metrics:", MetricRegistry.all_tags())

# Check metric dependencies
for tag in MetricRegistry.all_tags():
    metric_class = MetricRegistry.get_class(tag)
    print(f"{tag}: requires {metric_class.required_metrics}")
```

**Record Processing:**
```bash
# Monitor record processing
aiperf profile --log-level DEBUG [options...] 2>&1 | grep "record"
```

---

## Communication Debugging

### ZMQ Message Bus

**Enable ZMQ Logging:**
```python
from aiperf.common.config import ServiceConfig

service_config = ServiceConfig(
    zmq_debug=True,
    log_level="DEBUG"
)
```

**Monitor Message Flow:**
```bash
# Watch for message types
aiperf profile --log-level DEBUG [options...] 2>&1 | grep -E "(PUBLISH|SUBSCRIBE|REQUEST|REPLY)"
```

**Test Message Bus:**
```python
from aiperf.zmq.communication import ZMQCommunication
from aiperf.common.config import BaseZMQCommunicationConfig

# Create test communication
config = BaseZMQCommunicationConfig()
comm = ZMQCommunication(config)

# Test publish/subscribe
await comm.start()
await comm.publish(test_message)
```

### Message Serialization

**Debug Message Format:**
```python
from aiperf.common.messages import StatusMessage

# Serialize and inspect
message = StatusMessage(...)
serialized = message.model_dump_json()
print(f"Serialized: {serialized}")

# Deserialize and validate
deserialized = StatusMessage.model_validate_json(serialized)
print(f"Valid: {deserialized}")
```

### Communication Timeouts

**Adjust Timeouts:**
```python
from aiperf.common.config import BaseZMQCommunicationConfig

config = BaseZMQCommunicationConfig(
    request_timeout_ms=60000,  # 60 seconds
    heartbeat_interval_ms=5000  # 5 seconds
)
```

---

## Worker Debugging

### Worker Process Lifecycle

**Track Worker Creation:**
```bash
# Monitor worker processes
ps aux | grep -E "aiperf.*worker"

# Watch worker count
watch -n 1 'ps aux | grep -E "aiperf.*worker" | wc -l'
```

**Worker State Machine:**
```python
# Worker lifecycle states
INIT -> STARTING -> RUNNING -> STOPPING -> STOPPED
                            -> FAILED
```

### Worker Request Handling

**Debug Request Processing:**
```python
from aiperf.common.hooks import on_request

@on_request(MessageType.INFERENCE_REQUEST)
async def _debug_inference_request(self, message):
    self.debug(f"Received inference request: {message.request_id}")
    try:
        result = await self.process_request(message)
        self.debug(f"Request {message.request_id} completed")
        return result
    except Exception as e:
        self.error(f"Request {message.request_id} failed: {e}")
        raise
```

### Worker Resource Usage

**Monitor Worker Resources:**
```bash
# Memory usage per worker
ps -o pid,rss,cmd | grep aiperf | awk '{print $1, $2/1024 " MB", $3}'

# CPU usage per worker
top -b -n 1 | grep aiperf
```

---

## Configuration Debugging

### Configuration Validation

**Validate Before Running:**
```python
from aiperf.common.config import UserConfig
from pydantic import ValidationError

try:
    config = UserConfig(
        endpoint=endpoint_config,
        loadgen=loadgen_config
    )
    print("Configuration valid")
except ValidationError as e:
    print(f"Configuration errors:")
    for error in e.errors():
        print(f"  - {error['loc']}: {error['msg']}")
```

### Configuration Inspection

**Print Configuration:**
```python
import json
from aiperf.common.config import UserConfig

config = UserConfig(...)

# Pretty print configuration
print(json.dumps(config.model_dump(), indent=2))

# Print specific section
print(json.dumps(config.endpoint.model_dump(), indent=2))
```

### Configuration Override

**Override for Debugging:**
```python
# Create base config
config = UserConfig(...)

# Override specific fields
config.loadgen.request_count = 5
config.loadgen.concurrency = 1
config.endpoint.streaming = False
```

---

## Performance Debugging

### Identify Bottlenecks

**Profile Python Code:**
```bash
# Use cProfile
python -m cProfile -o profile.stats -m aiperf.cli profile [options...]

# Analyze results
python -m pstats profile.stats
>>> sort cumtime
>>> stats 20
```

**Line Profiler:**
```bash
# Install line_profiler
pip install line_profiler

# Add @profile decorator to functions
# Run with kernprof
kernprof -l -v aiperf/cli.py profile [options...]
```

### Memory Debugging

**Memory Profiler:**
```bash
# Install memory_profiler
pip install memory_profiler

# Profile memory usage
python -m memory_profiler aiperf/cli.py profile [options...]
```

**Track Memory Leaks:**
```python
import tracemalloc

tracemalloc.start()

# Run AIPerf
run_system_controller(user_config, service_config)

# Get memory snapshot
snapshot = tracemalloc.take_snapshot()
top_stats = snapshot.statistics('lineno')

for stat in top_stats[:10]:
    print(stat)
```

### Request Latency Analysis

**Enable Detailed Timing:**
```bash
# Use TRACE level for timing details
aiperf profile --log-level TRACE [options...] 2>&1 | grep -E "(latency|duration)"
```

**Export Request Data:**
```bash
# Export to JSON for analysis
aiperf profile --output-file results.json [options...]

# Analyze with Python
python -c "
import json
with open('results.json') as f:
    data = json.load(f)
    latencies = [r['latency'] for r in data['records']]
    print(f'Mean latency: {sum(latencies)/len(latencies):.2f}ms')
"
```

---

## Error Analysis

### Exception Handling

**Catch and Log Exceptions:**
```python
from aiperf.common.exceptions import AIPerfError

try:
    result = await process_request()
except AIPerfError as e:
    logger.error(f"AIPerf error: {e}")
    logger.debug(f"Error details: {e.raw_str()}")
except Exception as e:
    logger.exception(f"Unexpected error: {e}")
```

### Stack Trace Analysis

**Full Stack Traces:**
```bash
# Enable exception tracebacks
aiperf profile --log-level DEBUG [options...] 2>&1

# Save for later analysis
aiperf profile [options...] 2> errors.log
grep -A 20 "Traceback" errors.log
```

### Common Error Patterns

**Pattern 1: Import Errors**
```
ImportError: No module named 'aiperf'
```
**Solution:** Verify PYTHONPATH and installation

**Pattern 2: Validation Errors**
```
ValidationError: 1 validation error for UserConfig
  endpoint.type
    Input should be 'chat', 'completions', or 'embeddings'
```
**Solution:** Check enum values and field types

**Pattern 3: Communication Errors**
```
CommunicationError: Failed to connect to message bus
```
**Solution:** Check ZMQ configuration and ports

---

## Testing and Validation

### Unit Testing

**Test Individual Components:**
```python
import pytest
from aiperf.metrics import RequestLatencyMetric

def test_request_latency_metric():
    metric = RequestLatencyMetric()

    # Create mock record
    record = ParsedResponseRecord(
        request_start_time=0.0,
        request_end_time=1.5,
        valid=True
    )

    # Compute metric
    result = metric._parse_record(record, {})

    # Verify result
    assert result == 1500.0  # milliseconds
```

**Run Tests:**
```bash
# Run all tests
pytest tests/

# Run specific test file
pytest tests/metrics/test_request_latency_metric.py

# Run with debugging
pytest -v -s tests/

# Run with coverage
pytest --cov=aiperf tests/
```

### Integration Testing

**Test Complete Workflows:**
```python
import pytest
from aiperf.cli_runner import run_system_controller

@pytest.mark.integration
def test_benchmark_workflow(mock_server):
    endpoint_config = EndpointConfig(
        model_names=["test-model"],
        url=mock_server.url,
        type="chat"
    )

    loadgen_config = LoadGeneratorConfig(
        request_count=10,
        concurrency=1
    )

    user_config = UserConfig(
        endpoint=endpoint_config,
        loadgen=loadgen_config
    )

    service_config = load_service_config()

    # Should complete without errors
    run_system_controller(user_config, service_config)
```

### Mock Testing

**Create Mock Server:**
```python
from aiohttp import web

async def handle_chat(request):
    return web.json_response({
        "id": "test",
        "object": "chat.completion",
        "choices": [{
            "message": {
                "role": "assistant",
                "content": "Test response"
            }
        }]
    })

app = web.Application()
app.router.add_post("/v1/chat/completions", handle_chat)
web.run_app(app, port=8000)
```

---

## Best Practices

### Debugging Workflow

1. **Start with Minimal Configuration:**
   ```bash
   aiperf profile --model test --url http://localhost:8000 --endpoint-type chat --request-count 1
   ```

2. **Enable Appropriate Logging:**
   ```bash
   # Start with DEBUG, escalate to TRACE if needed
   aiperf profile --log-level DEBUG [options...]
   ```

3. **Isolate the Problem:**
   - Test endpoint separately
   - Reduce concurrency to 1
   - Use small request count
   - Disable streaming

4. **Collect Evidence:**
   - Save logs to file
   - Capture configuration
   - Document error messages
   - Note system state

5. **Test Hypothesis:**
   - Change one variable at a time
   - Verify fix resolves issue
   - Test edge cases

### Logging Best Practices

**Do:**
- Use lazy evaluation for expensive operations
- Include relevant context in messages
- Use appropriate log levels
- Log at decision points

**Don't:**
- Log sensitive data (API keys, tokens)
- Over-log in hot paths
- Use print() statements
- Log large data structures at INFO level

### Performance Best Practices

**Do:**
- Profile before optimizing
- Focus on bottlenecks
- Use appropriate data structures
- Cache expensive computations

**Don't:**
- Premature optimization
- Ignore memory usage
- Block the event loop
- Create resource leaks

### Testing Best Practices

**Do:**
- Write tests for bug fixes
- Use fixtures and mocks
- Test error conditions
- Maintain test coverage

**Don't:**
- Skip test validation
- Test implementation details
- Create brittle tests
- Ignore test failures

---

## Advanced Debugging Techniques

### Debugging Multiprocess Issues

**Process Tracing:**
```bash
# Trace system calls
strace -f -p $(pgrep -f "aiperf.*controller")

# Trace specific system call
strace -e trace=network -f python -m aiperf.cli profile [options...]
```

**Core Dumps:**
```bash
# Enable core dumps
ulimit -c unlimited

# Analyze core dump
gdb python core.12345
>>> bt  # backtrace
```

### Debugging Async Code

**Asyncio Debug Mode:**
```python
import asyncio

# Enable debug mode
asyncio.run(main(), debug=True)
```

**Detect Blocking Calls:**
```python
import asyncio

# Warn on slow callbacks
asyncio.get_event_loop().slow_callback_duration = 0.1
```

### Debugging Network Issues

**Packet Capture:**
```bash
# Capture HTTP traffic
tcpdump -i any -A 'port 8000' -w capture.pcap

# Analyze with wireshark
wireshark capture.pcap
```

**HTTP Debugging:**
```bash
# Use mitmproxy
mitmproxy --mode reverse:http://localhost:8000 --listen-port 8001

# Point AIPerf to proxy
aiperf profile --url http://localhost:8001 [options...]
```

---

## Debugging Checklist

Before filing a bug report, complete this checklist:

- [ ] Verified endpoint is accessible
- [ ] Tested with minimal configuration
- [ ] Enabled DEBUG logging
- [ ] Reproduced issue consistently
- [ ] Checked AIPerf version (`aiperf --version`)
- [ ] Reviewed logs for errors
- [ ] Tested with single worker
- [ ] Verified configuration is valid
- [ ] Checked system resources
- [ ] Saved logs and configuration
- [ ] Created minimal reproducible example
- [ ] Searched existing issues

---

## Key Takeaways

1. **Systematic Approach**: Follow a methodical debugging process
2. **Appropriate Logging**: Use the right log level for the situation
3. **Isolation**: Test components independently
4. **Documentation**: Save logs and configuration for analysis
5. **Understanding**: Know AIPerf's architecture and communication patterns
6. **Tools**: Leverage debugging tools and utilities
7. **Testing**: Validate fixes with tests
8. **Best Practices**: Follow debugging and development best practices

---

## Navigation

- [Previous Chapter: Chapter 40 - Module Organization](chapter-40-testing-strategies.md)
- [Next Chapter: Chapter 42 - Performance Profiling](chapter-42-performance-profiling.md)
- [Return to Index](INDEX.md)

---

**Document Information**
- **File**: `/home/anthony/nvidia/projects/aiperf/guidebook/chapter-41-debugging-techniques.md`
- **Purpose**: Comprehensive debugging guide for AIPerf developers
- **Target Audience**: Developers debugging AIPerf issues
- **Related Files**:
  - `/home/anthony/nvidia/projects/aiperf/aiperf/common/aiperf_logger.py`
  - `/home/anthony/nvidia/projects/aiperf/aiperf/common/exceptions.py`
  - `/home/anthony/nvidia/projects/aiperf/tests/`
