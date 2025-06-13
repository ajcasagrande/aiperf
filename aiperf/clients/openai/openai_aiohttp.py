#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0

import logging
import socket
import time
import typing
from typing import Any

import aiohttp

from aiperf.clients.openai.common import (
    OpenAIBaseRequest,
    OpenAIBaseResponse,
    OpenAIChatCompletionRequest,
    OpenAIChatResponsesRequest,
    OpenAIClientConfig,
    OpenAIClientConfigMixin,
    OpenAICompletionRequest,
    OpenAIEmbeddingsRequest,
)
from aiperf.clients.timers import RequestTimerKind, RequestTimers
from aiperf.common.enums import InferenceClientType
from aiperf.common.exceptions import InvalidPayloadError
from aiperf.common.factories import InferenceClientFactory
from aiperf.common.record_models import (
    InferenceServerErrorResponse,
    InferenceServerResponse,
    RequestRecord,
    SSEField,
    SSEFieldType,
    SSEMessage,
)

################################################################################
# OpenAI Inference Client
################################################################################

logger = logging.getLogger(__name__)


@InferenceClientFactory.register(InferenceClientType.OPENAI, override_priority=200)
class OpenAIClientAioHttp(OpenAIClientConfigMixin):
    """A high-performance inference client for communicating with OpenAI based REST APIs using aiohttp.

    This class is optimized for maximum performance and accurate timing measurements,
    making it ideal for benchmarking scenarios.
    """

    def __init__(self, client_config: OpenAIClientConfig) -> None:
        super().__init__(client_config)
        self.tcp_connector = self._create_tcp_connector()

    def _create_tcp_connector(self) -> aiohttp.TCPConnector:
        """Create a new connector with the given configuration."""

        def socket_factory(addr_info):
            """Custom socket factory optimized for SSE streaming performance."""
            family, type_, proto, _, _ = addr_info
            sock = socket.socket(family=family, type=type_, proto=proto)

            # Low-latency optimizations for streaming
            sock.setsockopt(
                socket.SOL_TCP, socket.TCP_NODELAY, 1
            )  # Disable Nagle's algorithm

            # Connection keepalive settings for long-lived SSE connections
            sock.setsockopt(
                socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1
            )  # Enable keepalive

            # Fine-tune keepalive timing (Linux-specific)
            if hasattr(socket, "TCP_KEEPIDLE"):
                sock.setsockopt(
                    socket.SOL_TCP, socket.TCP_KEEPIDLE, 600
                )  # Start keepalive after 10 min idle
                sock.setsockopt(
                    socket.SOL_TCP, socket.TCP_KEEPINTVL, 60
                )  # Keepalive interval: 60 seconds
                sock.setsockopt(
                    socket.SOL_TCP, socket.TCP_KEEPCNT, 3
                )  # 3 failed keepalive probes = dead

            # Buffer size optimizations for streaming
            sock.setsockopt(
                socket.SOL_SOCKET, socket.SO_RCVBUF, 1024
            )  # 87380)   # 85KB receive buffer
            sock.setsockopt(
                socket.SOL_SOCKET, socket.SO_SNDBUF, 1024
            )  # 65536)   # 64KB send buffer

            # Linux-specific TCP optimizations
            if hasattr(socket, "TCP_QUICKACK"):
                sock.setsockopt(
                    socket.SOL_TCP, socket.TCP_QUICKACK, 1
                )  # Quick ACK mode

            if hasattr(socket, "TCP_USER_TIMEOUT"):
                sock.setsockopt(
                    socket.SOL_TCP, socket.TCP_USER_TIMEOUT, 30000
                )  # 30 sec timeout

            return sock

        return aiohttp.TCPConnector(
            limit=2500,  # Connection pool size
            limit_per_host=2500,  # Per-host connection limit
            ttl_dns_cache=300,  # DNS cache TTL
            use_dns_cache=True,
            enable_cleanup_closed=True,
            force_close=False,  # Keep connections alive
            keepalive_timeout=300,
            # Performance optimizations
            happy_eyeballs_delay=None,  # Disable IPv6/IPv4 dual stack delay
            family=socket.AF_INET,  # IPv4 only for consistency
            socket_factory=socket_factory,  # Custom socket factory for TCP_NODELAY
        )

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
            start_perf_ns=time.perf_counter_ns(),
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
                InferenceServerErrorResponse(
                    perf_ns=time.perf_counter_ns(),
                    error=str(e),
                )
            )

        return record

    async def send_completion_request(
        self, payload: OpenAICompletionRequest
    ) -> RequestRecord[Any]:
        raise NotImplementedError(
            "OpenAIClientAioHttp does not support completion requests"
        )

    async def send_embeddings_request(
        self, payload: OpenAIEmbeddingsRequest
    ) -> RequestRecord[Any]:
        raise NotImplementedError(
            "OpenAIClientAioHttp does not support embeddings requests"
        )

    async def send_chat_responses_request(
        self, payload: OpenAIChatResponsesRequest
    ) -> RequestRecord[Any]:
        raise NotImplementedError(
            "OpenAIClientAioHttp does not support chat responses requests"
        )

    async def send_chat_completion_request(
        self, payload: OpenAIChatCompletionRequest
    ) -> RequestRecord[Any]:
        """Send chat completion request using aiohttp."""

        # Initialize RequestTimers for precise timing
        timers = RequestTimers()
        record: RequestRecord[Any] | None = None

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

            # Prepare headers
            headers = {
                "Content-Type": "application/json",
                "Accept": "text/event-stream",
            }

            if self.client_config.api_key:
                headers["Authorization"] = f"Bearer {self.client_config.api_key}"

            if self.client_config.organization:
                headers["OpenAI-Organization"] = self.client_config.organization

            # Construct full URL
            base_url = (
                f"https://{self.client_config.url}"
                if not self.client_config.url.startswith(("http://", "https://"))
                else self.client_config.url
            )
            url = f"{base_url.rstrip('/')}/{self.client_config.endpoint}"

            # Configure timeout
            timeout = aiohttp.ClientTimeout(
                total=self.client_config.timeout_ms / 1000.0,
                connect=300.0,  # 300 second connect timeout
                sock_connect=300.0,  # 300 second connect timeout
                sock_read=300.0,  # 300 second read timeout
                ceil_threshold=300.0,  # 300 second ceil threshold
            )

            record = RequestRecord(
                start_perf_ns=timers.capture_timestamp(RequestTimerKind.REQUEST_START),
            )
            # Make raw HTTP request with precise timing using aiohttp
            async with aiohttp.ClientSession(
                connector=self.tcp_connector,
                timeout=timeout,
                headers={"User-Agent": "aiperf/1.0"},
                skip_auto_headers={
                    "User-Agent",
                    "Accept-Encoding",
                },  # Skip auto-headers for performance
                connector_owner=False,
            ) as session:
                # Create record and capture initial timestamp
                timers.capture_timestamp(RequestTimerKind.SEND_START)

                async with session.post(
                    url,
                    json=request_payload,
                    headers=headers,
                ) as response:
                    timers.capture_timestamp(RequestTimerKind.SEND_END)

                    # Check for HTTP errors
                    if response.status != 200:
                        error_text = await response.text()
                        record.responses.append(
                            InferenceServerErrorResponse(
                                perf_ns=time.perf_counter_ns(),
                                error=f"HTTP {response.status}: {error_text}",
                            )
                        )
                        return record

                    timers.capture_timestamp(RequestTimerKind.RECV_START)

                    # TODO: look into better ways to parse the SSE stream in a performant and timestamp accurate manner

                    # Parse SSE stream with optimal performance
                    async for (
                        raw_message,
                        chunk_timestamp,
                    ) in OpenAIClientAioHttp._aiter_raw_sse_messages(response):
                        # logger.debug("Received SSE message: '%s'", raw_message)

                        message = SSEMessage(perf_ns=chunk_timestamp)
                        for line in raw_message.split("\n"):
                            if not line:
                                continue
                            # logger.debug("Processing SSE line: '%s'", line)
                            parts = line.split(":", 1)
                            # logger.debug("SSE parts: %s", parts)
                            if len(parts) < 2:
                                # Fields without a colon have no value
                                message.packets.append(
                                    SSEField(name=parts[0].strip(), value=None)
                                )
                                continue

                            field_name, value = parts

                            if field_name == "":
                                # Field name is empty, so this is a comment
                                field_name = SSEFieldType.COMMENT

                            message.packets.append(
                                SSEField(name=field_name.strip(), value=value.strip())
                            )

                        record.responses.append(message)

        except Exception as e:
            logger.error("Error in aiohttp request: %s", str(e))
            if record is None:
                record = RequestRecord(start_perf_ns=time.perf_counter_ns())
            record.responses.append(
                InferenceServerErrorResponse(
                    perf_ns=time.perf_counter_ns(),
                    error=str(e),
                )
            )

        finally:
            timers.capture_timestamp(RequestTimerKind.REQUEST_END)

            # Log precise timing information for debugging/monitoring
            try:
                total_duration = timers.duration(
                    RequestTimerKind.REQUEST_START, RequestTimerKind.REQUEST_END
                )
                send_duration = timers.duration(
                    RequestTimerKind.SEND_START, RequestTimerKind.SEND_END
                )
                recv_duration = timers.duration(
                    RequestTimerKind.RECV_START, RequestTimerKind.RECV_END
                )

                logger.debug(
                    "Request timing - Total: %d ns, Send: %d ns, Receive: %d ns",
                    total_duration,
                    send_duration,
                    recv_duration,
                )
            except Exception:
                # Don't fail on timing logging errors
                pass

        # Ensure record is never None
        if record is None:
            record = RequestRecord(start_perf_ns=time.perf_counter_ns())

        return record

    @staticmethod
    async def _aiter_raw_sse_messages(
        response: aiohttp.ClientResponse,
    ) -> typing.AsyncIterator[tuple[str, int]]:
        """Efficiently iterate over raw SSE messages from aiohttp response.

        Returns a tuple of the raw SSE message and the perf_counter_ns of the chunk.
        """

        while not response.content.at_eof():
            chunk = await response.content.readuntil(b"\n\n")
            chunk_ns = time.perf_counter_ns()
            if chunk:
                try:
                    # Use the fastest available decoder
                    yield chunk.decode("utf-8").strip(), chunk_ns
                except UnicodeDecodeError:
                    # Handle potential encoding issues gracefully
                    yield chunk.decode("utf-8", errors="replace").strip(), chunk_ns

    @staticmethod
    async def _aiter_sse_chunks(
        response: aiohttp.ClientResponse, chunk_size: int = 8192
    ) -> typing.AsyncIterator[tuple[str, int]]:
        """Efficiently iterate over SSE chunks from aiohttp response."""
        # Use a larger chunk size for better performance
        async for chunk in response.content.iter_chunked(chunk_size):
            if chunk:
                chunk_ns = time.perf_counter_ns()
                try:
                    # Use the fastest available decoder
                    yield chunk.decode("utf-8"), chunk_ns
                except UnicodeDecodeError:
                    # Handle potential encoding issues gracefully
                    yield chunk.decode("utf-8", errors="replace"), chunk_ns

    async def parse_response(
        self, response: OpenAIBaseResponse
    ) -> InferenceServerResponse:
        """Parse response (not implemented for streaming responses)."""
        raise NotImplementedError(
            "OpenAIClientAioHttp does not support parsing responses"
        )

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit - cleanup connector."""
        logger.debug("Async context manager exit - cleanup connector.")
