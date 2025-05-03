from abc import ABC, abstractmethod
import logging
from typing import Any, Dict, Optional, List, Union

class BaseComponent(ABC):
    """Base class for all components in AIPerf system."""
    
    def __init__(self, component_id: str, config: Optional[Dict[str, Any]] = None):
        """Initialize the component.
        
        Args:
            component_id: Unique identifier for this component
            config: Optional configuration dictionary
        """
        self.component_id = component_id
        self.config = config or {}
        self.logger = logging.getLogger(f"{self.__class__.__name__}:{component_id}")
        self._is_ready = False
        self._is_shutdown = False
    
    @abstractmethod
    async def initialize(self) -> bool:
        """Initialize the component with its configuration.
        
        Returns:
            True if initialization was successful, False otherwise
        """
        pass
    
    @abstractmethod
    async def ready_check(self) -> bool:
        """Check if the component is ready.
        
        Returns:
            True if the component is ready, False otherwise
        """
        pass
    
    @abstractmethod
    async def shutdown(self) -> bool:
        """Gracefully shutdown the component.
        
        Returns:
            True if shutdown was successful, False otherwise
        """
        pass
    
    async def keep_alive(self) -> bool:
        """Health check for this component.
        
        Returns:
            True if the component is healthy, False otherwise
        """
        return self._is_ready and not self._is_shutdown
    
    async def configure(self, config: Dict[str, Any]) -> bool:
        """Update the component configuration.
        
        Args:
            config: New configuration dictionary
        
        Returns:
            True if configuration was successful, False otherwise
        """
        self.config.update(config)
        return True

class BaseManager(BaseComponent):
    """Base class for all managers in AIPerf system."""
    
    def __init__(self, component_id: str, config: Optional[Dict[str, Any]] = None):
        """Initialize the manager.
        
        Args:
            component_id: Unique identifier for this manager
            config: Optional configuration dictionary
        """
        super().__init__(component_id, config)
    
    @abstractmethod
    async def publish_identity(self) -> bool:
        """Publish this manager's identity to the system.
        
        Returns:
            True if identity was published successfully, False otherwise
        """
        pass
    
    @abstractmethod
    async def handle_command(self, command: str, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Handle a command from the system controller.
        
        Args:
            command: Command string
            payload: Optional command payload
            
        Returns:
            Response dictionary with results
        """
        pass
