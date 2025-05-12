import asyncio
from typing import Dict, Callable, Optional, Union, Any

import zmq
from zmq import SocketType

from aiperf.common.comms.zmq_comms.base import ZmqSocketBase
from aiperf.common.comms.zmq_comms.pub import logger
from aiperf.common.models.push_pull import PushPullData


class ZmqPullSocket(ZmqSocketBase):
    def __init__(
        self, context: zmq.Context, address: str, bind: bool, socket_ops: dict = None
    ) -> None:
        """
        Initialize the ZMQ Puller class.

        Args:
            context (zmq.Context): The ZMQ context.
            address (str): The address to bind or connect to.
            bind (bool): Whether to bind or connect the socket.
            socket_ops (dict, optional): Additional socket options to set.
        """
        super().__init__(context, SocketType.PULL, address, bind, socket_ops)
        self._pull_callbacks: Dict[str, Any] = {}

    async def _initialize(self) -> None:
        # Start the receiver task
        asyncio.create_task(self._pull_receiver())
        logger.info(f"Pull socket initialized and listening on {self.address}")

    async def _pull_receiver(self) -> None:
        """Background task for receiving data from the pull socket."""
        while not self._is_shutdown:
            if not self._is_initialized or not self.socket:
                # Not initialized yet, wait a bit and check again
                await asyncio.sleep(0.1)
                continue

            try:
                # Receive data
                message_bytes = await self.socket.recv()
                message_json = message_bytes.decode()

                # Parse JSON into a PushPullData object
                pull_data = PushPullData.model_validate_json(message_json)
                topic = pull_data.topic

                # Call callbacks with PushPullData object
                if topic in self._pull_callbacks:
                    for callback in self._pull_callbacks[topic]:
                        try:
                            await callback(pull_data)
                        except Exception as e:
                            logger.error(
                                f"Error in pull callback for topic {topic}: {e}"
                            )
                else:
                    logger.warning(f"No callbacks registered for pull topic {topic}")
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error receiving data from pull socket: {e}")
                await asyncio.sleep(0.1)

    async def pull(
        self,
        topic: str,
        callback: Optional[Callable[[PushPullData], None]] = None,
    ) -> Union[PushPullData, bool, None]:
        """Pull data from a source.

        Args:
            topic: Topic to pull data from
            callback: Optional function to call when data is received.
                     If provided, this method will register the callback and return a boolean.
                     If not provided, this method will wait for and return the next message.

        Returns:
            If callback is provided: True if pull registration was successful, False otherwise
            If callback is not provided: The received PushPullData object
        """
        if not self._is_initialized or self._is_shutdown:
            logger.error(
                "Cannot pull data: communication not initialized or already shut down"
            )
            return None
        try:
            # If callback is provided, register it
            if callback:
                if topic not in self._pull_callbacks:
                    self._pull_callbacks[topic] = []
                self._pull_callbacks[topic].append(callback)
                logger.debug(f"Registered pull callback for {topic}")
                return True

            # If no callback, wait for message
            else:
                # Receive data
                message_bytes = await self.socket.recv()
                message_json = message_bytes.decode()

                pull_data = PushPullData.from_json(message_json)
                return pull_data
        except Exception as e:
            logger.error(f"Error pulling data from {topic}: {e}")
            return None
