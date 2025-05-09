import asyncio
import logging
import uuid
from typing import Callable, Dict, List, Optional, Set, Union

from aiperf.common.comms.communication import Communication
from aiperf.common.models.messages import BaseMessage
from aiperf.common.models.push_pull import PullData, PushData
from aiperf.common.models.request_response import (
    RequestData,
    RequestStateInfo,
    ResponseData,
)

logger = logging.getLogger(__name__)


class MemoryCommunication(Communication):
    """In-memory communication implementation.

    This communication class uses in-memory data structures to route messages
    between components, useful for testing and single-process deployments.
    """

    # Class-level storage for shared subscriptions across instances
    _subscriptions: Dict[str, Dict[str, Callable]] = {}
    _subscribers_by_topic: Dict[str, Set[str]] = {}
    _topic_history: Dict[str, List[BaseMessage]] = {}
    _client_registry: Dict[str, "MemoryCommunication"] = {}
    _lock = asyncio.Lock()
    _request_responses: Dict[str, asyncio.Future] = {}  # For request/response pattern

    # Class-level storage for PUSH-PULL pattern
    _pull_queues: Dict[str, asyncio.Queue] = {}
    _pull_callbacks: Dict[str, Dict[str, Callable]] = {}
    _active_pull_tasks: Dict[str, Dict[str, asyncio.Task]] = {}

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

    async def publish(self, topic: str, message: BaseMessage) -> bool:
        """Publish a message to a topic.

        Args:
            topic: Topic to publish to
            message: Message to publish (must be a Pydantic model)

        Returns:
            True if publish was successful, False otherwise
        """
        try:
            # Ensure topic exists in subscribers dict
            async with MemoryCommunication._lock:
                if topic not in MemoryCommunication._subscribers_by_topic:
                    MemoryCommunication._subscribers_by_topic[topic] = set()

                # Store message in topic history
                if topic not in MemoryCommunication._topic_history:
                    MemoryCommunication._topic_history[topic] = []
                MemoryCommunication._topic_history[topic].append(message)

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
                            self._safe_callback(callback, message, topic, client_id)
                        )

            return True
        except Exception as e:
            self.logger.error(f"Error publishing to {topic}: {e}")
            return False

    async def subscribe(
        self, topic: str, callback: Callable[[BaseMessage], None]
    ) -> bool:
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
        self,
        target: str,
        request_data: RequestData,
        timeout: float = 5.0,
    ) -> ResponseData:
        """Send a request and wait for a response.

        Args:
            target: Target component to send request to
            request_data: Request data (must be a RequestData instance)
            timeout: Timeout in seconds

        Returns:
            ResponseData object
        """
        try:
            # Set target if not already set
            if not request_data.target:
                request_data.target = target

            # Ensure client_id is set
            if not request_data.client_id:
                request_data.client_id = self.client_id

            # Generate request ID if not provided
            if not request_data.request_id:
                request_data.request_id = str(uuid.uuid4())

            request_id = request_data.request_id

            self.logger.info(f"Creating request {request_id} to {target}")

            # Create future for response
            future = asyncio.Future()
            async with MemoryCommunication._lock:
                MemoryCommunication._request_responses[request_id] = future

            # Send request to the target
            success = await self.publish(f"request.{target}", request_data)
            if not success:
                self.logger.error(f"Failed to send request to {target}")
                return ResponseData(
                    request_id=request_id,
                    client_id=self.client_id,
                    status="error",
                    message=f"Failed to send request to {target}",
                )

            # Wait for response with timeout
            try:
                self.logger.debug(f"Waiting for response to request {request_id}")
                response = await asyncio.wait_for(future, timeout=timeout)
                self.logger.info(f"Received response for request {request_id}")

                # Response is a ResponseData object, return it directly
                return response
            except asyncio.TimeoutError:
                self.logger.error(
                    f"Timeout waiting for response to request {request_id}"
                )
                return ResponseData(
                    request_id=request_id,
                    client_id=self.client_id,
                    status="error",
                    message="Request timed out",
                )
            finally:
                # Clean up
                async with MemoryCommunication._lock:
                    MemoryCommunication._request_responses.pop(request_id, None)

        except Exception as e:
            self.logger.error(f"Error sending request to {target}: {e}")
            return ResponseData(
                request_id=request_data.request_id
                if hasattr(request_data, "request_id")
                else str(uuid.uuid4()),
                client_id=self.client_id,
                status="error",
                message=str(e),
            )

    async def respond(self, client_id: str, response: ResponseData) -> bool:
        """Send a response to a request.

        Args:
            client_id: Client ID to respond to
            response: Response message (must be a ResponseData instance)

        Returns:
            True if the response was sent successfully, False otherwise
        """
        try:
            self.logger.debug(f"Responding to client {client_id}")
            self.logger.debug(
                f"Publishing response with request_id {response.request_id}"
            )

            # Publish response to client's response topic
            return await self.publish(f"response.{client_id}", response)
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
        self,
        callback: Callable[[BaseMessage], None],
        message: BaseMessage,
        topic: str,
        client_id: str,
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

    async def _handle_response(self, message: ResponseData) -> None:
        """Handle a response message.

        Args:
            message: Response message (must be a ResponseData instance)
        """
        try:
            request_id = message.request_id

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
                            # Access Pydantic model attributes appropriately
                            if hasattr(message, "data") and isinstance(
                                message.data, dict
                            ):
                                data = message.data
                                if data.get("component_type") == component_type:
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

    async def dump_request_state(self) -> RequestStateInfo:
        """Dump the current state of requests and responses for debugging.

        Returns:
            RequestStateInfo model with debugging information
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

                # Create and return RequestStateInfo model directly
                return RequestStateInfo(
                    pending_requests=pending_requests,
                    pending_request_count=len(pending_requests),
                    client_count=client_count,
                    subscription_count=subscription_count,
                    response_topics=response_topics,
                    response_subscribers=response_subscribers,
                    client_ids=list(MemoryCommunication._client_registry.keys()),
                )
        except Exception as e:
            self.logger.error(f"Error dumping request state: {e}")
            return RequestStateInfo(client_count=0, error=str(e))

    async def push(self, target: str, data: PushData) -> bool:
        """Push data to a target.

        Args:
            target: Target endpoint to push data to
            data: Data to be pushed (must be a PushData instance)

        Returns:
            True if data was pushed successfully, False otherwise
        """
        try:
            self.logger.debug(f"Pushing data to {target}")

            # Ensure source is set if not already
            if not data.source:
                data.source = self.client_id

            async with MemoryCommunication._lock:
                # Create queue if it doesn't exist
                if target not in MemoryCommunication._pull_queues:
                    MemoryCommunication._pull_queues[target] = asyncio.Queue()

                # Add message to queue (store the model directly)
                await MemoryCommunication._pull_queues[target].put(data)

                # If there are registered callbacks, they'll be called by the background tasks

            return True
        except Exception as e:
            self.logger.error(f"Error pushing data to {target}: {e}")
            return False

    async def pull(
        self,
        source: str,
        callback: Optional[Callable[[PullData], None]] = None,
    ) -> Union[PullData, bool]:
        """Pull data from a source.

        Args:
            source: Source endpoint to pull data from
            callback: Optional function to call when data is received.
                     If provided, this method will register the callback and return a boolean.
                     If not provided, this method will wait for and return the next message.

        Returns:
            If callback is provided: True if pull registration was successful, False otherwise
            If callback is not provided: The received PullData object
        """
        try:
            self.logger.debug(f"Pulling data from {source}")

            async with MemoryCommunication._lock:
                # Create queue if it doesn't exist
                if source not in MemoryCommunication._pull_queues:
                    MemoryCommunication._pull_queues[source] = asyncio.Queue()

                queue = MemoryCommunication._pull_queues[source]

                # If callback is provided, register it and start background task
                if callback:
                    # Initialize pull callbacks dict for this source if needed
                    if source not in MemoryCommunication._pull_callbacks:
                        MemoryCommunication._pull_callbacks[source] = {}

                    # Store callback
                    MemoryCommunication._pull_callbacks[source][self.client_id] = (
                        callback
                    )

                    # Initialize active tasks dict for this source if needed
                    if source not in MemoryCommunication._active_pull_tasks:
                        MemoryCommunication._active_pull_tasks[source] = {}

                    # Start background task if not already running
                    if (
                        self.client_id
                        not in MemoryCommunication._active_pull_tasks[source]
                    ):
                        task = asyncio.create_task(
                            self._pull_worker(source, self.client_id)
                        )
                        MemoryCommunication._active_pull_tasks[source][
                            self.client_id
                        ] = task

                    return True

                # If no callback, wait for next message
                else:
                    # Get PullData model directly from the queue
                    pull_data = await queue.get()
                    return pull_data
        except Exception as e:
            self.logger.error(f"Error pulling data from {source}: {e}")
            return False if callback else PullData(source="", data={})

    async def _pull_worker(self, source: str, client_id: str) -> None:
        """Background worker to pull messages from a queue and call callbacks.

        Args:
            source: Source endpoint to pull from
            client_id: Client ID to call callbacks for
        """
        self.logger.debug(f"Starting pull worker for {source}, client {client_id}")
        try:
            while True:
                # Check if client is still registered and has callbacks
                if client_id not in MemoryCommunication._client_registry:
                    self.logger.debug(
                        f"Client {client_id} no longer registered, stopping pull worker"
                    )
                    break

                if (
                    source not in MemoryCommunication._pull_callbacks
                    or client_id not in MemoryCommunication._pull_callbacks[source]
                ):
                    self.logger.debug(
                        f"No callbacks for {source}, client {client_id}, stopping pull worker"
                    )
                    break

                # Get queue
                queue = MemoryCommunication._pull_queues.get(source)
                if not queue:
                    self.logger.warning(f"Queue for {source} no longer exists")
                    await asyncio.sleep(0.1)
                    continue

                # Get message from queue
                try:
                    # Get PullData model directly from the queue
                    pull_data = await queue.get()

                    # Get callback
                    callback = MemoryCommunication._pull_callbacks[source][client_id]

                    # Call callback with the PullData object directly
                    if callback:
                        await self._safe_callback(
                            callback, pull_data, f"pull.{source}", client_id
                        )
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    self.logger.error(f"Error in pull worker: {e}")
                    await asyncio.sleep(0.1)
        except Exception as e:
            self.logger.error(f"Error in pull worker: {e}")
        finally:
            # Clean up task reference
            if (
                source in MemoryCommunication._active_pull_tasks
                and client_id in MemoryCommunication._active_pull_tasks[source]
            ):
                MemoryCommunication._active_pull_tasks[source].pop(client_id, None)
            self.logger.debug(f"Pull worker for {source}, client {client_id} stopped")
