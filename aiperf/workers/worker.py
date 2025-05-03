import uuid
import asyncio
import logging
from abc import abstractmethod
from typing import Any, Dict, List, Optional, Tuple, Union

from ..common.base_manager import BaseComponent
from ..common.models import Conversation, ConversationTurn, TimingCredit
from ..config.config_models import EndpointConfig

class Worker(BaseComponent):
    """Worker for AIPerf.
    
    Responsible for issuing requests to endpoints based on timing credits
    and data from the dataset manager. Handles the conversation flow and
    records results.
    """
    
    def __init__(self, endpoint_config: EndpointConfig, component_id: Optional[str] = None):
        """Initialize the worker.
        
        Args:
            endpoint_config: Endpoint configuration
            component_id: Optional component ID
        """
        super().__init__(component_id=component_id or f"worker_{uuid.uuid4().hex[:8]}", 
                         config=endpoint_config.__dict__)
        self.endpoint_config = endpoint_config
        self._active_conversations: Dict[str, Conversation] = {}
        self._is_initialized = False
        self._lock = asyncio.Lock()
        self._idle = True
    
    async def initialize(self) -> bool:
        """Initialize the worker.
        
        Returns:
            True if initialization was successful, False otherwise
        """
        self.logger.info(f"Initializing worker for endpoint: {self.endpoint_config.name}")
        
        try:
            # Initialize client for endpoint based on configuration
            await self._initialize_client()
            
            self._is_initialized = True
            self._is_ready = True
            return True
        except Exception as e:
            self.logger.error(f"Error initializing worker: {e}")
            return False
    
    @abstractmethod
    async def _initialize_client(self) -> bool:
        """Initialize client for the endpoint.
        
        Returns:
            True if initialization was successful, False otherwise
        """
        pass
    
    async def ready_check(self) -> bool:
        """Check if the worker is ready.
        
        Returns:
            True if the worker is ready, False otherwise
        """
        return self._is_initialized and self._is_ready
    
    async def shutdown(self) -> bool:
        """Gracefully shutdown the worker.
        
        Returns:
            True if shutdown was successful, False otherwise
        """
        self.logger.info("Shutting down worker")
        self._is_shutdown = True
        return True
    
    @property
    def is_idle(self) -> bool:
        """Check if the worker is idle.
        
        Returns:
            True if the worker is idle, False otherwise
        """
        return self._idle
    
    @abstractmethod
    async def process_credit(self, credit: TimingCredit, conversation_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Process a timing credit with conversation data.
        
        Args:
            credit: Timing credit
            conversation_data: Conversation data from dataset manager
            
        Returns:
            Response data or None if processing failed
        """
        pass
    
    @abstractmethod
    async def send_request(self, request_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Send a request to the endpoint.
        
        Args:
            request_data: Request data
            
        Returns:
            Response data or None if request failed
        """
        pass
    
    @abstractmethod
    async def handle_response(self, conversation_id: str, request_data: Dict[str, Any], 
                             response_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Handle a response from the endpoint.
        
        Args:
            conversation_id: Conversation ID
            request_data: Request data
            response_data: Response data
            
        Returns:
            Processed response data or None if processing failed
        """
        pass
