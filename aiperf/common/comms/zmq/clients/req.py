# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
import logging
import uuid

import zmq.asyncio

from aiperf.common.comms.zmq.clients.base import BaseZMQClient
from aiperf.common.exceptions import CommunicationRequestError
from aiperf.common.models.messages import (
    Message,
)

logger = logging.getLogger(__name__)


class ZMQReqClient(BaseZMQClient):
    def __init__(
        self,
        context: zmq.asyncio.Context,
        address: str,
        bind: bool,
        socket_ops: dict | None = None,
    ) -> None:
        """
        Initialize the ZMQ Req class.

        Args:
            context (zmq.asyncio.Context): The ZMQ context.
            address (str): The address to bind or connect to.
            bind (bool): Whether to bind or connect the socket.
            socket_ops (dict, optional): Additional socket options to set.
        """
        super().__init__(context, zmq.SocketType.DEALER, address, bind, socket_ops)

    async def _reset_socket(self) -> None:
        """Reset the socket to recover from inconsistent state.

        This is necessary when a REQ socket gets stuck after a failed request/response cycle.
        """
        logger.warning(
            "Resetting REQ socket due to inconsistent state (%s)", self.client_id
        )

        if self._socket:
            self._socket.close()

        # Recreate socket
        self._socket = self.context.socket(self.socket_type)

        if self.bind:
            self.socket.bind(self.address)
        else:
            self.socket.connect(self.address)

        # Set additional socket options requested by the caller
        for key, val in self.socket_ops.items():
            self._socket.setsockopt(key, val)

    async def request(
        self,
        request_data: Message,
    ) -> Message:
        """Send a request and wait for a response.

        Args:
            request_data: Request data (must be a RequestData instance)

        Returns:
            ResponseData object
        """
        self._ensure_initialized()

        # Generate request ID if not provided
        if not request_data.request_id:
            request_data.request_id = uuid.uuid4().hex

        # Serialize request
        request_json = request_data.model_dump_json()

        try:
            # Send request
            await self._socket.send_string(request_json)

            # Wait for response with timeout
            response_json = await self._socket.recv_string()
            response = Message.from_json(response_json)
            return response
        except Exception as e:
            raise CommunicationRequestError(
                f"Exception sending request: {e.__class__.__name__} {e}"
            ) from e
