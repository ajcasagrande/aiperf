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
Performance monitoring utilities for tracking request throughput and metrics.
"""

import time
from collections import defaultdict, deque
from dataclasses import dataclass


@dataclass
class MetricSnapshot:
    """Snapshot of performance metrics at a point in time."""

    timestamp: float
    total_requests: int
    successful_requests: int
    failed_requests: int
    requests_per_second: float
    avg_response_time_ms: float
    min_response_time_ms: float
    max_response_time_ms: float
    p95_response_time_ms: float
    active_workers: int


class PerformanceMonitor:
    """High-performance monitoring system for tracking request metrics."""

    def __init__(self, window_size_seconds: int = 60):
        """Initialize the performance monitor.

        Args:
            window_size_seconds: Time window for calculating rolling metrics
        """
        self.window_size = window_size_seconds

        # Request tracking
        self.total_requests = 0
        self.successful_requests = 0
        self.failed_requests = 0

        # Time-based metrics
        self.request_timestamps: deque = deque()
        self.response_times: deque = deque()

        # Worker tracking
        self.active_workers: set = set()
        self.worker_stats: dict[str, dict] = defaultdict(
            lambda: {"requests": 0, "total_time": 0.0, "last_seen": time.time()}
        )

        # Real-time monitoring
        self.start_time = time.time()
        self.last_snapshot = None

    def record_request_start(self, worker_id: str) -> float:
        """Record the start of a request.

        Args:
            worker_id: ID of the worker handling the request

        Returns:
            Request start timestamp
        """
        start_time = time.time()
        self.total_requests += 1
        self.active_workers.add(worker_id)

        # Clean old timestamps outside window
        cutoff_time = start_time - self.window_size
        while self.request_timestamps and self.request_timestamps[0] < cutoff_time:
            self.request_timestamps.popleft()

        self.request_timestamps.append(start_time)
        return start_time

    def record_request_end(
        self,
        worker_id: str,
        start_time: float,
        success: bool,
        response_time_ms: float | None = None,
    ):
        """Record the completion of a request.

        Args:
            worker_id: ID of the worker that handled the request
            start_time: Timestamp when request started
            success: Whether the request was successful
            response_time_ms: Response time in milliseconds (calculated if not provided)
        """
        end_time = time.time()

        if response_time_ms is None:
            response_time_ms = (end_time - start_time) * 1000

        # Update counters
        if success:
            self.successful_requests += 1
        else:
            self.failed_requests += 1

        # Update worker stats
        self.worker_stats[worker_id]["requests"] += 1
        self.worker_stats[worker_id]["total_time"] += response_time_ms
        self.worker_stats[worker_id]["last_seen"] = end_time

        # Clean old response times outside window
        cutoff_time = end_time - self.window_size
        while self.response_times and self.response_times[0][0] < cutoff_time:
            self.response_times.popleft()

        self.response_times.append((end_time, response_time_ms))

    def get_current_rps(self) -> float:
        """Calculate current requests per second based on recent activity."""
        current_time = time.time()
        cutoff_time = current_time - self.window_size

        # Count requests in the current window
        recent_requests = sum(1 for ts in self.request_timestamps if ts >= cutoff_time)

        # Calculate RPS
        return recent_requests / self.window_size if self.window_size > 0 else 0.0

    def get_response_time_stats(self) -> dict[str, float]:
        """Get response time statistics for the current window."""
        if not self.response_times:
            return {"avg": 0.0, "min": 0.0, "max": 0.0, "p95": 0.0}

        # Extract response times from current window
        current_time = time.time()
        cutoff_time = current_time - self.window_size
        recent_times = [rt for ts, rt in self.response_times if ts >= cutoff_time]

        if not recent_times:
            return {"avg": 0.0, "min": 0.0, "max": 0.0, "p95": 0.0}

        recent_times.sort()

        return {
            "avg": sum(recent_times) / len(recent_times),
            "min": min(recent_times),
            "max": max(recent_times),
            "p95": recent_times[int(len(recent_times) * 0.95)] if recent_times else 0.0,
        }

    def get_snapshot(self) -> MetricSnapshot:
        """Get a snapshot of current performance metrics."""
        response_stats = self.get_response_time_stats()

        snapshot = MetricSnapshot(
            timestamp=time.time(),
            total_requests=self.total_requests,
            successful_requests=self.successful_requests,
            failed_requests=self.failed_requests,
            requests_per_second=self.get_current_rps(),
            avg_response_time_ms=response_stats["avg"],
            min_response_time_ms=response_stats["min"],
            max_response_time_ms=response_stats["max"],
            p95_response_time_ms=response_stats["p95"],
            active_workers=len(self.active_workers),
        )

        self.last_snapshot = snapshot
        return snapshot

    def get_worker_stats(self) -> dict[str, dict]:
        """Get per-worker performance statistics."""
        current_time = time.time()
        stats = {}

        for worker_id, worker_data in self.worker_stats.items():
            if worker_data["requests"] > 0:
                avg_response_time = worker_data["total_time"] / worker_data["requests"]
                time_since_last_seen = current_time - worker_data["last_seen"]

                stats[worker_id] = {
                    "requests": worker_data["requests"],
                    "avg_response_time_ms": avg_response_time,
                    "last_seen_seconds_ago": time_since_last_seen,
                    "is_active": time_since_last_seen
                    < 30,  # Active if seen in last 30s
                }

        return stats

    def print_stats(self, include_workers: bool = True):
        """Print current performance statistics."""
        snapshot = self.get_snapshot()

        print(f"\n{'=' * 60}")
        print(f"Performance Metrics - {time.strftime('%H:%M:%S')}")
        print(f"{'=' * 60}")
        print(f"Total Requests:       {snapshot.total_requests:,}")
        print(f"Successful:           {snapshot.successful_requests:,}")
        print(f"Failed:               {snapshot.failed_requests:,}")
        print(
            f"Success Rate:         {(snapshot.successful_requests / max(snapshot.total_requests, 1) * 100):.1f}%"
        )
        print(f"Requests/Second:      {snapshot.requests_per_second:.2f}")
        print(f"Active Workers:       {snapshot.active_workers}")
        print("\nResponse Times (ms):")
        print(f"  Average:            {snapshot.avg_response_time_ms:.2f}")
        print(f"  Minimum:            {snapshot.min_response_time_ms:.2f}")
        print(f"  Maximum:            {snapshot.max_response_time_ms:.2f}")
        print(f"  95th Percentile:    {snapshot.p95_response_time_ms:.2f}")

        if include_workers:
            worker_stats = self.get_worker_stats()
            if worker_stats:
                print("\nWorker Performance:")
                for worker_id, stats in worker_stats.items():
                    status = "🟢" if stats["is_active"] else "🔴"
                    print(
                        f"  {status} {worker_id}: {stats['requests']} reqs, "
                        f"{stats['avg_response_time_ms']:.1f}ms avg"
                    )

        uptime = time.time() - self.start_time
        print(f"\nUptime: {uptime:.1f}s")
        print("=" * 60)


# Global performance monitor instance
global_monitor = PerformanceMonitor()


def get_monitor() -> PerformanceMonitor:
    """Get the global performance monitor instance."""
    return global_monitor
