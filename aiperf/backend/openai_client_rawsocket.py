#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0

import asyncio
import json
import logging
import socket
import ssl
import time
import urllib.parse
from typing import Any

from aiperf_timing import RequestTimerKind, RequestTimers  # type: ignore

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
# Raw Socket Connection Pool
################################################################################

logger = logging.getLogger(__name__)


class RawSocketConnection:
    """High-performance raw socket connection with keep-alive support."""

    def __init__(self, host: str, port: int, use_ssl: bool = True):
        self.host = host
        self.port = port
        self.use_ssl = use_ssl
        self.socket: socket.socket | None = None
        self.ssl_socket: ssl.SSLSocket | None = None
        self.reader: asyncio.StreamReader | None = None
        self.writer: asyncio.StreamWriter | None = None
        self.connected = False
        self.last_used = time.time()
        self.connection_id = id(self)

    async def connect(self) -> None:
        """Establish connection with optimized settings."""
        if self.connected:
            return

        try:
            # Create socket with performance optimizations
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

            # Optimize socket for low latency
            sock.setsockopt(
                socket.IPPROTO_TCP, socket.TCP_NODELAY, 1
            )  # Disable Nagle's algorithm
            sock.setsockopt(
                socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1
            )  # Enable keep-alive
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)  # Reuse address

            # Set socket to non-blocking for async
            sock.setblocking(False)

            # Connect with timeout
            try:
                await asyncio.wait_for(
                    asyncio.get_event_loop().sock_connect(sock, (self.host, self.port)),
                    timeout=5.0,
                )
            except asyncio.TimeoutError:
                sock.close()
                raise ConnectionError(f"Connection timeout to {self.host}:{self.port}")

            if self.use_ssl:
                # Create SSL context optimized for performance
                ssl_context = ssl.create_default_context()
                ssl_context.check_hostname = True
                ssl_context.verify_mode = ssl.CERT_REQUIRED

                # Performance optimizations
                ssl_context.set_ciphers(
                    "ECDHE+AESGCM:ECDHE+CHACHA20:DHE+AESGCM:DHE+CHACHA20:!aNULL:!MD5:!DSS"
                )

                # Wrap socket with SSL
                ssl_sock = ssl_context.wrap_socket(
                    sock, server_hostname=self.host, do_handshake_on_connect=False
                )
                ssl_sock.setblocking(False)

                # Perform SSL handshake
                while True:
                    try:
                        ssl_sock.do_handshake()
                        break
                    except ssl.SSLWantReadError:
                        await asyncio.get_event_loop().sock_recv(ssl_sock, 0)
                    except ssl.SSLWantWriteError:
                        await asyncio.get_event_loop().sock_sendall(ssl_sock, b"")

                self.ssl_socket = ssl_sock
                self.socket = ssl_sock
            else:
                self.socket = sock

            # Create stream reader/writer for efficient I/O
            self.reader, self.writer = await asyncio.open_connection(sock=self.socket)

            self.connected = True
            self.last_used = time.time()

            logger.debug(f"Connected to {self.host}:{self.port} (SSL: {self.use_ssl})")

        except Exception as e:
            if self.socket:
                self.socket.close()
            raise ConnectionError(f"Failed to connect to {self.host}:{self.port}: {e}")

    async def send_http_request(
        self, method: str, path: str, headers: dict[str, str], body: bytes | None = None
    ) -> None:
        """Send HTTP request with minimal overhead."""
        if not self.connected or not self.writer:
            await self.connect()

        # Build HTTP request manually for maximum performance
        request_lines = [f"{method} {path} HTTP/1.1"]

        # Add headers
        for key, value in headers.items():
            request_lines.append(f"{key}: {value}")

        # Add Content-Length if body is present
        if body:
            request_lines.append(f"Content-Length: {len(body)}")

        # Empty line to end headers
        request_lines.append("")
        request_lines.append("")

        # Join with CRLF as per HTTP spec
        request_data = "\r\n".join(request_lines).encode("utf-8")

        # Add body if present
        if body:
            request_data += body

        # Send request in one write for efficiency
        self.writer.write(request_data)
        await self.writer.drain()

        self.last_used = time.time()

    async def read_http_response_headers(self) -> tuple[int, dict[str, str]]:
        """Read and parse HTTP response headers."""
        if not self.reader:
            raise RuntimeError("Connection not established")

        # Read status line
        status_line = await self.reader.readline()
        if not status_line:
            raise ConnectionError("Connection closed by server")

        status_line = status_line.decode("utf-8").strip()
        parts = status_line.split(" ", 2)
        if len(parts) < 2:
            raise ValueError(f"Invalid HTTP status line: {status_line}")

        status_code = int(parts[1])

        # Read headers
        headers = {}
        while True:
            line = await self.reader.readline()
            if not line:
                raise ConnectionError("Connection closed while reading headers")

            line = line.decode("utf-8").strip()
            if not line:  # Empty line indicates end of headers
                break

            if ":" in line:
                key, value = line.split(":", 1)
                headers[key.strip().lower()] = value.strip()

        return status_code, headers

    async def read_chunk(self, size: int = 8192) -> bytes:
        """Read a chunk of data from the response."""
        if not self.reader:
            raise RuntimeError("Connection not established")

        return await self.reader.read(size)

    async def read_line(self) -> bytes:
        """Read a line from the response."""
        if not self.reader:
            raise RuntimeError("Connection not established")

        return await self.reader.readline()

    def close(self) -> None:
        """Close the connection."""
        if self.writer:
            self.writer.close()
        if self.socket:
            self.socket.close()

        self.connected = False
        self.reader = None
        self.writer = None
        self.socket = None
        self.ssl_socket = None


