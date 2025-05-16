#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#  http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
import logging
import uuid
from abc import ABC, abstractmethod

import zmq.asyncio
from zmq import SocketType

from aiperf.common.errors import Error
from aiperf.common.errors.comm_errors import CommInitializationError, CommShutdownError

logger = logging.getLogger(__name__)


class BaseZMQClient(ABC):
    def __init__(
        self,
        context: zmq.asyncio.Context,
        socket_type: SocketType,
        address: str,
        bind: bool,
        socket_ops: dict | None = None,
    ) -> None:
        """
        Initialize the ZMQ Base class.

        Args:
            context (zmq.asyncio.Context): The ZMQ context.
            address (str): The address to bind or connect to.
            bind (bool): Whether to bind or connect the socket.
            socket_type (SocketType): The type of ZMQ socket (PUB or SUB).
            socket_ops (dict, optional): Additional socket options to set.
        """
        self._is_shutdown: bool = False
        self._is_initialized: bool = False
        self.context: zmq.asyncio.Context = context
        self.address: str = address
        self.bind: bool = bind
        self.socket_type: SocketType = socket_type
        self.socket: zmq.asyncio.Socket | None = None
        self.socket_ops: dict = socket_ops or {}
        self.client_id: str = f"client_{uuid.uuid4().hex[:8]}"

    @property
    def socket_type_name(self) -> str:
        """Get the name of the socket type."""
        return self.socket_type.name

    async def initialize(self) -> Error | None:
        """Initialize the communication."""
        try:
            self.socket = self.context.socket(self.socket_type)
            if self.bind:
                logger.debug(
                    f"Binding ZMQ {self.socket_type_name} socket to {self.address}"
                )
                self.socket.bind(self.address)
            else:
                logger.debug(
                    f"Connecting ZMQ {self.socket_type_name} socket to {self.address}"
                )
                self.socket.connect(self.address)

            # Set safe timeouts for send and receive operations
            self.socket.setsockopt(zmq.RCVTIMEO, 30 * 1000)
            self.socket.setsockopt(zmq.SNDTIMEO, 30 * 1000)

            # Set additional socket options requested by the caller
            for key, val in self.socket_ops.items():
                self.socket.setsockopt(key, val)

            if init_err := await self._initialize():
                return init_err

            self._is_initialized = True
            logger.debug(
                "ZMQ %s socket initialized and connected to %s",
                self.socket_type_name,
                self.address,
            )
            return None
        except Exception as e:
            logger.error("Error initializing ZMQ socket: %s", e)
            return CommInitializationError.from_exception(e)

    async def shutdown(self) -> Error | None:
        """Shutdown the communication."""
        try:
            self.socket.close()
            logger.debug("ZMQ %s socket closed", self.socket_type_name)

        except Exception as e:
            logger.error("Error shutting down ZMQ socket: %s", e)
            return CommShutdownError.from_exception(e)

        finally:
            self._is_shutdown = True

    @abstractmethod
    async def _initialize(self) -> Error | None:
        """Override in subclass to implement custom initialization logic.

        This method is called after the socket is bound or connected.
        """
        pass
