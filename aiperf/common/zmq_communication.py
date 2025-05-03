import asyncio
import json
import logging
import zmq
import zmq.asyncio
import time
import uuid
from typing import Any, Dict, List, Optional, Callable

from .communication import Communication

logger = logging.getLogger(__name__)

class ZMQCommunication(Communication):
    """ZeroMQ-based implementation of the Communication interface.
    
    Uses ZeroMQ for publish/subscribe and request/reply patterns to
    facilitate communication between AIPerf components.
    """
    
    def __init__(self, 
                 pub_address: str = "tcp://127.0.0.1:5555",
                 sub_address: str = "tcp://127.0.0.1:5555",
                 req_address: str = "tcp://127.0.0.1:5556",
                 rep_address: str = "tcp://127.0.0.1:5556",
                 client_id: Optional[str] = None):
        """Initialize ZMQ communication.
        
        Args:
            pub_address: Address for publishing messages
            sub_address: Address for subscribing to messages
            req_address: Address for sending requests
            rep_address: Address for receiving requests and sending responses
            client_id: Optional client ID, will be generated if not provided
        """
        self.pub_address = pub_address
        self.sub_address = sub_address
        self.req_address = req_address
        self.rep_address = rep_address
        self.client_id = client_id or f"client_{uuid.uuid4().hex[:8]}"
        
        self.context = zmq.asyncio.Context()
        self.pub_socket = None
        self.sub_socket = None
        self.req_socket = None
        self.rep_socket = None
        
        self._subscribers = {}
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
            # Set up publish socket
            self.pub_socket = self.context.socket(zmq.PUB)
            self.pub_socket.connect(self.pub_address)
            
            # Set up subscribe socket
            self.sub_socket = self.context.socket(zmq.SUB)
            self.sub_socket.connect(self.sub_address)
            
            # Set up request socket
            self.req_socket = self.context.socket(zmq.REQ)
            self.req_socket.connect(self.req_address)
            
            # Set up reply socket
            self.rep_socket = self.context.socket(zmq.REP)
            self.rep_socket.bind(self.rep_address)
            
            # Start background tasks for receiving messages
            asyncio.create_task(self._sub_receiver())
            asyncio.create_task(self._rep_receiver())
            
            self._is_initialized = True
            logger.info(f"ZMQ communication initialized for client {self.client_id}")
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
            logger.info(f"Shutting down ZMQ communication for client {self.client_id}")
            
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
            
            # Clear subscribers
            self._subscribers = {}
            
            self._is_shutdown = True
            self._is_initialized = False
            return True
        except Exception as e:
            logger.error(f"Error shutting down ZMQ communication: {e}")
            return False
    
    async def publish(self, topic: str, message: Dict[str, Any]) -> bool:
        """Publish a message to a topic.
        
        Args:
            topic: Topic to publish to
            message: Message to publish
            
        Returns:
            True if message was published successfully, False otherwise
        """
        if not self._is_initialized or self._is_shutdown:
            logger.error("Cannot publish message: communication not initialized or already shut down")
            return False
            
        try:
            # Add client ID and timestamp to message
            enriched_message = {
                "client_id": self.client_id,
                "timestamp": time.time(),
                "data": message
            }
            
            # Serialize message
            message_json = json.dumps(enriched_message)
            
            # Publish message
            await self.pub_socket.send_multipart([topic.encode(), message_json.encode()])
            return True
        except Exception as e:
            logger.error(f"Error publishing message to topic {topic}: {e}")
            return False
    
    async def subscribe(self, topic: str, callback: Callable[[Dict[str, Any]], None]) -> bool:
        """Subscribe to a topic.
        
        Args:
            topic: Topic to subscribe to
            callback: Function to call when a message is received
            
        Returns:
            True if subscription was successful, False otherwise
        """
        if not self._is_initialized or self._is_shutdown:
            logger.error("Cannot subscribe to topic: communication not initialized or already shut down")
            return False
            
        try:
            # Subscribe to topic
            await self.sub_socket.subscribe(topic.encode())
            
            # Register callback
            if topic not in self._subscribers:
                self._subscribers[topic] = []
            self._subscribers[topic].append(callback)
            
            logger.info(f"Subscribed to topic: {topic}")
            return True
        except Exception as e:
            logger.error(f"Error subscribing to topic {topic}: {e}")
            return False
    
    async def request(self, target: str, request: Dict[str, Any], timeout: float = 5.0) -> Dict[str, Any]:
        """Send a request and wait for a response.
        
        Args:
            target: Target component to send request to
            request: Request message
            timeout: Timeout in seconds
            
        Returns:
            Response message
        """
        if not self._is_initialized or self._is_shutdown:
            logger.error("Cannot send request: communication not initialized or already shut down")
            return {"status": "error", "message": "Communication not initialized or already shut down"}
            
        try:
            # Generate request ID
            request_id = str(uuid.uuid4())
            
            # Add metadata to request
            enriched_request = {
                "request_id": request_id,
                "client_id": self.client_id,
                "target": target,
                "timestamp": time.time(),
                "data": request
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
            logger.error("Cannot send response: communication not initialized or already shut down")
            return False
            
        try:
            # Add metadata to response
            enriched_response = {
                "client_id": self.client_id,
                "target": target,
                "timestamp": time.time(),
                "data": response
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
        """Background task for receiving subscription messages."""
        while self._is_initialized and not self._is_shutdown:
            try:
                # Receive message
                [topic_bytes, message_bytes] = await self.sub_socket.recv_multipart()
                topic = topic_bytes.decode()
                message_json = message_bytes.decode()
                message = json.loads(message_json)
                
                # Process message
                if topic in self._subscribers:
                    data = message.get("data", {})
                    for callback in self._subscribers[topic]:
                        try:
                            callback(data)
                        except Exception as e:
                            logger.error(f"Error in subscriber callback for topic {topic}: {e}")
            except Exception as e:
                logger.error(f"Error receiving subscription message: {e}")
                await asyncio.sleep(0.1)
    
    async def _rep_receiver(self) -> None:
        """Background task for receiving requests and sending responses."""
        while self._is_initialized and not self._is_shutdown:
            try:
                # Receive request
                request_json = await self.rep_socket.recv_string()
                request = json.loads(request_json)
                
                # Extract request data
                request_id = request.get("request_id")
                target = request.get("target")
                data = request.get("data", {})
                
                # Store response data
                self._response_data[request_id] = data
                
                # Resolve future if it exists
                if request_id in self._response_futures:
                    future = self._response_futures[request_id]
                    if not future.done():
                        future.set_result(request_json)
            except Exception as e:
                logger.error(f"Error receiving request: {e}")
                await asyncio.sleep(0.1) 