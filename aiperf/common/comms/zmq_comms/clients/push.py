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

import zmq
from zmq import SocketType

from aiperf.common.comms.zmq_comms.clients.base import BaseZMQClient
from aiperf.common.models.messages import BaseMessage

logger = logging.getLogger(__name__)


class ZMQPushClient(BaseZMQClient):
    def __init__(
        self, context: zmq.Context, address: str, bind: bool, socket_ops: dict = None
    ) -> None:
        """
        Initialize the ZMQ Pusher class.

        Args:
            context (zmq.Context): The ZMQ context.
            address (str): The address to bind or connect to.
            bind (bool): Whether to bind or connect the socket.
            socket_ops (dict, optional): Additional socket options to set.
        """
        super().__init__(context, SocketType.PUSH, address, bind, socket_ops)

    async def push(self, message: BaseMessage) -> bool:
        """Push data to a target.

        Args:
            data: Data to be pushed (must be a PushData instance)

        Returns:
            True if data was pushed successfully, False otherwise
        """
        if not self._is_initialized or self._is_shutdown:
            logger.error(
                "Cannot push data: communication not initialized or already shut down"
            )
            return False

        try:
            # Serialize data directly using Pydantic's built-in method
            data_json = message.model_dump_json()

            # Send data
            await self.socket.send_string(data_json)
            logger.debug("Pushed data")
            return True
        except Exception as e:
            logger.error(f"Error pushing data: {e} {type(e)}")
            return False
