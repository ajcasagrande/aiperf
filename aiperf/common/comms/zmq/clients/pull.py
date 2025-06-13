# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
import asyncio
import logging
import os
from collections.abc import Callable, Coroutine
from typing import Any

import zmq.asyncio
from pydantic import ValidationError
from zmq import SocketType

from aiperf.common.comms.zmq.clients.base import BaseZMQClient
from aiperf.common.enums import MessageType
from aiperf.common.exceptions import AIPerfError
from aiperf.common.hooks import aiperf_task, on_init
from aiperf.common.messages import InferenceResultsMessage, Message, MessageValidator
from aiperf.common.utils import call_all_functions

logger = logging.getLogger(__name__)


class ZMQPullClient(BaseZMQClient):
    def __init__(
        self,
        context: zmq.asyncio.Context,
        address: str,
        bind: bool,
        socket_ops: dict | None = None,
    ) -> None:
        """
        Initialize the ZMQ Puller class.

        Args:
            context (zmq.asyncio.Context): The ZMQ context.
            address (str): The address to bind or connect to.
            bind (bool): Whether to bind or connect the socket.
            socket_ops (dict, optional): Additional socket options to set.
        """
        super().__init__(context, SocketType.PULL, address, bind, socket_ops)
        self._pull_callbacks: dict[
            MessageType, list[Callable[[Message], Coroutine[Any, Any, None]]]
        ] = {}
        self.queue: asyncio.Queue[str] | None = None

    @on_init
    async def _on_initialize(self) -> None:
        """Initialize the ZMQ Pull client."""
        self.queue = asyncio.Queue(
            maxsize=2 * (int(os.getenv("AIPERF_CONCURRENCY") or 100))
        )

    @aiperf_task
    async def _pull_receiver(self) -> None:
        """Background task for receiving data from the pull socket.

        This method is a coroutine that will run indefinitely until the client is
        shutdown. It will wait for messages from the socket and handle them.
        """
        if not self.is_initialized:
            await self.initialized_event.wait()

        while not self.is_shutdown:
            try:
                message_json = await self.socket.recv_string()
                logger.debug("Received message from pull socket: %s", message_json)
                await self.queue.put(message_json)
                logger.debug("Put message into queue")

            except zmq.Again:
                await asyncio.sleep(0.1)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(
                    "Exception receiving data from pull socket: %s %s",
                    type(e).__name__,
                    e,
                )
                await asyncio.sleep(0.1)

    @aiperf_task
    async def _queue_drainer(self) -> None:
        """Background task for draining the queue."""

        if not self.is_initialized:
            await self.initialized_event.wait()

        while not self.is_shutdown:
            try:
                # Receive data
                message_json = await self.queue.get()
                logger.debug("Drained message from queue: %s", message_json)

                # Parse JSON into a Message object
                try:
                    message = MessageValidator.validate_json(message_json)
                    if isinstance(message, InferenceResultsMessage):
                        logger.info(message)
                        logger.info(message_json)
                except ValidationError as e:
                    logger.error(
                        "Error parsing pull message: %s %s %s",
                        message_json,
                        type(e).__name__,
                        e,
                    )
                    continue

                topic = message.message_type

                # Call callbacks with Message object
                if topic in self._pull_callbacks:
                    _ = asyncio.create_task(
                        call_all_functions(self._pull_callbacks[topic], message)
                    )
                else:
                    logger.debug(
                        "Pull message received on topic without callback %s", topic
                    )

            except asyncio.CancelledError:
                break
            except AIPerfError:
                raise  # re-raise it up the stack
            except zmq.Again:
                await asyncio.sleep(0.1)
            except Exception as e:
                logger.error(
                    "Exception receiving data from pull socket: %s %s",
                    type(e).__name__,
                    e,
                )
                await asyncio.sleep(0.1)

    async def register_pull_callback(
        self,
        message_type: MessageType,
        callback: Callable[[Message], Coroutine[Any, Any, None]],
    ) -> None:
        """Register a ZMQ Pull data callback from a message type.

        Args:
            message_type:
            callback: function to call when data is received.

        Raises:
            CommunicationNotInitializedError: If the client is not initialized
            CommunicationPullError: If an exception occurred registering the pull callback
        """
        self._ensure_initialized()

        # Register callback
        if message_type not in self._pull_callbacks:
            self._pull_callbacks[message_type] = []
        self._pull_callbacks[message_type].append(callback)
