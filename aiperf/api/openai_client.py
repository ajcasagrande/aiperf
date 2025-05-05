import aiohttp
import asyncio
import json
import logging
import time
from typing import Any, Dict, List, Optional, Union

from .base_client import BaseClient
from ..config.config_models import EndpointConfig


class OpenAIClient(BaseClient):
    """OpenAI API client.

    Client for interacting with OpenAI-compatible APIs. Supports chat completions
    and streaming responses.
    """

    def __init__(self, config: EndpointConfig):
        """Initialize the OpenAI client.

        Args:
            config: Endpoint configuration
        """
        self.config = config
        self.url = config.url
        self.headers = config.headers.copy()
        self.timeout = config.timeout
        self.logger = logging.getLogger(f"OpenAIClient:{config.name}")
        self.session: Optional[aiohttp.ClientSession] = None

        # Access metadata for debug mode
        self.debug_mode = False
        if hasattr(config, "metadata") and isinstance(config.metadata, dict):
            self.debug_mode = config.metadata.get("debug_mode", False)
            self.logger.info(f"Debug mode set to: {self.debug_mode}")

        # Set authentication if provided
        if config.auth:
            # Access api_key as a property of AuthConfig instead of using .get()
            api_key = getattr(config.auth, "api_key", None)
            if api_key:
                self.headers["Authorization"] = f"Bearer {api_key}"

    async def initialize(self) -> bool:
        """Initialize the client.

        Returns:
            True if initialization was successful, False otherwise
        """
        try:
            # Check if API key was provided
            auth_header = self.headers.get("Authorization", "")
            using_placeholder_key = (
                not auth_header
                or auth_header == "Bearer YOUR_API_KEY"
                or auth_header == "Bearer "
            )

            self.logger.info(
                f"Debug mode: {self.debug_mode}, Using placeholder key: {using_placeholder_key}"
            )

            if using_placeholder_key:
                if self.debug_mode:
                    self.logger.warning(
                        "Using placeholder API key in debug mode. Mock responses will be returned."
                    )
                    # In debug mode with placeholder key, we can still initialize successfully
                    # Session still needed for potential non-auth endpoints
                    self.session = aiohttp.ClientSession(headers=self.headers)
                    self.logger.info("Initialized with mock response capability")
                    return True
                else:
                    self.logger.error(
                        "No valid API key provided. Please set a valid API key in the config."
                    )
                    return False

            # Initialize session with a longer timeout to avoid initialization timeouts
            tcp_connector = aiohttp.TCPConnector(
                limit=100,  # Increase connection pool size
                ttl_dns_cache=300,  # Cache DNS results for 5 minutes
            )

            self.session = aiohttp.ClientSession(
                headers=self.headers,
                connector=tcp_connector,
                timeout=aiohttp.ClientTimeout(total=self.timeout),
            )

            # Perform basic validation
            if not self.url:
                self.logger.error("No API URL provided")
                return False

            self.logger.info(f"OpenAI client initialized for endpoint: {self.url}")
            return True
        except Exception as e:
            self.logger.error(f"Error initializing OpenAI client: {e}")
            return False

    async def shutdown(self) -> bool:
        """Gracefully shutdown the client.

        Returns:
            True if shutdown was successful, False otherwise
        """
        if self.session:
            try:
                await self.session.close()
                return True
            except Exception as e:
                self.logger.error(f"Error shutting down OpenAI client: {e}")
                return False
        return True

    async def send_request(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """Send a request to the OpenAI API.

        Args:
            request_data: Request data

        Returns:
            Response data
        """
        if not self.session and not self.debug_mode:
            raise RuntimeError("Client not initialized")

        # Check if we're in debug mode with a placeholder API key
        auth_header = self.headers.get("Authorization", "")
        using_placeholder_key = (
            not auth_header
            or auth_header == "Bearer YOUR_API_KEY"
            or auth_header == "Bearer "
        )

        if self.debug_mode and using_placeholder_key:
            # Return mock data for testing
            self.logger.info(
                "Debug mode active - returning mock data instead of sending API request"
            )
            return self._generate_mock_response(request_data)

        # Initialize session if it doesn't exist (this can happen in some edge cases)
        if not self.session:
            try:
                self.session = aiohttp.ClientSession(headers=self.headers)
            except Exception as e:
                self.logger.error(f"Failed to create session for request: {e}")
                return {
                    "error": str(e),
                    "success": False,
                    "elapsed_time": 0,
                }

        endpoint = request_data.get("endpoint", "chat/completions")

        # Determine endpoint URL
        # Add /v1/ prefix if it's not already part of the URL and endpoint doesn't start with v1/
        if "/v1/" not in self.url and not endpoint.startswith("v1/"):
            endpoint_url = f"{self.url.rstrip('/')}/v1/{endpoint}"
        else:
            endpoint_url = f"{self.url.rstrip('/')}/{endpoint}"

        # Clean up request data by removing endpoint
        clean_request_data = request_data.copy()
        clean_request_data.pop("endpoint", None)

        # Handle streaming
        stream = clean_request_data.get("stream", False)

        start_time = time.time()
        try:
            if stream:
                return await self._handle_streaming_request(
                    endpoint_url, clean_request_data
                )
            else:
                return await self._handle_standard_request(
                    endpoint_url, clean_request_data
                )
        except asyncio.TimeoutError as e:
            self.logger.error(f"Timeout sending request to OpenAI API: {e}")
            return {
                "error": f"Request timed out after {self.timeout} seconds",
                "success": False,
                "elapsed_time": time.time() - start_time,
                "is_timeout": True,
            }
        except Exception as e:
            self.logger.error(f"Error sending request to OpenAI API: {e}")
            return {
                "error": str(e),
                "success": False,
                "elapsed_time": time.time() - start_time,
            }

    def _generate_mock_response(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate a mock response for testing purposes.

        Args:
            request_data: Request data

        Returns:
            Mock response data
        """
        start_time = time.time()

        # Extract messages to generate appropriate response
        messages = request_data.get("messages", [])
        last_message = messages[-1] if messages else {"content": ""}
        prompt = last_message.get("content", "")

        # Create a simple mock completion
        mock_response = {
            "id": f"mock-response-{int(time.time())}",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": request_data.get("model", "gpt-3.5-turbo"),
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": f"This is a mock response to: {prompt[:50]}...",
                    },
                    "finish_reason": "stop",
                }
            ],
            "usage": {
                "prompt_tokens": len(prompt.split()),
                "completion_tokens": 10,
                "total_tokens": len(prompt.split()) + 10,
            },
        }

        # Add a small delay to simulate network latency
        time.sleep(0.2)

        elapsed_time = time.time() - start_time
        return {
            "response": mock_response,
            "status_code": 200,
            "success": True,
            "elapsed_time": elapsed_time,
            "is_mock": True,
        }

    async def _handle_standard_request(
        self, endpoint_url: str, request_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Handle a standard (non-streaming) request.

        Args:
            endpoint_url: Endpoint URL
            request_data: Request data

        Returns:
            Response data
        """
        if not self.session:
            raise RuntimeError("Client not initialized")

        start_time = time.time()
        try:
            self.logger.info(f"Sending standard request to: {endpoint_url}")
            async with self.session.post(
                endpoint_url,
                json=request_data,
                timeout=aiohttp.ClientTimeout(total=self.timeout),
            ) as response:
                # Check for 404 Not Found response from mock server
                if response.status == 404 and self.debug_mode:
                    self.logger.warning(
                        f"Received 404 from endpoint {endpoint_url} in debug mode. Falling back to mock response."
                    )
                    # Fall back to mock response in debug mode
                    return self._generate_mock_response(request_data)

                # Log response status
                self.logger.info(
                    f"Received response with status: {response.status} from {endpoint_url}"
                )

                try:
                    response_text = await response.text()
                    self.logger.debug(f"Response text: {response_text[:200]}...")

                    # Try to parse as JSON
                    try:
                        response_data = json.loads(response_text)
                    except json.JSONDecodeError as e:
                        self.logger.error(
                            f"JSON decode error: {e}, response: {response_text[:200]}..."
                        )
                        if self.debug_mode:
                            self.logger.warning(
                                "Using mock response due to JSON parsing error"
                            )
                            return self._generate_mock_response(request_data)
                        response_data = {"error": f"Invalid JSON response: {str(e)}"}
                except Exception as e:
                    self.logger.error(f"Error reading response: {e}")
                    if self.debug_mode:
                        self.logger.warning(
                            "Using mock response due to response reading error"
                        )
                        return self._generate_mock_response(request_data)
                    response_data = {"error": f"Error reading response: {str(e)}"}

                elapsed_time = time.time() - start_time
                self.logger.info(f"Request completed in {elapsed_time:.4f} seconds")

                return {
                    "response": response_data,
                    "status_code": response.status,
                    "success": response.status == 200,
                    "elapsed_time": elapsed_time,
                }
        except asyncio.TimeoutError as e:
            self.logger.error(f"Timeout during request to {endpoint_url}: {e}")
            if self.debug_mode:
                self.logger.warning(f"Using mock response due to timeout: {e}")
                return self._generate_mock_response(request_data)
            return {
                "error": f"Request timed out after {self.timeout} seconds",
                "status_code": 408,  # Request Timeout
                "success": False,
                "elapsed_time": time.time() - start_time,
                "is_timeout": True,
            }
        except aiohttp.ClientResponseError as e:
            self.logger.error(f"HTTP error during request: {e}")
            # Fall back to mock response in debug mode
            if self.debug_mode:
                self.logger.warning(
                    f"Using mock response due to ClientResponseError: {e}"
                )
                return self._generate_mock_response(request_data)
            return {
                "error": f"HTTP error: {e.status} - {e.message}",
                "status_code": e.status,
                "success": False,
                "elapsed_time": time.time() - start_time,
            }
        except Exception as e:
            self.logger.error(f"Error during request: {e}")
            # Fall back to mock response in debug mode
            if self.debug_mode:
                self.logger.warning(f"Using mock response due to error: {e}")
                return self._generate_mock_response(request_data)
            return {
                "error": str(e),
                "success": False,
                "elapsed_time": time.time() - start_time,
            }

    async def _handle_streaming_request(
        self, endpoint_url: str, request_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Handle a streaming request.

        Args:
            endpoint_url: Endpoint URL
            request_data: Request data

        Returns:
            Response data
        """
        if not self.session:
            raise RuntimeError("Client not initialized")

        # Ensure we're requesting streaming
        request_data["stream"] = True

        start_time = time.time()
        first_token_time = None
        chunks = []

        try:
            self.logger.info(f"Sending streaming request to: {endpoint_url}")
            async with self.session.post(
                endpoint_url,
                json=request_data,
                timeout=aiohttp.ClientTimeout(total=self.timeout),
            ) as response:
                if response.status == 404 and self.debug_mode:
                    self.logger.warning(
                        f"Received 404 from streaming endpoint {endpoint_url} in debug mode. Falling back to mock response."
                    )
                    # Fall back to mock response in debug mode
                    return self._generate_mock_response(request_data)

                if response.status != 200:
                    error_text = await response.text()
                    self.logger.error(
                        f"Non-200 response: {response.status}, content: {error_text[:200]}"
                    )
                    # Fall back to mock in debug mode
                    if self.debug_mode:
                        self.logger.warning(
                            f"Using mock response due to non-200 status: {response.status}, error: {error_text[:100]}"
                        )
                        return self._generate_mock_response(request_data)
                    return {
                        "error": error_text,
                        "status_code": response.status,
                        "success": False,
                        "elapsed_time": time.time() - start_time,
                    }

                # For SSE responses, we need to read line by line
                self.logger.info(
                    f"Started reading streaming response from {endpoint_url}"
                )
                async for line in response.content:
                    if line:
                        line_text = line.decode("utf-8").strip()
                        self.logger.debug(f"Received line: {line_text[:50]}...")

                        if line_text == "data: [DONE]":
                            self.logger.info("Received [DONE] marker, ending stream")
                            break

                        if line_text.startswith("data: "):
                            try:
                                data = json.loads(line_text[6:])
                                chunks.append(data)

                                # Record time to first token
                                if first_token_time is None:
                                    first_token_time = time.time()
                                    self.logger.info(
                                        f"Received first token after {first_token_time - start_time:.4f} seconds"
                                    )
                            except json.JSONDecodeError as e:
                                self.logger.error(
                                    f"JSON decode error: {e}, line: {line_text[:50]}..."
                                )
                            except Exception as e:
                                self.logger.error(
                                    f"Error parsing streaming response: {e}, line: {line_text[:50]}..."
                                )

                self.logger.info(
                    f"Completed reading streaming response, received {len(chunks)} chunks"
                )
        except aiohttp.ClientResponseError as e:
            self.logger.error(f"HTTP error during streaming request: {e}")
            # Fall back to mock response in debug mode
            if self.debug_mode:
                self.logger.warning(f"Using mock response due to streaming error: {e}")
                return self._generate_mock_response(request_data)
            return {
                "error": f"HTTP error: {e.status} - {e.message}",
                "status_code": e.status,
                "success": False,
                "elapsed_time": time.time() - start_time,
            }
        except asyncio.TimeoutError as e:
            self.logger.error(f"Timeout during streaming request: {e}")
            if self.debug_mode:
                self.logger.warning(f"Using mock response due to timeout: {e}")
                return self._generate_mock_response(request_data)
            return {
                "error": f"Request timed out after {self.timeout} seconds",
                "success": False,
                "elapsed_time": time.time() - start_time,
                "is_timeout": True,
            }
        except Exception as e:
            self.logger.error(f"Error during streaming request: {e}")
            # Fall back to mock response in debug mode
            if self.debug_mode:
                self.logger.warning(f"Using mock response due to streaming error: {e}")
                return self._generate_mock_response(request_data)
            return {
                "error": str(e),
                "success": False,
                "elapsed_time": time.time() - start_time,
            }

        end_time = time.time()
        elapsed_time = end_time - start_time
        time_to_first_token = (
            (first_token_time - start_time) if first_token_time else None
        )

        return {
            "response": {"chunks": chunks, "total_chunks": len(chunks)},
            "status_code": 200,
            "success": True,
            "elapsed_time": elapsed_time,
            "time_to_first_token": time_to_first_token,
        }

    async def health_check(self) -> bool:
        """Check if the OpenAI API is healthy.

        Returns:
            True if the API is healthy, False otherwise
        """
        if not self.session:
            return False

        try:
            # Try to hit the models endpoint to check health
            async with self.session.get(
                f"{self.url.rstrip('/')}/models",
                timeout=aiohttp.ClientTimeout(total=10),
            ) as response:
                return response.status == 200
        except Exception as e:
            self.logger.error(f"Health check failed: {e}")
            return False
