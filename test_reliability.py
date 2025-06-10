#!/usr/bin/env python3
#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
"""
Reliability Test for ZMQ DEALER-ROUTER Broker

This test sends multiple messages to diagnose reliability issues and identify
potential race conditions, timing issues, or other problems.
"""

import asyncio
import logging
import time
import uuid

import zmq
import zmq.asyncio

from aiperf.common.comms.zmq.clients.dealer import ZMQDealerClient
from aiperf.common.comms.zmq.clients.dealer_router import ZMQDealerRouterBroker
from aiperf.common.comms.zmq.clients.router import ZMQRouterClient
from aiperf.common.enums import MessageType
from aiperf.common.messages import (
    ConversationRequestMessage,
    ConversationResponseMessage,
)


class ReliabilityTest:
    def __init__(self, num_messages: int = 100):
        self.num_messages = num_messages
        self.context = zmq.asyncio.Context.instance()

        # Use different ports to avoid conflicts
        self.frontend_address = "tcp://127.0.0.1:19556"
        self.backend_address = "tcp://127.0.0.1:19557"
        self.capture_address = "tcp://127.0.0.1:19558"

        self.broker = None
        self.router = None
        self.dealer = None

        self.results = {
            "sent": 0,
            "received": 0,
            "timeouts": 0,
            "errors": 0,
            "parse_errors": 0,
            "response_times": [],
        }

    async def setup(self):
        """Setup broker, router, and dealer."""
        print("Setting up test components...")

        # Create broker
        self.broker = ZMQDealerRouterBroker(
            context=self.context,
            frontend_address=self.frontend_address,
            backend_address=self.backend_address,
            capture_address=self.capture_address,
        )

        # Create router service
        self.router = ZMQRouterClient(
            context=self.context,
            address=self.backend_address,
            bind=False,
            id="test_router_reliability",
        )

        # Register handler
        self.router.register_request_handler(
            "test_service", MessageType.CONVERSATION_REQUEST, self._handle_conversation
        )

        # Create dealer client
        self.dealer = ZMQDealerClient(
            context=self.context,
            address=self.frontend_address,
            bind=False,
            id="test_dealer_reliability",
        )

        # Initialize components
        await self.router.initialize()
        await self.dealer.initialize()

    async def _handle_conversation(
        self, request: ConversationRequestMessage
    ) -> ConversationResponseMessage:
        """Simple handler that returns test data."""
        return ConversationResponseMessage(
            request_id=request.request_id,
            service_id=request.service_id,
            conversation_id=request.conversation_id,
            conversation_data=[
                {"test": "response", "msg_num": request.request_id[-8:]}
            ],
        )

    async def cleanup(self):
        """Clean up all components."""
        print("Cleaning up test components...")

        if self.dealer:
            await self.dealer.shutdown()
        if self.router:
            await self.router.shutdown()
        if self.broker:
            await self.broker.stop()

    async def send_single_message(self, msg_num: int) -> bool:
        """Send a single message and track the result."""
        request_id = f"test_{msg_num:04d}_{uuid.uuid4().hex[:8]}"

        message = ConversationRequestMessage(
            request_id=request_id,
            service_id="test_service",
            conversation_id="reliability_test",
            conversation_data=[{"message_number": msg_num}],
        )

        start_time = time.time()

        try:
            self.results["sent"] += 1
            response = await self.dealer.request(message, timeout=5.0)

            response_time = time.time() - start_time
            self.results["response_times"].append(response_time)
            self.results["received"] += 1

            # Validate response
            if response.request_id != request_id:
                print(
                    f"[{msg_num:04d}] ERROR: Request ID mismatch - Expected: {request_id}, Got: {response.request_id}"
                )
                self.results["errors"] += 1
                return False

            print(f"[{msg_num:04d}] SUCCESS: Response in {response_time:.3f}s")
            return True

        except asyncio.TimeoutError:
            response_time = time.time() - start_time
            print(f"[{msg_num:04d}] TIMEOUT: No response after {response_time:.3f}s")
            self.results["timeouts"] += 1
            return False

        except Exception as e:
            response_time = time.time() - start_time
            print(f"[{msg_num:04d}] ERROR: {e} (after {response_time:.3f}s)")
            self.results["errors"] += 1
            return False

    async def run_sequential_test(self):
        """Run messages one at a time to avoid concurrency issues."""
        print(f"\n=== Sequential Test: {self.num_messages} messages ===")

        for i in range(1, self.num_messages + 1):
            success = await self.send_single_message(i)

            # Add small delay between messages to avoid overwhelming
            if i % 10 == 0:
                print(
                    f"Progress: {i}/{self.num_messages} ({i / self.num_messages * 100:.1f}%)"
                )
                await asyncio.sleep(0.1)  # Small delay every 10 messages

    async def run_batch_test(self, batch_size: int = 10):
        """Run messages in small batches to test concurrency."""
        print(
            f"\n=== Batch Test: {self.num_messages} messages in batches of {batch_size} ==="
        )

        for batch_start in range(1, self.num_messages + 1, batch_size):
            batch_end = min(batch_start + batch_size - 1, self.num_messages)

            # Send batch of messages concurrently
            tasks = []
            for i in range(batch_start, batch_end + 1):
                tasks.append(self.send_single_message(i))

            # Wait for batch to complete
            await asyncio.gather(*tasks)

            print(f"Batch complete: {batch_start}-{batch_end}")
            await asyncio.sleep(0.2)  # Pause between batches

    def print_results(self):
        """Print detailed test results."""
        print("\n" + "=" * 60)
        print("RELIABILITY TEST RESULTS")
        print("=" * 60)

        sent = self.results["sent"]
        received = self.results["received"]
        timeouts = self.results["timeouts"]
        errors = self.results["errors"]

        success_rate = (received / sent * 100) if sent > 0 else 0

        print(f"Messages Sent:      {sent}")
        print(f"Messages Received:  {received}")
        print(f"Timeouts:           {timeouts}")
        print(f"Errors:             {errors}")
        print(f"Success Rate:       {success_rate:.1f}%")

        if self.results["response_times"]:
            times = self.results["response_times"]
            avg_time = sum(times) / len(times)
            min_time = min(times)
            max_time = max(times)

            print("\nResponse Times:")
            print(f"  Average:  {avg_time:.3f}s")
            print(f"  Minimum:  {min_time:.3f}s")
            print(f"  Maximum:  {max_time:.3f}s")

        # Success rate analysis
        if success_rate < 50:
            print(f"\n❌ CRITICAL: Very low success rate ({success_rate:.1f}%)")
            print("   Possible issues:")
            print("   - Socket binding conflicts")
            print("   - Race conditions in setup")
            print("   - Proxy initialization timing")
            print("   - Message routing problems")
        elif success_rate < 90:
            print(f"\n⚠️  WARNING: Moderate success rate ({success_rate:.1f}%)")
            print("   Some reliability issues detected")
        else:
            print(f"\n✅ GOOD: High success rate ({success_rate:.1f}%)")


