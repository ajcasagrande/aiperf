# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
import logging
import uuid

import zmq.asyncio

from aiperf.common.comms.zmq.zmq_defaults import ZMQSocketDefaults
from aiperf.common.exceptions import (
    InitializationError,
    NotInitializedError,
)
from aiperf.common.hooks import (
    on_start,
    on_stop,
)
from aiperf.common.lifecycle_mixins import (
    AIPerfTaskLifecycleMixin,
)

################################################################################
# Base ZMQ Client Class
################################################################################


class BaseZMQClient(AIPerfTaskLifecycleMixin):
    """Base class for all ZMQ clients. It can be used as-is to create a new ZMQ client,
    or it can be subclassed to create specific ZMQ client functionality.

    It inherits from the :class:`AIPerfLifecycleMixin`, allowing derived
    classes to implement specific hooks.
    """

    def __init__(
        self,
        context: zmq.asyncio.Context,
        socket_type: zmq.SocketType,
        address: str,
        bind: bool,
        socket_ops: dict | None = None,
        client_id: str | None = None,
    ) -> None:
        """
        Initialize the ZMQ Base class.

        Args:
            context (zmq.asyncio.Context): The ZMQ context.
            address (str): The address to bind or connect to.
            bind (bool): Whether to BIND or CONNECT the socket.
            socket_type (SocketType): The type of ZMQ socket (eg. PUB, SUB, ROUTER, DEALER, etc.).
            socket_ops (dict, optional): Additional socket options to set.
        """
        self.context: zmq.asyncio.Context = context
        self.address: str = address
        self.bind: bool = bind
        self.socket_type: zmq.SocketType = socket_type
        self._socket: zmq.asyncio.Socket | None = None
        self.socket_ops: dict = socket_ops or {}
        self.client_id: str = (
            client_id
            or f"{self.socket_type.name.lower()}_client_{uuid.uuid4().hex[:8]}"
        )
        super().__init__()
        # Set the logger after the super init to override the name
        self.logger = logging.getLogger(self.client_id)

    @property
    def socket_type_name(self) -> str:
        """Get the name of the socket type."""
        return self.socket_type.name

    @property
    def socket(self) -> zmq.asyncio.Socket:
        """Get the zmq socket for the client.

        Raises:
            NotInitializedError: If the client is not initialized
        """
        if not self._socket:
            raise NotInitializedError(
                "Communication channels are not initialized",
            )
        return self._socket

    @on_start
    async def _start_client(self) -> None:
        """Create the zmq socket, bind or connect it to the address, and set the socket options."""

        try:
            self._socket = self.context.socket(self.socket_type)
            if self.bind:
                self.logger.debug(
                    "ZMQ %s socket initialized, try BIND to %s (%s)",
                    self.socket_type_name,
                    self.address,
                    self.client_id,
                )
                self._socket.bind(self.address)
            else:
                self.logger.debug(
                    "ZMQ %s socket initialized, try CONNECT to %s (%s)",
                    self.socket_type_name,
                    self.address,
                    self.client_id,
                )
                self._socket.connect(self.address)

            # Set default timeouts
            self._socket.setsockopt(zmq.RCVTIMEO, ZMQSocketDefaults.RCVTIMEO)
            self._socket.setsockopt(zmq.SNDTIMEO, ZMQSocketDefaults.SNDTIMEO)

            # Set performance-oriented socket options
            self._socket.setsockopt(zmq.TCP_KEEPALIVE, ZMQSocketDefaults.TCP_KEEPALIVE)
            self._socket.setsockopt(
                zmq.TCP_KEEPALIVE_IDLE, ZMQSocketDefaults.TCP_KEEPALIVE_IDLE
            )
            self._socket.setsockopt(
                zmq.TCP_KEEPALIVE_INTVL, ZMQSocketDefaults.TCP_KEEPALIVE_INTVL
            )
            self._socket.setsockopt(
                zmq.TCP_KEEPALIVE_CNT, ZMQSocketDefaults.TCP_KEEPALIVE_CNT
            )
            self._socket.setsockopt(zmq.IMMEDIATE, ZMQSocketDefaults.IMMEDIATE)
            self._socket.setsockopt(zmq.LINGER, ZMQSocketDefaults.LINGER)

            # Set additional socket options requested by the caller
            for key, val in self.socket_ops.items():
                self._socket.setsockopt(key, val)

            self.logger.debug(
                "ZMQ %s socket %s to %s (%s)",
                self.socket_type_name,
                "BOUND" if self.bind else "CONNECTED",
                self.address,
                self.client_id,
            )

        except Exception as e:
            raise InitializationError(
                f"Failed to initialize ZMQ socket: {e}",
            ) from e

    @on_stop
    async def _close_socket(self) -> None:
        """Close the ZMQ socket"""
        if not self._socket:
            return

        self._socket.close()
        self._socket = None
