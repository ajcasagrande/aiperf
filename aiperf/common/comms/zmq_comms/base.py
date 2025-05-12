import logging
import uuid

import zmq
from zmq import SocketType

logger = logging.getLogger(__name__)


class ZmqSocketBase:
    def __init__(
        self,
        context: zmq.Context,
        socket_type: SocketType,
        address: str,
        bind: bool,
        socket_ops: dict = None,
    ) -> None:
        """
        Initialize the ZMQ Base class.

        Args:
            context (zmq.Context): The ZMQ context.
            address (str): The address to bind or connect to.
            bind (bool): Whether to bind or connect the socket.
            socket_type (SocketType): The type of ZMQ socket (PUB or SUB).
            socket_ops (dict, optional): Additional socket options to set.
        """
        self._is_shutdown = False
        self._is_initialized = False
        self.context = context
        self.address = address
        self.bind = bind
        self.socket_type = socket_type
        self.socket = self.context.socket(socket_type)
        self.socket_ops = socket_ops or {}
        self.client_id = f"client_{uuid.uuid4().hex[:8]}"

    async def initialize(self) -> None:
        """Initialize the PubSub communication."""
        try:
            if self.bind:
                self.socket.bind(self.address)
            else:
                self.socket.connect(self.address)
            self.socket.setsockopt(zmq.RCVTIMEO, 30 * 1000)
            self.socket.setsockopt(zmq.SNDTIMEO, 30 * 1000)
            for k, v in self.socket_ops.items():
                self.socket.setsockopt(k, v)
            await self._initialize()
            self._is_initialized = True
            logger.info(
                f"ZMQ{self.socket_type} initialized and bound to {self.address}"
            )
        except Exception as e:
            logger.error(f"Error initializing ZMQ socket: {e}")
            raise

    async def shutdown(self) -> None:
        """Shutdown the PubSub communication."""
        try:
            self.socket.close()
            self._is_shutdown = True
            logger.info(f"ZMQ {self.socket_type} socket closed")
        except Exception as e:
            logger.error(f"Error shutting down ZMQ socket: {e}")
            raise

    async def _initialize(self) -> None:
        pass
