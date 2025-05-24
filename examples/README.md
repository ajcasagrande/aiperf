<!--
#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#  http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
-->
# Examples

This directory contains example applications for the aiperf project.

## FastAPI Request Logger

A simple FastAPI webserver that logs all incoming requests and returns "ok".

### Features

- Logs all HTTP methods (GET, POST, PUT, DELETE, etc.)
- Logs request details including headers, query params, and body
- Returns JSON response with "ok" status
- Includes CORS middleware for cross-origin requests
- Health check endpoint at `/health`

### Running

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Run the server:
```bash
python fastapi_server.py
```

The server will start on `http://0.0.0.0:9797`

### Testing

Test with curl:
```bash
# GET request
curl http://localhost:9797/

# POST request with data
curl -X POST http://localhost:9797/api/test -H "Content-Type: application/json" -d '{"key": "value"}'

# Health check
curl http://localhost:9797/health
```

All requests will be logged to the console with details including method, path, headers, and response time.

## HTTP Worker Testing

The `test_http_worker.py` script demonstrates the high-performance HTTP worker functionality.

### Features

- Tests connection to FastAPI server
- Shows example HTTP request payloads
- Demonstrates various HTTP methods (GET, POST, PUT, DELETE)
- Validates server connectivity

### Running

1. Start the FastAPI server first:
```bash
python fastapi_server.py
```

2. Run the HTTP worker test:
```bash
python test_http_worker.py
```

### HTTP Worker Integration

The ZMQ Worker Manager now includes `http_request_worker_handler` that:

- Makes high-performance HTTP requests using `httpx`
- Supports connection pooling and HTTP/2
- Handles all HTTP methods with JSON/form data
- Returns detailed response information including timing
- Provides comprehensive error handling

Example request format for workers:
```json
{
  "method": "POST",
  "path": "/api/endpoint",
  "headers": {"Content-Type": "application/json"},
  "json": {"data": "value"},
  "params": {"query": "param"}
}
```

The worker returns:
```json
{
  "worker_id": "worker-123",
  "status_code": 200,
  "response_time_ms": 45.2,
  "headers": {"content-type": "application/json"},
  "content": "response body",
  "url": "http://localhost:9797/api/endpoint",
  "method": "POST"
}
```

## Performance Monitoring & Benchmarking

### Real-Time Performance Monitor

`monitor_worker_performance.py` provides live monitoring of ZMQ worker system performance:

**Features:**
- **Real-time metrics**: Updates every 2 seconds with live data
- **Throughput tracking**: Current RPS, total/successful/failed requests
- **Response time analysis**: Average, min, max, 95th percentile
- **Worker statistics**: Individual worker performance and activity
- **Performance indicators**: Visual performance ratings
- **System uptime**: Track how long the system has been running

**Usage:**
```bash
# Start monitoring (run this while your ZMQ workers are active)
python examples/monitor_worker_performance.py

# Show help
python examples/monitor_worker_performance.py --help
```

**Display includes:**
```
🚀 ZMQ Worker Performance Monitor - 2025-01-09 15:30:45
================================================================================
📊 THROUGHPUT METRICS
   Total Requests:       1,234
   Successful:           1,200
   Failed:               34
   Success Rate:         97.2%
   Current RPS:          45.67
   Active Workers:       8

⏱️  RESPONSE TIME METRICS (ms)
   Average:              123.45
   Minimum:              12.34
   Maximum:              567.89
   95th Percentile:      234.56

👷 WORKER DETAILS
   Active Workers:       8
   Inactive Workers:     0

   Top Workers:
     🟢 worker-0-1           234 reqs   98.7ms avg
     🟢 worker-1-2           221 reqs  102.3ms avg
     🟢 worker-2-3           198 reqs   95.1ms avg

📈 RATE ANALYSIS
   Current Rate:         45.7 RPS
   Estimated Peak:       68.5 RPS
   Performance:          🟢 Excellent

🕐 System Uptime:        01:23:45
```

### Throughput Benchmark Tool

`benchmark_throughput.py` provides comprehensive load testing capabilities:

