#!/usr/bin/env python3
#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
"""
Simple test to verify the DEALER client with request correlation works.
"""

import asyncio
import logging
import time

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


async def simple_handler(
    request: ConversationRequestMessage,
) -> ConversationResponseMessage:
    """Simple handler that returns test data."""
    await asyncio.sleep(0.1)  # Simulate processing time
    return ConversationResponseMessage(
        request_id=request.request_id,
        service_id=request.service_id,
        conversation_id=request.conversation_id,
        conversation_data=[{"test": "response", "msg_num": request.request_id[-8:]}],
    )


async def test_simple():
    """Test the new DEALER client with a simple scenario."""

    # Configure logging to see what's happening
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
    )

    context = zmq.asyncio.Context.instance()

    # Use different ports
    frontend_address = "tcp://127.0.0.1:19560"
    backend_address = "tcp://127.0.0.1:19561"

    print("Creating components...")

    # Create broker
    broker = ZMQDealerRouterBroker(
        context=context,
        frontend_address=frontend_address,
        backend_address=backend_address,
    )

    # Create router service
    router = ZMQRouterClient(
        context=context,
        address=backend_address,
        bind=False,
        id="test_router_simple",
    )

    # Register handler
    router.register_request_handler(
        "test_service", MessageType.CONVERSATION_REQUEST, simple_handler
    )

    # Create dealer client
    dealer = ZMQDealerClient(
        context=context,
        address=frontend_address,
        bind=False,
        id="test_dealer_simple",
    )

    try:
        print("Initializing components...")

        # Initialize router and dealer first
        await router.initialize()
        await dealer.initialize()

        print("Starting broker...")
        # Start broker in background
        broker_task = asyncio.create_task(broker.run())
        await asyncio.sleep(1.0)  # Give broker time to start

        print("Starting router receiver...")
        # Start router receiver
        router_task = asyncio.create_task(router._router_receiver())
        await asyncio.sleep(1.0)  # Give router time to connect

        print("Testing single request...")

        # Test single request first
        test_message = ConversationRequestMessage(
            service_id="test_service",
            conversation_id="test_conversation",
        )

        start_time = time.time()
        response = await dealer.request(test_message, timeout=10.0)
        duration = time.time() - start_time

        print(f"✅ Single request SUCCESS: {response.request_id} in {duration:.3f}s")

        print("Testing concurrent requests...")

        # Test concurrent requests
        messages = [
            ConversationRequestMessage(
                service_id="test_service",
                conversation_id="test_conversation",
            )
            for i in range(5)
        ]

        start_time = time.time()

        # Send all requests concurrently
        tasks = [dealer.request(msg, timeout=10.0) for msg in messages]
        responses = await asyncio.gather(*tasks)

        duration = time.time() - start_time

        print(
            f"✅ Concurrent requests SUCCESS: {len(responses)} responses in {duration:.3f}s"
        )

        # Verify all responses have correct request IDs
        success_count = 0
        for i, (msg, resp) in enumerate(zip(messages, responses, strict=False)):
            if msg.request_id == resp.request_id:
                success_count += 1
                print(f"  Request {i + 1}: ✅ {msg.request_id}")
            else:
                print(
                    f"  Request {i + 1}: ❌ Expected {msg.request_id}, got {resp.request_id}"
                )

        print(
            f"\nConcurrent correlation success rate: {success_count}/{len(messages)} ({success_count / len(messages) * 100:.1f}%)"
        )

        if success_count == len(messages):
            print("🎉 ALL TESTS PASSED! Request correlation is working correctly.")
        else:
            print("❌ Some concurrent requests failed correlation.")

        # Cancel background tasks
        broker_task.cancel()
        router_task.cancel()

        # Wait for cancellation
        await asyncio.gather(broker_task, router_task, return_exceptions=True)

        return success_count == len(messages)

    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        import traceback

        traceback.print_exc()
        return False

    finally:
        print("Cleaning up...")
        await dealer.shutdown()
        await router.shutdown()
        await broker.stop()


if __name__ == "__main__":
    success = asyncio.run(test_simple())
    exit(0 if success else 1)
