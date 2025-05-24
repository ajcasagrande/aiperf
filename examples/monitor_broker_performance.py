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
Real-time ZMQ Broker Performance Monitor using Capture Socket.
Monitors message flow through the broker proxy to calculate throughput and performance metrics.
"""

import asyncio
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field

import zmq
import zmq.asyncio

from aiperf.common.models.comms import ZMQCommunicationConfig, ZMQTCPTransportConfig


@dataclass
class BrokerMetrics:
    """Broker performance metrics snapshot."""

    total_messages: int = 0
    messages_per_second: float = 0.0
    active_workers: int = 0
    active_clients: int = 0
    avg_message_size: float = 0.0
    peak_mps: float = 0.0
    uptime_seconds: float = 0.0
    worker_distribution: dict[str, int] = field(default_factory=dict)
    client_distribution: dict[str, int] = field(default_factory=dict)


class ZMQBrokerMonitor:
    """Real-time ZMQ broker performance monitor using capture socket."""

    def __init__(
        self, zmq_config: ZMQCommunicationConfig | None = None, window_size: int = 100
    ):
        """Initialize the broker monitor.

        Args:
            zmq_config: ZMQ configuration with capture address
            window_size: Number of recent messages to keep for rate calculation
        """
        self.zmq_config = zmq_config or ZMQCommunicationConfig(
            protocol_config=ZMQTCPTransportConfig()
        )
        self.window_size = window_size

        # Message tracking
        self.message_times = deque(maxlen=window_size)
        self.message_sizes = deque(maxlen=window_size)
        self.worker_stats = defaultdict(int)
        self.client_stats = defaultdict(int)

        # Performance tracking
        self.total_messages = 0
        self.start_time = time.time()
        self.last_update = time.time()
        self.peak_mps = 0.0

        # ZMQ components
        self.context: zmq.asyncio.Context | None = None
        self.capture_socket: zmq.asyncio.Socket | None = None
        self.running = False

    async def initialize(self):
        """Initialize ZMQ context and capture socket."""
        self.context = zmq.asyncio.Context()
        self.capture_socket = self.context.socket(zmq.SUB)

        # Subscribe to all messages on capture socket
        self.capture_socket.setsockopt(zmq.SUBSCRIBE, b"")

        # Connect to broker's capture address
        capture_address = self.zmq_config.credit_broker_capture_address
        self.capture_socket.connect(capture_address)

        print(f"🔗 Connected to broker capture socket: {capture_address}")

    async def shutdown(self):
        """Clean shutdown of ZMQ components."""
        self.running = False
        if self.capture_socket:
            self.capture_socket.close()
        if self.context:
            self.context.term()

    def _parse_captured_message(
        self, frames: list
    ) -> tuple[str | None, str | None, int]:
        """Parse captured message frames.

        Args:
            frames: List of message frames from capture socket

        Returns:
            Tuple of (worker_id, client_id, message_size)
        """
        try:
            if len(frames) < 3:
                return None, None, 0

            # Frame structure from capture socket:
            # Frame 0: Source socket identity
            # Frame 1: Empty delimiter
            # Frame 2+: Message parts

            source_id = frames[0].decode("utf-8", errors="ignore")
            message_parts = frames[2:]

            # Calculate total message size
            total_size = sum(len(frame) for frame in message_parts)

            # Try to determine if this is from worker or client
            # Workers typically have predictable IDs, clients are more random
            if "-" in source_id and len(source_id.split("-")) >= 2:
                # Likely a worker ID (format: process-task)
                return source_id, None, total_size
            else:
                # Likely a client ID
                return None, source_id, total_size

        except Exception:
            # Silently handle parsing errors
            return None, None, 0

    def _calculate_rate(self) -> float:
        """Calculate current messages per second."""
        if len(self.message_times) < 2:
            return 0.0

        # Calculate rate over the time window
        time_span = self.message_times[-1] - self.message_times[0]
        if time_span <= 0:
            return 0.0

        return (len(self.message_times) - 1) / time_span

    def _get_metrics_snapshot(self) -> BrokerMetrics:
        """Get current broker metrics snapshot."""
        current_time = time.time()
        uptime = current_time - self.start_time
        current_mps = self._calculate_rate()

        # Update peak
        if current_mps > self.peak_mps:
            self.peak_mps = current_mps

        # Calculate average message size
        avg_size = (
            sum(self.message_sizes) / len(self.message_sizes)
            if self.message_sizes
            else 0.0
        )

        return BrokerMetrics(
            total_messages=self.total_messages,
            messages_per_second=current_mps,
            active_workers=len(
                [w for w, count in self.worker_stats.items() if count > 0]
            ),
            active_clients=len(
                [c for c, count in self.client_stats.items() if count > 0]
            ),
            avg_message_size=avg_size,
            peak_mps=self.peak_mps,
            uptime_seconds=uptime,
            worker_distribution=dict(self.worker_stats),
            client_distribution=dict(self.client_stats),
        )

    async def _capture_messages(self):
        """Capture and process messages from broker."""
        print("📡 Starting message capture from broker...")

        while self.running:
            try:
                # Ensure socket is available
                if not self.capture_socket:
                    await asyncio.sleep(0.1)
                    continue

                # Receive message frames with timeout
                frames = await self.capture_socket.recv_multipart(zmq.NOBLOCK)

                # Parse message
                worker_id, client_id, message_size = self._parse_captured_message(
                    frames
                )

                # Update tracking
                current_time = time.time()
                self.message_times.append(current_time)
                self.message_sizes.append(message_size)
                self.total_messages += 1

                # Update worker/client stats
                if worker_id:
                    self.worker_stats[worker_id] += 1
                if client_id:
                    self.client_stats[client_id] += 1

            except zmq.Again:
                # No message available, small sleep
                await asyncio.sleep(0.01)
            except Exception as e:
                print(f"⚠️ Error capturing message: {e}")
                await asyncio.sleep(0.1)

    async def start_monitoring(self, update_interval: float = 2.0):
        """Start real-time monitoring display.

        Args:
            update_interval: How often to update display (seconds)
        """
        self.running = True
        capture_task: asyncio.Task | None = None

        try:
            await self.initialize()

            # Start capture task
            capture_task = asyncio.create_task(self._capture_messages())

            print("🚀 ZMQ Broker Performance Monitor Started")
            print("Press Ctrl+C to stop monitoring\n")

            while self.running:
                # Clear screen and show header
                print("\033[2J\033[H", end="")  # Clear screen

                # Display current time and status
                current_time = time.strftime("%Y-%m-%d %H:%M:%S")
                print(f"🚀 ZMQ Broker Performance Monitor - {current_time}")
                print("=" * 80)

                # Get current metrics
                metrics = self._get_metrics_snapshot()

                # Display main throughput metrics
                print("📊 BROKER THROUGHPUT METRICS")
                print(f"   Total Messages:       {metrics.total_messages:,}")
                print(f"   Current MPS:          {metrics.messages_per_second:.2f}")
                print(f"   Peak MPS:             {metrics.peak_mps:.2f}")
                print(f"   Avg Message Size:     {metrics.avg_message_size:.0f} bytes")

                # Display connection metrics
                print("\n🔗 CONNECTION METRICS")
                print(f"   Active Workers:       {metrics.active_workers}")
                print(f"   Active Clients:       {metrics.active_clients}")
                print(
                    f"   Total Connections:    {metrics.active_workers + metrics.active_clients}"
                )

                # Display worker distribution (top 10)
                if metrics.worker_distribution:
                    print("\n👷 TOP WORKER ACTIVITY")
                    sorted_workers = sorted(
                        metrics.worker_distribution.items(),
                        key=lambda x: x[1],
                        reverse=True,
                    )[:10]

                    for worker_id, message_count in sorted_workers:
                        activity_bar = "█" * min(
                            20, message_count // max(1, metrics.total_messages // 100)
                        )
                        print(
                            f"   {worker_id[:20]:<20} {message_count:>6} msgs {activity_bar}"
                        )

                # Display client distribution (top 5)
                if metrics.client_distribution:
                    print("\n📱 TOP CLIENT ACTIVITY")
                    sorted_clients = sorted(
                        metrics.client_distribution.items(),
                        key=lambda x: x[1],
                        reverse=True,
                    )[:5]

                    for client_id, message_count in sorted_clients:
                        activity_bar = "█" * min(
                            15, message_count // max(1, metrics.total_messages // 100)
                        )
                        print(
                            f"   {client_id[:20]:<20} {message_count:>6} msgs {activity_bar}"
                        )

                # Performance indicators
                print("\n📈 PERFORMANCE ANALYSIS")
                if metrics.messages_per_second > 100:
                    perf_indicator = "🟢 Excellent"
                elif metrics.messages_per_second > 50:
                    perf_indicator = "🟡 Good"
                elif metrics.messages_per_second > 10:
                    perf_indicator = "🟠 Fair"
                elif metrics.messages_per_second > 0:
                    perf_indicator = "🔴 Low"
                else:
                    perf_indicator = "⏳ Idle"

                print(f"   Performance:          {perf_indicator}")

                # System information
                uptime_str = f"{int(metrics.uptime_seconds // 3600):02d}:{int((metrics.uptime_seconds % 3600) // 60):02d}:{int(metrics.uptime_seconds % 60):02d}"
                print(f"   Broker Uptime:        {uptime_str}")

                # Load estimation
                if metrics.peak_mps > 0:
                    load_percentage = (
                        metrics.messages_per_second / metrics.peak_mps
                    ) * 100
                    load_bar = "█" * int(load_percentage // 5)  # 20 char max
                    print(f"   Current Load:         {load_percentage:.1f}% {load_bar}")

                print("\n" + "=" * 80)
                print("📡 Monitoring broker capture socket")
                print("Press Ctrl+C to stop monitoring")

                # Wait for next update
                await asyncio.sleep(update_interval)

        except KeyboardInterrupt:
            print("\n\n👋 Monitoring stopped by user")
        except Exception as e:
            print(f"\n❌ Monitoring error: {e}")
            import traceback

            traceback.print_exc()
        finally:
            self.running = False
            if capture_task:
                capture_task.cancel()
                try:
                    await capture_task
                except asyncio.CancelledError:
                    pass
            await self.shutdown()


async def show_help():
    """Show help information about the broker monitoring tool."""
    print("""