async def main():
    """Main test runner."""
    # Configure logging for better diagnostics
    logging.basicConfig(
        level=logging.WARNING,  # Reduce noise, focus on errors
        format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
    )

    # Test with smaller number first to diagnose quickly
    test = ReliabilityTest(num_messages=20)

    try:
        await test.setup()

        # Start broker in background
        broker_task = asyncio.create_task(test.broker.run())

        # Give broker time to initialize
        await asyncio.sleep(1.0)

        # Start router receiver
        router_task = asyncio.create_task(test.router._router_receiver())

        # Give router time to connect
        await asyncio.sleep(1.0)

        print("Test setup complete. Starting reliability tests...")

        # Run sequential test first
        await test.run_sequential_test()

        test.print_results()

        # If sequential test shows issues, don't run batch test
        success_rate = (
            test.results["received"] / test.results["sent"] * 100
            if test.results["sent"] > 0
            else 0
        )

        if success_rate > 80:
            print("\nSequential test passed. Running batch test...")
            # Reset results for batch test
            test.results = {
                "sent": 0,
                "received": 0,
                "timeouts": 0,
                "errors": 0,
                "parse_errors": 0,
                "response_times": [],
            }
            await test.run_batch_test(batch_size=5)
            test.print_results()
        else:
            print(
                f"\nSkipping batch test due to low sequential success rate ({success_rate:.1f}%)"
            )

        # Cancel background tasks
        broker_task.cancel()
        router_task.cancel()

        # Wait for cancellation
        try:
            await broker_task
        except asyncio.CancelledError:
            pass
        try:
            await router_task
        except asyncio.CancelledError:
            pass

    finally:
        await test.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
