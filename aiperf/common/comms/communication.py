from abc import ABC, abstractmethod
from typing import Callable, Optional, Union, Coroutine, Any

from aiperf.common.enums import ClientType
from aiperf.common.models.messages import BaseMessage
from aiperf.common.models.push_pull import PushPullData
from aiperf.common.models.request_response import (
    RequestData,
    ResponseData,
)


class Communication(ABC):
    """Base class for communication between AIPerf components."""

    @abstractmethod
    async def initialize(self) -> bool:
        """Initialize communication channels.

        Returns:
            True if initialization was successful, False otherwise
        """
        pass

    @abstractmethod
    async def shutdown(self) -> bool:
        """Gracefully shutdown communication channels.

        Returns:
            True if shutdown was successful, False otherwise
        """
        pass

    @abstractmethod
    async def create_clients(self, *types: ClientType) -> None:
        """Create and initialize clients for the given types.

        Args:
            types: List of ClientType values to create clients for
        """
        pass

    @abstractmethod
    async def publish(
        self, client_type: ClientType, topic: str, message: BaseMessage
    ) -> bool:
        """Publish a message to a topic.

        Args:
            client_type: Client type to publish from
            topic: Topic to publish to
            message: Message to publish (must be a Pydantic model)

        Returns:
            True if message was published successfully, False otherwise
        """
        pass

    @abstractmethod
    async def subscribe(
        self,
        client_type: ClientType,
        topic: str,
        callback: Callable[[BaseMessage], Coroutine[Any, Any, None]] = None,
    ) -> bool:
        """Subscribe to a topic.

        Args:
            client_type: Client type to subscribe from
            topic: Topic to subscribe to
            callback: Function to call when a message is received (receives BaseMessage object)

        Returns:
            True if subscription was successful, False otherwise
        """
        pass

    @abstractmethod
    async def request(
        self,
        client_type: ClientType,
        target: str,
        request_data: RequestData,
        timeout: float = 5.0,
    ) -> ResponseData:
        """Send a request and wait for a response.

        Args:
            client_type: Client type to send request from
            target: Target component to send request to
            request_data: Request data (must be a RequestData instance)
            timeout: Timeout in seconds

        Returns:
            ResponseData object
        """
        pass

    @abstractmethod
    async def respond(
        self, client_type: ClientType, target: str, response: ResponseData
    ) -> bool:
        """Send a response to a request.

        Args:
            client_type: Client type to send response from
            target: Target component to send response to
            response: Response message (must be a ResponseData instance)

        Returns:
            True if response was sent successfully, False otherwise
        """
        pass

    @abstractmethod
    async def push(self, client_type: ClientType, data: PushPullData) -> bool:
        """Push data to a target.

        Args:
            client_type: Client type to push data from
            data: Data to be pushed (must be a PushData instance)

        Returns:
            True if data was pushed successfully, False otherwise
        """
        pass

    @abstractmethod
    async def pull(
        self,
        client_type: ClientType,
        source: str,
        callback: Optional[Callable[[PushPullData], Coroutine[Any, Any, None]]] = None,
    ) -> Union[PushPullData, bool]:
        """Pull data from a source.

        Args:
            client_type: Client type to pull data from
            source: Source endpoint to pull data from
            callback: Optional function to call when data is received.
                     If provided, this method will register the callback and return a boolean.
                     If not provided, this method will wait for and return the next message.

        Returns:
            If callback is provided: True if pull registration was successful, False otherwise
            If callback is not provided: The received PushPullData object
        """
        pass
