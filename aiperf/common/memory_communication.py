import asyncio
import logging
import time
import uuid
from typing import Any, Dict, List, Optional, Callable, Set

from .communication import Communication

logger = logging.getLogger(__name__)

class MemoryCommunication(Communication):
    """In-memory implementation of the Communication interface.
    
    Uses Python's asyncio for in-memory communication between components.
    Useful for testing and small-scale deployments.
    """
    
    # Shared state for all instances
    _topics: Dict[str, Set[str]] = {}  # Topic -> client IDs
    _subscribers: Dict[str, Dict[str, List[Callable]]] = {}  # Topic -> {client_id -> callbacks}
    _messages: Dict[str, asyncio.Queue] = {}  # client_id -> message queue
    _requests: Dict[str, asyncio.Queue] = {}  # target -> request queue
    _responses: Dict[str, Dict[str, asyncio.Future]] = {}  # client_id -> {request_id -> future}
    
    def __init__(self, client_id: Optional[str] = None):
        """Initialize in-memory communication.
        
        Args:
            client_id: Optional client ID, will be generated if not provided
        """
        self.client_id = client_id or f"client_{uuid.uuid4().hex[:8]}"
        self._is_initialized = False
        self._is_shutdown = False
        
    async def initialize(self) -> bool:
        """Initialize communication channels.
        
        Returns:
            True if initialization was successful, False otherwise
        """
        if self._is_initialized:
            return True
            
        try:
            # Create message queue for this client
            MemoryCommunication._messages[self.client_id] = asyncio.Queue()
            
            # Create request queue for this client
            MemoryCommunication._requests[self.client_id] = asyncio.Queue()
            
            # Create response futures map for this client
            MemoryCommunication._responses[self.client_id] = {}
            
            # Start background tasks for processing messages and requests
            asyncio.create_task(self._process_messages())
            asyncio.create_task(self._process_requests())
            
            self._is_initialized = True
            logger.info(f"In-memory communication initialized for client {self.client_id}")
            return True
        except Exception as e:
            logger.error(f"Error initializing in-memory communication: {e}")
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
            logger.info(f"Shutting down in-memory communication for client {self.client_id}")
            
            # Remove message queue for this client
            MemoryCommunication._messages.pop(self.client_id, None)
            
            # Remove request queue for this client
            MemoryCommunication._requests.pop(self.client_id, None)
            
            # Remove response futures for this client
            MemoryCommunication._responses.pop(self.client_id, None)
            
            # Remove subscriptions for this client
            for topic, clients in MemoryCommunication._topics.items():
                if self.client_id in clients:
                    clients.remove(self.client_id)
                    
            for topic, clients in MemoryCommunication._subscribers.items():
                clients.pop(self.client_id, None)
            
            self._is_shutdown = True
            self._is_initialized = False
            return True
        except Exception as e:
            logger.error(f"Error shutting down in-memory communication: {e}")
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
            # Check if topic exists
            if topic not in MemoryCommunication._topics:
                # No subscribers for this topic
                return True
                
            # Add metadata to message
            enriched_message = {
                "topic": topic,
                "client_id": self.client_id,
                "timestamp": time.time(),
                "data": message
            }
            
            # Queue message for all subscribed clients
            for client_id in MemoryCommunication._topics[topic]:
                if client_id != self.client_id:  # Don't send to self
                    if client_id in MemoryCommunication._messages:
                        await MemoryCommunication._messages[client_id].put(enriched_message)
                    
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
            # Create topic if it doesn't exist
            if topic not in MemoryCommunication._topics:
                MemoryCommunication._topics[topic] = set()
                
            # Add client to topic
            MemoryCommunication._topics[topic].add(self.client_id)
            
            # Create subscribers for topic if it doesn't exist
            if topic not in MemoryCommunication._subscribers:
                MemoryCommunication._subscribers[topic] = {}
                
            # Create subscribers for client if it doesn't exist
            if self.client_id not in MemoryCommunication._subscribers[topic]:
                MemoryCommunication._subscribers[topic][self.client_id] = []
                
            # Add callback to subscribers
            MemoryCommunication._subscribers[topic][self.client_id].append(callback)
            
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
            # Check if target exists
            if target not in MemoryCommunication._requests:
                logger.error(f"Target component not found: {target}")
                return {"status": "error", "message": f"Target component not found: {target}"}
                
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
            
            # Create future for response
            future = asyncio.Future()
            MemoryCommunication._responses[self.client_id][request_id] = future
            
            # Queue request for target
            await MemoryCommunication._requests[target].put(enriched_request)
            
            # Wait for response with timeout
            try:
                response = await asyncio.wait_for(future, timeout)
                return response.get("data", {})
            except asyncio.TimeoutError:
                logger.error(f"Timeout waiting for response to request {request_id}")
                MemoryCommunication._responses[self.client_id].pop(request_id, None)
                return {"status": "error", "message": "Request timed out"}
            finally:
                # Clean up future
                MemoryCommunication._responses[self.client_id].pop(request_id, None)
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
            # Check if target exists
            if target not in MemoryCommunication._responses:
                logger.error(f"Target component not found: {target}")
                return False
                
            # Find request ID in response
            request_id = response.get("request_id")
            if not request_id:
                logger.error("Response missing request_id")
                return False
                
            # Check if future exists for request
            if request_id not in MemoryCommunication._responses[target]:
                logger.error(f"No pending request with ID {request_id} for target {target}")
                return False
                
            # Add metadata to response
            enriched_response = {
                "request_id": request_id,
                "client_id": self.client_id,
                "target": target,
                "timestamp": time.time(),
                "data": response
            }
            
            # Resolve future with response
            future = MemoryCommunication._responses[target][request_id]
            if not future.done():
                future.set_result(enriched_response)
                
            return True
        except Exception as e:
            logger.error(f"Error sending response to {target}: {e}")
            return False
    
    async def _process_messages(self) -> None:
        """Background task for processing messages."""
        while self._is_initialized and not self._is_shutdown:
            try:
                if self.client_id not in MemoryCommunication._messages:
                    # Client has been shut down
                    break
                    
                # Get message from queue
                message = await MemoryCommunication._messages[self.client_id].get()
                
                # Extract message data
                topic = message.get("topic")
                data = message.get("data", {})
                
                # Call callbacks for topic
                if (topic in MemoryCommunication._subscribers and 
                    self.client_id in MemoryCommunication._subscribers[topic]):
                    callbacks = MemoryCommunication._subscribers[topic][self.client_id]
                    for callback in callbacks:
                        try:
                            callback(data)
                        except Exception as e:
                            logger.error(f"Error in subscriber callback for topic {topic}: {e}")
            except Exception as e:
                logger.error(f"Error processing message: {e}")
                await asyncio.sleep(0.1)
    
    async def _process_requests(self) -> None:
        """Background task for processing requests."""
        while self._is_initialized and not self._is_shutdown:
            try:
                if self.client_id not in MemoryCommunication._requests:
                    # Client has been shut down
                    break
                    
                # Get request from queue
                request = await MemoryCommunication._requests[self.client_id].get()
                
                # Emit event for request handler
                # In a real implementation, this would trigger a call to handle_request
                request_id = request.get("request_id")
                source_client = request.get("client_id")
                data = request.get("data", {})
                
                # For testing purposes, echo the request as a response
                # In a real implementation, this would be handled by the component
                if source_client in MemoryCommunication._responses:
                    if request_id in MemoryCommunication._responses[source_client]:
                        future = MemoryCommunication._responses[source_client][request_id]
                        if not future.done():
                            response = {
                                "request_id": request_id,
                                "client_id": self.client_id,
                                "target": source_client,
                                "timestamp": time.time(),
                                "data": {"echo": data}
                            }
                            future.set_result(response)
            except Exception as e:
                logger.error(f"Error processing request: {e}")
                await asyncio.sleep(0.1) 