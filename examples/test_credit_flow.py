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
Test script to verify credit drop flow and monitor performance.
This script helps debug the complete flow: Timing Manager -> Worker Manager -> FastAPI Server
"""

import asyncio
import time

from aiperf.common.metrics.performance_monitor import get_monitor


async def monitor_credit_flow(duration_seconds: int = 60):
    """Monitor credit drop processing for a specified duration.

    Args:
        duration_seconds: How long to monitor the system
    """
    monitor = get_monitor()

    print("🔍 Credit Drop Flow Monitor")
    print("=" * 50)
    print(f"Monitoring for {duration_seconds} seconds...")
    print("This will show if credit drops are being processed by workers")
    print()

    start_time = time.time()
    last_request_count = 0

    try:
        while (time.time() - start_time) < duration_seconds:
            snapshot = monitor.get_snapshot()

            # Check if we're seeing new requests
            if snapshot.total_requests > last_request_count:
                new_requests = snapshot.total_requests - last_request_count
                current_time = time.strftime("%H:%M:%S")
                print(
                    f"[{current_time}] ✅ New requests detected: +{new_requests} "
                    f"(Total: {snapshot.total_requests}, RPS: {snapshot.requests_per_second:.2f})"
                )
                last_request_count = snapshot.total_requests
            elif snapshot.total_requests == 0:
                current_time = time.strftime("%H:%M:%S")
                print(f"[{current_time}] ⏳ No requests detected yet...")

            # Show periodic stats
            elapsed = time.time() - start_time
            if int(elapsed) % 10 == 0 and elapsed > 0:  # Every 10 seconds
                print(f"\n📊 Statistics after {int(elapsed)}s:")
                print(f"   Total Requests:   {snapshot.total_requests}")
                print(
                    f"   Success Rate:     {(snapshot.successful_requests / max(snapshot.total_requests, 1) * 100):.1f}%"
                )
                print(f"   Current RPS:      {snapshot.requests_per_second:.2f}")
                print(f"   Active Workers:   {snapshot.active_workers}")
                if snapshot.avg_response_time_ms > 0:
                    print(f"   Avg Response:     {snapshot.avg_response_time_ms:.2f}ms")
                print()

            await asyncio.sleep(1)

    except KeyboardInterrupt:
        print("\n⚠️ Monitoring stopped by user")

    # Final report
    final_snapshot = monitor.get_snapshot()
    print("\n📋 Final Report:")
    print(f"   Monitoring Duration:  {duration_seconds}s")
    print(f"   Total Requests:       {final_snapshot.total_requests}")
    print(f"   Successful:           {final_snapshot.successful_requests}")
    print(f"   Failed:               {final_snapshot.failed_requests}")
    if final_snapshot.total_requests > 0:
        print(
            f"   Success Rate:         {(final_snapshot.successful_requests / final_snapshot.total_requests * 100):.1f}%"
        )
        print(
            f"   Average RPS:          {final_snapshot.total_requests / duration_seconds:.2f}"
        )
    else:
        print("   ❌ No requests were processed!")
        print("\n🔧 Troubleshooting:")
        print("   1. Is the timing manager running and sending credit drops?")
        print("   2. Is the worker manager receiving and processing credit drops?")
        print("   3. Is the FastAPI server running on port 9797?")
        print("   4. Check the logs for any error messages")


async def test_fastapi_connectivity():
    """Test if FastAPI server is accessible."""
    try:
        import httpx

        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get("http://localhost:9797/health")
            print(f"✅ FastAPI server is running (Status: {response.status_code})")
            return True
    except ImportError:
        print("❌ httpx not installed - cannot test FastAPI connectivity")
        return False
    except Exception as e:
        print(f"❌ FastAPI server not reachable: {e}")
        print("   Please start: python examples/fastapi_server.py")
        return False


async def main():
    """Main test function."""
    print("🧪 Credit Drop Flow Test")
    print("=" * 40)

    # Test FastAPI connectivity first
    fastapi_ok = await test_fastapi_connectivity()

    print("\n🎯 Testing credit drop processing...")
    print("This monitor will show if:")
    print("• Credit drops are being received by the worker manager")
    print("• Workers are making HTTP requests to the FastAPI server")
    print("• The complete flow is working end-to-end")
    print()

    if not fastapi_ok:
        print("⚠️ Warning: FastAPI server not reachable")
        print("Workers will likely fail to process requests")
        print()

    duration = 60  # Monitor for 1 minute
    print(f"Starting {duration}-second monitoring session...")
    print("Press Ctrl+C to stop early")
    print()

    await monitor_credit_flow(duration)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Test stopped by user")
    except Exception as e:
        print(f"\n❌ Test error: {e}")
