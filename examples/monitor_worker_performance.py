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
Real-time performance monitoring for ZMQ Worker Manager.
Shows live throughput metrics and worker statistics.
"""

import asyncio
import time

from aiperf.common.metrics.performance_monitor import get_monitor


class WorkerPerformanceMonitor:
    """Real-time performance monitor for ZMQ workers."""

    def __init__(self, update_interval: float = 2.0):
        """Initialize the monitor.

        Args:
            update_interval: How often to update the display (seconds)
        """
        self.update_interval = update_interval
        self.running = False
        self.monitor = get_monitor()

    async def start_monitoring(self):
        """Start real-time monitoring display."""
        self.running = True
        print("🔍 Starting ZMQ Worker Performance Monitor")
        print("Press Ctrl+C to stop monitoring\n")

        try:
            while self.running:
                # Clear screen and show header
                print("\033[2J\033[H", end="")  # Clear screen

                # Display current time and status
                current_time = time.strftime("%Y-%m-%d %H:%M:%S")
                print(f"🚀 ZMQ Worker Performance Monitor - {current_time}")
                print("=" * 80)

                # Get current metrics
                snapshot = self.monitor.get_snapshot()
                worker_stats = self.monitor.get_worker_stats()

                # Display main metrics
                print("📊 THROUGHPUT METRICS")
                print(f"   Total Requests:       {snapshot.total_requests:,}")
                print(f"   Successful:           {snapshot.successful_requests:,}")
                print(f"   Failed:               {snapshot.failed_requests:,}")

                if snapshot.total_requests > 0:
                    success_rate = (
                        snapshot.successful_requests / snapshot.total_requests
                    ) * 100
                    print(f"   Success Rate:         {success_rate:.1f}%")
                else:
                    print("   Success Rate:         0.0%")

                print(f"   Current RPS:          {snapshot.requests_per_second:.2f}")
                print(f"   Active Workers:       {snapshot.active_workers}")

                # Display response time metrics
                print("\n⏱️  RESPONSE TIME METRICS (ms)")
                print(f"   Average:              {snapshot.avg_response_time_ms:.2f}")
                print(f"   Minimum:              {snapshot.min_response_time_ms:.2f}")
                print(f"   Maximum:              {snapshot.max_response_time_ms:.2f}")
                print(f"   95th Percentile:      {snapshot.p95_response_time_ms:.2f}")

                # Display worker details
                if worker_stats:
                    print("\n👷 WORKER DETAILS")
                    active_workers = [
                        w for w, s in worker_stats.items() if s["is_active"]
                    ]
                    inactive_workers = [
                        w for w, s in worker_stats.items() if not s["is_active"]
                    ]

                    print(f"   Active Workers:       {len(active_workers)}")
                    print(f"   Inactive Workers:     {len(inactive_workers)}")

                    # Show top 10 most active workers
                    sorted_workers = sorted(
                        worker_stats.items(),
                        key=lambda x: x[1]["requests"],
                        reverse=True,
                    )[:10]

                    if sorted_workers:
                        print("\n   Top Workers:")
                        for worker_id, stats in sorted_workers:
                            status = "🟢" if stats["is_active"] else "🔴"
                            print(
                                f"     {status} {worker_id[:20]:<20} "
                                f"{stats['requests']:>6} reqs  "
                                f"{stats['avg_response_time_ms']:>6.1f}ms avg"
                            )
                else:
                    print("\n👷 No worker activity detected yet")

                # Display rate information
                print("\n📈 RATE ANALYSIS")
                if snapshot.requests_per_second > 0:
                    estimated_peak = (
                        snapshot.requests_per_second * 1.5
                    )  # Rough estimate
                    print(
                        f"   Current Rate:         {snapshot.requests_per_second:.1f} RPS"
                    )
                    print(f"   Estimated Peak:       {estimated_peak:.1f} RPS")

                    # Performance indicators
                    if snapshot.avg_response_time_ms < 100:
                        perf_indicator = "🟢 Excellent"
                    elif snapshot.avg_response_time_ms < 500:
                        perf_indicator = "🟡 Good"
                    elif snapshot.avg_response_time_ms < 1000:
                        perf_indicator = "🟠 Fair"
                    else:
                        perf_indicator = "🔴 Poor"

                    print(f"   Performance:          {perf_indicator}")
                else:
                    print("   Status:               ⏳ Waiting for requests...")

                # System uptime
                uptime = time.time() - self.monitor.start_time
                uptime_str = f"{int(uptime // 3600):02d}:{int((uptime % 3600) // 60):02d}:{int(uptime % 60):02d}"
                print(f"\n🕐 System Uptime:        {uptime_str}")

                print("\n" + "=" * 80)
                print("Press Ctrl+C to stop monitoring")

                # Wait for next update
                await asyncio.sleep(self.update_interval)

        except KeyboardInterrupt:
            self.running = False
            print("\n\n👋 Monitoring stopped by user")

        except Exception as e:
            print(f"\n❌ Monitoring error: {e}")
            self.running = False

    def stop_monitoring(self):
        """Stop the monitoring loop."""
        self.running = False


async def show_help():
    """Show help information about the monitoring tool."""
    print("""
🔍 ZMQ Worker Performance Monitor
================================

This tool provides real-time monitoring of your ZMQ worker system performance.

METRICS DISPLAYED:
- Total/Successful/Failed requests
- Current requests per second (RPS)
- Response time statistics (avg, min, max, p95)
- Active worker count and individual worker stats
- Performance indicators and system uptime

USAGE:
1. Start your ZMQ Worker Manager with HTTP workers
2. Run this monitor: python examples/monitor_worker_performance.py
3. Send requests through your system
4. Watch real-time performance metrics

The monitor updates every 2 seconds and shows a rolling window of recent activity.
Worker performance is tracked individually, showing which workers are most active.

Press Ctrl+C anytime to stop monitoring.
""")


async def main():
    """Main entry point for the monitor."""
    import sys

    if len(sys.argv) > 1 and sys.argv[1] in ["--help", "-h", "help"]:
        await show_help()
        return

    monitor = WorkerPerformanceMonitor()
    await monitor.start_monitoring()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Goodbye!")
    except Exception as e:
        print(f"\n❌ Error: {e}")
