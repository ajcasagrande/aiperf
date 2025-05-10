import asyncio
import uuid

import zmq
from zmq import SocketType

from aiperf.common.comms.zmq_comms.base import ZmqSocketBase
from aiperf.common.comms.zmq_comms.pub import logger
from aiperf.common.models.request_response import ResponseData, RequestData


class ZmqReqSocket(ZmqSocketBase):
    def __init__(
        self, context: zmq.Context, address: str, bind: bool, socket_ops: dict = None
    ) -> None:
        """
        Initialize the ZMQ Req class.

        Args:
            context (zmq.Context): The ZMQ context.
            address (str): The address to bind or connect to.
            bind (bool): Whether to bind or connect the socket.
            socket_ops (dict, optional): Additional socket options to set.
        """
        super().__init__(context, SocketType.REQ, address, bind, socket_ops)

    async def request(
        self,
        target: str,
        request_data: RequestData,
        timeout: float = 5.0,
    ) -> ResponseData | None:
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
                "Cannot send request: communication not initialized or already shut down"
            )
            return ResponseData(
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
                response = ResponseData.model_validate_json(response_json)
                return response

            except asyncio.TimeoutError:
                logger.error(
                    f"Timeout waiting for response to request {request_data.request_id}"
                )
                self._response_futures.pop(request_data.request_id, None)

                return ResponseData(
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

            return ResponseData(
                request_id=request_data.request_id,
                client_id=self.client_id,
                status="error",
                message=str(e),
            )
