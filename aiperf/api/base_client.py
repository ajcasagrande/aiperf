from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Union

class BaseClient(ABC):
    """Base client for API endpoints.
    
    Abstract base class for all API clients. Provides common interface
    for interacting with different API types.
    """
    
    @abstractmethod
    async def initialize(self) -> bool:
        """Initialize the client.
        
        Returns:
            True if initialization was successful, False otherwise
        """
        pass
    
    @abstractmethod
    async def shutdown(self) -> bool:
        """Gracefully shutdown the client.
        
        Returns:
            True if shutdown was successful, False otherwise
        """
        pass
    
    @abstractmethod
    async def send_request(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """Send a request to the endpoint.
        
        Args:
            request_data: Request data
            
        Returns:
            Response data
        """
        pass
    
    @abstractmethod
    async def health_check(self) -> bool:
        """Check if the endpoint is healthy.
        
        Returns:
            True if the endpoint is healthy, False otherwise
        """
        pass 