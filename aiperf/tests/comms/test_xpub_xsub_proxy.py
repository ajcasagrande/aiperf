# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

import asyncio
import json

import pytest
import zmq.asyncio

from aiperf.common.comms.zmq.clients.xpub_xsub_proxy import ZMQXPubXSubProxy
from aiperf.common.config.zmq_config import (
    ZMQTCPProxyConfig,
    ZMQTCPTransportConfig,
)
from aiperf.services.proxies import XPubXSubProxyService


class TestXPubXSubProxyClient:
    """Test the XPUB/XSUB proxy client functionality."""

    @pytest.fixture
    async def context(self):
        """Create and cleanup ZMQ context."""
        ctx = zmq.asyncio.Context()
        yield ctx
        ctx.term()

    @pytest.fixture
    async def proxy_client(self, context):
        """Create and cleanup proxy client."""
        client = ZMQXPubXSubProxy(
            context=context,
            zmq_proxy_config=ZMQTCPProxyConfig(
                host="127.0.0.1",
                frontend_port=15555,
                backend_port=15556,
            ),
        )
        await client.run()
        yield client
        await client.stop()

    async def test_proxy_initialization(self, context):
        """Test proxy client initialization."""
        client = ZMQXPubXSubProxy(
            context=context,
            zmq_proxy_config=ZMQTCPProxyConfig(
                host="127.0.0.1",
                frontend_port=15555,
                backend_port=15556,
            ),
        )

        assert not client.is_running()
        await client.run()
        assert client.is_running()
        assert not client.is_shutdown()

        await client.stop()
        assert client.is_shutdown()

    async def test_proxy_addresses(self, proxy_client):
        """Test getting proxy addresses."""
        assert proxy_client.frontend_address == "tcp://127.0.0.1:15555"
        assert proxy_client.backend_address == "tcp://127.0.0.1:15556"

    async def test_proxy_message_forwarding(self, context, proxy_client):
        """Test that the proxy forwards messages between publishers and subscribers."""
        # Create publisher socket
        pub_socket = context.socket(zmq.PUB)
        pub_socket.connect(proxy_client.frontend_address)

        # Create subscriber socket
        sub_socket = context.socket(zmq.SUB)
        sub_socket.connect(proxy_client.backend_address)
        sub_socket.setsockopt(zmq.SUBSCRIBE, b"test_topic")

        # Give sockets time to connect
        await asyncio.sleep(0.2)

        # Send message from publisher
        test_message = {"data": "test_data", "timestamp": 123456}
        message_json = json.dumps(test_message)
        await pub_socket.send_multipart([b"test_topic", message_json.encode()])

        # Receive message on subscriber
        try:
            topic, message_data = await asyncio.wait_for(
                sub_socket.recv_multipart(), timeout=2.0
            )

            assert topic == b"test_topic"
            received_data = json.loads(message_data.decode())
            assert received_data == test_message

        except asyncio.TimeoutError:
            pytest.fail("Message was not received by subscriber")

        # Cleanup
        pub_socket.close()
        sub_socket.close()

    async def test_proxy_multiple_publishers_subscribers(self, context, proxy_client):
        """Test proxy with multiple publishers and subscribers."""
        # Create multiple publishers
        publishers = []
        for _ in range(2):
            pub_socket = context.socket(zmq.PUB)
            pub_socket.connect(proxy_client.frontend_address)
            publishers.append(pub_socket)

        # Create multiple subscribers
        subscribers = []
        for _ in range(2):
            sub_socket = context.socket(zmq.SUB)
            sub_socket.connect(proxy_client.backend_address)
            sub_socket.setsockopt(zmq.SUBSCRIBE, b"topic")
            subscribers.append(sub_socket)

        # Give sockets time to connect
        await asyncio.sleep(0.2)

        # Send messages from both publishers
        messages = []
        for i, pub_socket in enumerate(publishers):
            test_message = {"publisher": i, "data": f"message_{i}"}
            message_json = json.dumps(test_message)
            await pub_socket.send_multipart([b"topic", message_json.encode()])
            messages.append(test_message)

        # Receive messages on both subscribers
        received_messages = []
        for sub_socket in subscribers:
            for _ in range(2):  # Expect 2 messages per subscriber
                try:
                    topic, message_data = await asyncio.wait_for(
                        sub_socket.recv_multipart(), timeout=2.0
                    )
                    received_data = json.loads(message_data.decode())
                    received_messages.append(received_data)
                except asyncio.TimeoutError:
                    pytest.fail("Expected message was not received")

        # Each subscriber should receive both messages
        assert len(received_messages) == 4  # 2 subscribers × 2 messages

        # Cleanup
        for pub_socket in publishers:
            pub_socket.close()
        for sub_socket in subscribers:
            sub_socket.close()