**Features:**
- **Multiple test scenarios**: Light, medium, and high load tests
- **Configurable RPS**: Set target requests per second
- **Live monitoring**: Real-time performance display during tests
- **Connection pooling**: High-performance HTTP client with connection reuse
- **Detailed statistics**: Response times, success rates, error analysis

**Usage:**
```bash
# Run the full benchmark suite
python examples/benchmark_throughput.py

# Each scenario will prompt you to continue:
# 1. Light Load - 10 RPS for 30s
# 2. Medium Load - 50 RPS for 30s
# 3. High Load - 100 RPS for 60s
```

**Live display during benchmarks:**
```
🔥 LIVE PERFORMANCE METRICS 🔥
============================================================
Performance Metrics - 15:30:45
============================================================
Total Requests:       1,500
Successful:           1,485
Failed:               15
Success Rate:         99.0%
Requests/Second:      98.76
Active Workers:       0

Response Times (ms):
  Average:            45.23
  Minimum:            12.10
  Maximum:            234.56
  95th Percentile:    89.12

Uptime: 152.3s
============================================================
Press Ctrl+C to stop benchmark
```

### Performance Metrics Collected

The monitoring system tracks:

1. **Throughput Metrics:**
   - Total requests processed
   - Successful vs failed requests
   - Current requests per second (RPS)
   - Success rate percentage

2. **Response Time Analysis:**
   - Average response time
   - Minimum and maximum response times
   - 95th percentile response time
   - Response time distribution

3. **Worker Performance:**
   - Active worker count
   - Per-worker request counts
   - Per-worker average response times
   - Worker activity status

4. **System Health:**
   - Error rates and types
   - Connection status
   - Resource utilization indicators
   - System uptime

### Integration with ZMQ Workers

The monitoring system integrates seamlessly with the HTTP worker handler:

1. **Automatic tracking**: All HTTP requests are automatically monitored
2. **Worker identification**: Each worker is individually tracked
3. **Real-time updates**: Metrics update as requests are processed
4. **Zero overhead**: Minimal performance impact on actual request processing

### Getting Started with Performance Monitoring

1. **Start the FastAPI server:**
   ```bash
   python examples/fastapi_server.py
   ```

2. **Start your ZMQ Worker Manager** (with HTTP workers enabled)

3. **Start the performance monitor:**
   ```bash
   python examples/monitor_worker_performance.py
   ```

4. **Run load tests:**
   ```bash
   python examples/benchmark_throughput.py
   ```

5. **Watch real-time metrics** as requests flow through your system!

### Testing Credit Drop Flow

The `test_credit_flow.py` script helps debug the complete credit drop processing flow:

**Features:**
- **End-to-end testing**: Verifies the complete flow from timing manager to FastAPI server
- **Real-time monitoring**: Shows when credit drops are being processed
- **Connectivity testing**: Checks if FastAPI server is reachable
- **Troubleshooting guidance**: Provides specific debugging steps

**Usage:**
```bash
# Test the complete credit drop flow
python examples/test_credit_flow.py
```

**Sample output:**
```
🧪 Credit Drop Flow Test
========================================
✅ FastAPI server is running (Status: 200)

🎯 Testing credit drop processing...
This monitor will show if:
• Credit drops are being received by the worker manager
• Workers are making HTTP requests to the FastAPI server
• The complete flow is working end-to-end

Starting 60-second monitoring session...
Press Ctrl+C to stop early

🔍 Credit Drop Flow Monitor
==================================================
[15:30:45] ✅ New requests detected: +5 (Total: 5, RPS: 2.50)
[15:30:46] ✅ New requests detected: +3 (Total: 8, RPS: 4.00)

📊 Statistics after 10s:
   Total Requests:   25
   Success Rate:     100.0%
   Current RPS:      2.50
   Active Workers:   4
   Avg Response:     45.23ms
```

**If no requests are detected:**
The script provides troubleshooting guidance to check:
1. Timing manager is running and sending credit drops
2. Worker manager is receiving and processing credit drops
3. FastAPI server is accessible on port 9797
4. Log messages for any errors

The monitoring tools provide everything you need to optimize your system's performance and track throughput under various load conditions.
