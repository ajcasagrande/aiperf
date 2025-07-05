# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
from collections.abc import Callable
from typing import Any

import zmq.asyncio

from aiperf.common.comms.base import CommunicationClientFactory
from aiperf.common.comms.zmq.zmq_base_client import BaseZMQClient
from aiperf.common.enums import CommunicationClientType, MessageType
from aiperf.common.exceptions import CommunicationError
from aiperf.common.hooks import aiperf_task_loop
from aiperf.common.messages import Message
from aiperf.common.utils import call_all_functions


@CommunicationClientFactory.register(CommunicationClientType.SUB)
class ZMQSubClient(BaseZMQClient):
    """
    ZMQ SUB socket client for subscribing to messages from PUB sockets.
    One-to-Many or Many-to-One communication pattern.

    ASCII Diagram:
    ┌──────────────┐    ┌──────────────┐
    │     PUB      │───>│              │
    │ (Publisher)  │    │              │
    └──────────────┘    │     SUB      │
    ┌──────────────┐    │ (Subscriber) │
    │     PUB      │───>│              │
    │ (Publisher)  │    │              │
    └──────────────┘    └──────────────┘
    OR
    ┌──────────────┐    ┌──────────────┐
    │              │───>│     SUB      │
    │              │    │ (Subscriber) │
    │     PUB      │    └──────────────┘
    │ (Publisher)  │    ┌──────────────┐
    │              │───>│     SUB      │
    │              │    │ (Subscriber) │
    └──────────────┘    └──────────────┘


    Usage Pattern:
    - Single SUB socket subscribes to multiple PUB publishers (One-to-Many)
    OR
    - Multiple SUB sockets subscribe to a single PUB publisher (Many-to-One)

    - Subscribes to specific message topics/types
    - Receives all messages matching subscriptions

    SUB/PUB is a One-to-Many communication pattern. If you need Many-to-Many,
    use a ZMQ Proxy as well. see :class:`ZMQXPubXSubProxy` for more details.
    """

    def __init__(
        self,
        context: zmq.asyncio.Context,
        address: str,
        bind: bool,
        socket_ops: dict | None = None,
    ) -> None:
        """
        Initialize the ZMQ Subscriber class.

        Args:
            context (zmq.asyncio.Context): The ZMQ context.
            address (str): The address to bind or connect to.
            bind (bool): Whether to bind or connect the socket.
            socket_ops (dict, optional): Additional socket options to set.
        """
        super().__init__(context, zmq.SocketType.SUB, address, bind, socket_ops)

        self._subscribers: dict[MessageType | str, list[Callable[[Message], Any]]] = {}

    async def subscribe(
        self, message_type: MessageType | str, callback: Callable[[Message], Any]
    ) -> None:
        """Subscribe to a message_type.

        Args:
            message_type: MessageType or str to subscribe to
            callback: Function to call when a message is received (receives Message object)

        Raises:
            Exception if subscription was not successful, None otherwise
        """
        await self._ensure_initialized()

        try:
            if message_type not in self._subscribers:
                self._subscribers[message_type] = []
                # Only subscribe to message_type once per client
                self.socket.subscribe(message_type.encode())

            self._subscribers[message_type].append(callback)

            self.logger.debug(
                "Subscribed to message_type: %s, %s",
                message_type,
                self._subscribers[message_type],
            )

        except Exception as e:
            self.logger.error(
                "Exception subscribing to message_type %s: %s", message_type, e
            )
            raise CommunicationError(
                f"Failed to subscribe to message_type {message_type}: {e}",
            ) from e

    async def unsubscribe(
        self,
        message_type: MessageType | str,
        callback: Callable[[Message], Any] | None = None,
    ) -> None:
        """Remove a callback for a specified message_type. If no callbacks are left, unsubscribe from the message_type.

        Args:
            message_type: MessageType or str to unsubscribe from
            callback: Function to remove from the subscription. If None, all callbacks for the message_type will be removed.
        """
        if message_type not in self._subscribers:
            self.logger.warning(
                "Message type %s not subscribed to, skipping unsubscribe",
                message_type,
            )
            return

        await self._ensure_initialized()

        if callback:
            self._subscribers[message_type].remove(callback)
        else:
            self._subscribers[message_type] = []

        if not self._subscribers[message_type]:
            try:
                self.socket.unsubscribe(message_type.encode())
                self._subscribers.pop(message_type)
            except Exception as e:
                self.logger.error(
                    "Exception unsubscribing from message_type %s: %s", message_type, e
                )
                raise CommunicationError(
                    f"Failed to unsubscribe from message_type {message_type}: {e}",
                ) from e

    async def _handle_message(self, topic_bytes: bytes, message_bytes: bytes) -> None:
        """Handle a message from a subscribed message_type."""
        message_type = topic_bytes.decode()
        message_json = message_bytes.decode()
        self.logger.debug(
            "Received message from message_type: '%s', message: %s",
            message_type,
            message_json,
        )

        message = Message.from_json(message_json)

        # Call callbacks with the parsed message object
        if message_type in self._subscribers:
            await call_all_functions(self._subscribers[message_type], message)

    @aiperf_task_loop
    async def _sub_receiver_loop(self) -> None:
        """Background task for receiving messages from subscribed topics.

        This method is a coroutine that will run indefinitely until the client is
        shutdown. It will wait for messages from the socket and handle them.
        """
        try:
            (
                topic_bytes,
                message_bytes,
            ) = await self.socket.recv_multipart()

            self.execute_async(self._handle_message(topic_bytes, message_bytes))
        except zmq.Again:
            # This means we timed out waiting for a message.
            # We can continue to the next iteration of the loop.
            return