📡 ZMQ Broker Performance Monitor
================================

This tool provides real-time monitoring of ZMQ broker message flow using the capture socket.

FEATURES:
- Real-time message throughput (messages per second)
- Worker and client activity tracking
- Message size analysis
- Connection monitoring
- Performance indicators
- Load analysis with visual bars

METRICS DISPLAYED:
- Total messages processed through broker
- Current and peak messages per second (MPS)
- Active worker and client counts
- Top workers and clients by activity
- Average message size
- Performance indicators and load percentage

HOW IT WORKS:
The monitor connects to the broker's capture socket which receives copies of all
messages flowing through the broker proxy. This provides accurate real-time metrics
without impacting the broker's performance.

USAGE:
1. Ensure your ZMQ broker is running with capture enabled
2. Run: python examples/monitor_broker_performance.py
3. Watch real-time broker statistics
4. Press Ctrl+C to stop

The display updates every 2 seconds showing current broker activity and performance.
""")


async def main():
    """Main entry point for the broker monitor."""
    import sys

    if len(sys.argv) > 1 and sys.argv[1] in ["--help", "-h", "help"]:
        await show_help()
        return

    # Use default ZMQ configuration
    zmq_config = ZMQCommunicationConfig(protocol_config=ZMQTCPTransportConfig())

    monitor = ZMQBrokerMonitor(zmq_config=zmq_config)
    await monitor.start_monitoring()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Goodbye!")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback

        traceback.print_exc()
