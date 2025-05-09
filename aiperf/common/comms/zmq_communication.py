import asyncio
import json
import logging
import uuid
from typing import Callable, Optional, Union

import zmq
import zmq.asyncio

from aiperf.common.comms.communication import Communication
from aiperf.common.models.comms import ZMQCommunicationConfig
from aiperf.common.models.messages import BaseMessage, MessageType
from aiperf.common.models.push_pull import PullData, PushData
from aiperf.common.models.request_response import (
    RequestData,
    RequestStateInfo,
    ResponseData,
)

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
            message: Message to publish (must be a Pydantic model)

        Returns:
            True if message was published successfully, False otherwise
        """
        if not self._is_initialized or self._is_shutdown:
            logger.error(
                "Cannot publish message: communication not initialized or already shut down"
            )
            return False

        try:
            # Serialize message using Pydantic's built-in method
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
        self, topic: str, callback: Callable[[BaseMessage], None]
    ) -> bool:
        """Subscribe to a topic.

        Args:
            topic: Topic to subscribe to
            callback: Function to call when a message is received (receives BaseMessage object)

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
        if not self._is_initialized or self._is_shutdown:
            logger.error(
                "Cannot send request: communication not initialized or already shut down"
            )
            return ResponseData(
                request_id="error",
                client_id=self.config.client_id,
                status="error",
                message="Communication not initialized or already shut down",
            )

        try:
            # Set target if not already set
            if not request_data.target:
                request_data.target = target

            # Ensure client_id is set
            if not request_data.client_id:
                request_data.client_id = self.config.client_id

            # Generate request ID if not provided
            if not request_data.request_id:
                request_data.request_id = str(uuid.uuid4())

            # Serialize request
            request_json = request_data.model_dump_json()

            # Create future for response
            future = asyncio.Future()
            self._response_futures[request_data.request_id] = future

            # Send request
            await self.req_socket.send_string(request_json)

            # Wait for response with timeout
            try:
                response_json = await asyncio.wait_for(future, timeout)

                # Parse JSON first, then create the ResponseData object
                response_dict = json.loads(response_json)
                response = ResponseData(**response_dict)
                return response

            except asyncio.TimeoutError:
                logger.error(
                    f"Timeout waiting for response to request {request_data.request_id}"
                )
                self._response_futures.pop(request_data.request_id, None)

                return ResponseData(
                    request_id=request_data.request_id,
                    client_id=self.config.client_id,
                    status="error",
                    message="Request timed out",
                )
            finally:
                # Clean up future
                self._response_futures.pop(request_data.request_id, None)
        except Exception as e:
            logger.error(f"Error sending request to {target}: {e}")

            return ResponseData(
                request_id=request_data.request_id
                if hasattr(request_data, "request_id")
                else str(uuid.uuid4()),
                client_id=self.config.client_id,
                status="error",
                message=str(e),
            )

    async def respond(self, target: str, response: ResponseData) -> bool:
        """Send a response to a request.

        Args:
            target: Target component to send response to
            response: Response message (must be a ResponseData instance)

        Returns:
            True if response was sent successfully, False otherwise
        """
        if not self._is_initialized or self._is_shutdown:
            logger.error(
                "Cannot send response: communication not initialized or already shut down"
            )
            return False

        try:
            # Serialize response using Pydantic's built-in method
            response_json = response.model_dump_json()

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

                # Parse JSON to get the message data and reconstruct into BaseMessage object
                message_dict = json.loads(message_json)

                # Determine message type and create appropriate object
                # This requires knowing the message type from the topic or message content
                # For simplicity, just using BaseMessage here but in a real implementation
                # you would need to determine the proper subclass
                from aiperf.common.models.messages import (
                    CommandMessage,
                    DataMessage,
                    HeartbeatMessage,
                    RegistrationMessage,
                    ResponseMessage,
                    StatusMessage,
                )

                # Note: This is a simplified approach - in a real implementation,
                # you would need more sophisticated logic to determine the message type
                if "message_type" in message_dict:
                    msg_type = message_dict.get("message_type")
                    if msg_type == MessageType.STATUS.value:
                        message = StatusMessage(**message_dict)
                    elif msg_type == MessageType.HEARTBEAT.value:
                        message = HeartbeatMessage(**message_dict)
                    elif msg_type == MessageType.COMMAND.value:
                        message = CommandMessage(**message_dict)
                    elif msg_type == MessageType.RESPONSE.value:
                        message = ResponseMessage(**message_dict)
                    elif msg_type == MessageType.DATA.value:
                        message = DataMessage(**message_dict)
                    elif msg_type == MessageType.REGISTRATION.value:
                        message = RegistrationMessage(**message_dict)
                    else:
                        message = BaseMessage(**message_dict)
                elif topic.startswith("request."):
                    message = RequestData(**message_dict)
                elif topic.startswith("response."):
                    message = ResponseData(**message_dict)
                else:
                    # Default to base message if type can't be determined
                    message = BaseMessage(**message_dict)

                # Call callbacks with the parsed message object
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

                # Parse JSON to create RequestData object
                request_dict = json.loads(request_json)
                request = RequestData(**request_dict)
                request_id = request.request_id

                # Store request data
                self._response_data[request_id] = request

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

                # Parse JSON into a PullData object
                message_dict = json.loads(message_json)
                pull_data = PullData(**message_dict)
                source = pull_data.source

                # Call callbacks with PullData object
                if source in self._pull_callbacks:
                    for callback in self._pull_callbacks[source]:
                        try:
                            await callback(pull_data)
                        except Exception as e:
                            logger.error(
                                f"Error in pull callback for source {source}: {e}"
                            )
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error receiving data from pull socket: {e}")
                await asyncio.sleep(0.1)

    async def push(self, target: str, data: PushData) -> bool:
        """Push data to a target.

        Args:
            target: Target endpoint to push data to
            data: Data to be pushed (must be a PushData instance)

        Returns:
            True if data was pushed successfully, False otherwise
        """
        if not self._is_initialized or self._is_shutdown:
            logger.error(
                "Cannot push data: communication not initialized or already shut down"
            )
            return False

        try:
            # Ensure source is set if not already
            if not data.source:
                data.source = self.config.client_id

            # Serialize data directly using Pydantic's built-in method
            data_json = data.model_dump_json()

            # Send data
            await self.push_socket.send_string(data_json)
            logger.debug(f"Pushed data to {target}")
            return True
        except Exception as e:
            logger.error(f"Error pushing data to {target}: {e}")
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
        if not self._is_initialized or self._is_shutdown:
            logger.error(
                "Cannot pull data: communication not initialized or already shut down"
            )
            return False if callback else PullData(source="", data={})

        try:
            # If callback is provided, register it
            if callback:
                if source not in self._pull_callbacks:
                    self._pull_callbacks[source] = []
                self._pull_callbacks[source].append(callback)
                logger.debug(f"Registered pull callback for {source}")
                return True

            # If no callback, wait for message
            else:
                # Receive data
                message_bytes = await self.pull_socket.recv()
                message_json = message_bytes.decode()

                # Parse JSON into a PullData object
                message_dict = json.loads(message_json)
                pull_data = PullData(**message_dict)
                return pull_data
        except Exception as e:
            logger.error(f"Error pulling data from {source}: {e}")
            return False if callback else PullData(source="", data={})

    async def dump_request_state(self) -> RequestStateInfo:
        """Dump the current state of requests and responses for debugging.

        Returns:
            RequestStateInfo model with debugging information
        """
        try:
            pending_requests = list(self._response_futures.keys())
            client_count = 1  # Just this instance in ZMQ mode

            # Create and return RequestStateInfo model directly
            return RequestStateInfo(
                pending_requests=pending_requests,
                pending_request_count=len(pending_requests),
                client_count=client_count,
                subscription_count=sum(
                    len(callbacks) for callbacks in self._subscribers.values()
                ),
                response_topics=[],
                client_ids=[self.config.client_id],
            )
        except Exception as e:
            logger.error(f"Error dumping request state: {e}")
            return RequestStateInfo(client_count=0, error=str(e))
