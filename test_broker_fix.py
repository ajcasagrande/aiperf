#!/usr/bin/env python3
#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
"""
Focused test script to verify the broker routing fix.
"""

import asyncio
import contextlib
import os
import sys

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


import zmq.asyncio

from aiperf.common.comms.zmq.clients.dealer import ZMQDealerClient
from aiperf.common.comms.zmq.clients.dealer_router import ZMQDealerRouterBroker
from aiperf.common.comms.zmq.clients.router import ZMQRouterClient
from aiperf.common.comms.zmq.debug_utils import debug_conversation_response_flow
from aiperf.common.enums import MessageType
from aiperf.common.messages import (
    ConversationRequestMessage,
    ConversationResponseMessage,
    Message,
)


async def simple_echo_handler(message: Message) -> Message:
    """Simple echo handler for testing."""
    print(f"[HANDLER] Received: {message.request_id}")

    # Create a response message
    response = ConversationResponseMessage(
        request_id=message.request_id,
        service_id="test_service",
        conversation_id="1234567890",
        conversation_data=[{"test": "fixed"}],
    )

    # Add some delay to simulate processing
    await asyncio.sleep(0.1)

    return response


async def test_broker_fix():
    """Test DEALER-ROUTER communication through fixed broker."""
    print("\n=== Testing Fixed Broker ===")

    # Enable debug logging
    debug_conversation_response_flow()

    context = zmq.asyncio.Context()

    # Create broker
    broker = ZMQDealerRouterBroker(
        context=context,
        frontend_address="tcp://127.0.0.1:18556",  # Use unique ports
        backend_address="tcp://127.0.0.1:18557",
        capture_address="tcp://127.0.0.1:18558",
    )

    # Create router service
    router = ZMQRouterClient(
        context=context,
        address="tcp://127.0.0.1:18557",  # Connect to broker backend
        bind=False,
        id="test_router_fixed",
    )

    # Register handler
    router.register_request_handler(
        service_id="test_service",
        message_type=MessageType.CONVERSATION_REQUEST,
        handler=simple_echo_handler,
    )

    # Create dealer client
    dealer = ZMQDealerClient(
        context=context,
        address="tcp://127.0.0.1:18556",  # Connect to broker frontend
        bind=False,
        id="test_dealer_fixed",
    )

    try:
        print("[TEST] Initializing broker...")
        await broker._initialize()

        print("[TEST] Initializing router...")
        await router.initialize()

        print("[TEST] Initializing dealer...")
        await dealer.initialize()

        # Start broker in background
        print("[TEST] Starting broker...")
        broker_task = asyncio.create_task(broker.run())

        # Start router receiver
        print("[TEST] Starting router receiver...")
        router_task = asyncio.create_task(router._router_receiver())

        # Give services time to start
        await asyncio.sleep(2)

        # Send test message
        test_message = ConversationRequestMessage(
            service_id="test_service",
            conversation_id="test_conversation",
        )

        print(f"[TEST] Sending message: {test_message.request_id}")
        response = await dealer.request(test_message, timeout=10.0)
        print(f"[TEST] SUCCESS! Received response: {response.request_id}")
        print(f"[TEST] Response data: {response.conversation_data}")

        return True

    except Exception as e:
        print(f"[TEST] FAILED: {e}")
        return False

    finally:
        print("[TEST] Cleaning up...")
        # Clean up
        broker_task.cancel()
        router_task.cancel()

        with contextlib.suppress(asyncio.CancelledError):
            await asyncio.gather(broker_task, router_task, return_exceptions=True)

        await broker.stop()


async def main():
    """Main test function."""
    print("Broker Fix Test")
    print("===============")

    try:
        success = await test_broker_fix()
        if success:
            print("\n✅ BROKER FIX SUCCESSFUL!")
            print("Routing envelope is now properly preserved")
        else:
            print("\n❌ BROKER FIX FAILED!")

    except Exception as e:
        print(f"\n💥 TEST ERROR: {e}")


if __name__ == "__main__":
    asyncio.run(main())
