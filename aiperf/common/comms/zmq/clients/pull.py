# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
import asyncio
import logging
from collections.abc import Callable, Coroutine
from typing import Any

import zmq.asyncio
from zmq import SocketType

from aiperf.common.comms.zmq.clients.base import BaseZMQClient
from aiperf.common.decorators import aiperf_task
from aiperf.common.exceptions import AIPerfError
from aiperf.common.models import BaseMessage, Message
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
            str, list[Callable[[Message], Coroutine[Any, Any, None]]]
        ] = {}

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
                # Receive data
                message_json = await self.socket.recv_string()

                # Parse JSON into a BaseMessage object
                message = BaseMessage.model_validate_json(message_json)
                topic = message.payload.message_type

                # Call callbacks with BaseMessage object
                if topic in self._pull_callbacks:
                    await call_all_functions(self._pull_callbacks[topic], message)

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

        logger.debug("Pull receiver task finished %s", self.client_id)

    async def pull(
        self,
        topic: str,
        callback: Callable[[Message], Coroutine[Any, Any, None]],
    ) -> None:
        """Register a ZMQ Pull data callback from a source (topic).

        Args:
            topic: Topic (source) to pull data from
            callback: function to call when data is received.

        Raises:
            CommunicationNotInitializedError: If the client is not initialized
            CommunicationPullError: If an exception occurred registering the pull callback
        """
        self._ensure_initialized()

        # Register callback
        if topic not in self._pull_callbacks:
            self._pull_callbacks[topic] = []
        self._pull_callbacks[topic].append(callback)
