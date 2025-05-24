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
Benchmark script to test HTTP request throughput and monitor performance.
"""

import asyncio
import sys
import time
from typing import Any

import httpx

from aiperf.common.metrics.performance_monitor import PerformanceMonitor


class ThroughputBenchmark:
    """Benchmark utility for testing HTTP request throughput."""

    def __init__(self, target_url: str = "http://localhost:9797"):
        """Initialize the benchmark.

        Args:
            target_url: Base URL for the target server
        """
        self.target_url = target_url
        self.monitor = PerformanceMonitor(window_size_seconds=10)  # 10-second window
        self.running = False
        self.client = None

    async def make_request(
        self, session_id: str, request_data: dict[str, Any]
    ) -> dict[str, Any]:
        """Make a single HTTP request and record metrics.

        Args:
            session_id: Unique session identifier
            request_data: Request configuration

        Returns:
            Response data
        """
        if not self.client:
            return {"success": False, "error": "client_not_initialized"}

        worker_id = f"bench-{session_id}"
        start_time = self.monitor.record_request_start(worker_id)

        try:
            # Extract request parameters
            method = request_data.get("method", "GET").upper()
            path = request_data.get("path", "/")
            headers = request_data.get("headers", {})
            params = request_data.get("params", {})
            json_data = request_data.get("json")

            # Add benchmark tracking
            headers["X-Benchmark-Session"] = session_id
            headers["X-Request-Time"] = str(start_time)

            # Make request
            url = f"{self.target_url}{path}"
            response = await self.client.request(
                method=method, url=url, headers=headers, params=params, json=json_data
            )

            # Record success
            response_time_ms = response.elapsed.total_seconds() * 1000
            self.monitor.record_request_end(
                worker_id, start_time, True, response_time_ms
            )

            return {
                "success": True,
                "status_code": response.status_code,
                "response_time_ms": response_time_ms,
                "content_length": len(response.content),
            }

        except httpx.TimeoutException:
            self.monitor.record_request_end(worker_id, start_time, False)
            return {"success": False, "error": "timeout"}

        except httpx.ConnectError:
            self.monitor.record_request_end(worker_id, start_time, False)
            return {"success": False, "error": "connection_error"}

        except Exception as e:
            self.monitor.record_request_end(worker_id, start_time, False)
            return {"success": False, "error": str(e)}

    async def run_concurrent_requests(
        self,
        requests_per_second: int,
        duration_seconds: int,
        request_template: dict[str, Any],
    ) -> None:
        """Run concurrent requests at a target rate.

        Args:
            requests_per_second: Target requests per second
            duration_seconds: How long to run the test
            request_template: Template for request data
        """
        print(
            f"🚀 Starting benchmark: {requests_per_second} RPS for {duration_seconds}s"
        )

        # Create HTTP client with connection pooling
        timeout = httpx.Timeout(30.0)
        limits = httpx.Limits(max_keepalive_connections=100, max_connections=200)

        async with httpx.AsyncClient(
            timeout=timeout, limits=limits, http2=True
        ) as client:
            self.client = client
            self.running = True

            # Calculate request interval
            interval = 1.0 / requests_per_second if requests_per_second > 0 else 0.1

            # Start monitoring task
            monitor_task = asyncio.create_task(self._monitor_performance())

            # Track active requests
            active_requests = set()
            request_count = 0
            start_time = time.time()

            try:
                while self.running and (time.time() - start_time) < duration_seconds:
                    # Clean up completed requests
                    completed = [task for task in active_requests if task.done()]
                    for task in completed:
                        active_requests.remove(task)

                    # Create new request
                    session_id = f"session-{request_count:06d}"
                    task = asyncio.create_task(
                        self.make_request(session_id, request_template)
                    )
                    active_requests.add(task)
                    request_count += 1

                    # Wait for next request interval
                    await asyncio.sleep(interval)

                # Wait for remaining requests to complete
                if active_requests:
                    print(
                        f"⏳ Waiting for {len(active_requests)} remaining requests..."
                    )
                    await asyncio.gather(*active_requests, return_exceptions=True)

            except KeyboardInterrupt:
                print("\n⚠️  Benchmark interrupted by user")

            finally:
                self.running = False
                monitor_task.cancel()

                # Cancel any remaining requests
                for task in active_requests:
                    if not task.done():
                        task.cancel()

                # Final statistics
                print("\n📊 Final Statistics:")
                self.monitor.print_stats(include_workers=False)

    async def _monitor_performance(self):
        """Monitor and display performance metrics in real-time."""
        try:
            while self.running:
                await asyncio.sleep(2)  # Update every 2 seconds

                # Clear screen and show current stats
                print("\033[2J\033[H", end="")  # Clear screen
                print("🔥 LIVE PERFORMANCE METRICS 🔥")
                self.monitor.print_stats(include_workers=False)
                print("Press Ctrl+C to stop benchmark")

        except asyncio.CancelledError:
            pass

    async def test_server_connectivity(self) -> bool:
        """Test if the target server is reachable.

        Returns:
            True if server is reachable, False otherwise
        """
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{self.target_url}/health")
                print(f"✅ Server is reachable - Status: {response.status_code}")
                return True
        except httpx.ConnectError:
            print(f"❌ Cannot connect to {self.target_url}")
            print("Please ensure the FastAPI server is running:")
            print("  python examples/fastapi_server.py")
            return False
        except Exception as e:
            print(f"❌ Error testing connectivity: {e}")
            return False


async def run_benchmark_suite():
    """Run a comprehensive benchmark suite."""

    benchmark = ThroughputBenchmark()

    # Test connectivity first
    if not await benchmark.test_server_connectivity():
        return

    # Define test scenarios
    scenarios = [
        {
            "name": "Light Load - GET Requests",
            "rps": 10,
            "duration": 30,
            "request": {"method": "GET", "path": "/health"},
        },
        {
            "name": "Medium Load - Mixed Requests",
            "rps": 50,
            "duration": 30,
            "request": {
                "method": "POST",
                "path": "/api/test",
                "headers": {"Content-Type": "application/json"},
                "json": {"test": "benchmark", "timestamp": time.time()},
            },
        },
        {
            "name": "High Load - Stress Test",
            "rps": 100,
            "duration": 60,
            "request": {"method": "GET", "path": "/"},
        },
    ]

    print("🎯 HTTP Throughput Benchmark Suite")
    print("=" * 50)

    for i, scenario in enumerate(scenarios, 1):
        print(f"\n📋 Scenario {i}: {scenario['name']}")
        print(f"Target: {scenario['rps']} RPS for {scenario['duration']}s")

        input("Press Enter to start this scenario (Ctrl+C to skip)...")

        try:
            await benchmark.run_concurrent_requests(
                requests_per_second=scenario["rps"],
                duration_seconds=scenario["duration"],
                request_template=scenario["request"],
            )
        except KeyboardInterrupt:
            print("Skipping to next scenario...")
            continue

        print("\n⏸️  Scenario complete. Cooling down for 5 seconds...")
        await asyncio.sleep(5)

    print("\n🏁 Benchmark suite completed!")


if __name__ == "__main__":
    print("HTTP Throughput Benchmark Tool")
    print("=" * 40)

    try:
        asyncio.run(run_benchmark_suite())
    except KeyboardInterrupt:
        print("\n👋 Benchmark terminated by user")
        sys.exit(0)
