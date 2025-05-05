import asyncio
import json
import logging
import time
import uuid
from typing import Any, Dict, List, Optional, Callable, Set, Union

from .communication import Communication

logger = logging.getLogger(__name__)


class MemoryCommunication(Communication):
    """In-memory communication implementation.

    This communication class uses in-memory data structures to route messages
    between components, useful for testing and single-process deployments.
    """

    # Class-level storage for shared subscriptions across instances
    _subscriptions: Dict[str, Dict[str, Callable]] = {}
    _subscribers_by_topic: Dict[str, Set[str]] = {}
    _topic_history: Dict[str, List[Dict[str, Any]]] = {}
    _client_registry: Dict[str, "MemoryCommunication"] = {}
    _lock = asyncio.Lock()

    def __init__(self, client_id: Optional[str] = None):
        """Initialize in-memory communication.

        Args:
            client_id: Optional client ID
        """
        self.client_id = client_id or str(uuid.uuid4())
        self.logger = logging.getLogger(f"communication.memory.{self.client_id[:8]}")
        self.logger.info(
            f"Initializing MemoryCommunication with client_id {self.client_id}"
        )

        # Register this instance in the class-level registry
        self._register_client()

    def _register_client(self):
        """Register this client in the class-level registry."""
        MemoryCommunication._client_registry[self.client_id] = self
        self.logger.debug(f"Registered client {self.client_id}")

    async def publish(self, topic: str, message: Any) -> bool:
        """Publish a message to a topic.

        Args:
            topic: Topic to publish to
            message: Message to publish

        Returns:
            True if publish was successful, False otherwise
        """
        # Handle message serialization if necessary
        if not isinstance(message, dict):
            try:
                if isinstance(message, str):
                    message_dict = json.loads(message)
                else:
                    message_dict = {"data": message}
            except (json.JSONDecodeError, TypeError):
                message_dict = {"data": str(message)}
        else:
            message_dict = message

        # Add source to message if not present
        if "source" not in message_dict and "client_id" not in message_dict:
            message_dict["source"] = self.client_id

        # Add timestamp if not present
        if "timestamp" not in message_dict:
            import time

            message_dict["timestamp"] = time.time()

        self.logger.debug(f"Publishing to {topic}: {message_dict}")

        try:
            # Ensure topic exists in subscribers dict
            async with MemoryCommunication._lock:
                if topic not in MemoryCommunication._subscribers_by_topic:
                    MemoryCommunication._subscribers_by_topic[topic] = set()

                # Store message in topic history
                if topic not in MemoryCommunication._topic_history:
                    MemoryCommunication._topic_history[topic] = []
                MemoryCommunication._topic_history[topic].append(message_dict)

                # Limit history size
                if len(MemoryCommunication._topic_history[topic]) > 100:
                    MemoryCommunication._topic_history[topic] = (
                        MemoryCommunication._topic_history[topic][-100:]
                    )

                # Find subscribers for this topic
                subscribers = MemoryCommunication._subscribers_by_topic.get(
                    topic, set()
                )

            # Call each subscriber's callback for this topic
            for client_id in subscribers:
                if client_id in MemoryCommunication._client_registry:
                    client = MemoryCommunication._client_registry[client_id]
                    if topic in MemoryCommunication._subscriptions.get(client_id, {}):
                        callback = MemoryCommunication._subscriptions[client_id][topic]
                        # Schedule the callback to run in the event loop
                        asyncio.create_task(
                            self._safe_callback(
                                callback, message_dict, topic, client_id
                            )
                        )

            return True
        except Exception as e:
            self.logger.error(f"Error publishing to {topic}: {e}")
            return False

    async def subscribe(self, topic: str, callback: Callable) -> bool:
        """Subscribe to a topic.

        Args:
            topic: Topic to subscribe to
            callback: Callback function to call when a message is received

        Returns:
            True if subscription was successful, False otherwise
        """
        try:
            self.logger.debug(f"Subscribing to {topic}")

            async with MemoryCommunication._lock:
                # Create client subscriptions entry if it doesn't exist
                if self.client_id not in MemoryCommunication._subscriptions:
                    MemoryCommunication._subscriptions[self.client_id] = {}

                # Store the callback for this topic
                MemoryCommunication._subscriptions[self.client_id][topic] = callback

                # Add to topic's subscribers
                if topic not in MemoryCommunication._subscribers_by_topic:
                    MemoryCommunication._subscribers_by_topic[topic] = set()
                MemoryCommunication._subscribers_by_topic[topic].add(self.client_id)

                # Send any historical messages for wildcard topics
                if topic.endswith(".*"):
                    base_topic = topic[:-2]  # Remove the ".*"
                    matching_topics = [
                        t
                        for t in MemoryCommunication._topic_history
                        if t.startswith(base_topic)
                    ]

                    # Send historical messages for matching topics
                    for matching_topic in matching_topics:
                        for message in MemoryCommunication._topic_history.get(
                            matching_topic, []
                        ):
                            asyncio.create_task(
                                self._safe_callback(
                                    callback, message, matching_topic, self.client_id
                                )
                            )
                # Send any historical messages for exact topic
                elif topic in MemoryCommunication._topic_history:
                    for message in MemoryCommunication._topic_history[topic]:
                        asyncio.create_task(
                            self._safe_callback(
                                callback, message, topic, self.client_id
                            )
                        )

            return True
        except Exception as e:
            self.logger.error(f"Error subscribing to {topic}: {e}")
            return False

    async def unsubscribe(self, topic: str) -> bool:
        """Unsubscribe from a topic.

        Args:
            topic: Topic to unsubscribe from

        Returns:
            True if unsubscription was successful, False otherwise
        """
        try:
            self.logger.debug(f"Unsubscribing from {topic}")

            async with MemoryCommunication._lock:
                # Remove from client's subscriptions
                if self.client_id in MemoryCommunication._subscriptions:
                    MemoryCommunication._subscriptions[self.client_id].pop(topic, None)

                # Remove from topic's subscribers
                if topic in MemoryCommunication._subscribers_by_topic:
                    MemoryCommunication._subscribers_by_topic[topic].discard(
                        self.client_id
                    )

            return True
        except Exception as e:
            self.logger.error(f"Error unsubscribing from {topic}: {e}")
            return False

    async def respond(self, client_id: str, message: Any) -> bool:
        """Send a response directly to a client.

        Args:
            client_id: Client ID to respond to
            message: Message to send

        Returns:
            True if response was sent successfully, False otherwise
        """
        try:
            # Use a special direct message topic for the target client
            direct_topic = f"_direct.{client_id}"
            return await self.publish(direct_topic, message)
        except Exception as e:
            self.logger.error(f"Error responding to {client_id}: {e}")
            return False

    async def close(self) -> bool:
        """Close the communication channel.

        Returns:
            True if closing was successful, False otherwise
        """
        try:
            self.logger.debug(f"Closing communication for {self.client_id}")

            async with MemoryCommunication._lock:
                # Remove all subscriptions for this client
                MemoryCommunication._subscriptions.pop(self.client_id, None)

                # Remove from all topic subscribers
                for (
                    topic,
                    subscribers,
                ) in MemoryCommunication._subscribers_by_topic.items():
                    subscribers.discard(self.client_id)

                # Remove from client registry
                MemoryCommunication._client_registry.pop(self.client_id, None)

            return True
        except Exception as e:
            self.logger.error(f"Error closing communication: {e}")
            return False

    async def _safe_callback(
        self, callback: Callable, message: Dict[str, Any], topic: str, client_id: str
    ) -> None:
        """Safely call a callback function.

        Args:
            callback: Callback function
            message: Message to pass to callback
            topic: Topic the message was published to
            client_id: Client ID that subscribed
        """
        try:
            await callback(message)
        except Exception as e:
            self.logger.error(f"Error in callback for {client_id} on {topic}: {e}")

    async def get_component_by_type(self, component_type: str) -> Optional[str]:
        """Get a component by its type.

        Args:
            component_type: Type of component to find

        Returns:
            Component ID if found, None otherwise
        """
        try:
            # Check if there's a topic for component identities
            component_ids = []

            # Look in topic history for component identities
            async with MemoryCommunication._lock:
                for topic, messages in MemoryCommunication._topic_history.items():
                    if topic == "system.identity" or topic.startswith(
                        "system.identity."
                    ):
                        for message in messages:
                            data = message.get("data", message)
                            if (
                                isinstance(data, dict)
                                and data.get("component_type") == component_type
                            ):
                                component_ids.append(data.get("component_id"))

            # Return the first component ID if found
            return component_ids[0] if component_ids else None
        except Exception as e:
            self.logger.error(f"Error getting component by type {component_type}: {e}")
            return None

    async def list_topics(self) -> List[str]:
        """List all available topics.

        Returns:
            List of topics
        """
        try:
            async with MemoryCommunication._lock:
                return list(MemoryCommunication._subscribers_by_topic.keys())
        except Exception as e:
            self.logger.error(f"Error listing topics: {e}")
            return []

    async def list_clients(self) -> List[str]:
        """List all registered clients.

        Returns:
            List of client IDs
        """
        try:
            async with MemoryCommunication._lock:
                return list(MemoryCommunication._client_registry.keys())
        except Exception as e:
            self.logger.error(f"Error listing clients: {e}")
            return []

    async def get_client_subscriptions(self, client_id: str) -> List[str]:
        """Get all topics a client has subscribed to.

        Args:
            client_id: Client ID

        Returns:
            List of topics
        """
        try:
            async with MemoryCommunication._lock:
                if client_id in MemoryCommunication._subscriptions:
                    return list(MemoryCommunication._subscriptions[client_id].keys())
                return []
        except Exception as e:
            self.logger.error(f"Error getting subscriptions for {client_id}: {e}")
            return []
