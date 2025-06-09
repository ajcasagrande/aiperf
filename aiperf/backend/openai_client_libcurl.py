#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0

import asyncio
import json
import logging
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Any

import pycurl

from aiperf.backend.openai_common import (
    OpenAIBackendClientConfig,
    OpenAIBackendClientProtocol,
    OpenAIBaseRequest,
    OpenAIBaseResponse,
    OpenAIChatCompletionRequest,
    OpenAIChatResponsesRequest,
    OpenAIClientMixin,
    OpenAICompletionRequest,
    OpenAIEmbeddingsRequest,
)
from aiperf.common.enums import BackendClientType
from aiperf.common.exceptions import InvalidPayloadError
from aiperf.common.factories import BackendClientFactory
from aiperf.common.record_models import (
    BackendClientErrorResponse,
    BackendClientResponse,
    RequestRecord,
)

################################################################################
# libcurl-based HTTP Client Components
################################################################################

logger = logging.getLogger(__name__)


@dataclass
class LibcurlTimings:
    """Simple timing data container using only Python perf_counter_ns."""

    request_start_ns: int = 0
    send_start_ns: int = 0
    send_end_ns: int = 0
    recv_start_ns: int = 0
    recv_end_ns: int = 0
    request_end_ns: int = 0

    def duration_ns(self, start_name: str, end_name: str) -> int | None:
        """Calculate duration between two timing points."""
        start_time = getattr(self, f"{start_name}_ns", 0)
        end_time = getattr(self, f"{end_name}_ns", 0)
        if start_time > 0 and end_time > 0 and end_time >= start_time:
            return end_time - start_time
        return None


@dataclass
class CurlResponse:
    """Response data container for libcurl requests."""

    status_code: int = 0
    headers: dict[str, str] = field(default_factory=dict)
    chunks: list[tuple[bytes, int]] = field(
        default_factory=list
    )  # (data, relative_timestamp_ns)
    error: str | None = None
    total_time: float = 0.0
    connect_time: float = 0.0
    ttfb_time: float = 0.0  # Time to first byte
    timings: LibcurlTimings = field(default_factory=LibcurlTimings)


