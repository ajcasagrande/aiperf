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
import asyncio
import logging
from collections.abc import Callable
from typing import Any

import zmq.asyncio
from zmq import SocketType

from aiperf.common.comms.zmq_comms.clients.base_zmq_client import BaseZMQClient
from aiperf.common.errors.base_error import Error
from aiperf.common.errors.comm_errors import CommNotInitializedError, CommPullError
from aiperf.common.models.message_models import BaseMessage

logger = logging.getLogger(__name__)


class ZMQPullClient(BaseZMQClient):
    def __init__(
        self,
        context: zmq.asyncio.Context,
        address: str,
        bind: bool,
        socket_ops: dict = None,
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
        self._pull_callbacks: dict[str, Any] = {}

    async def _initialize(self) -> None:
        # Start the receiver task
        asyncio.create_task(self._pull_receiver())
        logger.debug(f"Pull socket initialized and listening on {self.address}")

    async def _pull_receiver(self) -> None:
        """Background task for receiving data from the pull socket."""
        while not self._is_shutdown:
            if not self._is_initialized or not self.socket:
                # Not initialized yet, wait a bit and check again
                await asyncio.sleep(0.1)
                continue

            try:
                # Receive data
                message_bytes = await self.socket.recv()
                message_json = message_bytes.decode()

                # Parse JSON into a PushPullData object
                message = BaseMessage.model_validate_json(message_json)
                topic = message.payload.message_type

                # Call callbacks with PushPullData object
                if topic in self._pull_callbacks:
                    for callback in self._pull_callbacks[topic]:
                        try:
                            await callback(message)
                        except Exception as e:
                            logger.error(
                                f"Error in pull callback for topic {topic}: {e}"
                            )
                else:
                    logger.warning(f"No callbacks registered for pull topic {topic}")
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error receiving data from pull socket: {e}")
                await asyncio.sleep(0.1)

    async def pull(
        self,
        topic: str,
        callback: Callable[[BaseMessage], Error | None] | None = None,
    ) -> tuple[BaseMessage | None, Error | None]:
        """Pull data from a source.

        Args:
            topic: Topic to pull data from
            callback: Optional function to call when data is received.
                      If provided, this method will register the callback and return
                      a boolean. If not provided, this method will wait for and return
                      the next response.

        Returns:
            If callback is provided: tuple[None, Error | None].
            If callback is not provided: tuple[BaseMessage | None, Error | None].
        """
        if not self._is_initialized or self._is_shutdown:
            logger.error(
                "Cannot pull data: communication not initialized or already shut down"
            )
            return None, CommNotInitializedError()
        try:
            # If callback is provided, register it
            if callback:
                if topic not in self._pull_callbacks:
                    self._pull_callbacks[topic] = []
                self._pull_callbacks[topic].append(callback)
                logger.debug(f"Registered pull callback for {topic}")
                return None, None

            # If no callback, wait for response
            else:
                # Receive data
                message_bytes = await self.socket.recv()
                message_json = message_bytes.decode()

                message = BaseMessage.model_validate_json(message_json)
                return message, None
        except Exception as e:
            logger.error(f"Error pulling data from {topic}: {e}")
            return None, CommPullError.from_exception(e)
