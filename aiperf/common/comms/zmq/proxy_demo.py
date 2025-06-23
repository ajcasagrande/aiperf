# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
Demo script showing how to use the XPUB/XSUB proxy service for many-to-many pub/sub communications.

This example demonstrates:
- Setting up an XPUB/XSUB proxy using ZMQ's built-in proxy functionality
- Multiple publishers sending to the proxy
- Multiple subscribers receiving through the proxy
- Topic-based message routing
- Efficient message forwarding using zmq.proxy()
"""

import asyncio
import json
import logging
from typing import Any

import zmq.asyncio

from aiperf.common.comms.zmq.proxy_service import ZMQProxyService
from aiperf.common.config.zmq_config import ZMQTCPTransportConfig

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class SimplePublisher:
    """A simple publisher that sends messages to the proxy."""

    def __init__(
        self, context: zmq.asyncio.Context, publisher_address: str, publisher_id: str
    ):
        self.context = context
        self.publisher_address = publisher_address
        self.publisher_id = publisher_id
        self.socket: zmq.asyncio.Socket | None = None

    async def initialize(self) -> None:
        """Initialize the publisher socket."""
        self.socket = self.context.socket(zmq.PUB)
        self.socket.connect(self.publisher_address)
        # Give socket time to connect
        await asyncio.sleep(0.1)
        logger.info(
            f"Publisher {self.publisher_id} connected to {self.publisher_address}"
        )

    async def publish(self, topic: str, data: dict[str, Any]) -> None:
        """Publish a message to a topic."""
        if not self.socket:
            raise RuntimeError("Publisher not initialized")

        # Create a simple message-like structure
        message_data = {
            "publisher_id": self.publisher_id,
            "topic": topic,
            "data": data,
            "timestamp": asyncio.get_event_loop().time(),
        }

        message_json = json.dumps(message_data)
        await self.socket.send_multipart([topic.encode(), message_json.encode()])
        logger.info(
            f"Publisher {self.publisher_id} sent message to topic '{topic}': {data}"
        )

    async def shutdown(self) -> None:
        """Shutdown the publisher."""
        if self.socket:
            self.socket.close()


class SimpleSubscriber:
    """A simple subscriber that receives messages from the proxy."""

    def __init__(
        self, context: zmq.asyncio.Context, subscriber_address: str, subscriber_id: str
    ):
        self.context = context
        self.subscriber_address = subscriber_address
        self.subscriber_id = subscriber_id
        self.socket: zmq.asyncio.Socket | None = None
        self.running = False

    async def initialize(self) -> None:
        """Initialize the subscriber socket."""
        self.socket = self.context.socket(zmq.SUB)
        self.socket.connect(self.subscriber_address)
        logger.info(
            f"Subscriber {self.subscriber_id} connected to {self.subscriber_address}"
        )

    async def subscribe(self, topic: str) -> None:
        """Subscribe to a topic."""
        if not self.socket:
            raise RuntimeError("Subscriber not initialized")

        self.socket.setsockopt(zmq.SUBSCRIBE, topic.encode())
        logger.info(f"Subscriber {self.subscriber_id} subscribed to topic '{topic}'")

    async def start_listening(self) -> None:
        """Start listening for messages."""
        if not self.socket:
            raise RuntimeError("Subscriber not initialized")

        self.running = True
        logger.info(f"Subscriber {self.subscriber_id} started listening")

        while self.running:
            try:
                # Receive message with timeout
                topic, message_data = await asyncio.wait_for(
                    self.socket.recv_multipart(), timeout=1.0
                )

                topic_str = topic.decode()
                message_json = message_data.decode()
                message_dict = json.loads(message_json)

                logger.info(
                    f"Subscriber {self.subscriber_id} received message on topic '{topic_str}' "
                    f"from publisher {message_dict.get('publisher_id')}: {message_dict.get('data')}"
                )

            except asyncio.TimeoutError:
                # Timeout is normal, continue listening
                continue
            except Exception as e:
                logger.error(f"Error in subscriber {self.subscriber_id}: {e}")
                break

    async def stop_listening(self) -> None:
        """Stop listening for messages."""
        self.running = False

    async def shutdown(self) -> None:
        """Shutdown the subscriber."""
        await self.stop_listening()
        if self.socket:
            self.socket.close()


async def run_proxy_demo():
    """Run the XPUB/XSUB proxy demonstration."""
    logger.info("Starting XPUB/XSUB Proxy Demo")

    # Create ZMQ context
    context = zmq.asyncio.Context()

    try:
        # Create proxy service configuration
        config = ZMQTCPTransportConfig(
            host="127.0.0.1",
            controller_pub_sub_port=5555,  # Base port for proxy frontend
            component_pub_sub_port=5556,  # Base port for proxy backend
        )

        # Create and start the proxy service
        proxy_service = ZMQProxyService(
            config, proxy_name="demo_proxy", context=context
        )
        await proxy_service.initialize()

        logger.info("Proxy service started:")
        logger.info(f"  Publisher address: {proxy_service.get_publisher_address()}")
        logger.info(f"  Subscriber address: {proxy_service.get_subscriber_address()}")

        # Create publishers
        publishers = []
        for i in range(2):
            pub = SimplePublisher(
                context, proxy_service.get_publisher_address(), f"pub_{i + 1}"
            )
            await pub.initialize()
            publishers.append(pub)

        # Create subscribers
        subscribers = []
        for i in range(3):
            sub = SimpleSubscriber(
                context, proxy_service.get_subscriber_address(), f"sub_{i + 1}"
            )
            await sub.initialize()

            # Subscribe to different topics
            if i == 0:
                await sub.subscribe("news")
                await sub.subscribe("weather")
            elif i == 1:
                await sub.subscribe("news")
            else:
                await sub.subscribe("weather")
                await sub.subscribe("sports")

            subscribers.append(sub)

        # Start subscriber listening tasks
        subscriber_tasks = []
        for sub in subscribers:
            task = asyncio.create_task(sub.start_listening())
            subscriber_tasks.append(task)

        # Give subscribers time to fully connect and subscribe
        await asyncio.sleep(1)

        # Publish some messages
        logger.info("Publishing messages...")

        # Publisher 1 sends news and weather
        await publishers[0].publish(
            "news", {"headline": "Breaking: New ZMQ Proxy Works!"}
        )
        await publishers[0].publish(
            "weather", {"temperature": "22°C", "condition": "sunny"}
        )

        # Publisher 2 sends sports and news
        await publishers[1].publish("sports", {"team": "Lakers", "score": "110-95"})
        await publishers[1].publish(
            "news", {"headline": "Tech: NVIDIA Releases New AI Framework"}
        )

        # More messages from both publishers
        await publishers[0].publish(
            "weather", {"temperature": "20°C", "condition": "cloudy"}
        )
        await publishers[1].publish("sports", {"team": "Warriors", "score": "105-98"})

        # Let messages propagate
        await asyncio.sleep(2)

        logger.info("Demo completed! Shutting down...")

        # Shutdown subscribers
        for sub in subscribers:
            await sub.shutdown()

        # Cancel subscriber tasks
        for task in subscriber_tasks:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        # Shutdown publishers
        for pub in publishers:
            await pub.shutdown()

        # Shutdown proxy service
        await proxy_service.shutdown()

        logger.info("Demo shutdown complete")

    finally:
        # Terminate context
        context.term()


if __name__ == "__main__":
    asyncio.run(run_proxy_demo())
