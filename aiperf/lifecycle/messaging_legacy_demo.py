#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
Demonstration of the legacy-compatible messaging system.

This script shows how to use the new messaging system that integrates
with the legacy aiperf pub/sub infrastructure.
"""

import asyncio
import logging

from aiperf.common.config import ServiceConfig
from aiperf.common.enums import CommunicationBackend
from aiperf.lifecycle.messaging_legacy import Command, Message, MessageBus

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ServiceA:
    """Example service using the legacy-compatible messaging system."""

    def __init__(self, service_id: str, service_config: ServiceConfig):
        self.service_id = service_id
        self.message_bus = MessageBus(logger=logger, service_config=service_config)

    async def start(self):
        """Start the service and set up message handling."""
        # Start the message bus (this initializes ZMQ communication)
        await self.message_bus.start()

        # Register this service for targeted messages
        self.message_bus.register_service(self.service_id, self.handle_targeted_message)

        # Subscribe to specific message types
        self.message_bus.subscribe("DATA_UPDATE", self.handle_data_update)
        self.message_bus.subscribe("STATUS_REQUEST", self.handle_status_request)

        logger.info(f"Service {self.service_id} started and ready for messages")

    async def stop(self):
        """Stop the service."""
        await self.message_bus.stop()
        logger.info(f"Service {self.service_id} stopped")

    async def handle_targeted_message(self, message: Message):
        """Handle messages targeted specifically to this service."""
        logger.info(
            f"{self.service_id} received targeted message: {message.type} - {message.content}"
        )

    async def handle_data_update(self, message: Message):
        """Handle data update messages."""
        logger.info(f"{self.service_id} processing data update: {message.content}")

        # Send acknowledgment
        await self.message_bus.publish(
            Message(
                type="DATA_ACK",
                content=f"Processed by {self.service_id}",
                sender_id=self.service_id,
            )
        )

    async def handle_status_request(self, message: Message):
        """Handle status request messages."""
        logger.info(f"{self.service_id} received status request")

        # Send status response
        await self.message_bus.send_response(
            message,
            {"service_id": self.service_id, "status": "healthy", "uptime": "5 minutes"},
        )

    async def send_data(self, data: str):
        """Send data to other services."""
        await self.message_bus.publish(
            Message(type="DATA_UPDATE", content=data, sender_id=self.service_id)
        )

    async def send_command(self, target_service: str, command_type: str, data: any):
        """Send a command to another service."""
        command = Command(
            type=command_type,
            content=data,
            sender_id=self.service_id,
            target_id=target_service,
            timeout=10.0,
        )

        try:
            response = await self.message_bus.send_command(command)
            logger.info(f"{self.service_id} received command response: {response}")
            return response
        except asyncio.TimeoutError:
            logger.error(f"{self.service_id} command timed out")
            return None


async def demo_legacy_messaging():
    """Demonstrate the legacy-compatible messaging system."""
    logger.info("=== Legacy-Compatible Messaging Demo ===")

    # Create service configuration for ZMQ TCP communication
    service_config = ServiceConfig(
        comm_backend=CommunicationBackend.ZMQ_TCP,
        # Note: The config will automatically create ZMQTCPConfig with default ports
    )

    # Create two services
    service_a = ServiceA("service_a", service_config)
    service_b = ServiceA("service_b", service_config)

    try:
        # Start both services
        await service_a.start()
        await service_b.start()

        # Wait a moment for subscriptions to be established
        await asyncio.sleep(1.0)

        logger.info("\n--- Publishing broadcast messages ---")
        await service_a.send_data("Hello from Service A!")
        await service_b.send_data("Hello from Service B!")

        # Wait for message processing
        await asyncio.sleep(1.0)

        logger.info("\n--- Sending targeted commands ---")
        await service_a.send_command("service_b", "STATUS_REQUEST", None)
        await service_b.send_command("service_a", "STATUS_REQUEST", None)

        # Wait for command processing
        await asyncio.sleep(2.0)

        logger.info("\n--- Demo complete ---")

    except Exception as e:
        logger.error(f"Demo failed: {e}")
        raise
    finally:
        # Cleanup
        await service_a.stop()
        await service_b.stop()


async def demo_simple_usage():
    """Demonstrate simple usage without complex service setup."""
    logger.info("\n=== Simple Usage Demo ===")

    # Create a simple message bus
    service_config = ServiceConfig(comm_backend=CommunicationBackend.ZMQ_TCP)
    bus = MessageBus(service_config=service_config)

    messages_received = []

    # Simple message handler
    async def handle_message(message: Message):
        messages_received.append(message)
        logger.info(f"Received: {message.type} - {message.content}")

    try:
        # Start the bus
        await bus.start()

        # Subscribe to messages
        bus.subscribe("SIMPLE_MESSAGE", handle_message)

        # Wait for subscription to be established
        await asyncio.sleep(0.5)

        # Send some messages
        await bus.publish(
            Message(
                type="SIMPLE_MESSAGE", content="Hello World!", sender_id="demo_sender"
            )
        )

        await bus.publish(
            Message(
                type="SIMPLE_MESSAGE",
                content="This is using real ZMQ!",
                sender_id="demo_sender",
            )
        )

        # Wait for processing
        await asyncio.sleep(1.0)

        logger.info(f"Total messages received: {len(messages_received)}")

    finally:
        await bus.stop()


if __name__ == "__main__":

    async def main():
        await demo_simple_usage()
        await demo_legacy_messaging()

    # Run the demo
    asyncio.run(main())