class TestZMQProxyService:
    """Test the ZMQ proxy service functionality."""

    @pytest.fixture
    async def config(self):
        """Create test configuration."""
        return ZMQTCPTransportConfig(
            host="127.0.0.1",
            controller_pub_sub_port=16555,
            component_pub_sub_port=16556,
        )

    @pytest.fixture
    async def proxy_service(self, config):
        """Create and cleanup proxy service."""
        service = XPubXSubProxyService(config)
        await service.run()
        yield service
        await service.stop()

    async def test_proxy_service_initialization(self, config):
        """Test proxy service initialization and shutdown."""
        service = XPubXSubProxyService(config)

        assert not service.is_running
        await service.run()
        assert service.is_running
        assert not service.is_shutdown

        await service.stop()
        assert service.is_shutdown

    async def test_proxy_service_addresses(self, proxy_service):
        """Test proxy service address generation."""
        pub_addr = proxy_service.frontend_address
        sub_addr = proxy_service.backend_address

        assert "tcp://127.0.0.1:" in pub_addr
        assert "tcp://127.0.0.1:" in sub_addr
        assert pub_addr != sub_addr

    async def test_proxy_service_health_check(self, proxy_service):
        """Test proxy service health check."""
        is_healthy = await proxy_service.health_check()
        assert is_healthy

    async def test_proxy_service_status(self, proxy_service):
        """Test proxy service status reporting."""
        status = proxy_service.get_status()

        assert status["name"] == "test_proxy"
        assert status["initialized"] is True
        assert status["shutdown"] is False
        assert "frontend_address" in status
        assert "backend_address" in status

    async def test_proxy_service_messaging_integration(self, proxy_service):
        """Test that the proxy service properly handles messaging."""
        context = zmq.asyncio.Context()

        try:
            # Create publisher and subscriber
            pub_socket = context.socket(zmq.PUB)
            pub_socket.connect(proxy_service.frontend_address)

            sub_socket = context.socket(zmq.SUB)
            sub_socket.connect(proxy_service.backend_address)
            sub_socket.setsockopt(zmq.SUBSCRIBE, b"integration_test")

            # Give sockets time to connect
            await asyncio.sleep(0.2)

            # Send test message
            test_data = {"test": "integration", "value": 42}
            message_json = json.dumps(test_data)
            await pub_socket.send_multipart(
                [b"integration_test", message_json.encode()]
            )

            # Receive and verify message
            try:
                topic, message_data = await asyncio.wait_for(
                    sub_socket.recv_multipart(), timeout=2.0
                )

                assert topic == b"integration_test"
                received_data = json.loads(message_data.decode())
                assert received_data == test_data

            except asyncio.TimeoutError:
                pytest.fail("Integration test message was not received")

        finally:
            # Cleanup
            pub_socket.close()
            sub_socket.close()
            context.term()


@pytest.mark.asyncio
async def test_proxy_topic_filtering():
    """Test that the proxy correctly filters messages by topic."""
    context = zmq.asyncio.Context()

    try:
        # Create proxy
        proxy = ZMQXPubXSubProxy(
            context=context,
            zmq_proxy_config=ZMQTCPProxyConfig(
                host="127.0.0.1",
                frontend_port=17555,
                backend_port=17556,
            ),
        )
        await proxy.run()

        # Create publisher
        pub_socket = context.socket(zmq.PUB)
        pub_socket.connect(proxy.frontend_address)

        # Create subscribers for different topics
        sub1 = context.socket(zmq.SUB)
        sub1.connect(proxy.backend_address)
        sub1.setsockopt(zmq.SUBSCRIBE, b"topic1")

        sub2 = context.socket(zmq.SUB)
        sub2.connect(proxy.backend_address)
        sub2.setsockopt(zmq.SUBSCRIBE, b"topic2")

        # Give sockets time to connect
        await asyncio.sleep(0.2)

        # Send messages to different topics
        await pub_socket.send_multipart([b"topic1", b"message_for_topic1"])
        await pub_socket.send_multipart([b"topic2", b"message_for_topic2"])
        await pub_socket.send_multipart([b"topic3", b"message_for_topic3"])

        # Subscriber 1 should only receive topic1 message
        try:
            topic, message = await asyncio.wait_for(sub1.recv_multipart(), timeout=1.0)
            assert topic == b"topic1"
            assert message == b"message_for_topic1"
        except asyncio.TimeoutError:
            pytest.fail("Subscriber 1 did not receive topic1 message")

        # Subscriber 2 should only receive topic2 message
        try:
            topic, message = await asyncio.wait_for(sub2.recv_multipart(), timeout=1.0)
            assert topic == b"topic2"
            assert message == b"message_for_topic2"
        except asyncio.TimeoutError:
            pytest.fail("Subscriber 2 did not receive topic2 message")

        # Neither subscriber should receive topic3 message (no subscribers)
        # We can't easily test for non-receipt, so we'll just verify the above works

    finally:
        # Cleanup
        pub_socket.close()
        sub1.close()
        sub2.close()
        await proxy.stop()
        context.term()
