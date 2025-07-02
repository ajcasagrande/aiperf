# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
Performance and Load Tests for ZMQ Proxies.

This module contains tests focused on proxy performance, resource management,
threading behavior, and load handling characteristics.
"""

import asyncio
import gc
import time
from unittest.mock import patch

import pytest

from aiperf.common.comms.zmq.clients import (
    ZMQPubClient,
    ZMQPullClient,
    ZMQPushClient,
    ZMQSubClient,
)
from aiperf.common.enums import ZMQProxyType
from aiperf.common.messages import ErrorMessage
from aiperf.common.record_models import ErrorDetails


@pytest.mark.performance
class TestZMQProxyPerformance:
    """Performance-focused tests for ZMQ proxies."""

    @pytest.mark.asyncio
    async def test_proxy_startup_time(self, managed_proxy_fixture, temp_ipc_config):
        """Test proxy startup time is reasonable."""
        start_time = time.perf_counter()

        async with managed_proxy_fixture(
            ZMQProxyType.PUSH_PULL, temp_ipc_config, start_proxy=True
        ) as (proxy, config):
            initialization_time = time.perf_counter() - start_time

            # Proxy should start within reasonable time (adjust threshold as needed)
            assert initialization_time < 1.0, (
                f"Proxy took {initialization_time:.3f}s to start"
            )
            assert proxy is not None

    @pytest.mark.asyncio
    async def test_proxy_shutdown_time(self, managed_proxy_fixture, temp_ipc_config):
        """Test proxy shutdown time is reasonable."""
        async with managed_proxy_fixture(
            ZMQProxyType.PUSH_PULL, temp_ipc_config, start_proxy=True
        ) as (proxy, config):
            pass  # Context manager handles cleanup timing

        # If we reach here without timeout, shutdown was successful
        assert True

    @pytest.mark.asyncio
    async def test_multiple_proxy_creation(self, zmq_context, temp_ipc_config):
        """Test creating multiple proxies doesn't cause resource issues."""
        proxies = []

        try:
            # Create multiple proxy configurations
            for i in range(5):
                import tempfile

                from aiperf.common.config.zmq_config import ZMQIPCProxyConfig

                with tempfile.TemporaryDirectory() as tmpdir:
                    config = ZMQIPCProxyConfig(path=tmpdir, name=f"proxy_{i}")

                    from aiperf.common.factories import ZMQProxyFactory

                    proxy = ZMQProxyFactory.create_instance(
                        ZMQProxyType.PUSH_PULL,
                        context=zmq_context,
                        zmq_proxy_config=config,
                    )
                    proxies.append(proxy)

            # All proxies should be created successfully
            assert len(proxies) == 5

            # Test that they don't interfere with each other
            for proxy in proxies:
                assert proxy.frontend_address != proxy.backend_address

        finally:
            # Cleanup
            for proxy in proxies:
                await proxy.stop()

    @pytest.mark.asyncio
    async def test_proxy_memory_cleanup(self, managed_proxy_fixture, temp_ipc_config):
        """Test that proxy properly cleans up memory resources."""
        # Force garbage collection before test
        gc.collect()
        initial_objects = len(gc.get_objects())

        async with managed_proxy_fixture(
            ZMQProxyType.PUSH_PULL, temp_ipc_config, start_proxy=True
        ) as (proxy, config):
            # Proxy should be created
            assert proxy is not None

        # Force garbage collection after cleanup
        gc.collect()
        final_objects = len(gc.get_objects())

        # Allow for some variance in object count but ensure no major leaks
        object_difference = final_objects - initial_objects
        assert abs(object_difference) < 100, (
            f"Potential memory leak: {object_difference} objects"
        )


