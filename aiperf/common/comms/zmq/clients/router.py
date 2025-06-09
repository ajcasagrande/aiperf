#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0

import os
import uuid

import zmq.asyncio
from zmq import SocketType

from aiperf.common.comms.zmq.clients.base import BaseZMQClient
from aiperf.common.hooks import on_init
from aiperf.common.messages import Message


class ZMQRouterClient(BaseZMQClient):
    """A ZMQ Router client."""

    def __init__(
        self,
        context: zmq.asyncio.Context,
        address: str,
        bind: bool = False,
        id: str | None = None,
        socket_ops: dict | None = None,
    ) -> None:
        """
        Initialize the ZMQ Router client.
        """
        super().__init__(context, SocketType.ROUTER, address, bind, socket_ops)
        # keep the id fairly short for smaller messages
        self.id = id or f"{os.getpid()}_{uuid.uuid4().hex[:8]}"

    @on_init
    async def _on_init(self) -> None:
        """
        Initialize the ZMQ Router client's identity. Connection has already been made.
        """
        self.socket.setsockopt(zmq.IDENTITY, self.id.encode())

    async def send_message(self, message: Message) -> Message:
        """Send a message to a worker and await response.

        Args:
            message: The message to send

        Returns:
            The response from the worker
        """

        # Convert to JSON and send
        data = message.model_dump_json()
        self.logger.info(f"Sending message: {message}")
        await self.socket.send_string(data)
        # self.logger.info(f"Waiting for response: {message}")
        # # Wait for response
        # response = await self.socket.recv_string()
        # response_data = json.loads(response.decode("utf-8"))
        # self.logger.info(f"Received response: {response_data}")
        return None
        # return response_data
