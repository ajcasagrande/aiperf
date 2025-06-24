# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
import logging
from abc import ABC, abstractmethod
from collections.abc import Callable, Coroutine
from typing import Any, TypeVar

from aiperf.common.enums import MessageType, Topic
from aiperf.common.models import Message

logger = logging.getLogger(__name__)


################################################################################
# Base Communication Client Class
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


class PushClientInterface(BaseCommunicationClient):
    """Interface for push clients."""

    @abstractmethod
    async def push(self, message: Message) -> None:
        """Push data to a target.

        Args:
            topic: Topic to push to
            message: Message to be pushed
        """
        pass


class PullClientInterface(BaseCommunicationClient):
    """Interface for pull clients."""

    @abstractmethod
    async def register_pull_callback(
        self,
        message_type: MessageType,
        callback: Callable[[MessageT], Coroutine[Any, Any, None]],
    ) -> None:
        """Register a callback for a pull client.

        Args:
            message_type: The message type to register the callback for
            callback: The callback to register
        """
        pass


class ReqClientInterface(BaseCommunicationClient):
    """Interface for request clients."""

    # TODO: Should this accept a target service type for routing?
    @abstractmethod
    async def request(
        self,
        message: MessageT,
    ) -> MessageOutputT:
        """Send a request and wait for a response.

        Args:
            message: Message to send (will be routed based on the message type)

        Returns:
            Response message if successful
        """
        pass


class RepClientInterface(BaseCommunicationClient):
    """Interface for reply clients."""

    @abstractmethod
    def register_request_handler(
        self,
        service_id: str,
        message_type: MessageType,
        handler: Callable[[MessageT], Coroutine[Any, Any, MessageOutputT | None]],
    ) -> None:
        """Register a request handler for a message type.

        Args:
            service_id: The service ID to register the handler for
            message_type: The message type to register the handler for
            handler: The handler to register
        """
        pass


class SubClientInterface(BaseCommunicationClient):
    """Interface for subscribe clients."""

    @abstractmethod
    async def subscribe(
        self,
        topic: Topic,
        callback: Callable[[MessageT], Coroutine[Any, Any, None]],
    ) -> None:
        """Subscribe to a topic.

        Args:
            topic: Topic to subscribe to
            callback: Function to call when a message is received
        """
        pass


class PubClientInterface(BaseCommunicationClient):
    """Interface for publish clients."""

    @abstractmethod
    async def publish(self, topic: Topic, message: Message) -> None:
        """Publish a message to a topic."""
        pass


################################################################################
# Base Communication Class
################################################################################


class BaseCommunication(ABC):
    """Base class for specifying the base communication layer for AIPerf components."""

    @abstractmethod
    async def initialize(self) -> None:
        """Initialize communication channels."""
        pass

    @property
    @abstractmethod
    def is_initialized(self) -> bool:
        """Check if communication channels are initialized.

        Returns:
            True if communication channels are initialized, False otherwise
        """
        pass

    @property
    @abstractmethod
    def is_shutdown(self) -> bool:
        """Check if communication channels are shutdown.

        Returns:
            True if communication channels are shutdown, False otherwise
        """
        pass

    @abstractmethod
    async def shutdown(self) -> None:
        """Gracefully shutdown communication channels."""
        pass

    @abstractmethod
    async def create_pub_client(
        self, address: str, bind: bool = False, socket_ops: dict | None = None
    ) -> PubClientInterface:
        """Create a publish client.

        Args:
            address: The address to bind or connect to.
            bind: Whether to bind or connect the socket.
            socket_ops: Additional socket options to set.
        """
        pass

    @abstractmethod
    async def create_sub_client(
        self, address: str, bind: bool = False, socket_ops: dict | None = None
    ) -> SubClientInterface:
        """Create a subscribe client.

        Args:
            address: The address to bind or connect to.
            bind: Whether to bind or connect the socket.
            socket_ops: Additional socket options to set.
        """
        pass

    @abstractmethod
    async def create_push_client(
        self, address: str, bind: bool = False, socket_ops: dict | None = None
    ) -> PushClientInterface:
        """Create a push client.

        Args:
            address: The address to bind or connect to.
            bind: Whether to bind or connect the socket.
            socket_ops: Additional socket options to set.
        """
        pass

    @abstractmethod
    async def create_pull_client(
        self, address: str, bind: bool = False, socket_ops: dict | None = None
    ) -> PullClientInterface:
        """Create a pull client.

        Args:
            address: The address to bind or connect to.
            bind: Whether to bind or connect the socket.
            socket_ops: Additional socket options to set.
        """
        pass

    @abstractmethod
    async def create_req_client(
        self, address: str, bind: bool = False, socket_ops: dict | None = None
    ) -> ReqClientInterface:
        """Create a request client.

        Args:
            address: The address to bind or connect to.
            bind: Whether to bind or connect the socket.
            socket_ops: Additional socket options to set.
        """
        pass

    @abstractmethod
    async def create_rep_client(
        self, address: str, bind: bool = False, socket_ops: dict | None = None
    ) -> RepClientInterface:
        """Create a reply client.

        Args:
            address: The address to bind or connect to.
            bind: Whether to bind or connect the socket.
            socket_ops: Additional socket options to set.
        """
        pass
