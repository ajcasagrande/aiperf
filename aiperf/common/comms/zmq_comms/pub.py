import logging

import zmq.asyncio
from zmq import SocketType

from .base import ZmqSocketBase
from aiperf.common.models.messages import BaseMessage

logger = logging.getLogger(__name__)


class ZmqPublisher(ZmqSocketBase):
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
        """Publish a message to a topic.

        Args:
            topic: Topic to publish to
            message: Message to publish (must be a Pydantic model)

        Returns:
            True if message was published successfully, False otherwise
        """
        if not self._is_initialized or self._is_shutdown:
            logger.error(
                "Cannot publish message: communication not initialized or already shut down"
            )
            return False

        try:
            # Serialize message using Pydantic's built-in method
            message_json = message.model_dump_json()

            # Publish message
            await self.socket.send_multipart([topic.encode(), message_json.encode()])
            return True
        except Exception as e:
            logger.error(f"Error publishing message to topic {topic}: {e}")
            return False
