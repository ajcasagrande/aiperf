<!--
# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
-->
# Chapter 50: Troubleshooting Guide

## Overview

This comprehensive troubleshooting guide helps diagnose and resolve common AIPerf issues. Find solutions to error messages, performance problems, configuration issues, and operational challenges.

## Table of Contents

- [Common Problems](#common-problems)
- [Diagnostic Procedures](#diagnostic-procedures)
- [Error Messages](#error-messages)
- [Performance Issues](#performance-issues)
- [Configuration Issues](#configuration-issues)
- [Network Issues](#network-issues)
- [FAQ](#faq)
- [Getting Help](#getting-help)

---

## Common Problems

### Problem 1: Connection Refused

**Symptoms:**
```
ERROR: Connection refused at http://localhost:8000
InferenceClientError: Failed to connect to endpoint
```

**Causes:**
- Inference server not running
- Wrong URL or port
- Firewall blocking connection
- Network issues

**Solutions:**

1. **Verify Server is Running:**
   ```bash
   curl http://localhost:8000/v1/models
   ```

2. **Check Port:**
   ```bash
   netstat -an | grep 8000
   lsof -i :8000
   ```

3. **Test Connectivity:**
   ```bash
   telnet localhost 8000
   nc -zv localhost 8000
   ```

4. **Fix Configuration:**
   ```bash
   # Correct URL format
   aiperf profile --url http://localhost:8000  # Correct
   aiperf profile --url localhost:8000         # Wrong
   ```

---

### Problem 2: Request Timeouts

**Symptoms:**
```
WARNING: Request timeout after 60.0 seconds
ERROR: Timeout waiting for response
```

**Causes:**
- Server overloaded
- Requests taking too long
- Network latency
- Insufficient timeout setting

**Solutions:**

1. **Increase Timeout:**
   ```bash
   aiperf profile --request-timeout-seconds 120.0 [options...]
   ```

2. **Reduce Load:**
   ```bash
   # Lower concurrency
   aiperf profile --concurrency 5 [options...]

   # Reduce request rate
   aiperf profile --request-rate 10 [options...]
   ```

3. **Check Server Performance:**
   ```bash
   # Monitor server logs
   tail -f /path/to/server/logs

   # Check server metrics
   curl http://localhost:8000/metrics
   ```

4. **Optimize Request Size:**
   ```bash
   # Reduce max tokens
   aiperf profile --output-tokens-mean 100 [options...]
   ```

---

### Problem 3: Memory Errors

**Symptoms:**
```
MemoryError: Unable to allocate memory
OSError: [Errno 12] Cannot allocate memory
```

**Causes:**
- Insufficient system memory
- Memory leak
- Too many workers
- Large dataset

**Solutions:**

1. **Reduce Workers:**
   ```bash
   aiperf profile --num-workers 2 [options...]
   ```

2. **Monitor Memory:**
   ```bash
   # Check memory usage
   free -h
   watch -n 1 free -h

   # Check per-process memory
   ps aux --sort=-%mem | head -20
   ```

3. **Increase System Memory:**
   ```bash
   # Docker
   docker run --memory=8g aiperf:latest [options...]

   # Kubernetes
   resources:
     limits:
       memory: 8Gi
   ```

4. **Use Streaming Dataset:**
   ```python
   # Load dataset incrementally instead of all at once
   def load_streaming(filename):
       with open(filename) as f:
           for line in f:
               yield parse_line(line)
   ```

---

### Problem 4: Service Hangs

**Symptoms:**
```
INFO: Starting services...
[No further output, process appears frozen]
```

**Causes:**
- Invalid configuration
- Deadlock in services
- ZMQ communication issue
- Resource exhaustion

**Solutions:**

1. **Enable Debug Logging:**
   ```bash
   aiperf profile --log-level DEBUG --service-log-level DEBUG [options...]
   ```

2. **Kill and Restart:**
   ```bash
   # Find process
   ps aux | grep aiperf

   # Kill
   pkill -9 -f aiperf

   # Restart with minimal config
   aiperf profile --model test --url http://localhost:8000 --endpoint-type chat --request-count 1
   ```

3. **Check System Resources:**
   ```bash
   # CPU usage
   top

   # File descriptors
   lsof -p $(pgrep -f aiperf) | wc -l

   # Check limits
   ulimit -a
   ```

4. **Test Configuration:**
   ```python
   from aiperf.common.config import UserConfig

   try:
       config = UserConfig(...)
       print("Configuration valid")
   except Exception as e:
       print(f"Configuration error: {e}")
   ```

---

### Problem 5: Invalid Responses

**Symptoms:**
```
ERROR: Failed to parse response
ValidationError: Invalid response format
```

**Causes:**
- Endpoint returns non-standard format
- Response malformed
- Streaming format incorrect
- Version mismatch

**Solutions:**

1. **Verify Response Format:**
   ```bash
   # Test endpoint directly
   curl -X POST http://localhost:8000/v1/chat/completions \
     -H "Content-Type: application/json" \
     -d '{
       "model": "Qwen/Qwen3-0.6B",
       "messages": [{"role": "user", "content": "Hello"}]
     }'
   ```

2. **Check Endpoint Type:**
   ```bash
   # Ensure correct endpoint type
   aiperf profile --endpoint-type chat  # For /v1/chat/completions
   aiperf profile --endpoint-type completions  # For /v1/completions
   ```

3. **Disable Streaming (Testing):**
   ```bash
   # Test without streaming
   aiperf profile --no-streaming [options...]
   ```

4. **Custom Response Extractor:**
   ```python
   # Create custom extractor if needed
   @ResponseExtractorFactory.register(EndpointType.CUSTOM)
   class CustomExtractor:
       async def extract(self, response):
           # Custom parsing logic
           pass
   ```

---

## Diagnostic Procedures

### Procedure 1: Connection Diagnostic

```bash
#!/bin/bash
# diagnose_connection.sh

echo "=== Connection Diagnostic ==="

# 1. Test DNS resolution
echo "1. DNS Resolution:"
nslookup localhost

# 2. Test port availability
echo "2. Port Check:"
nc -zv localhost 8000

# 3. Test HTTP connection
echo "3. HTTP Test:"
curl -I http://localhost:8000

# 4. Test endpoint
echo "4. Endpoint Test:"
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model": "test", "messages": [{"role": "user", "content": "test"}]}'
```

### Procedure 2: Performance Diagnostic

```bash
#!/bin/bash
# diagnose_performance.sh

echo "=== Performance Diagnostic ==="

# 1. System resources
echo "1. System Resources:"
free -h
df -h

# 2. CPU usage
echo "2. CPU Usage:"
mpstat 1 5

# 3. Network
echo "3. Network Stats:"
netstat -s | grep -i error

# 4. AIPerf processes
echo "4. AIPerf Processes:"
ps aux | grep aiperf

# 5. File descriptors
echo "5. Open Files:"
lsof | grep aiperf | wc -l
```

### Procedure 3: Configuration Diagnostic

```python
#!/usr/bin/env python3
# diagnose_config.py

from aiperf.common.config import UserConfig, EndpointConfig, LoadGeneratorConfig
import json

def diagnose_config():
    """Diagnose configuration issues"""

    print("=== Configuration Diagnostic ===\n")

    # 1. Test endpoint config
    print("1. Testing Endpoint Configuration:")
    try:
        endpoint = EndpointConfig(
            model_names=["Qwen/Qwen3-0.6B"],
            url="http://localhost:8000",
            type="chat"
        )
        print("   ✓ Endpoint config valid")
        print(f"   URL: {endpoint.url}")
        print(f"   Type: {endpoint.type}")
    except Exception as e:
        print(f"   ✗ Endpoint config error: {e}")

    # 2. Test loadgen config
    print("\n2. Testing LoadGen Configuration:")
    try:
        loadgen = LoadGeneratorConfig(
            request_count=10,
            concurrency=1
        )
        print("   ✓ LoadGen config valid")
        print(f"   Requests: {loadgen.request_count}")
        print(f"   Concurrency: {loadgen.concurrency}")
    except Exception as e:
        print(f"   ✗ LoadGen config error: {e}")

    # 3. Test user config
    print("\n3. Testing User Configuration:")
    try:
        user = UserConfig(
            endpoint=endpoint,
            loadgen=loadgen
        )
        print("   ✓ User config valid")
    except Exception as e:
        print(f"   ✗ User config error: {e}")

if __name__ == "__main__":
    diagnose_config()
```

---

## Error Messages

### "No module named 'aiperf'"

**Error:**
```
ImportError: No module named 'aiperf'
ModuleNotFoundError: No module named 'aiperf'
```

**Solutions:**

1. **Install AIPerf:**
   ```bash
   pip install aiperf
   ```

2. **Check Installation:**
   ```bash
   pip list | grep aiperf
   python -c "import aiperf; print(aiperf.__version__)"
   ```

3. **Verify PYTHONPATH:**
   ```bash
   echo $PYTHONPATH
   export PYTHONPATH=/path/to/aiperf:$PYTHONPATH
   ```

---

### "ValidationError: 1 validation error"

**Error:**
```
ValidationError: 1 validation error for UserConfig
  endpoint.type
    Input should be 'chat', 'completions', or 'embeddings'
```

**Solutions:**

1. **Check Field Type:**
   ```python
   # Correct
   endpoint = EndpointConfig(type="chat")

   # Wrong
   endpoint = EndpointConfig(type="chatbot")
   ```

2. **Review Valid Values:**
   ```python
   from aiperf.common.enums import EndpointType
   print(list(EndpointType))
   ```

---

### "CommunicationError: Failed to connect to message bus"

**Error:**
```
CommunicationError: Failed to connect to message bus
zmq.error.ZMQError: Address already in use
```

**Solutions:**

1. **Check Port Availability:**
   ```bash
   lsof -i :50051
   ```

2. **Kill Existing Process:**
   ```bash
   pkill -f aiperf
   ```

3. **Use Different Port:**
   ```python
   from aiperf.common.config import ServiceConfig

   service_config = ServiceConfig(
       zmq_base_port=60000  # Different port range
   )
   ```

---

## Performance Issues

### Slow Request Processing

**Symptoms:**
- Low throughput
- High latency
- Long benchmark duration

**Diagnostic:**
```bash
# Profile AIPerf itself
python -m cProfile -o profile.stats -m aiperf.cli profile [options...]

# Analyze
python -m pstats profile.stats
>>> sort cumtime
>>> stats 20
```

**Solutions:**

1. **Increase Workers:**
   ```bash
   aiperf profile --num-workers 8 [options...]
   ```

2. **Optimize Concurrency:**
   ```bash
   # Find optimal concurrency
   for c in 5 10 20 50; do
     echo "Testing concurrency: $c"
     aiperf profile --concurrency $c [options...] --output-file "results_c${c}.json"
   done
   ```

3. **Reduce Logging:**
   ```bash
   # Set to WARNING or ERROR
   aiperf profile --log-level WARNING [options...]
   ```

---

### High Memory Usage

**Symptoms:**
- Memory consumption increases over time
- Out of memory errors
- Swapping

**Diagnostic:**
```python
import tracemalloc

tracemalloc.start()

# Run benchmark
run_system_controller(user_config, service_config)

# Get memory snapshot
snapshot = tracemalloc.take_snapshot()
top_stats = snapshot.statistics('lineno')

for stat in top_stats[:10]:
    print(stat)
```

**Solutions:**

1. **Reduce Dataset Size:**
   ```bash
   # Load dataset incrementally
   aiperf profile --request-count 100 [options...]
   ```

2. **Enable Garbage Collection:**
   ```python
   import gc
   gc.collect()
   ```

3. **Monitor and Limit:**
   ```bash
   # Docker
   docker run --memory=4g --memory-swap=4g aiperf:latest [options...]
   ```

---

## Configuration Issues

### Invalid Endpoint Configuration

**Problem:**
```yaml
endpoint:
  url: localhost:8000  # Missing protocol
  type: chat_completion  # Wrong type name
```

**Solution:**
```yaml
endpoint:
  url: http://localhost:8000  # Correct protocol
  type: chat  # Correct type name
```

---

### Dataset Loading Errors

**Problem:**
```
DatasetLoaderError: File not found: dataset.jsonl
```

**Solutions:**

1. **Verify File Path:**
   ```bash
   ls -l dataset.jsonl
   realpath dataset.jsonl
   ```

2. **Use Absolute Path:**
   ```bash
   aiperf profile --input-file /full/path/to/dataset.jsonl [options...]
   ```

3. **Check File Format:**
   ```bash
   # Validate JSONL format
   cat dataset.jsonl | jq -c .
   ```

---

## Network Issues

### Connection Timeouts

**Diagnostic:**
```bash
# Test network latency
ping -c 10 localhost

# Test connection
time curl http://localhost:8000/v1/models

# Monitor connections
watch -n 1 'netstat -an | grep 8000 | grep ESTABLISHED | wc -l'
```

**Solutions:**

1. **Increase Timeouts:**
   ```bash
   aiperf profile --request-timeout-seconds 120.0 [options...]
   ```

2. **Reduce Load:**
   ```bash
   aiperf profile --concurrency 5 --request-rate 10 [options...]
   ```

---

### SSL/TLS Errors

**Error:**
```
SSLError: [SSL: CERTIFICATE_VERIFY_FAILED]
```

**Solutions:**

1. **Disable SSL Verification (Testing Only):**
   ```python
   import ssl
   import aiohttp

   connector = aiohttp.TCPConnector(ssl=False)
   ```

2. **Use Correct Certificate:**
   ```bash
   export SSL_CERT_FILE=/path/to/cert.pem
   ```

---

## FAQ

### Q: How do I debug a hanging process?

**A:** Use these techniques:

```bash
# 1. Check process state
ps aux | grep aiperf

# 2. Get stack trace
kill -USR1 $(pgrep -f aiperf)

# 3. Attach debugger
gdb -p $(pgrep -f aiperf)
>>> thread apply all bt

# 4. Use strace
strace -p $(pgrep -f aiperf)
```

---

### Q: How do I reduce memory usage?

**A:** Try these approaches:

1. Reduce workers: `--num-workers 2`
2. Reduce concurrency: `--concurrency 5`
3. Use streaming dataset loading
4. Disable verbose logging: `--log-level WARNING`
5. Limit request count: `--request-count 100`

---

### Q: Why are results inconsistent?

**A:** Check these factors:

1. **Server State:** Ensure server is warmed up
2. **System Load:** Run on idle system
3. **Network:** Check for network variability
4. **Configuration:** Use consistent configuration
5. **Warmup:** Add warmup requests

```bash
# Add warmup
aiperf profile --warmup-request-count 10 [options...]
```

---

### Q: How do I benchmark behind a proxy?

**A:** Configure proxy settings:

```bash
# Set environment variables
export HTTP_PROXY=http://proxy.example.com:8080
export HTTPS_PROXY=http://proxy.example.com:8080
export NO_PROXY=localhost,127.0.0.1

# Run AIPerf
aiperf profile [options...]
```

---

## Getting Help

### Collect Diagnostic Information

```bash
#!/bin/bash
# collect_diagnostics.sh

echo "=== AIPerf Diagnostic Report ==="
echo "Date: $(date)"
echo

echo "=== System Information ==="
uname -a
cat /etc/os-release
echo

echo "=== Python Environment ==="
python --version
pip list | grep aiperf
echo

echo "=== AIPerf Configuration ==="
aiperf --version
echo

echo "=== System Resources ==="
free -h
df -h
echo

echo "=== Network ==="
netstat -an | grep 8000
echo

echo "=== Logs (last 50 lines) ==="
tail -50 aiperf.log
```

### Report Issues

When reporting issues, include:

1. **AIPerf version:** `aiperf --version`
2. **Python version:** `python --version`
3. **Operating system:** `uname -a`
4. **Complete error message**
5. **Minimal reproduction steps**
6. **Configuration used**
7. **Logs with `--log-level DEBUG`**

### Community Support

- **GitHub Issues:** https://github.com/ai-dynamo/aiperf/issues
- **Discord:** https://discord.gg/D92uqZRjCZ
- **Documentation:** https://github.com/ai-dynamo/aiperf/docs

---

## Troubleshooting Checklist

- [ ] Verified endpoint is accessible
- [ ] Tested with minimal configuration
- [ ] Enabled DEBUG logging
- [ ] Checked system resources
- [ ] Reviewed error messages
- [ ] Tested network connectivity
- [ ] Validated configuration
- [ ] Checked AIPerf version
- [ ] Reviewed logs
- [ ] Isolated the problem
- [ ] Collected diagnostic information
- [ ] Searched existing issues

---

## Key Takeaways

1. **Systematic Approach:** Follow diagnostic procedures
2. **Logging:** Enable DEBUG for troubleshooting
3. **Isolation:** Test with minimal configuration
4. **Documentation:** Collect diagnostic information
5. **Community:** Seek help when needed
6. **Prevention:** Follow best practices
7. **Testing:** Validate in isolation before production

---

## Navigation

- [Previous Chapter: Chapter 49 - Deployment Guide](chapter-49-deployment-guide.md)
- [Return to Index](INDEX.md)

---

**Document Information**
- **File**: `/home/anthony/nvidia/projects/aiperf/guidebook/chapter-50-troubleshooting-guide.md`
- **Purpose**: Comprehensive troubleshooting guide
- **Target Audience**: All AIPerf users
- **Related Chapters**:
  - [Chapter 41 - Debugging Techniques](chapter-41-debugging-techniques.md)
  - [Chapter 42 - Performance Profiling](chapter-42-performance-profiling.md)
