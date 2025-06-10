#!/usr/bin/env python3
#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
"""
Test script for ZMQ debug logging.

This script helps verify that the enhanced debug logging is working properly
and can help track down issues with conversation_response messages.
"""

import asyncio
import os
import sys

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import contextlib
import logging

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
    print(f"Handler received: {message}")

    # Create a response message - IMPORTANT: Copy the request_id for proper routing
    response = ConversationResponseMessage(
        request_id=message.request_id,  # This is critical for routing back through broker
        service_id="test_service",
        conversation_id="1234567890",
        conversation_data=[{"test": "test"}],
    )

    # Add some delay to simulate processing
    await asyncio.sleep(0.1)

    return response


async def test_basic_dealer_router():
    """Test basic DEALER-ROUTER communication without broker."""
    print("\n=== Testing Basic DEALER-ROUTER Communication ===")

    context = zmq.asyncio.Context()

    # Create router first
    router = ZMQRouterClient(
        context=context,
        address="tcp://127.0.0.1:16555",  # Use port 16555 for basic test
        bind=True,
        id="test_router",
    )

    # Register handler
    router.register_request_handler(
        service_id="test_service",
        message_type=MessageType.CONVERSATION_REQUEST,
        handler=simple_echo_handler,
    )

    # Create dealer
    dealer = ZMQDealerClient(
        context=context,
        address="tcp://127.0.0.1:16555",  # Connect to same port
        bind=False,
        id="test_dealer",
    )

    try:
        # Initialize both
        await asyncio.gather(router.initialize(), dealer.initialize())

        # Start router receiver
        router_task = asyncio.create_task(router._router_receiver())

        # Give router time to start
        await asyncio.sleep(0.5)

        # Send test message
        test_message = ConversationRequestMessage(
            service_id="test_service",
            conversation_id="test_conversation",
        )

        print(f"Sending test message: {test_message}")
        response = await dealer.request(test_message, timeout=10.0)
        print(f"Received response: {response}")

        # Cancel router task
        router_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await router_task

    finally:
        await asyncio.gather(router.shutdown(), dealer.shutdown())
        context.term()


async def test_broker_dealer_router():
    """Test DEALER-ROUTER communication through broker."""
    print("\n=== Testing DEALER-ROUTER Communication Through Broker ===")

    # Enable debug logging
    debug_conversation_response_flow()

    context = zmq.asyncio.Context()

    # Create broker with separate port range
    broker = ZMQDealerRouterBroker(
        context=context,
        frontend_address="tcp://127.0.0.1:17556",  # Use port 17556 for broker frontend
        backend_address="tcp://127.0.0.1:17557",  # Use port 17557 for broker backend
        capture_address="tcp://127.0.0.1:17558",  # Use port 17558 for broker capture
    )

    # Create router service that connects to broker backend
    router = ZMQRouterClient(
        context=context,
        address="tcp://127.0.0.1:17557",  # Connect to broker backend
        bind=False,
        id="test_router_with_broker",
    )

    # Register handler
    router.register_request_handler(
        service_id="test_service",
        message_type=MessageType.CONVERSATION_REQUEST,
        handler=simple_echo_handler,
    )

    # Create dealer (connects to broker frontend)
    dealer = ZMQDealerClient(
        context=context,
        address="tcp://127.0.0.1:17556",  # Connect to broker frontend
        bind=False,
        id="test_dealer_with_broker",
    )

    try:
        # Start broker
        broker_task = asyncio.create_task(broker.run())
        await asyncio.sleep(1.0)  # Give broker time to start

        # Initialize router and dealer
        await asyncio.gather(router.initialize(), dealer.initialize())

        # Start router receiver
        router_task = asyncio.create_task(router._router_receiver())

        # Give everything time to connect
        await asyncio.sleep(2.0)

        # Send test message
        test_message = ConversationRequestMessage(
            service_id="test_service",
            conversation_id="test_conversation",
        )

        print(f"Sending test message through broker: {test_message}")
        response = await dealer.request(test_message, timeout=30.0)
        print(f"Received response through broker: {response}")

        # Cancel tasks
        router_task.cancel()
        broker_task.cancel()

        with contextlib.suppress(asyncio.CancelledError):
            await asyncio.gather(router_task, broker_task, return_exceptions=True)

    finally:
        await asyncio.gather(
            router.shutdown(), dealer.shutdown(), return_exceptions=True
        )
        context.term()


async def main():
    """Main test function."""
    print("ZMQ Debug Test Script")
    print("====================")

    try:
        # Test basic communication first
        await test_basic_dealer_router()

        # Test with broker
        await test_broker_dealer_router()

        print("\n=== All Tests Completed ===")

    except Exception as e:
        print(f"Test failed with error: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    # Configure logging first
    logging.basicConfig(level=logging.DEBUG)

    # Run the test
    asyncio.run(main())
