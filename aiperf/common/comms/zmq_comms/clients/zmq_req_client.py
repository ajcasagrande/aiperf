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
import uuid

import zmq.asyncio
from zmq import SocketType

from aiperf.common.comms.zmq_comms.clients.base_zmq_client import BaseZMQClient
from aiperf.common.errors.comm_errors import CommReqError
from aiperf.common.models.message_models import BaseMessage
from aiperf.common.models.payload_models import ErrorPayload

logger = logging.getLogger(__name__)


class ZMQReqClient(BaseZMQClient):
    def __init__(
        self,
        context: zmq.asyncio.Context,
        address: str,
        bind: bool,
        socket_ops: dict = None,
    ) -> None:
        """
        Initialize the ZMQ Req class.

        Args:
            context (zmq.asyncio.Context): The ZMQ context.
            address (str): The address to bind or connect to.
            bind (bool): Whether to bind or connect the socket.
            socket_ops (dict, optional): Additional socket options to set.
        """
        super().__init__(context, SocketType.REQ, address, bind, socket_ops)
        self._response_futures = {}
        self.client_id = uuid.uuid4().hex

    async def initialize(self) -> None:
        """Initialize the socket and start processing messages."""
        if err := await super().initialize():
            return err

        self._background_task = asyncio.create_task(self._process_messages())
        return None

    async def _process_messages(self) -> None:
        """Process incoming response messages in the background."""
        while not self._is_shutdown:
            try:
                if self.socket and not self._is_shutdown:
                    response_json = await self.socket.recv_string()
                    await self._handle_response(response_json)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error processing messages: {e}")
                await asyncio.sleep(0.1)

        return None

    async def _handle_response(self, response_json: str) -> None:
        """Handle a response response.

        Args:
            response_json: The JSON response string
        """
        try:
            response = BaseMessage.model_validate_json(response_json)
            request_id = response.request_id

            if request_id in self._response_futures:
                future = self._response_futures[request_id]
                if not future.done():
                    future.set_result(response_json)
            else:
                logger.warning(
                    f"Received response for unknown request ID: {request_id}"
                )
        except Exception as e:
            logger.error(f"Error handling response: {e}")
            return CommReqError.from_exception(e)

        return None

    async def shutdown(self) -> None:
        """Shutdown the socket and clean up resources."""
        if self._background_task and not self._background_task.done():
            self._background_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._background_task

        # Resolve any pending futures with errors
        for request_id, future in self._response_futures.items():
            if not future.done():
                error_response = BaseMessage(
                    request_id=request_id,
                    payload=ErrorPayload(
                        error_message="Socket was shut down",
                    ),
                )
                future.set_result(error_response.model_dump_json())

        self._response_futures.clear()

        return await super().shutdown()

    async def request(
        self,
        target: str,
        request_data: BaseMessage,
        timeout: float = 5.0,
    ) -> BaseMessage:
        """Send a request and wait for a response.

        Args:
            target: Target component to send request to
            request_data: Request data (must be a RequestData instance)
            timeout: Timeout in seconds

        Returns:
            ResponseData object
        """
        if not self._is_initialized or self._is_shutdown:
            logger.error(
                "Cannot send request: communication not initialized or already "
                "shut down"
            )
            return BaseMessage(
                request_id="error",
                client_id=self.client_id,
                status="error",
                message="Communication not initialized or already shut down",
            )

        try:
            # Set target if not already set
            if not request_data.target:
                request_data.target = target

            # Ensure client_id is set
            if not request_data.client_id:
                request_data.client_id = self.client_id

            # Generate request ID if not provided
            if not request_data.request_id:
                request_data.request_id = uuid.uuid4().hex

            # Serialize request
            request_json = request_data.model_dump_json()

            # Create future for response
            future = asyncio.Future()
            self._response_futures[request_data.request_id] = future

            # Send request
            await self.socket.send_string(request_json)

            # Wait for response with timeout
            try:
                response_json = await asyncio.wait_for(future, timeout)
                response = BaseMessage.model_validate_json(response_json)
                return response

            except asyncio.TimeoutError:
                logger.error(
                    f"Timeout waiting for response to request {request_data.request_id}"
                )
                self._response_futures.pop(request_data.request_id, None)

                return BaseMessage(
                    request_id=request_data.request_id,
                    client_id=self.client_id,
                    status="error",
                    message="Request timed out",
                )
            finally:
                # Clean up future
                self._response_futures.pop(request_data.request_id, None)
        except Exception as e:
            logger.error(f"Error sending request to {target}: {e}")

            return BaseMessage(
                request_id=request_data.request_id
                if hasattr(request_data, "request_id")
                else "error",
                client_id=self.client_id,
                status="error",
                message=str(e),
            )
