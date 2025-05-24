#!/usr/bin/env python3
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
"""
Comparison demo showing both monitoring approaches:
1. Worker Performance Monitor - tracks HTTP request metrics
2. Broker Performance Monitor - tracks ZMQ message flow

Run this to see the difference between application-level and broker-level monitoring.
"""

import asyncio
import sys

print("""
🔍 AIPerf Monitoring Comparison Demo
===================================

This demo shows two different monitoring approaches for the ZMQ Worker Manager:

1️⃣ WORKER PERFORMANCE MONITOR (monitor_worker_performance.py)
   📊 Tracks HTTP request metrics from worker handlers
   📈 Shows response times, success rates, worker activity
   🎯 Application-level monitoring

2️⃣ BROKER PERFORMANCE MONITOR (monitor_broker_performance.py)
   📡 Monitors ZMQ message flow through broker capture socket
   📊 Shows message throughput, worker/client connections
   🎯 Infrastructure-level monitoring

USAGE:
------
# Start worker performance monitor (HTTP-level)
python examples/monitor_worker_performance.py

# Start broker performance monitor (ZMQ-level)
python examples/monitor_broker_performance.py

# Or run this comparison script
python examples/monitor_comparison.py [worker|broker]

WHEN TO USE WHICH:
-----------------
🔧 Worker Monitor: Use when you want to see:
   - HTTP request success rates and response times
   - Individual worker performance
   - Application-level bottlenecks
   - End-to-end request metrics

🔧 Broker Monitor: Use when you want to see:
   - Raw ZMQ message throughput
   - Broker infrastructure performance
   - Connection and load balancing insights
   - Lower-level communication metrics

COMBINED MONITORING:
-------------------
For complete observability, run both monitors simultaneously:
- Broker monitor shows ZMQ infrastructure health
- Worker monitor shows application performance
- Together they provide full-stack visibility

""")


async def run_worker_monitor():
    """Run the worker performance monitor."""
    print("🚀 Starting Worker Performance Monitor...")
    print("This monitors HTTP request metrics from worker handlers\n")

    try:
        from monitor_worker_performance import main as worker_main

        await worker_main()
    except ImportError:
        print(
            "❌ Could not import worker monitor. Make sure monitor_worker_performance.py exists."
        )
    except Exception as e:
        print(f"❌ Error running worker monitor: {e}")


async def run_broker_monitor():
    """Run the broker performance monitor."""
    print("🚀 Starting Broker Performance Monitor...")
    print("This monitors ZMQ message flow through broker capture socket\n")

    try:
        from monitor_broker_performance import main as broker_main

        await broker_main()
    except ImportError:
        print(
            "❌ Could not import broker monitor. Make sure monitor_broker_performance.py exists."
        )
    except Exception as e:
        print(f"❌ Error running broker monitor: {e}")


async def show_comparison():
    """Show detailed comparison of both monitoring approaches."""
    print("""
📊 DETAILED MONITORING COMPARISON
=================================

🔍 WORKER PERFORMANCE MONITOR
-----------------------------
SOURCE: HTTP request handler metrics
SCOPE: Application layer (HTTP requests)
METRICS:
├── Total/successful/failed requests
├── Requests per second (RPS)
├── Response time statistics (avg/min/max/p95)
├── Success rate percentage
├── Active worker count
├── Individual worker performance
└── Performance indicators

BEST FOR:
✅ Monitoring application performance
✅ Debugging slow HTTP requests
✅ Tracking worker efficiency
✅ End-to-end request monitoring

📡 BROKER PERFORMANCE MONITOR
-----------------------------
SOURCE: ZMQ broker capture socket
SCOPE: Infrastructure layer (ZMQ messages)
METRICS:
├── Total messages through broker
├── Messages per second (MPS)
├── Average message size
├── Active worker/client connections
├── Message distribution per worker/client
├── Broker load percentage
└── Infrastructure health

BEST FOR:
✅ Monitoring ZMQ infrastructure
✅ Detecting broker bottlenecks
✅ Load balancing insights
✅ Connection monitoring

🎯 RECOMMENDATION
----------------
Use BOTH monitors for complete observability:

Terminal 1: python examples/monitor_broker_performance.py
Terminal 2: python examples/monitor_worker_performance.py
Terminal 3: aiperf run [your-config]

This gives you:
- Infrastructure health (broker monitor)
- Application performance (worker monitor)
- Complete system visibility
""")


async def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        await show_comparison()
        return

    mode = sys.argv[1].lower()

    if mode == "worker":
        await run_worker_monitor()
    elif mode == "broker":
        await run_broker_monitor()
    elif mode in ["help", "--help", "-h"]:
        await show_comparison()
    else:
        print(f"❌ Unknown mode: {mode}")
        print("Use: worker, broker, or help")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Demo stopped")
    except Exception as e:
        print(f"\n❌ Error: {e}")
