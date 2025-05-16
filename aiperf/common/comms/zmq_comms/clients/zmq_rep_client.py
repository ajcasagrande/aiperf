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
import contextlib
import logging

import zmq
from zmq import SocketType

from aiperf.common.comms.zmq_comms.clients.base_zmq_client import BaseZMQClient
from aiperf.common.errors.base_error import Error
from aiperf.common.errors.comm_errors import CommNotInitializedError, CommRepError
from aiperf.common.models.message_models import BaseMessage

logger = logging.getLogger(__name__)


class ZMQRepClient(BaseZMQClient):
    def __init__(
        self, context: zmq.Context, address: str, bind: bool, socket_ops: dict = None
    ) -> None:
        """
        Initialize the ZMQ REP class.

        Args:
            context (zmq.Context): The ZMQ context.
            address (str): The address to bind or connect to.
            bind (bool): Whether to bind or connect the socket.
            socket_ops (dict, optional): Additional socket options to set.
        """
        super().__init__(context, SocketType.REP, address, bind, socket_ops)

        self._response_futures = {}
        self._response_data = {}
        self._receiver_task = None

    async def initialize(self) -> Error | None:
        """Initialize the socket and start the receiver task.

        Returns:
            Error if initialization was not successful, None otherwise
        """
        if err := await super().initialize():
            return err

        if err := await self._initialize():
            return err

        return None

    async def _initialize(self) -> Error | None:
        # Start the receiver task
        self._receiver_task = asyncio.create_task(self._rep_receiver())
        logger.debug(f"REP socket initialized and listening on {self.address}")
        return None

    async def shutdown(self) -> Error | None:
        """Shutdown the socket and clean up resources."""
        if self._receiver_task and not self._receiver_task.done():
            self._receiver_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._receiver_task

        # Resolve any pending futures with errors
        for _, future in self._response_futures.items():
            if not future.done():
                future.set_exception(ConnectionError("Socket was shut down"))

        self._response_futures.clear()
        self._response_data.clear()

        return await super().shutdown()

    async def wait_for_request(
        self, timeout: float = None
    ) -> tuple[BaseMessage | None, Error | None]:
        """Wait for a request to arrive.

        Args:
            timeout: Timeout in seconds or None for no timeout

        Returns:
            Tuple containing request message or None if timeout occurred and Error or None
        """
        if not self._is_initialized or self._is_shutdown:
            logger.error(
                "Cannot wait for request: communication not initialized or already "
                "shut down"
            )
            return None, CommNotInitializedError()

        try:
            # Create a future for the next request
            request_id = "next_request"  # Special ID for the next request
            future = asyncio.Future()
            self._response_futures[request_id] = future

            try:
                # Wait for the request with optional timeout
                if timeout is not None:
                    request_json = await asyncio.wait_for(future, timeout)
                else:
                    request_json = await future

                # Parse the request
                request = BaseMessage.model_validate_json(request_json)
                return request, None

            except asyncio.TimeoutError:
                logger.debug("Timeout waiting for request")
                return None, CommRepError.from_exception(asyncio.TimeoutError())

            finally:
                # Clean up future
                self._response_futures.pop(request_id, None)

        except Exception as e:
            logger.error(f"Error waiting for request: {e}")
            return None, CommRepError.from_exception(e)

    async def respond(self, target: str, response: BaseMessage) -> Error | None:
        """Send a response to a request.

        Args:
            target: Target component to send response to
            response: Response message (must be a BaseMessage instance)

        Returns:
            Error if response was not sent successfully, None otherwise
        """
        if not self._is_initialized or self._is_shutdown:
            logger.error(
                "Cannot send response: communication not initialized or already "
                "shut down"
            )
            return CommNotInitializedError()

        try:
            # Serialize response using Pydantic's built-in method
            response_json = response.model_dump_json()

            # Send response
            await self.socket.send_string(response_json)
            return None
        except Exception as e:
            logger.error(f"Error sending response to {target}: {e}")
            return CommRepError.from_exception(e)

    async def _rep_receiver(self) -> Error | None:
        """Background task for receiving requests and sending responses."""
        while not self._is_shutdown:
            if not self._is_initialized or not self.socket:
                # Not initialized yet, wait a bit and check again
                await asyncio.sleep(0.1)
                continue

            try:
                # Receive request
                request_json = await self.socket.recv_string()

                # Parse JSON to create RequestData object
                request = BaseMessage.model_validate_json(request_json)
                request_id = request.request_id

                # Store request data
                self._response_data[request_id] = request

                # Check for special "next_request" future
                if "next_request" in self._response_futures:
                    future = self._response_futures.pop("next_request")
                    if not future.done():
                        future.set_result(request_json)
                # Resolve future if it exists for the specific request ID
                elif request_id in self._response_futures:
                    future = self._response_futures[request_id]
                    if not future.done():
                        future.set_result(request_json)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error receiving request: {e}")
                await asyncio.sleep(0.1)

        return None
