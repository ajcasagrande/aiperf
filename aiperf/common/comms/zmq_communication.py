import asyncio
import json
import logging
import time
import uuid
from typing import Any, Callable, Dict, Optional, Union

import zmq.asyncio

from aiperf.common.comms.communication import Communication
from aiperf.common.models.comms import ZMQCommunicationConfig
from aiperf.common.models.messages import BaseMessage

logger = logging.getLogger(__name__)


class ZMQCommunication(Communication):
    """ZeroMQ-based implementation of the Communication interface.

    Uses ZeroMQ for publish/subscribe and request/reply patterns to
    facilitate communication between AIPerf components.
    """

    def __init__(
        self,
        config: Optional[ZMQCommunicationConfig] = None,
        is_controller: bool = False,
    ):
        """Initialize ZMQ communication.

        Args:
            config: ZMQCommunicationConfig object with configuration parameters
            is_controller: Flag indicating if this is the system controller (which binds to sockets)
                           or a service (which connects to sockets)
        """
        self.config = config or ZMQCommunicationConfig()
        self.is_controller = is_controller

        # Generate client_id if not provided
        if not self.config.client_id:
            self.config.client_id = f"client_{uuid.uuid4().hex[:8]}"

        self.context = zmq.asyncio.Context()
        self.pub_socket = None
        self.sub_socket = None
        self.req_socket = None
        self.rep_socket = None
        self.push_socket = None
        self.pull_socket = None

        self._subscribers = {}
        self._pull_callbacks = {}
        self._is_initialized = False
        self._is_shutdown = False
        self._response_futures = {}
        self._response_data = {}

    async def initialize(self) -> bool:
        """Initialize communication channels.

        Returns:
            True if initialization was successful, False otherwise
        """
        if self._is_initialized:
            return True

        try:
            # Set up publish socket - controller binds, services connect
            self.pub_socket = self.context.socket(zmq.PUB)
            if self.is_controller:
                self.pub_socket.connect(self.config.pub_address)
                logger.info(
                    f"Controller bound to PUB socket: {self.config.pub_address}"
                )
            else:
                self.pub_socket.connect(self.config.pub_address)
                logger.info(
                    f"Service connected to PUB socket: {self.config.pub_address}"
                )

            # Set up subscribe socket - controller binds, services connect
            self.sub_socket = self.context.socket(zmq.SUB)
            if self.is_controller:
                self.sub_socket.bind(self.config.sub_address)
                logger.info(
                    f"Controller bound to SUB socket: {self.config.sub_address}"
                )
            else:
                self.sub_socket.connect(self.config.sub_address)
                logger.info(
                    f"Service connected to SUB socket: {self.config.sub_address}"
                )

            # Set up request/reply sockets - controller binds to REP, services connect to REQ
            self.req_socket = self.context.socket(zmq.REQ)
            self.req_socket.connect(self.config.req_address)
            logger.info(f"Connected to REQ socket: {self.config.req_address}")

            self.rep_socket = self.context.socket(zmq.REP)
            if self.is_controller:
                self.rep_socket.bind(self.config.rep_address)
                logger.info(
                    f"Controller bound to REP socket: {self.config.rep_address}"
                )
            else:
                self.rep_socket.connect(self.config.rep_address)
                logger.info(
                    f"Service connected to REP socket: {self.config.rep_address}"
                )

            # Set up push/pull sockets - controller binds to PULL, services connect to PUSH
            self.push_socket = self.context.socket(zmq.PUSH)
            self.push_socket.connect(self.config.push_address)
            logger.info(f"Connected to PUSH socket: {self.config.push_address}")

            self.pull_socket = self.context.socket(zmq.PULL)
            if self.is_controller:
                self.pull_socket.bind(self.config.pull_address)
                logger.info(
                    f"Controller bound to PULL socket: {self.config.pull_address}"
                )
            else:
                self.pull_socket.connect(self.config.pull_address)
                logger.info(
                    f"Service connected to PULL socket: {self.config.pull_address}"
                )

            # Start background tasks for receiving messages
            asyncio.create_task(self._sub_receiver())
            asyncio.create_task(self._rep_receiver())
            asyncio.create_task(self._pull_receiver())

            self._is_initialized = True
            logger.info(
                f"ZMQ communication initialized for client {self.config.client_id} (controller: {self.is_controller})"
            )
            return True
        except Exception as e:
            logger.error(f"Error initializing ZMQ communication: {e}")
            await self.shutdown()
            return False

    async def shutdown(self) -> bool:
        """Gracefully shutdown communication channels.

        Returns:
            True if shutdown was successful, False otherwise
        """
        if self._is_shutdown:
            return True

        try:
            logger.info(
                f"Shutting down ZMQ communication for client {self.config.client_id}"
            )

            # Close sockets
            if self.pub_socket:
                self.pub_socket.close()
                self.pub_socket = None

            if self.sub_socket:
                self.sub_socket.close()
                self.sub_socket = None

            if self.req_socket:
                self.req_socket.close()
                self.req_socket = None

            if self.rep_socket:
                self.rep_socket.close()
                self.rep_socket = None

            if self.push_socket:
                self.push_socket.close()
                self.push_socket = None

            if self.pull_socket:
                self.pull_socket.close()
                self.pull_socket = None

            # Clear subscribers and callbacks
            self._subscribers = {}
            self._pull_callbacks = {}

            self._is_shutdown = True
            self._is_initialized = False
            return True
        except Exception as e:
            logger.error(f"Error shutting down ZMQ communication: {e}")
            return False

    async def publish(self, topic: str, message: BaseMessage) -> bool:
        """Publish a message to a topic.

        Args:
            topic: Topic to publish to
            message: Message to publish

        Returns:
            True if message was published successfully, False otherwise
        """
        if not self._is_initialized or self._is_shutdown:
            logger.error(
                "Cannot publish message: communication not initialized or already shut down"
            )
            return False

        try:
            # Serialize message
            message_json = message.model_dump_json()

            # Publish message
            await self.pub_socket.send_multipart(
                [topic.encode(), message_json.encode()]
            )
            return True
        except Exception as e:
            logger.error(f"Error publishing message to topic {topic}: {e}")
            return False

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
        if not self._is_initialized or self._is_shutdown:
            logger.error(
                "Cannot subscribe to topic: communication not initialized or already shut down"
            )
            return False

        try:
            # Subscribe to topic
            self.sub_socket.subscribe(topic.encode())

            # Register callback
            if topic not in self._subscribers:
                self._subscribers[topic] = []
            self._subscribers[topic].append(callback)

            logger.info(f"Subscribed to topic: {topic}")
            return True
        except Exception as e:
            logger.error(f"Error subscribing to topic {topic}: {e}")
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
        if not self._is_initialized or self._is_shutdown:
            logger.error(
                "Cannot send request: communication not initialized or already shut down"
            )
            return {
                "status": "error",
                "message": "Communication not initialized or already shut down",
            }

        try:
            # Generate request ID
            request_id = str(uuid.uuid4())

            # Add metadata to request
            enriched_request = {
                "request_id": request_id,
                "client_id": self.config.client_id,
                "target": target,
                "timestamp": time.time(),
                "data": request,
            }

            # Serialize request
            request_json = json.dumps(enriched_request)

            # Create future for response
            future = asyncio.Future()
            self._response_futures[request_id] = future

            # Send request
            await self.req_socket.send_string(request_json)

            # Wait for response with timeout
            try:
                response_json = await asyncio.wait_for(future, timeout)
                response = json.loads(response_json)
                return response.get("data", {})
            except asyncio.TimeoutError:
                logger.error(f"Timeout waiting for response to request {request_id}")
                self._response_futures.pop(request_id, None)
                return {"status": "error", "message": "Request timed out"}
            finally:
                # Clean up future
                self._response_futures.pop(request_id, None)
        except Exception as e:
            logger.error(f"Error sending request to {target}: {e}")
            return {"status": "error", "message": str(e)}

    async def respond(self, target: str, response: Dict[str, Any]) -> bool:
        """Send a response to a request.

        Args:
            target: Target component to send response to
            response: Response message

        Returns:
            True if response was sent successfully, False otherwise
        """
        if not self._is_initialized or self._is_shutdown:
            logger.error(
                "Cannot send response: communication not initialized or already shut down"
            )
            return False

        try:
            # Add metadata to response
            enriched_response = {
                "client_id": self.config.client_id,
                "target": target,
                "timestamp": time.time(),
                "data": response,
            }

            # Serialize response
            response_json = json.dumps(enriched_response)

            # Send response
            await self.rep_socket.send_string(response_json)
            return True
        except Exception as e:
            logger.error(f"Error sending response to {target}: {e}")
            return False

    async def _sub_receiver(self) -> None:
        """Background task for receiving messages from subscribed topics."""
        while not self._is_shutdown:
            if not self._is_initialized or not self.sub_socket:
                # Not initialized yet, wait a bit and check again
                await asyncio.sleep(0.1)
                continue

            try:
                # Receive message
                topic_bytes, message_bytes = await self.sub_socket.recv_multipart()
                topic = topic_bytes.decode()
                message_json = message_bytes.decode()
                logger.debug(f"Received message from {topic}: {message_json}")
                message = BaseMessage.model_validate_json(message_json)

                # Call callbacks
                if topic in self._subscribers:
                    for callback in self._subscribers[topic]:
                        try:
                            await callback(message)
                        except Exception as e:
                            logger.error(
                                f"Error in subscriber callback for topic {topic}: {e}"
                            )
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error receiving message from subscription: {e}")
                await asyncio.sleep(0.1)

    async def _rep_receiver(self) -> None:
        """Background task for receiving requests and sending responses."""
        while not self._is_shutdown:
            if not self._is_initialized or not self.rep_socket:
                # Not initialized yet, wait a bit and check again
                await asyncio.sleep(0.1)
                continue

            try:
                # Receive request
                request_json = await self.rep_socket.recv_string()
                request = json.loads(request_json)

                # Extract request data
                request_id = request.get("request_id")
                data = request.get("data", {})

                # Store response data
                self._response_data[request_id] = data

                # Resolve future if it exists
                if request_id in self._response_futures:
                    future = self._response_futures[request_id]
                    if not future.done():
                        future.set_result(request_json)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error receiving request: {e}")
                await asyncio.sleep(0.1)

    async def _pull_receiver(self) -> None:
        """Background task for receiving data from the pull socket."""
        while not self._is_shutdown:
            if not self._is_initialized or not self.pull_socket:
                # Not initialized yet, wait a bit and check again
                await asyncio.sleep(0.1)
                continue

            try:
                # Receive data
                message_bytes = await self.pull_socket.recv()
                message_json = message_bytes.decode()
                message = json.loads(message_json)

                # Extract data
                source = message.get("source")
                data = message.get("data", {})

                # Call callbacks
                if source in self._pull_callbacks:
                    for callback in self._pull_callbacks[source]:
                        try:
                            await callback(data)
                        except Exception as e:
                            logger.error(
                                f"Error in pull callback for source {source}: {e}"
                            )
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error receiving pull data: {e}")
                await asyncio.sleep(0.1)

    async def push(self, target: str, data: Dict[str, Any]) -> bool:
        """Push data to a target using ZeroMQ PUSH pattern.

        Args:
            target: Target endpoint to push data to
            data: Data to be pushed

        Returns:
            True if data was pushed successfully, False otherwise
        """
        if not self._is_initialized or self._is_shutdown:
            logger.error(
                "Cannot push data: communication not initialized or already shut down"
            )
            return False

        try:
            # Add metadata to message
            message = {
                "source": self.config.client_id,
                "target": target,
                "timestamp": time.time(),
                "data": data,
            }

            # Serialize message
            message_json = json.dumps(message)

            # Send message
            await self.push_socket.send_string(message_json)
            return True
        except Exception as e:
            logger.error(f"Error pushing data to {target}: {e}")
            return False

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
        if not self._is_initialized or self._is_shutdown:
            logger.error(
                "Cannot pull data: communication not initialized or already shut down"
            )
            if callback:
                return False
            else:
                return {
                    "status": "error",
                    "message": "Communication not initialized or already shut down",
                }

        try:
            # If callback is provided, register it
            if callback:
                if source not in self._pull_callbacks:
                    self._pull_callbacks[source] = []

                self._pull_callbacks[source].append(callback)
                logger.info(f"Registered pull callback for source {source}")
                return True

            # If no callback, wait for the next message
            else:
                # Create a temporary callback and future to receive one message
                future = asyncio.Future()

                # Define temporary callback that resolves the future
                def temp_callback(data):
                    if not future.done():
                        future.set_result(data)

                # Register temporary callback
                if source not in self._pull_callbacks:
                    self._pull_callbacks[source] = []

                self._pull_callbacks[source].append(temp_callback)

                try:
                    # Wait for data with timeout
                    data = await asyncio.wait_for(future, timeout=5.0)
                    return data
                finally:
                    # Clean up temporary callback
                    if source in self._pull_callbacks:
                        if temp_callback in self._pull_callbacks[source]:
                            self._pull_callbacks[source].remove(temp_callback)

                        # Remove the source entry if no callbacks remain
                        if not self._pull_callbacks[source]:
                            del self._pull_callbacks[source]

        except asyncio.TimeoutError:
            logger.error(f"Timeout waiting for data from {source}")
            return {"status": "error", "message": "Pull timed out"}
        except Exception as e:
            logger.error(f"Error pulling data from {source}: {e}")
            if callback:
                return False
            else:
                return {"status": "error", "message": str(e)}
