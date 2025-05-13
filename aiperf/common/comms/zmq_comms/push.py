import logging

import zmq
from zmq import SocketType

from aiperf.common.models.push_pull import PushPullData

from .base import ZmqSocketBase

logger = logging.getLogger(__name__)


class ZmqPushSocket(ZmqSocketBase):
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

    async def push(self, data: PushPullData) -> bool:
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
            # Ensure source is set if not already
            if not data.source:
                data.source = self.client_id

            # Serialize data directly using Pydantic's built-in method
            data_json = data.model_dump_json()

            # Send data
            await self.socket.send_string(data_json)
            logger.debug(f"Pushed data")
            return True
        except Exception as e:
            logger.error(f"Error pushing data: {e} {type(e)}")
            return False
