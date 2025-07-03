# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
import asyncio
import logging
import uuid

# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
from abc import ABC, abstractmethod
from collections.abc import Callable, Coroutine
from typing import Any, TypeVar

import zmq.asyncio

from aiperf.common.constants import TASK_CANCEL_TIMEOUT_SHORT
from aiperf.common.enums import MessageType
from aiperf.common.exceptions import (
    AIPerfError,
    CommunicationError,
    CommunicationErrorReason,
)
from aiperf.common.hooks import (
    AIPerfHook,
    AIPerfTaskHook,
    AIPerfTaskMixin,
    supports_hooks,
)
from aiperf.common.messages import Message

logger = logging.getLogger(__name__)


################################################################################
# Base ZMQ Client Interfaces
################################################################################

MessageT = TypeVar("MessageT", bound=Message)
MessageOutputT = TypeVar("MessageOutputT", bound=Message)


class BaseCommunicationClient(ABC):
    """Base class for specifying the base communication client for AIPerf components."""

    @abstractmethod
    async def initialize(self) -> None:
        """Initialize communication channels."""
        pass

    @abstractmethod
    async def shutdown(self) -> None:
        """Shutdown communication channels."""
        pass


class PushClient(BaseCommunicationClient):
    """Interface for push clients."""

    @abstractmethod
    async def push(self, message: Message) -> None:
        """Push data to a target. The message will be routed automatically
        based on the message type.

        Args:
            message_type: MessageType to push to
            message: Message to be pushed
        """
        pass


class PullClient(BaseCommunicationClient):
    """Interface for pull clients."""

    @abstractmethod
    async def register_pull_callback(
        self,
        message_type: MessageType,
        callback: Callable[[MessageT], Coroutine[Any, Any, None]],
        max_concurrency: int | None = None,
    ) -> None:
        """Register a callback for a pull client. The callback will be called when
        a message is received for the given message type.

        Args:
            message_type: The message type to register the callback for
            callback: The callback to register
            max_concurrency: The maximum number of concurrent requests to allow.
        """
        pass


class ReqClient(BaseCommunicationClient):
    """Interface for request clients."""

    # TODO: Should this accept a target service type for routing?
    @abstractmethod
    async def request(
        self,
        message: MessageT,
        timeout: float = 10,
    ) -> MessageOutputT:
        """Send a request and wait for a response. The message will be routed automatically
        based on the message type.

        Args:
            message: Message to send (will be routed based on the message type)
            timeout: Timeout in seconds for the request.

        Returns:
            Response message if successful
        """
        pass

    @abstractmethod
    async def request_async(
        self,
        message: MessageT,
        callback: Callable[[MessageOutputT], Coroutine[Any, Any, None]],
    ) -> None:
        """Send a request and be notified when the response is received. The message will be routed automatically
        based on the message type.

        Args:
            message: Message to send (will be routed based on the message type)
            callback: Callback to be called when the response is received
        """
        pass


class RepClient(BaseCommunicationClient):
    """Interface for reply clients."""

    @abstractmethod
    def register_request_handler(
        self,
        service_id: str,
        message_type: MessageType,
        handler: Callable[[MessageT], Coroutine[Any, Any, MessageOutputT | None]],
    ) -> None:
        """Register a request handler for a message type. The handler will be called when
        a request is received for the given message type.

        Args:
            service_id: The service ID to register the handler for
            message_type: The message type to register the handler for
            handler: The handler to register
        """
        pass


class SubClient(BaseCommunicationClient):
    """Interface for subscribe clients."""

    @abstractmethod
    async def subscribe(
        self,
        message_type: MessageType,
        callback: Callable[[MessageT], Coroutine[Any, Any, None]],
    ) -> None:
        """Subscribe to a specific message type. The callback will be called when
        a message is received for the given message type."""
        pass


class PubClient(BaseCommunicationClient):
    """Interface for publish clients."""

    @abstractmethod
    async def publish(self, message: Message) -> None:
        """Publish a message. The message will be routed automatically based on the message type."""
        pass


################################################################################
# Base ZMQ Client Class
################################################################################


