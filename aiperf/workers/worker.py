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

    def __init__(
        self, endpoint_config: EndpointConfig, component_id: Optional[str] = None
    ):
        """Initialize the worker.

        Args:
            endpoint_config: Endpoint configuration
            component_id: Optional component ID
        """
        self.component_id = component_id or f"worker_{uuid.uuid4().hex[:8]}"
        self.endpoint_config = endpoint_config
        self.logger = logging.getLogger(f"worker.{self.component_id}")
        self._is_initialized = False
        self._is_shutdown = False
        self._idle = True
        self._lock = asyncio.Lock()
        self._active_conversations: Dict[str, Conversation] = {}

    async def initialize(self) -> bool:
        """Initialize the worker.

        Returns:
            True if initialization was successful, False otherwise
        """
        try:
            self.logger.info(f"Initializing worker {self.component_id}")

            # Initialize client for API requests
            if hasattr(self, "_initialize_client"):
                success = await self._initialize_client()
                if not success:
                    self.logger.error("Failed to initialize API client")
                    return False

            self._is_initialized = True
            self.logger.info(f"Worker {self.component_id} initialized successfully")
            return True
        except Exception as e:
            self.logger.error(f"Error initializing worker: {e}")
            return False

    async def _initialize_client(self) -> bool:
        """Initialize client for the endpoint.

        Returns:
            True if initialization was successful, False otherwise
        """
        # This is implemented by concrete subclasses
        # but no longer marked as @abstractmethod to allow worker_manager
        # to import this class without instantiating it directly
        raise NotImplementedError(
            "_initialize_client must be implemented by subclasses"
        )

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
        self._is_shutdown = True
        self._is_initialized = False
        return True

    @property
    def is_idle(self) -> bool:
        """Check if the worker is idle.

        Returns:
            True if the worker is idle, False otherwise
        """
        return self._idle

    @abstractmethod
    async def process_credit(
        self, credit: TimingCredit, conversation_data: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Process a timing credit with conversation data.

        Args:
            credit: Timing credit
            conversation_data: Conversation data from dataset manager

        Returns:
            Response data or None if processing failed
        """
        pass

    @abstractmethod
    async def send_request(
        self, request_data: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Send a request to the endpoint.

        Args:
            request_data: Request data

        Returns:
            Response data or None if request failed
        """
        pass

    @abstractmethod
    async def handle_response(
        self,
        conversation_id: str,
        request_data: Dict[str, Any],
        response_data: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        """Handle a response from the endpoint.

        Args:
            conversation_id: Conversation ID
            request_data: Request data
            response_data: Response data

        Returns:
            Processed response data or None if processing failed
        """
        pass

    async def keep_alive(self) -> bool:
        """Check if the worker is alive and healthy.

        Returns:
            True if worker is healthy, False otherwise
        """
        return self._is_initialized and not self._is_shutdown

    def get_stats(self) -> Dict[str, Any]:
        """Get worker statistics.

        Returns:
            Dictionary with worker statistics
        """
        return {
            "worker_id": self.component_id,
            "endpoint": self.endpoint_config.name,
            "is_idle": self._idle,
            "is_initialized": self._is_initialized,
            "is_shutdown": self._is_shutdown,
            "active_conversations": len(self._active_conversations),
        }