class LibcurlConnection:
    """High-performance libcurl connection with optimal settings."""

    def __init__(self, base_url: str, timeout_ms: int = 30000):
        self.base_url = base_url
        self.timeout_ms = timeout_ms
        self.curl = pycurl.Curl()
        self.connected = False
        self.last_used = time.time()
        self._setup_curl_optimizations()

    def _setup_curl_optimizations(self):
        """Configure libcurl for maximum performance and low latency."""
        c = self.curl

        # Basic settings
        c.setopt(pycurl.FOLLOWLOCATION, 0)  # Don't follow redirects
        c.setopt(pycurl.MAXREDIRS, 0)
        c.setopt(pycurl.TIMEOUT_MS, self.timeout_ms)
        c.setopt(pycurl.CONNECTTIMEOUT_MS, 5000)  # 5 second connect timeout

        # HTTP version and protocol optimization
        c.setopt(pycurl.HTTP_VERSION, pycurl.CURL_HTTP_VERSION_1_1)
        c.setopt(pycurl.PIPEWAIT, 1)  # Enable HTTP pipelining support

        # TCP/SSL optimizations for low latency
        c.setopt(pycurl.TCP_NODELAY, 1)  # Disable Nagle's algorithm
        c.setopt(pycurl.TCP_KEEPALIVE, 1)  # Enable TCP keep-alive
        c.setopt(pycurl.TCP_KEEPIDLE, 60)  # Keep-alive idle time
        c.setopt(pycurl.TCP_KEEPINTVL, 30)  # Keep-alive interval

        # Connection reuse optimization
        c.setopt(pycurl.FRESH_CONNECT, 0)  # Allow connection reuse
        c.setopt(pycurl.FORBID_REUSE, 0)  # Don't forbid connection reuse

        # SSL optimizations
        c.setopt(pycurl.SSL_VERIFYPEER, 1)
        c.setopt(pycurl.SSL_VERIFYHOST, 2)
        c.setopt(pycurl.SSLVERSION, pycurl.SSLVERSION_TLSv1_2)

        # Compression settings - disable for lowest latency
        c.setopt(pycurl.ACCEPT_ENCODING, "")  # Disable compression

        # Buffer optimizations
        c.setopt(pycurl.BUFFERSIZE, 64 * 1024)  # 64KB buffer for optimal performance

        # DNS optimizations
        c.setopt(pycurl.DNS_CACHE_TIMEOUT, 300)  # 5-minute DNS cache
        c.setopt(pycurl.DNS_USE_GLOBAL_CACHE, 1)

        # Disable unnecessary features for performance
        c.setopt(pycurl.NOSIGNAL, 1)  # Don't use signals
        c.setopt(pycurl.NOPROGRESS, 1)  # Disable progress meter

        logger.debug("libcurl connection optimized for low latency")

    async def perform_request_async(
        self,
        method: str,
        path: str,
        headers: dict[str, str],
        body: bytes | None = None,
    ) -> CurlResponse:
        """Perform HTTP request asynchronously using libcurl."""

        # Create response container with timing
        response = CurlResponse()
        response.timings.request_start_ns = time.perf_counter_ns()

        # Setup request
        url = f"{self.base_url.rstrip('/')}/{path.lstrip('/')}"
        self.curl.setopt(pycurl.URL, url)

        # Set HTTP method
        if method == "GET":
            self.curl.setopt(pycurl.HTTPGET, 1)
        elif method == "POST":
            self.curl.setopt(pycurl.POST, 1)
            if body:
                self.curl.setopt(pycurl.POSTFIELDS, body)
                self.curl.setopt(pycurl.POSTFIELDSIZE, len(body))
        else:
            self.curl.setopt(pycurl.CUSTOMREQUEST, method)
            if body:
                self.curl.setopt(pycurl.POSTFIELDS, body)

        # Set headers
        header_list = [f"{key}: {value}" for key, value in headers.items()]
        self.curl.setopt(pycurl.HTTPHEADER, header_list)

        # Setup data capture with streaming support
        response_headers = {}

        def header_callback(header_line: bytes) -> None:
            """Callback to capture response headers."""
            header_lines = header_line.decode("utf-8", errors="replace").strip()
            if ":" in header_lines:
                key, value = header_lines.split(":", 1)
                response_headers[key.strip().lower()] = value.strip()

        # For streaming responses, we need to capture data as it arrives
        def write_callback(data: bytes) -> int:
            """Callback to capture streaming response data."""
            current_time = time.perf_counter_ns()
            # Calculate relative timestamp from request start
            relative_timestamp = current_time - response.timings.request_start_ns
            response.chunks.append((data, relative_timestamp))

            # Capture TTFB on first chunk
            if len(response.chunks) == 1:
                response.timings.recv_start_ns = current_time

            return len(data)

        self.curl.setopt(pycurl.HEADERFUNCTION, header_callback)
        self.curl.setopt(pycurl.WRITEFUNCTION, write_callback)

        # Perform request in thread pool to avoid blocking
        loop = asyncio.get_event_loop()
        executor = ThreadPoolExecutor(max_workers=1)

        try:
            # Start timing
            response.timings.send_start_ns = time.perf_counter_ns()

            # Execute curl request in thread
            await loop.run_in_executor(executor, self.curl.perform)

            response.timings.send_end_ns = time.perf_counter_ns()

            # Get response information
            response.status_code = self.curl.getinfo(pycurl.RESPONSE_CODE)
            response.total_time = self.curl.getinfo(pycurl.TOTAL_TIME)
            response.connect_time = self.curl.getinfo(pycurl.CONNECT_TIME)
            response.ttfb_time = self.curl.getinfo(pycurl.STARTTRANSFER_TIME)
            response.headers = response_headers

            self.last_used = time.time()
            self.connected = True

            logger.debug(
                "libcurl request completed - Status: %d, Total: %.3fs, Connect: %.3fs, TTFB: %.3fs",
                response.status_code,
                response.total_time,
                response.connect_time,
                response.ttfb_time,
            )

        except pycurl.error as e:
            error_code, error_msg = e.args
            response.error = f"libcurl error {error_code}: {error_msg}"
            logger.error("libcurl request failed: %s", response.error)

        except Exception as e:
            response.error = f"Unexpected error: {str(e)}"
            logger.error("Unexpected error in libcurl request: %s", response.error)

        finally:
            executor.shutdown(wait=False)

        return response

    def close(self):
        """Close the libcurl connection."""
        if self.curl:
            self.curl.close()
        self.connected = False


