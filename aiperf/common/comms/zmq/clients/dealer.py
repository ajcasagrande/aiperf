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
import os
import uuid
from collections.abc import Callable

import zmq.asyncio
from zmq import SocketType

from aiperf.common.comms.zmq.clients.base import BaseZMQClient
from aiperf.common.decorators import on_init


class DealerClient(BaseZMQClient):
    """A ZMQ Dealer client."""

    def __init__(
        self,
        context: zmq.asyncio.Context,
        address: str,
        callback: Callable,
        id: str | None = None,
        socket_ops: dict | None = None,
    ) -> None:
        """
        Initialize the ZMQ Dealer client.
        """
        super().__init__(context, SocketType.DEALER, address, False, socket_ops)
        # keep the id fairly short for smaller messages
        self.id = id or f"{os.getpid()}_{uuid.uuid4().hex[:8]}"
        self.callback = callback

    @on_init
    async def _on_init(self) -> None:
        """
        Initialize the ZMQ Dealer client's identity. Connection has already been made.
        """
        self.socket.setsockopt(zmq.IDENTITY, self.id.encode())

    async def run(self) -> None:
        """
        Process messages from the dealer in a loop.
        """
        # Only check that the socket is initialized once, and then use the
        # private _socket attribute directly to avoid extra checks.
        self._ensure_initialized()

        while not self.stop_event.is_set():
            try:
                # Receive message from broker
                message = await self._socket.recv_multipart()

                try:
                    # Process message using provided callback
                    result = await self.callback(message, self.id)
                except Exception as e:
                    self.logger.error(f"Error in worker {self.id}: {e}")
                    # Send error response
                    await self._socket.send_multipart(
                        [message[0], f"ERROR: {str(e)}".encode()]
                    )

                # Send response back through broker to client
                if result:
                    await self._socket.send_multipart(
                        result if isinstance(result, list) else [result]
                    )
                else:
                    # Send acknowledgment if no specific result
                    await self._socket.send_multipart([message[0], b"ACK"])

            except Exception as e:
                self.logger.error(f"Error in worker {self.id}: {e}")
                # continue the loop