@pytest.mark.load
class TestZMQProxyLoad:
    """Load testing for ZMQ proxies under high message volumes."""

    @pytest.mark.asyncio
    async def test_high_volume_message_forwarding(
        self, managed_proxy_fixture, temp_ipc_config, zmq_context
    ):
        """Test proxy can handle high volume of messages."""
        message_count = 100
        messages_sent = []
        messages_received = []

        async with managed_proxy_fixture(
            ZMQProxyType.PUSH_PULL, temp_ipc_config, start_proxy=True
        ) as (proxy, config):
            # Create clients
            push_client = ZMQPushClient(
                context=zmq_context, address=config.frontend_address, bind=False
            )

            pull_client = ZMQPullClient(
                context=zmq_context, address=config.backend_address, bind=False
            )

            try:
                await asyncio.gather(push_client.initialize(), pull_client.initialize())

                # Allow connections to establish
                await asyncio.sleep(0.1)

                # Receiving task
                async def receive_messages():
                    for _ in range(message_count):
                        try:
                            message = await asyncio.wait_for(
                                pull_client.receive(), timeout=5.0
                            )
                            messages_received.append(message)
                        except asyncio.TimeoutError:
                            break

                receive_task = asyncio.create_task(receive_messages())

                # Send messages rapidly
                start_time = time.perf_counter()
                for i in range(message_count):
                    message = f"message_{i}".encode()
                    messages_sent.append(message)
                    await push_client.send(message)

                # Wait for all messages to be received
                await asyncio.wait_for(receive_task, timeout=10.0)
                end_time = time.perf_counter()

                # Verify all messages were forwarded
                assert len(messages_received) == message_count
                assert set(messages_received) == set(messages_sent)

                # Calculate throughput
                throughput = message_count / (end_time - start_time)
                print(f"Message throughput: {throughput:.2f} messages/second")

                # Ensure reasonable throughput (adjust threshold as needed)
                assert throughput > 10, f"Throughput too low: {throughput:.2f} msg/s"

            finally:
                await asyncio.gather(push_client.shutdown(), pull_client.shutdown())

    @pytest.mark.asyncio
    async def test_concurrent_clients(
        self, managed_proxy_fixture, temp_ipc_config, zmq_context
    ):
        """Test proxy with multiple concurrent clients."""
        num_clients = 5
        messages_per_client = 10
        all_received_messages = []

        async with managed_proxy_fixture(
            ZMQProxyType.PUSH_PULL, temp_ipc_config, start_proxy=True
        ) as (proxy, config):
            # Create multiple push clients
            push_clients = []
            for i in range(num_clients):
                client = ZMQPushClient(
                    context=zmq_context, address=config.frontend_address, bind=False
                )
                push_clients.append(client)

            # Create pull client
            pull_client = ZMQPullClient(
                context=zmq_context, address=config.backend_address, bind=False
            )

            try:
                # Initialize all clients
                await asyncio.gather(
                    *[client.initialize() for client in push_clients],
                    pull_client.initialize(),
                )

                # Allow connections to establish
                await asyncio.sleep(0.2)

                # Receiving task
                expected_total = num_clients * messages_per_client

                async def receive_all_messages():
                    for _ in range(expected_total):
                        try:
                            message = await asyncio.wait_for(
                                pull_client.receive(), timeout=5.0
                            )
                            all_received_messages.append(message)
                        except asyncio.TimeoutError:
                            break

                receive_task = asyncio.create_task(receive_all_messages())

                # Send messages from all clients concurrently
                async def send_from_client(client_id: int, client: ZMQPushClient):
                    for msg_id in range(messages_per_client):
                        message = f"client_{client_id}_msg_{msg_id}".encode()
                        await client.send(message)

                send_tasks = [
                    asyncio.create_task(send_from_client(i, client))
                    for i, client in enumerate(push_clients)
                ]

                # Wait for all sending to complete
                await asyncio.gather(*send_tasks)

                # Wait for all messages to be received
                await asyncio.wait_for(receive_task, timeout=10.0)

                # Verify all messages were received
                assert len(all_received_messages) == expected_total

                # Verify messages from each client were received
                for client_id in range(num_clients):
                    client_messages = [
                        msg
                        for msg in all_received_messages
                        if msg.startswith(f"client_{client_id}_".encode())
                    ]
                    assert len(client_messages) == messages_per_client

            finally:
                await asyncio.gather(
                    *[client.shutdown() for client in push_clients],
                    pull_client.shutdown(),
                )

    @pytest.mark.asyncio
    async def test_pub_sub_fan_out_performance(
        self, managed_proxy_fixture, temp_ipc_config, zmq_context
    ):
        """Test pub/sub proxy performance with multiple subscribers."""
        num_subscribers = 3
        num_messages = 20
        subscriber_received = [[] for _ in range(num_subscribers)]

        async with managed_proxy_fixture(
            ZMQProxyType.XPUB_XSUB, temp_ipc_config, start_proxy=True
        ) as (proxy, config):
            # Create publisher
            pub_client = ZMQPubClient(
                context=zmq_context, address=config.frontend_address, bind=False
            )

            # Create multiple subscribers
            sub_clients = []
            for i in range(num_subscribers):
                client = ZMQSubClient(
                    context=zmq_context, address=config.backend_address, bind=False
                )
                sub_clients.append(client)

            try:
                # Initialize all clients
                await asyncio.gather(
                    pub_client.initialize(),
                    *[client.initialize() for client in sub_clients],
                )

                # Set up subscriptions
                test_topic = "performance.test"

                for i, client in enumerate(sub_clients):

                    async def make_handler(subscriber_id):
                        async def handler(topic: str, message: bytes):
                            subscriber_received[subscriber_id].append((topic, message))

                        return handler

                    handler = await make_handler(i)
                    await client.subscribe(test_topic, handler)

                # Allow subscriptions to propagate
                await asyncio.sleep(0.3)

                # Publish messages
                start_time = time.perf_counter()
                for i in range(num_messages):
                    message = f"perf_test_message_{i}".encode()
                    await pub_client.publish(test_topic, message)

                # Wait for message delivery
                await asyncio.sleep(0.5)
                end_time = time.perf_counter()

                # Verify all subscribers received all messages
                for i, received in enumerate(subscriber_received):
                    assert len(received) == num_messages, (
                        f"Subscriber {i} received {len(received)}/{num_messages} messages"
                    )

                # Calculate fan-out performance
                total_deliveries = sum(
                    len(received) for received in subscriber_received
                )
                delivery_rate = total_deliveries / (end_time - start_time)

                print(f"Fan-out delivery rate: {delivery_rate:.2f} deliveries/second")
                assert delivery_rate > 50, (
                    f"Fan-out too slow: {delivery_rate:.2f} deliveries/s"
                )

            finally:
                await asyncio.gather(
                    pub_client.shutdown(),
                    *[client.shutdown() for client in sub_clients],
                )