class LibcurlConnectionPool:
    """Connection pool for libcurl connections with advanced management."""

    def __init__(self, max_connections: int = 100, max_idle_time: float = 300.0):
        self.max_connections = max_connections
        self.max_idle_time = max_idle_time
        self.connections: dict[str, list[LibcurlConnection]] = {}
        self.total_connections = 0
        self._lock = asyncio.Lock()

    async def get_connection(
        self, base_url: str, timeout_ms: int = 30000
    ) -> LibcurlConnection:
        """Get a connection from the pool or create a new one."""
        async with self._lock:
            # Try to reuse existing connection
            if base_url in self.connections and self.connections[base_url]:
                for conn in self.connections[base_url][:]:
                    if (
                        conn.connected
                        and (time.time() - conn.last_used) < self.max_idle_time
                    ):
                        self.connections[base_url].remove(conn)
                        return conn
                    else:
                        # Remove stale connection
                        self.connections[base_url].remove(conn)
                        conn.close()
                        self.total_connections -= 1

            # Create new connection if under limit
            if self.total_connections < self.max_connections:
                conn = LibcurlConnection(base_url, timeout_ms)
                self.total_connections += 1
                return conn

            # Pool is full, create temporary connection
            return LibcurlConnection(base_url, timeout_ms)

    async def return_connection(self, base_url: str, conn: LibcurlConnection) -> None:
        """Return a connection to the pool."""
        if not conn.connected:
            return

        async with self._lock:
            if base_url not in self.connections:
                self.connections[base_url] = []

            # Only keep connection if pool isn't too big
            if len(self.connections[base_url]) < 10:  # Max 10 per host
                self.connections[base_url].append(conn)
            else:
                conn.close()
                self.total_connections -= 1

    async def close_all(self) -> None:
        """Close all connections in the pool."""
        async with self._lock:
            for connections in self.connections.values():
                for conn in connections:
                    conn.close()
            self.connections.clear()
            self.total_connections = 0


################################################################################
# OpenAI Backend Client - libcurl Implementation
################################################################################


