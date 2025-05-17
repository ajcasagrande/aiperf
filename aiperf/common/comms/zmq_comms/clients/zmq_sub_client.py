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

import zmq.asyncio
from zmq import SocketType

from aiperf.common.comms.zmq_comms.clients.base_zmq_client import BaseZMQClient
from aiperf.common.exceptions.comm_exceptions import (
    CommunicationNotInitializedException,
    CommunicationSubscribeException,
)
from aiperf.common.models.message_models import BaseMessage

logger = logging.getLogger(__name__)


class ZMQSubClient(BaseZMQClient):
    def __init__(
        self,
        context: zmq.asyncio.Context,
        address: str,
        bind: bool,
        socket_ops: dict = None,
    ) -> None:
        """
        Initialize the ZMQ Subscriber class.

        Args:
            context (zmq.asyncio.Context): The ZMQ context.
            address (str): The address to bind or connect to.
            bind (bool): Whether to bind or connect the socket.
            socket_ops (dict, optional): Additional socket options to set.
        """
        super().__init__(context, SocketType.SUB, address, bind, socket_ops)
        self._subscribers: dict[str, list[Callable[[BaseMessage], None]]] = {}

    async def _initialize(self) -> None:
        asyncio.create_task(self._sub_receiver())
        return None

    async def subscribe(
        self, topic: str, callback: Callable[[BaseMessage], None]
    ) -> None:
        """Subscribe to a topic.

        Args:
            topic: Topic to subscribe to
            callback: Function to call when a response is received
            (receives BaseMessage object)

        Raises:
            Exception if subscription was not successful, None otherwise
        """
        if not self._is_initialized or self._is_shutdown:
            logger.error(
                "Cannot subscribe to topic: communication not initialized or already shut down"
            )
            raise CommunicationNotInitializedException()

        try:
            # Subscribe to topic
            self.socket.subscribe(topic.encode())

            # Register callback
            if topic not in self._subscribers:
                self._subscribers[topic] = []
            self._subscribers[topic].append(callback)

            logger.debug("Subscribed to topic: %s", topic)

        except Exception as e:
            logger.error("Exception subscribing to topic %s: %s", topic, e)
            raise CommunicationSubscribeException from e

        return None

    async def _sub_receiver(self) -> None:
        """Background task for receiving messages from subscribed topics."""
        while not self._is_shutdown:
            if not self._is_initialized or not self.socket:
                # Not initialized yet, wait a bit and check again
                await asyncio.sleep(0.1)
                continue

            try:
                # Receive response
                (
                    topic_bytes,
                    message_bytes,
                ) = await self.socket.recv_multipart()
                topic = topic_bytes.decode()
                message_json = message_bytes.decode()
                logger.debug(
                    "Client %s received message from topic: '%s', message: %s",
                    self.client_id,
                    topic,
                    message_json,
                )

                message = BaseMessage.model_validate_json(message_json)

                # Call callbacks with the parsed response object
                if topic in self._subscribers:
                    for callback in self._subscribers[topic]:
                        try:
                            await callback(message)
                        except Exception as e:
                            logger.exception(
                                "Exception in subscriber callback for topic %s: %s %s",
                                topic,
                                e,
                                type(e),
                            )
            except asyncio.CancelledError:
                break
            except zmq.Again:
                # Handle ZMQ timeout or interruption
                logger.debug(
                    "ZMQ recv timeout due to no messages. trying again @ %s",
                    self.address,
                )
                await asyncio.sleep(0.001)
            except Exception as e:
                logger.error(
                    "Exception receiving response from subscription: %s, %s",
                    e,
                    type(e),
                )
                await asyncio.sleep(0.1)
