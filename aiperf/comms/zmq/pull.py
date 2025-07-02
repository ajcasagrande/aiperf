# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
import asyncio
import logging
import os
from collections.abc import Callable, Coroutine
from typing import Any

import zmq.asyncio

from aiperf.common.comms.base import PullClient
from aiperf.common.comms.zmq.clients.base import BaseZMQClient
from aiperf.common.constants import TASK_CANCEL_TIMEOUT_SHORT
from aiperf.common.enums import MessageType
from aiperf.common.hooks import aiperf_task, on_stop
from aiperf.common.messages import Message
from aiperf.common.utils import call_all_functions

logger = logging.getLogger(__name__)


class ZMQPullClient(BaseZMQClient, PullClient):
    def __init__(
        self,
        context: zmq.asyncio.Context,
        address: str,
        bind: bool,
        socket_ops: dict | None = None,
        max_concurrency: int | None = None,
    ) -> None:
        """
        Initialize the ZMQ Puller class.

        Args:
            context (zmq.asyncio.Context): The ZMQ context.
            address (str): The address to bind or connect to.
            bind (bool): Whether to bind or connect the socket.
            socket_ops (dict, optional): Additional socket options to set.
            max_concurrency (int, optional): The maximum number of concurrent requests to allow.
        """
        super().__init__(context, zmq.SocketType.PULL, address, bind, socket_ops)
        self._pull_callbacks: dict[
            MessageType, list[Callable[[Message], Coroutine[Any, Any, None]]]
        ] = {}
        self.tasks: set[asyncio.Task] = set()

        if max_concurrency is not None:
            self.semaphore = asyncio.Semaphore(value=max_concurrency)
        else:
            self.semaphore = asyncio.Semaphore(
                value=int(os.getenv("AIPERF_WORKER_CONCURRENT_REQUESTS", 500))
            )

    @aiperf_task
    async def _pull_receiver(self) -> None:
        """Background task for receiving data from the pull socket.

        This method is a coroutine that will run indefinitely until the client is
        shutdown. It will wait for messages from the socket and handle them.
        """
        if not self.is_initialized:
            await self.initialized_event.wait()

        while not self.stop_event.is_set():
            try:
                # acquire the semaphore to limit the number of concurrent requests
                # NOTE: This MUST be done BEFORE calling recv_string() to allow the zmq push/pull
                # logic to properly load balance the requests.
                await self.semaphore.acquire()

                message_json = await self.socket.recv_string()
                logger.debug("Received message from pull socket: %s", message_json)
                task = asyncio.create_task(self._process_message(message_json))
                self.tasks.add(task)
                task.add_done_callback(self.tasks.discard)

            except zmq.Again:
                self.semaphore.release()
                await asyncio.sleep(0)  # Yield to other tasks
                continue

            except (asyncio.CancelledError, zmq.ContextTerminated):
                break

            except Exception as e:
                logger.error(
                    "Exception receiving data from pull socket: %s %s",
                    type(e).__name__,
                    e,
                )
                self.semaphore.release()
                await asyncio.sleep(0.1)

    @on_stop
    async def _stop(self) -> None:
        """Wait for all tasks to complete."""
        for task in list(self.tasks):
            if not task.done():
                task.cancel()

        await asyncio.wait_for(
            asyncio.gather(*self.tasks),
            timeout=TASK_CANCEL_TIMEOUT_SHORT,
        )
        self.tasks.clear()

    async def _process_message(self, message_json: str) -> None:
        """Process a message from the pull socket.

        This method is called by the background task when a message is received from
        the pull socket. It will deserialize the message and call the appropriate
        callback function.
        """
        message = Message.from_json(message_json)

        # Call callbacks with Message object
        if message.message_type in self._pull_callbacks:
            await call_all_functions(
                self._pull_callbacks[message.message_type], message
            )
        else:
            logger.warning(
                "Pull message received for message type %s without callback",
                message.message_type,
            )

        # release the semaphore to allow receiving more messages
        self.semaphore.release()

    async def register_pull_callback(
        self,
        message_type: MessageType,
        callback: Callable[[Message], Coroutine[Any, Any, None]],
        max_concurrency: int | None = None,
    ) -> None:
        """Register a ZMQ Pull data callback for a given message type.

        Note that more than one callback can be registered for a given message type.

        Args:
            message_type: The message type to register the callback for.
            callback: The function to call when data is received.
            max_concurrency: The maximum number of concurrent requests to allow.
        Raises:
            CommunicationError: If the client is not initialized
        """
        await self._ensure_initialized()

        if max_concurrency is not None:
            self.semaphore = asyncio.Semaphore(value=max_concurrency)

        # Register callback
        if message_type not in self._pull_callbacks:
            self._pull_callbacks[message_type] = []
        self._pull_callbacks[message_type].append(callback)
