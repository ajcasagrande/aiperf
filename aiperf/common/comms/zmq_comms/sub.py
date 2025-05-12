import asyncio
import logging
from typing import Dict, List, Callable

import zmq
from zmq import SocketType

from aiperf.common.comms.zmq_comms.base import ZmqSocketBase
from aiperf.common.models.messages import BaseMessage

logger = logging.getLogger(__name__)


class ZmqSubscriber(ZmqSocketBase):
    def __init__(
        self, context: zmq.Context, address: str, bind: bool, socket_ops: dict = None
    ) -> None:
        """
        Initialize the ZMQ Subscriber class.

        Args:
            context (zmq.Context): The ZMQ context.
            address (str): The address to bind or connect to.
            bind (bool): Whether to bind or connect the socket.
            socket_ops (dict, optional): Additional socket options to set.
        """
        super().__init__(context, SocketType.SUB, address, bind, socket_ops)
        self._subscribers: Dict[str, List[Callable[[BaseMessage], None]]] = {}

    async def _initialize(self) -> None:
        asyncio.create_task(self._sub_receiver())

    async def subscribe(
        self, topic: str, callback: Callable[[BaseMessage], None]
    ) -> bool:
        """Subscribe to a topic.

        Args:
            topic: Topic to subscribe to
            callback: Function to call when a message is received (receives BaseMessage object)

        Returns:
            True if subscription was successful, False otherwise
        """
        if not self._is_initialized or self._is_shutdown:
            logger.error(
                "Cannot subscribe to topic: communication not initialized or already shut down"
            )
            return False

        try:
            # Subscribe to topic
            self.socket.subscribe(topic.encode())

            # Register callback
            if topic not in self._subscribers:
                self._subscribers[topic] = []
            self._subscribers[topic].append(callback)

            logger.info(f"Subscribed to topic: {topic}")
            return True
        except Exception as e:
            logger.error(f"Error subscribing to topic {topic}: {e}")
            return False

    async def _sub_receiver(self) -> None:
        """Background task for receiving messages from subscribed topics."""
        while not self._is_shutdown:
            if not self._is_initialized or not self.socket:
                # Not initialized yet, wait a bit and check again
                await asyncio.sleep(0.1)
                continue

            try:
                # Receive message
                (
                    topic_bytes,
                    message_bytes,
                ) = await self.socket.recv_multipart()
                topic = topic_bytes.decode()
                message_json = message_bytes.decode()
                message = BaseMessage.model_validate_json(message_json)

                # Call callbacks with the parsed message object
                if topic in self._subscribers:
                    for callback in self._subscribers[topic]:
                        try:
                            await callback(message)
                        except Exception as e:
                            logger.error(
                                f"Error in subscriber callback for topic {topic}: {e} {type(e)}"
                            )
            except asyncio.CancelledError:
                break
            except zmq.Again as e:
                # Handle ZMQ timeout or interruption
                logger.debug(
                    f"ZMQ recv timeout due to no messages. trying again @ {self.address}"
                )
                await asyncio.sleep(0.001)
            except Exception as e:
                logger.error(
                    f"Error receiving message from subscription: {e}, {type(e)}"
                )
                await asyncio.sleep(0.1)