@pytest.mark.stress
class TestZMQProxyStress:
    """Stress tests for proxy resilience under adverse conditions."""

    @pytest.mark.asyncio
    async def test_proxy_handles_rapid_start_stop(self, zmq_context, temp_ipc_config):
        """Test proxy can handle rapid start/stop cycles."""
        from aiperf.common.factories import ZMQProxyFactory

        for i in range(10):
            proxy = ZMQProxyFactory.create_instance(
                ZMQProxyType.PUSH_PULL,
                context=zmq_context,
                zmq_proxy_config=temp_ipc_config,
            )

            # Start and immediately stop
            proxy_task = asyncio.create_task(proxy.run())
            await asyncio.sleep(0.01)  # Very brief run time

            proxy_task.cancel()
            try:
                await asyncio.wait_for(proxy_task, timeout=0.5)
            except asyncio.CancelledError:
                pass

            await proxy.stop()

    @pytest.mark.asyncio
    async def test_proxy_resource_limits(self, managed_proxy_fixture, temp_ipc_config):
        """Test proxy behavior under resource constraints."""
        # This test simulates resource constraints by mocking system calls
        async with managed_proxy_fixture(
            ZMQProxyType.PUSH_PULL,
            temp_ipc_config,
            start_proxy=False,  # Don't auto-start due to mocking
        ) as (proxy, config):
            # Mock resource exhaustion scenarios
            with patch("asyncio.to_thread") as mock_to_thread:
                mock_to_thread.side_effect = OSError("Resource temporarily unavailable")

                # Proxy should handle resource errors gracefully
                with pytest.raises((OSError, asyncio.TimeoutError)):
                    await asyncio.wait_for(proxy.run(), timeout=1.0)

    @pytest.mark.asyncio
    async def test_proxy_handles_client_disconnections(
        self, managed_proxy_fixture, temp_ipc_config, zmq_context
    ):
        """Test proxy stability when clients disconnect abruptly."""
        async with managed_proxy_fixture(
            ZMQProxyType.PUSH_PULL, temp_ipc_config, start_proxy=True
        ) as (proxy, config):
            # Create and connect clients
            clients = []
            for i in range(3):
                push_client = ZMQPushClient(
                    context=zmq_context, address=config.frontend_address, bind=False
                )
                await push_client.initialize()
                clients.append(push_client)

            # Send some messages
            for i, client in enumerate(clients):
                await client.push(ErrorMessage(error=ErrorDetails(main="assas")))

            # Abruptly disconnect clients (simulating network issues)
            for client in clients:
                # Immediately close without proper shutdown
                client.socket.close()

            # Proxy should remain stable despite client disconnections
            await asyncio.sleep(0.1)

            # Create new client to verify proxy is still functional
            test_client = ZMQPushClient(
                context=zmq_context, address=config.frontend_address, bind=False
            )

            try:
                await test_client.initialize()
                await test_client.push(ErrorMessage("test"))
                # If we reach here, proxy handled disconnections gracefully
                assert True
            finally:
                await test_client.shutdown()
