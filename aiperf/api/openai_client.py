import aiohttp
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
        
        # Set authentication if provided
        if config.auth:
            api_key = config.auth.get("api_key")
            if api_key:
                self.headers["Authorization"] = f"Bearer {api_key}"
    
    async def initialize(self) -> bool:
        """Initialize the client.
        
        Returns:
            True if initialization was successful, False otherwise
        """
        try:
            self.session = aiohttp.ClientSession(headers=self.headers)
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
        if not self.session:
            raise RuntimeError("Client not initialized")
            
        endpoint = request_data.get("endpoint", "chat/completions")
        
        # Determine endpoint URL
        endpoint_url = f"{self.url.rstrip('/')}/{endpoint}"
        
        # Clean up request data by removing endpoint
        clean_request_data = request_data.copy()
        clean_request_data.pop("endpoint", None)
        
        # Handle streaming
        stream = clean_request_data.get("stream", False)
        
        start_time = time.time()
        try:
            if stream:
                return await self._handle_streaming_request(endpoint_url, clean_request_data)
            else:
                return await self._handle_standard_request(endpoint_url, clean_request_data)
        except Exception as e:
            self.logger.error(f"Error sending request to OpenAI API: {e}")
            return {
                "error": str(e),
                "success": False,
                "elapsed_time": time.time() - start_time
            }
    
    async def _handle_standard_request(self, endpoint_url: str, request_data: Dict[str, Any]) -> Dict[str, Any]:
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
        async with self.session.post(
            endpoint_url,
            json=request_data,
            timeout=aiohttp.ClientTimeout(total=self.timeout)
        ) as response:
            response_data = await response.json()
            elapsed_time = time.time() - start_time
            return {
                "response": response_data,
                "status_code": response.status,
                "success": response.status == 200,
                "elapsed_time": elapsed_time
            }
    
    async def _handle_streaming_request(self, endpoint_url: str, request_data: Dict[str, Any]) -> Dict[str, Any]:
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
        
        async with self.session.post(
            endpoint_url,
            json=request_data,
            timeout=aiohttp.ClientTimeout(total=self.timeout)
        ) as response:
            if response.status != 200:
                error_text = await response.text()
                return {
                    "error": error_text,
                    "status_code": response.status,
                    "success": False,
                    "elapsed_time": time.time() - start_time
                }
                
            async for line in response.content:
                if line.strip():
                    if line.strip() == b"data: [DONE]":
                        break
                        
                    try:
                        line_text = line.decode("utf-8").strip()
                        if line_text.startswith("data: "):
                            data = json.loads(line_text[6:])
                            chunks.append(data)
                            
                            # Record time to first token
                            if first_token_time is None:
                                first_token_time = time.time()
                    except Exception as e:
                        self.logger.error(f"Error parsing streaming response: {e}, line: {line}")
            
        end_time = time.time()
        elapsed_time = end_time - start_time
        time_to_first_token = (first_token_time - start_time) if first_token_time else None
        
        return {
            "response": {
                "chunks": chunks,
                "total_chunks": len(chunks)
            },
            "status_code": response.status,
            "success": True,
            "elapsed_time": elapsed_time,
            "time_to_first_token": time_to_first_token
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
                timeout=aiohttp.ClientTimeout(total=10)
            ) as response:
                return response.status == 200
        except Exception as e:
            self.logger.error(f"Health check failed: {e}")
            return False 