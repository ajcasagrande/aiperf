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

import zmq.asyncio
from zmq import SocketType

from aiperf.common.models.messages import BaseMessage
from aiperf.common.comms.zmq_comms.clients.base import BaseZMQClient

logger = logging.getLogger(__name__)


class ZMQPubClient(BaseZMQClient):
    def __init__(
        self, context: zmq.Context, address: str, bind: bool, socket_ops: dict = None
    ) -> None:
        """
        Initialize the ZMQ Publisher class.

        Args:
            context (zmq.Context): The ZMQ context.
            address (str): The address to bind or connect to.
            bind (bool): Whether to bind or connect the socket.
            socket_ops (dict, optional): Additional socket options to set.
        """
        super().__init__(context, SocketType.PUB, address, bind, socket_ops)

    async def publish(self, topic: str, message: BaseMessage) -> bool:
        """Publish a response to a topic.

        Args:
            topic: Topic to publish to
            message: Message to publish (must be a Pydantic model)

        Returns:
            True if response was published successfully, False otherwise
        """
        if not self._is_initialized or self._is_shutdown:
            logger.error(
                "Cannot publish response: communication not initialized or already shut down"
            )
            return False

        try:
            # Serialize response using Pydantic's built-in method
            message_json = message.model_dump_json()

            # Publish response
            await self.socket.send_multipart([topic.encode(), message_json.encode()])
            return True
        except Exception as e:
            logger.error(f"Error publishing response to topic {topic}: {e}")
            return False