@BackendClientFactory.register(
    BackendClientType.OPENAI, override_priority=19999900999000
)
class OpenAIBackendClientLibcurl(OpenAIClientMixin, OpenAIBackendClientProtocol):
    """High-performance OpenAI client using libcurl for optimal HTTP performance."""

    def __init__(self, client_config: OpenAIBackendClientConfig):
        super().__init__(client_config)

        # Initialize connection pool
        self._connection_pool = LibcurlConnectionPool(
            max_connections=150, max_idle_time=300.0
        )

        # Parse URL for libcurl
        if not client_config.url.startswith(("http://", "https://")):
            self._base_url = f"https://{client_config.url}"
        else:
            self._base_url = client_config.url

    async def format_payload(
        self, endpoint: str, payload: OpenAIBaseRequest | dict[str, Any]
    ) -> OpenAIBaseRequest:
        """Format payload for the given endpoint."""
        if isinstance(payload, dict):
            return self._convert_dict_to_request(endpoint, payload)
        return payload

    def _convert_dict_to_request(
        self, endpoint: str, payload: dict[str, Any]
    ) -> OpenAIBaseRequest:
        """Convert dictionary payload to proper OpenAI request object."""
        if endpoint == "v1/chat/completions":
            return OpenAIChatCompletionRequest(
                messages=payload["messages"],
                model=self.client_config.model,
                max_tokens=self.client_config.max_tokens,
                kwargs=payload.get("kwargs", {}),
            )
        elif endpoint == "v1/completions":
            return OpenAICompletionRequest(
                prompt=payload["prompt"],
                model=self.client_config.model,
                max_tokens=self.client_config.max_tokens,
                kwargs=payload.get("kwargs", {}),
            )
        elif endpoint == "v1/embeddings":
            return OpenAIEmbeddingsRequest(
                input=payload["input"],
                model=self.client_config.model,
                dimensions=payload["dimensions"],
                encoding_format=payload["encoding_format"],
                user=payload["user"],
                kwargs=payload.get("kwargs", {}),
            )
        elif endpoint == "v1/responses":
            return OpenAIChatResponsesRequest(
                input=payload["input"],
                model=self.client_config.model,
                max_output_tokens=self.client_config.max_tokens,
                kwargs=payload.get("kwargs", {}),
            )
        else:
            raise ValueError(f"Invalid endpoint: {endpoint}")

    async def send_request(
        self, endpoint: str, payload: OpenAIBaseRequest
    ) -> RequestRecord:
        """Send request to the specified endpoint with the given payload."""
        record: RequestRecord[Any] = RequestRecord(
            start_perf_counter_ns=time.perf_counter_ns(),
        )

        try:
            if isinstance(payload, OpenAIChatCompletionRequest):
                record = await self.send_chat_completion_request(payload)
            elif isinstance(payload, OpenAICompletionRequest):
                record = await self.send_completion_request(payload)
            elif isinstance(payload, OpenAIEmbeddingsRequest):
                record = await self.send_embeddings_request(payload)
            elif isinstance(payload, OpenAIChatResponsesRequest):
                record = await self.send_chat_responses_request(payload)
            else:
                raise InvalidPayloadError(f"Invalid payload: {payload}")

        except InvalidPayloadError:
            raise  # re-raise the error to be handled by the caller
        except Exception as e:
            # swallow all other errors and return a generic error response
            record.responses.append(
                BackendClientErrorResponse(
                    timestamp_ns=time.perf_counter_ns(),
                    error=str(e),
                )
            )

        return record

    async def send_completion_request(
        self, payload: OpenAICompletionRequest
    ) -> RequestRecord[Any]:
        """Send completion request using fallback OpenAI client."""
        record: RequestRecord[Any] = RequestRecord(
            start_perf_counter_ns=time.perf_counter_ns(),
        )

        response = await self.client.completions.create(
            model=self.client_config.model,
            prompt=payload.prompt,
            max_tokens=self.client_config.max_tokens,
        )
        record.responses.append(
            BackendClientResponse(
                timestamp_ns=time.perf_counter_ns(),
                response=response,
            )
        )
        return record

    async def send_embeddings_request(
        self, payload: OpenAIEmbeddingsRequest
    ) -> RequestRecord[Any]:
        """Send embeddings request using fallback OpenAI client."""
        record: RequestRecord[Any] = RequestRecord(
            start_perf_counter_ns=time.perf_counter_ns(),
        )
        response = await self.client.embeddings.create(
            model=self.client_config.model,
            input=payload.input,
            dimensions=payload.dimensions,
            user=payload.user,
        )
        record.responses.append(
            BackendClientResponse(
                timestamp_ns=time.perf_counter_ns(),
                response=response,
            )
        )
        return record

    async def send_chat_responses_request(
        self, payload: OpenAIChatResponsesRequest
    ) -> RequestRecord[Any]:
        """Send chat responses request using fallback OpenAI client."""
        record: RequestRecord[Any] = RequestRecord(
            start_perf_counter_ns=time.perf_counter_ns(),
        )

        async for response in await self.client.responses.create(
            input=payload.input,
            model=self.client_config.model,
            stream=True,
        ):
            record.responses.append(
                BackendClientResponse(
                    timestamp_ns=time.perf_counter_ns(),
                    response=response,
                )
            )
        return record

    async def send_chat_completion_request(
        self, payload: OpenAIChatCompletionRequest
    ) -> RequestRecord[Any]:
        """Send chat completion request using libcurl for maximum performance."""

        # Initialize timing with native Python perf_counter_ns
        request_start_ns = time.perf_counter_ns()
        record: RequestRecord[Any] | None = None
        connection: LibcurlConnection | None = None

        try:
            # Prepare request payload
            request_payload = {
                "model": self.client_config.model,
                "messages": payload.messages,
                "max_tokens": self.client_config.max_tokens,
                "stream": True,
            }

            # Add optional parameters if configured
            if self.client_config.stop:
                request_payload["stop"] = self.client_config.stop

            # Add any additional kwargs from payload
            if payload.kwargs:
                request_payload.update(payload.kwargs)

            # Serialize JSON payload
            json_payload = json.dumps(request_payload, separators=(",", ":")).encode(
                "utf-8"
            )

            # Prepare headers optimized for performance
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.client_config.api_key}",
                "Accept": "text/event-stream",
                "User-Agent": "aiperf-libcurl/1.0",
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
            }

            if self.client_config.organization:
                headers["OpenAI-Organization"] = self.client_config.organization

            # Start timing - use request start as baseline
            record = RequestRecord(
                start_perf_counter_ns=request_start_ns,
            )

            # Get connection from pool
            connection = await self._connection_pool.get_connection(
                self._base_url, self.client_config.timeout_ms
            )

            # Send HTTP request using libcurl
            curl_response = await connection.perform_request_async(
                method="POST",
                path=self.client_config.endpoint,
                headers=headers,
                body=json_payload,
            )

            # Check for HTTP errors
            if curl_response.error:
                current_time = time.perf_counter_ns()
                record.responses.append(
                    BackendClientErrorResponse(
                        timestamp_ns=current_time,
                        error=f"libcurl error: {curl_response.error}",
                    )
                )
                return record

            if curl_response.status_code != 200:
                error_body = b"".join(chunk[0] for chunk in curl_response.chunks)
                current_time = time.perf_counter_ns()
                record.responses.append(
                    BackendClientErrorResponse(
                        timestamp_ns=current_time,
                        error=f"HTTP {curl_response.status_code}: {error_body.decode('utf-8', errors='replace')}",
                    )
                )
                return record

            # Process streaming SSE response
            buffer = ""
            first_chunk = True

            for chunk_data, chunk_timestamp in curl_response.chunks:
                # Record timing for first chunk (TTFT)
                if first_chunk:
                    first_chunk = False
                    logger.debug("First chunk received via libcurl - TTFT achieved")

                # Process chunk data
                try:
                    chunk_text = chunk_data.decode("utf-8")
                except UnicodeDecodeError:
                    chunk_text = chunk_data.decode("utf-8", errors="replace")

                buffer += chunk_text

                # Process complete lines
                while "\n" in buffer:
                    line, buffer = buffer.split("\n", 1)
                    line = line.strip()

                    if not line:
                        continue

                    # Handle SSE format
                    if line.startswith("data: "):
                        data_content = line[6:]  # Remove "data: " prefix

                        # Check for stream end
                        if data_content == "[DONE]":
                            curl_response.timings.recv_end_ns = time.perf_counter_ns()
                            await self._connection_pool.return_connection(
                                self._base_url, connection
                            )
                            connection = None
                            return record

                        # Skip empty data chunks at start
                        if data_content.strip() == "" and len(record.responses) == 0:
                            continue

                        try:
                            # Store raw SSE data with absolute timing (relative timestamp + request start)
                            absolute_timestamp = request_start_ns + chunk_timestamp
                            record.responses.append(
                                BackendClientResponse[str](
                                    timestamp_ns=absolute_timestamp,
                                    response=data_content,
                                )
                            )
                        except Exception as e:
                            absolute_timestamp = request_start_ns + chunk_timestamp
                            record.responses.append(
                                BackendClientErrorResponse(
                                    timestamp_ns=absolute_timestamp,
                                    error=str(e),
                                )
                            )

                    elif line.startswith("event: error"):
                        logger.error("Error event in streaming response: %s", line)
                        absolute_timestamp = request_start_ns + chunk_timestamp
                        record.responses.append(
                            BackendClientErrorResponse(
                                timestamp_ns=absolute_timestamp,
                                error=line,
                            )
                        )
                        break

            # Mark end of receiving if we have curl_response
            if "curl_response" in locals() and curl_response is not None:
                curl_response.timings.recv_end_ns = time.perf_counter_ns()

        except Exception as e:
            logger.error("Error in libcurl request: %s", str(e))
            current_time = time.perf_counter_ns()
            if record is None:
                record = RequestRecord(start_perf_counter_ns=current_time)
            record.responses.append(
                BackendClientErrorResponse(
                    timestamp_ns=current_time,
                    error=str(e),
                )
            )

        finally:
            # Clean up connection
            if connection:
                if connection.connected:
                    await self._connection_pool.return_connection(
                        self._base_url, connection
                    )
                else:
                    connection.close()

            # Mark request end time
            request_end_ns = time.perf_counter_ns()

            # Log performance metrics from libcurl
            try:
                if "curl_response" in locals() and curl_response is not None:
                    curl_response.timings.request_end_ns = request_end_ns

                    total_time = curl_response.timings.duration_ns(
                        "request_start", "request_end"
                    )
                    send_time = curl_response.timings.duration_ns(
                        "send_start", "send_end"
                    )
                    recv_time = curl_response.timings.duration_ns(
                        "recv_start", "recv_end"
                    )

                    logger.debug(
                        "libcurl timing - Total: %d ns, Send: %d ns, Receive: %d ns, Chunks: %d",
                        total_time or 0,
                        send_time or 0,
                        recv_time or 0,
                        len(record.responses) if record else 0,
                    )
            except Exception:
                pass  # Don't fail on timing logging errors

        if record is None:
            current_time = time.perf_counter_ns()
            record = RequestRecord(start_perf_counter_ns=current_time)

        return record

    async def parse_response(
        self, response: OpenAIBaseResponse
    ) -> BackendClientResponse[OpenAIBaseResponse]:
        """Parse response (not implemented for streaming responses)."""
        raise NotImplementedError(
            "OpenAIBackendClientLibcurl does not support parsing responses"
        )

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit - cleanup connections."""
        if hasattr(self, "_connection_pool"):
            await self._connection_pool.close_all()
