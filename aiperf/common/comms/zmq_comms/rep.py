import asyncio

import zmq
from zmq import SocketType

from aiperf.common.comms.zmq_comms.base import ZmqSocketBase
from aiperf.common.comms.zmq_comms.pub import logger
from aiperf.common.models.request_response import (
    RequestData,
    ResponseData,
)


class ZmqRepSocket(ZmqSocketBase):
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

    async def _initialize(self) -> None:
        # Start the receiver task
        asyncio.create_task(self._rep_receiver())
        logger.info(f"REP socket initialized and listening on {self.address}")

    async def respond(self, target: str, response: ResponseData) -> bool:
        """Send a response to a request.

        Args:
            target: Target component to send response to
            response: Response message (must be a ResponseData instance)

        Returns:
            True if response was sent successfully, False otherwise
        """
        if not self._is_initialized or self._is_shutdown:
            logger.error(
                "Cannot send response: communication not initialized or already shut down"
            )
            return False

        try:
            # Serialize response using Pydantic's built-in method
            response_json = response.model_dump_json()

            # Send response
            await self.socket.send_string(response_json)
            return True
        except Exception as e:
            logger.error(f"Error sending response to {target}: {e}")
            return False

    async def _rep_receiver(self) -> None:
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
                request = RequestData.from_json(request_json)
                request_id = request.request_id

                # Store request data
                self._response_data[request_id] = request

                # Resolve future if it exists
                if request_id in self._response_futures:
                    future = self._response_futures[request_id]
                    if not future.done():
                        future.set_result(request_json)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error receiving request: {e}")
                await asyncio.sleep(0.1)