class RawSocketConnectionPool:
    """Connection pool for raw sockets with keep-alive support."""

    def __init__(self, max_connections: int = 100, max_idle_time: float = 300.0):
        self.max_connections = max_connections
        self.max_idle_time = max_idle_time
        self.connections: dict[tuple[str, int, bool], list[RawSocketConnection]] = {}
        self.total_connections = 0
        self._lock = asyncio.Lock()

    async def get_connection(
        self, host: str, port: int, use_ssl: bool = True
    ) -> RawSocketConnection:
        """Get a connection from the pool or create a new one."""
        key = (host, port, use_ssl)

        async with self._lock:
            # Try to reuse existing connection
            if key in self.connections and self.connections[key]:
                for conn in self.connections[key][:]:
                    if (
                        conn.connected
                        and (time.time() - conn.last_used) < self.max_idle_time
                    ):
                        self.connections[key].remove(conn)
                        return conn
                    else:
                        # Remove stale connection
                        self.connections[key].remove(conn)
                        conn.close()
                        self.total_connections -= 1

            # Create new connection if under limit
            if self.total_connections < self.max_connections:
                conn = RawSocketConnection(host, port, use_ssl)
                await conn.connect()
                self.total_connections += 1
                return conn

            # Pool is full, create temporary connection
            conn = RawSocketConnection(host, port, use_ssl)
            await conn.connect()
            return conn

    async def return_connection(self, conn: RawSocketConnection) -> None:
        """Return a connection to the pool."""
        if not conn.connected:
            return

        key = (conn.host, conn.port, conn.use_ssl)

        async with self._lock:
            if key not in self.connections:
                self.connections[key] = []

            # Only keep connection if pool isn't too big
            if len(self.connections[key]) < 10:  # Max 10 per host
                self.connections[key].append(conn)
            else:
                conn.close()
                self.total_connections -= 1

    async def cleanup_stale_connections(self) -> None:
        """Clean up stale connections from the pool."""
        async with self._lock:
            current_time = time.time()
            for key, connections in list(self.connections.items()):
                for conn in connections[:]:
                    if (
                        not conn.connected
                        or (current_time - conn.last_used) > self.max_idle_time
                    ):
                        connections.remove(conn)
                        conn.close()
                        self.total_connections -= 1

                # Remove empty lists
                if not connections:
                    del self.connections[key]

    async def close_all(self) -> None:
        """Close all connections in the pool."""
        async with self._lock:
            for connections in self.connections.values():
                for conn in connections:
                    conn.close()
            self.connections.clear()
            self.total_connections = 0