@supports_hooks(
    AIPerfHook.ON_INIT,
    AIPerfHook.ON_STOP,
    AIPerfHook.ON_CLEANUP,
    AIPerfTaskHook.AIPERF_TASK,
)
class BaseZMQClient(AIPerfTaskMixin, BaseCommunicationClient):
    """Base class for all ZMQ clients. It can be used as-is to create a new ZMQ client,
    or it can be subclassed to create specific ZMQ client functionality.

    It inherits from the :class:`AIPerfTaskMixin`, allowing derived
    classes to implement specific hooks.
    """

    def __init__(
        self,
        context: zmq.asyncio.Context,
        socket_type: zmq.SocketType,
        address: str,
        bind: bool,
        socket_ops: dict | None = None,
    ) -> None:
        """
        Initialize the ZMQ Base class.

        Args:
            context (zmq.asyncio.Context): The ZMQ context.
            address (str): The address to bind or connect to.
            bind (bool): Whether to bind or connect the socket.
            socket_type (SocketType): The type of ZMQ socket (PUB or SUB).
            socket_ops (dict, optional): Additional socket options to set.
        """
        self.logger = logging.getLogger(__name__)
        self.stop_event: asyncio.Event = asyncio.Event()
        self.initialized_event: asyncio.Event = asyncio.Event()
        self.context: zmq.asyncio.Context = context
        self.address: str = address
        self.bind: bool = bind
        self.socket_type: zmq.SocketType = socket_type
        self._socket: zmq.asyncio.Socket | None = None
        self.socket_ops: dict = socket_ops or {}
        self.client_id: str = f"{self.socket_type.name}_client_{uuid.uuid4().hex[:8]}"
        super().__init__()

    @property
    def is_initialized(self) -> bool:
        """Check if the client is initialized."""
        return self.initialized_event.is_set()

    @property
    def stop_requested(self) -> bool:
        """Check if the client is shutdown."""
        return self.stop_event.is_set()

    @property
    def socket_type_name(self) -> str:
        """Get the name of the socket type."""
        return self.socket_type.name

    @property
    def socket(self) -> zmq.asyncio.Socket:
        """Get the zmq socket for the client.

        Raises:
            CommunicationError: If the client is not initialized
        """
        if not self._socket:
            raise CommunicationError(
                CommunicationErrorReason.NOT_INITIALIZED_ERROR,
                "Communication channels are not initialized",
            )
        return self._socket

    async def _ensure_initialized(self) -> None:
        """Ensure the communication channels are initialized and not shutdown.

        Raises:
            CommunicationError: If the communication channels are not initialized
                or shutdown
        """
        if not self.is_initialized:
            await self.initialize()
        if self.stop_requested:
            raise asyncio.CancelledError()

    async def initialize(self) -> None:
        """Initialize the communication.

        This method will:
        - Create the zmq socket
        - Bind or connect the socket to the address
        - Set the socket options
        - Run the AIPerfHook.ON_INIT hooks
        """
        try:
            self._socket = self.context.socket(self.socket_type)
            if self.bind:
                self.logger.debug(
                    "ZMQ %s socket initialized and bound to %s (%s)",
                    self.socket_type_name,
                    self.address,
                    self.client_id,
                )
                self._socket.bind(self.address)
            else:
                self.logger.debug(
                    "ZMQ %s socket initialized and connected to %s (%s)",
                    self.socket_type_name,
                    self.address,
                    self.client_id,
                )
                self._socket.connect(self.address)

            # In BaseZMQClient.initialize()
            # Reduce timeouts to more reasonable values
            self._socket.setsockopt(zmq.RCVTIMEO, 300000)  # 5 minutes
            self._socket.setsockopt(zmq.SNDTIMEO, 300000)  # 5 minutes

            # Add performance-oriented socket options
            self._socket.setsockopt(zmq.TCP_KEEPALIVE, 1)
            self._socket.setsockopt(zmq.TCP_KEEPALIVE_IDLE, 60)
            self._socket.setsockopt(zmq.TCP_KEEPALIVE_INTVL, 10)
            self._socket.setsockopt(zmq.TCP_KEEPALIVE_CNT, 3)
            self._socket.setsockopt(zmq.IMMEDIATE, 1)  # Don't queue messages
            self._socket.setsockopt(zmq.LINGER, 0)  # Don't wait on close

            # Set additional socket options requested by the caller
            for key, val in self.socket_ops.items():
                self._socket.setsockopt(key, val)

            await self.run_hooks(AIPerfHook.ON_INIT)

            self.initialized_event.set()
            self.logger.debug(
                "ZMQ %s socket initialized and connected to %s (%s)",
                self.socket_type_name,
                self.address,
                self.client_id,
            )

        except AIPerfError:
            raise  # re-raise it up the stack
        except Exception as e:
            raise CommunicationError(
                CommunicationErrorReason.INITIALIZATION_ERROR,
                f"Failed to initialize ZMQ socket: {e}",
            ) from e

    async def shutdown(self) -> None:
        """Shutdown the communication.

        This method will:
        - Close the zmq socket
        - Run the AIPerfHook.ON_CLEANUP hooks
        """
        if self.stop_requested:
            return

        self.stop_event.set()

        try:
            await self.run_hooks(AIPerfHook.ON_STOP)
        except Exception as e:
            self.logger.error(
                "Exception running ON_STOP hooks: %s (%s)", e, self.client_id
            )

        # Cancel all registered tasks
        for task in self.registered_tasks:
            task.cancel()

        # Wait for all tasks to complete
        await asyncio.wait_for(
            asyncio.gather(*self.registered_tasks),
            timeout=TASK_CANCEL_TIMEOUT_SHORT,
        )
        self.registered_tasks.clear()

        # Run the ON_STOP and ON_CLEANUP hooks
        try:
            cancelled_error = None
            try:
                await self.run_hooks(AIPerfHook.ON_STOP)
            except asyncio.CancelledError as e:
                cancelled_error = e

            try:
                await self.run_hooks(AIPerfHook.ON_CLEANUP)
            except asyncio.CancelledError as e:
                cancelled_error = e

            # Re-raise the cancelled error if it was raised during the stop hooks
            if cancelled_error:
                raise cancelled_error

        except AIPerfError:
            raise  # re-raise it up the stack

        except Exception as e:
            self.logger.error(
                "Exception cleaning up ZMQ socket: %s (%s)", e, self.client_id
            )

        finally:
            try:
                if self._socket:
                    self._socket.close()
                    # self.logger.debug(
                    #     "ZMQ %s socket closed (%s)", self.socket_type_name, self.client_id
                    # )

            except Exception as e:
                self.logger.error(
                    "Exception shutting down ZMQ socket: %s (%s)", e, self.client_id
                )

            self._socket = None
