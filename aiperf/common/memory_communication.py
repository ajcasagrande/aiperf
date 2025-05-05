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
    _request_responses: Dict[str, asyncio.Future] = {}  # For request/response pattern

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
        self._is_initialized = False
        self._is_shutdown = False

        # Register this instance in the class-level registry
        self._register_client()

    def _register_client(self):
        """Register this client in the class-level registry."""
        MemoryCommunication._client_registry[self.client_id] = self
        self.logger.debug(f"Registered client {self.client_id}")

    async def initialize(self) -> bool:
        """Initialize communication channels.

        Returns:
            True if initialization was successful, False otherwise
        """
        try:
            self.logger.debug(f"Initializing communication for {self.client_id}")
            # Subscribe to responses for this client
            await self.subscribe(f"response.{self.client_id}", self._handle_response)
            self._is_initialized = True
            return True
        except Exception as e:
            self.logger.error(f"Error initializing communication: {e}")
            return False

    async def shutdown(self) -> bool:
        """Gracefully shutdown communication channels.

        Returns:
            True if shutdown was successful, False otherwise
        """
        if self._is_shutdown:
            return True

        try:
            self.logger.debug(f"Shutting down communication for {self.client_id}")

            # Clear client from registry and subscriptions
            await self.close()

            self._is_shutdown = True
            self._is_initialized = False
            return True
        except Exception as e:
            self.logger.error(f"Error shutting down communication: {e}")
            return False

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
        try:
            # Generate request ID
            request_id = str(uuid.uuid4())

            self.logger.info(f"Creating request {request_id} to {target}")

            # Create future for response
            future = asyncio.Future()
            async with MemoryCommunication._lock:
                MemoryCommunication._request_responses[request_id] = future

            # Prepare request message
            enriched_request = {
                "request_id": request_id,
                "client_id": self.client_id,
                "timestamp": time.time(),
                "data": request,
            }

            # Send request to the target
            success = await self.publish(f"request.{target}", enriched_request)
            if not success:
                self.logger.error(f"Failed to send request to {target}")
                return {
                    "status": "error",
                    "message": f"Failed to send request to {target}",
                }

            # Wait for response with timeout
            try:
                self.logger.debug(f"Waiting for response to request {request_id}")
                response = await asyncio.wait_for(future, timeout=timeout)
                self.logger.info(f"Received response for request {request_id}")

                # Extract data from response
                if isinstance(response, dict) and "data" in response:
                    return response.get("data", {})
                return response
            except asyncio.TimeoutError:
                self.logger.error(
                    f"Timeout waiting for response to request {request_id}"
                )
                return {"status": "error", "message": "Request timed out"}
            finally:
                # Clean up
                async with MemoryCommunication._lock:
                    MemoryCommunication._request_responses.pop(request_id, None)

        except Exception as e:
            self.logger.error(f"Error sending request to {target}: {e}")
            return {"status": "error", "message": str(e)}

    async def respond(self, client_id: str, message: Any) -> bool:
        """Send a response to a request.

        Args:
            client_id: Client ID to respond to
            message: Response message

        Returns:
            True if the response was sent successfully, False otherwise
        """
        try:
            self.logger.debug(f"Responding to client {client_id}")

            # Ensure message is a dict with request_id
            if not isinstance(message, dict):
                message = {"data": message, "request_id": "unknown"}
            elif (
                "request_id" not in message
                and "data" in message
                and isinstance(message["data"], dict)
            ):
                # Try to extract request_id from data
                if "request_id" in message["data"]:
                    message["request_id"] = message["data"]["request_id"]

            if "request_id" in message:
                self.logger.debug(
                    f"Publishing response with request_id {message['request_id']}"
                )
            else:
                self.logger.warning(f"Response missing request_id: {message}")

            # Publish response to client's response topic
            return await self.publish(f"response.{client_id}", message)
        except Exception as e:
            self.logger.error(f"Error responding to client {client_id}: {e}")
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

    async def _handle_response(self, message: Dict[str, Any]) -> None:
        """Handle a response message.

        Args:
            message: Response message
        """
        try:
            # Get request ID from response
            request_id = message.get("request_id")
            if not request_id:
                # Look in data field if it exists
                if isinstance(message.get("data"), dict):
                    request_id = message.get("data", {}).get("request_id")

                if not request_id:
                    self.logger.warning(
                        f"Received response without request_id: {message}"
                    )
                    return

            self.logger.info(f"Received response for request {request_id}")

            # Find the future for this request
            async with MemoryCommunication._lock:
                future = MemoryCommunication._request_responses.get(request_id)

            if future and not future.done():
                self.logger.info(f"Setting result for request {request_id}")
                future.set_result(message)
            else:
                if future and future.done():
                    self.logger.warning(
                        f"Future already complete for request: {request_id}"
                    )
                else:
                    self.logger.warning(
                        f"Received response for unknown request: {request_id}"
                    )
        except Exception as e:
            self.logger.error(f"Error handling response: {e}")

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

    async def dump_request_state(self) -> Dict[str, Any]:
        """Dump the current state of requests and responses for debugging.

        Returns:
            Dictionary with debugging information
        """
        try:
            async with MemoryCommunication._lock:
                pending_requests = list(MemoryCommunication._request_responses.keys())
                subscription_count = sum(
                    len(subs) for subs in MemoryCommunication._subscriptions.values()
                )
                client_count = len(MemoryCommunication._client_registry)
                response_topics = [
                    t
                    for t in MemoryCommunication._subscribers_by_topic.keys()
                    if t.startswith("response.")
                ]

                # Check response subscribers
                response_subscribers = {}
                for topic in response_topics:
                    subscribers = MemoryCommunication._subscribers_by_topic.get(
                        topic, set()
                    )
                    response_subscribers[topic] = list(subscribers)

                return {
                    "pending_requests": pending_requests,
                    "pending_request_count": len(pending_requests),
                    "client_count": client_count,
                    "subscription_count": subscription_count,
                    "response_topics": response_topics,
                    "response_subscribers": response_subscribers,
                    "client_ids": list(MemoryCommunication._client_registry.keys()),
                }
        except Exception as e:
            self.logger.error(f"Error dumping request state: {e}")
            return {"error": str(e)}
