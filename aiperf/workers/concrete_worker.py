import uuid
import asyncio
import logging
import time
from typing import Any, Dict, List, Optional, Union

from .worker import Worker
from ..common.models import TimingCredit, Conversation, ConversationTurn
from ..config.config_models import EndpointConfig
from ..api.clients import ClientFactory
from ..api.base_client import BaseClient


class ConcreteWorker(Worker):
    """Concrete implementation of the Worker abstract class.

    Implements all required methods for a functional worker that can
    process credits, send requests, and handle responses.
    """

    def __init__(
        self, endpoint_config: EndpointConfig, component_id: Optional[str] = None
    ):
        """Initialize the concrete worker.

        Args:
            endpoint_config: Endpoint configuration
            component_id: Optional component ID
        """
        super().__init__(endpoint_config, component_id)
        self._client: Optional[BaseClient] = None
        self._current_credit: Optional[TimingCredit] = None
        self._last_request_time: Optional[float] = None
        self._credit_count = 0
        self._success_count = 0
        self._error_count = 0

    async def initialize(self) -> bool:
        """Initialize the worker.

        Returns:
            True if initialization was successful, False otherwise
        """
        try:
            self.logger.info(
                f"Initializing concrete worker {self.component_id} for endpoint: {self.endpoint_config.name}"
            )

            # Initialize client for the endpoint
            success = await self._initialize_client()
            if not success:
                self.logger.error(
                    f"Failed to initialize client for endpoint: {self.endpoint_config.name}"
                )
                return False

            self._is_initialized = True
            self.logger.info(
                f"Worker {self.component_id} initialized successfully with endpoint {self.endpoint_config.name}"
            )
            return True
        except Exception as e:
            self.logger.error(f"Error initializing worker: {e}")
            return False

    async def _initialize_client(self) -> bool:
        """Initialize client for the endpoint.

        Returns:
            True if initialization was successful, False otherwise
        """
        try:
            if self._client:
                # Client already initialized
                return True

            # Ensure debug_mode is properly set in the endpoint config
            debug_mode = False
            if (
                hasattr(self.endpoint_config, "metadata")
                and isinstance(self.endpoint_config.metadata, dict)
                and "debug_mode" in self.endpoint_config.metadata
            ):
                debug_mode = self.endpoint_config.metadata.get("debug_mode", False)
                self.logger.info(f"Using debug_mode={debug_mode} from endpoint config")
            else:
                self.logger.info(
                    "No debug_mode found in endpoint config, defaulting to False"
                )

                # Ensure metadata exists and is a dict
                if not hasattr(self.endpoint_config, "metadata") or not isinstance(
                    self.endpoint_config.metadata, dict
                ):
                    self.endpoint_config.metadata = {}

                # Explicitly set debug_mode in metadata
                self.endpoint_config.metadata["debug_mode"] = debug_mode

            # Log the authentication details (omitting sensitive information)
            auth_key = "PLACEHOLDER"
            if hasattr(self.endpoint_config.auth, "api_key"):
                auth_key = (
                    "VALID_KEY" if self.endpoint_config.auth.api_key else "EMPTY_KEY"
                )
                if self.endpoint_config.auth.api_key == "YOUR_API_KEY":
                    auth_key = "PLACEHOLDER_KEY"

            self.logger.debug(f"Auth key status: {auth_key}, debug_mode: {debug_mode}")

            # Create client through factory using the complete endpoint configuration
            self._client = ClientFactory.create_client(
                api_type=self.endpoint_config.api_type,
                url=self.endpoint_config.url,
                headers=self.endpoint_config.headers,
                auth=self.endpoint_config.auth,
                timeout=self.endpoint_config.timeout,
                metadata=self.endpoint_config.metadata,  # Pass through the metadata
            )

            if not self._client:
                self.logger.error(
                    f"Failed to create client for endpoint: {self.endpoint_config.name}"
                )
                return False

            # Initialize the client
            self.logger.debug("Initializing client...")
            success = await self._client.initialize()
            if not success:
                self.logger.error("Failed to initialize client")
                return False

            self.logger.info(
                f"Client initialized for endpoint: {self.endpoint_config.name}"
            )
            return True
        except Exception as e:
            self.logger.error(f"Error initializing client: {e}", exc_info=True)
            return False

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
        if not self._is_initialized or self._is_shutdown:
            self.logger.error(
                "Cannot process credit: worker not initialized or already shut down"
            )
            return None

        if not self._client:
            self.logger.error("Cannot process credit: client not initialized")
            return None

        try:
            # Increment credit count
            async with self._lock:
                self._credit_count += 1
                self._idle = False
                self._current_credit = credit

            # Get conversation ID or generate one
            conversation_id = conversation_data.get(
                "conversation_id", str(uuid.uuid4())
            )

            # Prepare request data
            request_data = self._prepare_request_data(conversation_data)

            # Record start time
            start_time = time.time()

            # Send request to endpoint
            self.logger.info(
                f"Sending request for credit {credit.credit_id}, conversation {conversation_id}"
            )
            response_data = await self.send_request(request_data)

            # Record end time
            end_time = time.time()
            processing_time = end_time - start_time

            if not response_data:
                self.logger.error(
                    f"Failed to get response for credit: {credit.credit_id}"
                )
                self._error_count += 1
                async with self._lock:
                    self._idle = True
                    self._current_credit = None
                return None

            # Log response status
            success = response_data.get("success", False)
            status_code = response_data.get("status_code", None)
            self.logger.info(
                f"Received response for credit {credit.credit_id}: success={success}, status_code={status_code}, processing_time={processing_time:.2f}s"
            )

            # Handle response
            processed_data = await self.handle_response(
                conversation_id, request_data, response_data
            )

            # Add timing information to the response
            if processed_data:
                processed_data["timing"] = {
                    "start_time": start_time,
                    "end_time": end_time,
                    "processing_time": processing_time,
                    "credit_id": credit.credit_id,
                    "scheduled_time": credit.scheduled_time,
                }

            self._success_count += 1

            async with self._lock:
                self._idle = True
                self._current_credit = None

            return processed_data
        except Exception as e:
            self.logger.error(f"Error processing credit: {e}")
            self._error_count += 1

            async with self._lock:
                self._idle = True
                self._current_credit = None

            return None

    def _prepare_request_data(
        self, conversation_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Prepare request data based on conversation data.

        Args:
            conversation_data: Conversation data from dataset manager

        Returns:
            Request data for the API client
        """
        # Default to chat completions if not specified
        api_endpoint = conversation_data.get("endpoint", "chat/completions")

        if self.endpoint_config.api_type == "openai":
            # Prepare OpenAI-compatible request
            messages = conversation_data.get("messages", [])
            if not messages and "prompt" in conversation_data:
                # Convert prompt to messages format if needed
                messages = [{"role": "user", "content": conversation_data["prompt"]}]

            model = conversation_data.get("model", "gpt-3.5-turbo")
            temperature = conversation_data.get("temperature", 0.7)
            max_tokens = conversation_data.get("max_tokens", 1024)

            return {
                "endpoint": api_endpoint,
                "model": model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "stream": conversation_data.get("stream", False),
            }
        else:
            # For other API types, pass through the request data
            return conversation_data

    async def send_request(
        self, request_data: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Send a request to the endpoint.

        Args:
            request_data: Request data

        Returns:
            Response data or None if request failed
        """
        if not self._client:
            self.logger.error("Cannot send request: client not initialized")
            return None

        try:
            response = await self._client.send_request(request_data)
            return response
        except Exception as e:
            self.logger.error(f"Error sending request: {e}")
            return None

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
        try:
            # Get conversation
            conversation = self._active_conversations.get(conversation_id)
            if not conversation:
                self.logger.warning(f"Conversation not found: {conversation_id}")
                conversation = Conversation(conversation_id=conversation_id)
                self._active_conversations[conversation_id] = conversation

            # Extract request details
            request_messages = request_data.get("messages", [])
            request_text = ""
            if request_messages:
                request_text = request_messages[-1].get("content", "")

            # Extract response details based on API type
            response_text = ""
            tokens_used = {
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0,
            }
            success = response_data.get("success", False)

            if success:
                if self.endpoint_config.api_type == "openai":
                    api_response = response_data.get("response", {})

                    # Handle streaming responses
                    if "chunks" in api_response:
                        chunks = api_response.get("chunks", [])
                        response_text = self._extract_text_from_chunks(chunks)
                    else:
                        # Handle standard response
                        choices = api_response.get("choices", [])
                        if choices:
                            if "message" in choices[0]:
                                response_text = (
                                    choices[0].get("message", {}).get("content", "")
                                )
                            elif "text" in choices[0]:
                                response_text = choices[0].get("text", "")

                        # Extract token usage if available
                        usage = api_response.get("usage", {})
                        if usage:
                            tokens_used = {
                                "prompt_tokens": usage.get("prompt_tokens", 0),
                                "completion_tokens": usage.get("completion_tokens", 0),
                                "total_tokens": usage.get("total_tokens", 0),
                            }
                else:
                    # Generic handling for other API types
                    response_text = str(response_data.get("response", ""))

            # Create a new conversation turn
            turn = ConversationTurn(
                request=request_text,
                response=response_text,
                success=success,
                tokens=tokens_used,
                metadata={"request": request_data, "raw_response": response_data},
            )

            # Add turn to conversation
            conversation.turns.append(turn)

            # Return processed data
            return {
                "conversation_id": conversation_id,
                "request": request_text,
                "response": response_text,
                "success": success,
                "tokens": tokens_used,
                "turn_index": len(conversation.turns) - 1,
            }
        except Exception as e:
            self.logger.error(f"Error handling response: {e}")
            return None

    def _extract_text_from_chunks(self, chunks: List[Dict[str, Any]]) -> str:
        """Extract text from streaming response chunks.

        Args:
            chunks: List of response chunks

        Returns:
            Extracted text
        """
        text = ""

        for chunk in chunks:
            choices = chunk.get("choices", [])
            if not choices:
                continue

            delta = choices[0].get("delta", {})
            if "content" in delta:
                text += delta["content"]

        return text

    async def shutdown(self) -> bool:
        """Gracefully shutdown the worker.

        Returns:
            True if shutdown was successful, False otherwise
        """
        self.logger.info("Shutting down worker")

        if self._client:
            try:
                await self._client.shutdown()
            except Exception as e:
                self.logger.error(f"Error shutting down client: {e}")

        self._is_shutdown = True
        return True

    def get_stats(self) -> Dict[str, Any]:
        """Get worker statistics.

        Returns:
            Dictionary with worker statistics
        """
        return {
            "worker_id": self.component_id,
            "endpoint": self.endpoint_config.name,
            "credit_count": self._credit_count,
            "success_count": self._success_count,
            "error_count": self._error_count,
            "is_idle": self._idle,
            "active_conversations": len(self._active_conversations),
        }
