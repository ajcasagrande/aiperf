from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, Union, Callable


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
    async def publish(self, topic: str, message: Dict[str, Any]) -> bool:
        """Publish a message to a topic.

        Args:
            topic: Topic to publish to
            message: Message to publish

        Returns:
            True if message was published successfully, False otherwise
        """
        pass

    @abstractmethod
    async def subscribe(
        self, topic: str, callback: Callable[[Dict[str, Any]], None]
    ) -> bool:
        """Subscribe to a topic.

        Args:
            topic: Topic to subscribe to
            callback: Function to call when a message is received

        Returns:
            True if subscription was successful, False otherwise
        """
        pass

    @abstractmethod
    async def request(
        self, target: str, request: Dict[str, Any], timeout: float = 5.0
    ) -> Dict[str, Any]:
        """Send a request and wait for a response.

        Args:
            target: Target component to send request to
            request: Request message
            timeout: Timeout in seconds

        Returns:
            Response message
        """
        pass

    @abstractmethod
    async def respond(self, target: str, response: Dict[str, Any]) -> bool:
        """Send a response to a request.

        Args:
            target: Target component to send response to
            response: Response message

        Returns:
            True if response was sent successfully, False otherwise
        """
        pass

    @abstractmethod
    async def push(self, target: str, data: Dict[str, Any]) -> bool:
        """Push data to a target using ZeroMQ PUSH pattern.

        Args:
            target: Target endpoint to push data to
            data: Data to be pushed

        Returns:
            True if data was pushed successfully, False otherwise
        """
        pass

    @abstractmethod
    async def pull(
        self, source: str, callback: Optional[Callable[[Dict[str, Any]], None]] = None
    ) -> Union[Dict[str, Any], bool]:
        """Pull data from a source using ZeroMQ PULL pattern.

        Args:
            source: Source endpoint to pull data from
            callback: Optional function to call when data is received.
                     If provided, this method will register the callback and return a boolean.
                     If not provided, this method will wait for and return the next message.

        Returns:
            If callback is provided: True if pull registration was successful, False otherwise
            If callback is not provided: The received data dictionary
        """
        pass
