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
# 🔍 AIPerf Monitoring Tools

This directory contains two powerful monitoring tools for the ZMQ Worker Manager system, each providing different levels of observability.

## 📊 Available Monitors

### 1. Worker Performance Monitor
**File**: `monitor_worker_performance.py`
**Level**: Application Layer (HTTP requests)
**Source**: HTTP worker handler metrics

```bash
python examples/monitor_worker_performance.py
```

**Features:**
- ✅ HTTP request success rates and response times
- ✅ Individual worker performance tracking
- ✅ Requests per second (RPS) calculation
- ✅ Response time statistics (avg/min/max/p95)
- ✅ Real-time performance indicators
- ✅ Worker activity visualization

### 2. Broker Performance Monitor 🆕
**File**: `monitor_broker_performance.py`
**Level**: Infrastructure Layer (ZMQ messages)
**Source**: ZMQ broker capture socket

```bash
python examples/monitor_broker_performance.py
```

**Features:**
- ✅ Real-time ZMQ message throughput (MPS)
- ✅ Worker and client connection monitoring
- ✅ Message size analysis
- ✅ Load balancing insights with visual bars
- ✅ Broker infrastructure health
- ✅ Peak performance tracking

## 🎯 When to Use Which Monitor

### Use Worker Monitor When:
- 🔧 Debugging application performance issues
- 🔧 Monitoring end-to-end request latency
- 🔧 Tracking HTTP request success rates
- 🔧 Optimizing worker efficiency
- 🔧 Analyzing response time patterns

### Use Broker Monitor When:
- 🔧 Monitoring ZMQ infrastructure health
- 🔧 Detecting broker bottlenecks
- 🔧 Understanding load distribution
- 🔧 Tracking raw message throughput
- 🔧 Monitoring worker/client connections

## 🚀 Monitoring Setup Guide

### Single Monitor Setup
```bash
# Option 1: Application-level monitoring
python examples/monitor_worker_performance.py

# Option 2: Infrastructure-level monitoring
python examples/monitor_broker_performance.py
```

### Full Observability Setup (Recommended)
For complete system visibility, run both monitors:

```bash
# Terminal 1: Infrastructure monitoring
python examples/monitor_broker_performance.py

# Terminal 2: Application monitoring
python examples/monitor_worker_performance.py

# Terminal 3: Run your workload
aiperf run your-config.yaml
```

### Quick Comparison Demo
```bash
python examples/monitor_comparison.py [worker|broker|help]
```

## 📈 Monitor Comparison

| Aspect | Worker Monitor | Broker Monitor |
|--------|---------------|----------------|
| **Data Source** | HTTP handler metrics | ZMQ capture socket |
| **Scope** | Application layer | Infrastructure layer |
| **Granularity** | Request-level | Message-level |
| **Response Times** | ✅ Detailed stats | ❌ Not tracked |
| **Success Rates** | ✅ HTTP status tracking | ❌ Not applicable |
| **Message Throughput** | ❌ Not directly | ✅ Real-time MPS |
| **Connection Health** | ❌ Worker activity only | ✅ Full connection tracking |
| **Load Distribution** | ❌ Request-based only | ✅ Message-based insights |
| **Performance Impact** | Minimal | None (passive monitoring) |

## 🔧 Technical Details

### Worker Monitor Architecture
```
HTTP Request → Worker Handler → Performance Metrics → Monitor Display
```
- Integrates with `aiperf.common.metrics.performance_monitor`
- Tracks metrics in worker handlers during request processing
- Provides application-level observability

### Broker Monitor Architecture
```
ZMQ Messages → Broker Proxy → Capture Socket → Monitor Display
```
- Connects to broker's capture address (passive monitoring)
- Receives copies of all messages flowing through broker
- Zero performance impact on broker operations

## 📊 Sample Outputs

### Worker Monitor Display
```
🚀 ZMQ Worker Performance Monitor - 2025-01-24 15:30:45
================================================================
📊 THROUGHPUT METRICS
   Total Requests:       1,247
   Successful:           1,198
   Failed:               49
   Success Rate:         96.1%
   Current RPS:          23.45
   Active Workers:       8

⏱️  RESPONSE TIME METRICS (ms)
   Average:              145.32
   Minimum:              12.45
   Maximum:              1,203.67
   95th Percentile:      287.91
```

### Broker Monitor Display
```
🚀 ZMQ Broker Performance Monitor - 2025-01-24 15:30:45
================================================================
📊 BROKER THROUGHPUT METRICS
   Total Messages:       2,847
   Current MPS:          47.32
   Peak MPS:             89.15
   Avg Message Size:     1,247 bytes

🔗 CONNECTION METRICS
   Active Workers:       8
   Active Clients:       3
   Total Connections:    11

👷 TOP WORKER ACTIVITY
   worker-0-1           342 msgs ████████████████████
   worker-0-2           298 msgs ████████████████
   worker-1-0           276 msgs ███████████████
```

## 🚨 Troubleshooting

### Common Issues

**Worker Monitor shows no activity:**
- Ensure worker manager is running with HTTP workers
- Check that requests are being sent through the system
- Verify worker handlers are using the performance monitor

**Broker Monitor shows no messages:**
- Ensure broker is running with capture socket enabled
- Check ZMQ configuration has correct capture address
- Verify broker proxy is processing messages

**Connection refused errors:**
- Check that services are running and listening on expected ports
- Verify ZMQ addresses in configuration match monitor expectations
- Ensure firewall/network policies allow connections

### Performance Considerations

- **Worker Monitor**: Minimal overhead (~1-2% performance impact)
- **Broker Monitor**: Zero overhead (passive capture socket monitoring)
- Both monitors use efficient data structures and update frequencies

## 🎉 Best Practices

1. **Start with Broker Monitor** for infrastructure baseline
2. **Add Worker Monitor** for application-level insights
3. **Use both together** for complete observability
4. **Monitor during load testing** to identify bottlenecks
5. **Establish performance baselines** before optimization
6. **Set up alerts** based on monitor thresholds

---

*For more information, see the individual monitor files or run with `--help` flag.*