################################################################################
# OpenAI Backend Client - Raw Socket Implementation
################################################################################


@BackendClientFactory.register(BackendClientType.OPENAI, override_priority=99900000)
class OpenAIBackendClientRawSocket(OpenAIClientMixin, OpenAIBackendClientProtocol):
    """Ultra high-performance OpenAI client using raw sockets optimized for TTFT."""

    def __init__(self, client_config: OpenAIBackendClientConfig):
        super().__init__(client_config)

        # Initialize high-performance connection pool
        self._connection_pool = RawSocketConnectionPool(
            max_connections=200, max_idle_time=300.0
        )

        # Parse URL for connection details
        parsed = urllib.parse.urlparse(
            client_config.url
            if client_config.url.startswith(("http://", "https://"))
            else f"https://{client_config.url}"
        )

        self._host = parsed.hostname or client_config.url.split("/")[0]
        self._port = parsed.port or (443 if parsed.scheme == "https" else 80)
        self._use_ssl = parsed.scheme == "https"
        self._base_path = parsed.path.rstrip("/")

        # Start background cleanup task
        self._cleanup_task = asyncio.create_task(self._periodic_cleanup())

    async def _periodic_cleanup(self) -> None:
        """Periodically clean up stale connections."""
        while True:
            try:
                await asyncio.sleep(60)  # Cleanup every minute
                await self._connection_pool.cleanup_stale_connections()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.warning(f"Error in connection cleanup: {e}")

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
        """Send chat completion request using raw sockets for maximum performance."""

        # Initialize precise timing with Rust module
        timers = RequestTimers()
        record: RequestRecord[Any] | None = None
        connection: RawSocketConnection | None = None

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
                "Host": self._host,
                # "Connection": "keep-alive",
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.client_config.api_key}",
                "Accept": "text/event-stream",
                # "Accept-Encoding": "identity",  # Disable compression for lower latency
                "User-Agent": "aiperf-rawsocket/1.0",
                "Cache-Control": "no-cache",
            }

            if self.client_config.organization:
                headers["OpenAI-Organization"] = self.client_config.organization

            # Build request path
            request_path = f"{self._base_path}/{self.client_config.endpoint}".replace(
                "//", "/"
            )

            # Start timing
            record = RequestRecord(
                start_perf_counter_ns=timers.capture_timestamp(
                    RequestTimerKind.REQUEST_START
                ),
            )

            # Get connection from pool
            timers.capture_timestamp(RequestTimerKind.SEND_START)
            connection = await self._connection_pool.get_connection(
                self._host, self._port, self._use_ssl
            )

            # Send HTTP request
            await connection.send_http_request(
                "POST", request_path, headers, json_payload
            )
            timers.capture_timestamp(RequestTimerKind.SEND_END)

            # Read response headers
            timers.capture_timestamp(RequestTimerKind.RECV_START)
            (
                status_code,
                response_headers,
            ) = await connection.read_http_response_headers()

            # Check for HTTP errors
            if status_code != 200:
                error_body = await connection.read_chunk(4096)
                record.responses.append(
                    BackendClientErrorResponse(
                        timestamp_ns=time.perf_counter_ns(),
                        error=f"HTTP {status_code}: {error_body.decode('utf-8', errors='replace')}",
                    )
                )
                return record

            # Handle chunked transfer encoding
            is_chunked = (
                response_headers.get("transfer-encoding", "").lower() == "chunked"
            )

            # Parse SSE stream with optimal buffering
            buffer = ""
            first_chunk = True

            while True:
                # Read data chunk
                if is_chunked:
                    # Read chunk size
                    chunk_size_line = await connection.read_line()
                    if not chunk_size_line:
                        break

                    chunk_size_str = (
                        chunk_size_line.decode("utf-8").strip().split(";")[0]
                    )
                    if chunk_size_str == "0":  # End of chunks
                        break

                    try:
                        chunk_size = int(chunk_size_str, 16)
                    except ValueError:
                        break

                    if chunk_size == 0:
                        break

                    # Read chunk data
                    chunk_data = await connection.read_chunk(chunk_size)
                    await connection.read_line()  # Read trailing CRLF
                else:
                    # Read fixed-size chunks
                    chunk_data = await connection.read_chunk(4096)
                    if not chunk_data:
                        break

                # Record timing for first chunk (TTFT)
                chunk_timestamp = timers.capture_timestamp(RequestTimerKind.RECV_CHUNK)

                if first_chunk:
                    first_chunk = False
                    logger.debug("First chunk received - TTFT achieved")

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
                            timers.capture_timestamp(RequestTimerKind.RECV_END)
                            await self._connection_pool.return_connection(connection)
                            connection = None
                            return record

                        # Skip empty data chunks at start
                        if data_content.strip() == "" and len(record.responses) == 0:
                            continue

                        try:
                            # Store raw SSE data for accurate timing
                            record.responses.append(
                                BackendClientResponse[str](
                                    timestamp_ns=chunk_timestamp,
                                    response=data_content,
                                )
                            )
                        except Exception as e:
                            record.responses.append(
                                BackendClientErrorResponse(
                                    timestamp_ns=chunk_timestamp,
                                    error=str(e),
                                )
                            )
                            continue

                    elif line.startswith("event: error"):
                        logger.error("Error event in streaming response: %s", line)
                        record.responses.append(
                            BackendClientErrorResponse(
                                timestamp_ns=chunk_timestamp,
                                error=line,
                            )
                        )
                        break

            timers.capture_timestamp(RequestTimerKind.RECV_END)

        except Exception as e:
            logger.error("Error in raw socket request: %s", str(e))
            if record is None:
                record = RequestRecord(start_perf_counter_ns=time.perf_counter_ns())
            record.responses.append(
                BackendClientErrorResponse(
                    timestamp_ns=time.perf_counter_ns(),
                    error=str(e),
                )
            )

        finally:
            # Clean up connection
            if connection:
                if connection.connected:
                    await self._connection_pool.return_connection(connection)
                else:
                    connection.close()

            timers.capture_timestamp(RequestTimerKind.REQUEST_END)

            # Log performance metrics
            try:
                total_time = timers.duration(
                    RequestTimerKind.REQUEST_START, RequestTimerKind.REQUEST_END
                )
                send_time = timers.duration(
                    RequestTimerKind.SEND_START, RequestTimerKind.SEND_END
                )
                recv_time = timers.duration(
                    RequestTimerKind.RECV_START, RequestTimerKind.RECV_END
                )

                logger.debug(
                    "Raw socket timing - Total: %d ns, Send: %d ns, Receive: %d ns, Chunks: %d",
                    total_time or 0,
                    send_time or 0,
                    recv_time or 0,
                    len(record.responses) if record else 0,
                )
            except Exception:
                pass  # Don't fail on timing logging errors

        if record is None:
            record = RequestRecord(start_perf_counter_ns=time.perf_counter_ns())

        return record

    async def parse_response(
        self, response: OpenAIBaseResponse
    ) -> BackendClientResponse[OpenAIBaseResponse]:
        """Parse response (not implemented for streaming responses)."""
        raise NotImplementedError(
            "OpenAIBackendClientRawSocket does not support parsing responses"
        )

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit - cleanup connections."""
        if hasattr(self, "_cleanup_task"):
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass

        if hasattr(self, "_connection_pool"):
            await self._connection_pool.close_all()
