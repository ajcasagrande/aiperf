#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0

import logging
import socket
import time
import typing
from typing import Any

import aiohttp

from aiperf.backend.openai_common import (
    OpenAIBackendClientConfigMixin,
    OpenAIBaseRequest,
    OpenAIBaseResponse,
    OpenAIChatCompletionRequest,
    OpenAIChatResponsesRequest,
    OpenAICompletionRequest,
    OpenAIEmbeddingsRequest,
)
from aiperf.common.enums import (
    BackendClientType,
)
from aiperf.common.exceptions import InvalidPayloadError
from aiperf.common.factories import BackendClientFactory
from aiperf.common.record_models import (
    BackendClientErrorResponse,
    BackendClientResponse,
    RequestRecord,
    RequestTimerKind,
    RequestTimers,
)

################################################################################
# OpenAI Backend Client
################################################################################

logger = logging.getLogger(__name__)


@BackendClientFactory.register(BackendClientType.OPENAI)
class OpenAIBackendClientAioHttp(OpenAIBackendClientConfigMixin):
    """A high-performance backend client for communicating with OpenAI based REST APIs using aiohttp.

    This class is optimized for maximum performance and accurate timing measurements,
    making it ideal for benchmarking scenarios.
    """

    def _create_tcp_connector(self) -> aiohttp.TCPConnector:
        """Create a new connector with the given configuration."""
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
        raise NotImplementedError(
            "OpenAIBackendClientAioHttp does not support completion requests"
        )

    async def send_embeddings_request(
        self, payload: OpenAIEmbeddingsRequest
    ) -> RequestRecord[Any]:
        raise NotImplementedError(
            "OpenAIBackendClientAioHttp does not support embeddings requests"
        )

    async def send_chat_responses_request(
        self, payload: OpenAIChatResponsesRequest
    ) -> RequestRecord[Any]:
        raise NotImplementedError(
            "OpenAIBackendClientAioHttp does not support chat responses requests"
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
                "Authorization": f"Bearer {self.client_config.api_key}",
                "Accept": "text/event-stream",
            }

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

            # Make raw HTTP request with precise timing using aiohttp
            async with aiohttp.ClientSession(
                connector=self._create_tcp_connector(),
                timeout=timeout,
                headers={"User-Agent": "aiperf/1.0"},
                skip_auto_headers={"User-Agent"},  # Skip auto-headers for performance
            ) as session:
                # Create record and capture initial timestamp
                record = RequestRecord(
                    start_perf_counter_ns=timers.capture_timestamp(
                        RequestTimerKind.REQUEST_START
                    ),
                )

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
                            BackendClientErrorResponse(
                                timestamp_ns=time.perf_counter_ns(),
                                error=f"HTTP {response.status}: {error_text}",
                            )
                        )
                        return record

                    timers.capture_timestamp(RequestTimerKind.RECV_START)

                    # TODO: look into better ways to parse the SSE stream in a performant and timestamp accurate manner

                    # Parse SSE stream with optimal performance
                    buffer = ""
                    async for chunk in self._aiter_sse_chunks(response):
                        chunk_timestamp = time.perf_counter_ns()

                        buffer += chunk

                        # Process complete lines efficiently
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
                                    break

                                # Skip empty data chunks at the start
                                if (
                                    data_content.strip() == ""
                                    and len(record.responses) == 0
                                ):
                                    continue

                                try:
                                    timers.append_chunk_timestamp(chunk_timestamp)
                                    # Store the raw SSE data directly for most accurate timing
                                    record.responses.append(
                                        BackendClientResponse[str](
                                            timestamp_ns=chunk_timestamp,
                                            response=data_content,
                                        )
                                    )
                                except Exception as e:
                                    # Handle any response processing errors
                                    record.responses.append(
                                        BackendClientErrorResponse(
                                            timestamp_ns=chunk_timestamp,
                                            error=str(e),
                                        )
                                    )
                                    continue

                            elif line.startswith("event: error"):
                                logger.error(
                                    "Error event in streaming API call: %s", line
                                )
                                record.responses.append(
                                    BackendClientErrorResponse(
                                        timestamp_ns=chunk_timestamp,
                                        error=line,
                                    )
                                )
                                break

                    timers.capture_timestamp(RequestTimerKind.RECV_END)

        except Exception as e:
            logger.error("Error in aiohttp request: %s", str(e))
            if record is None:
                record = RequestRecord(start_perf_counter_ns=time.perf_counter_ns())
            record.responses.append(
                BackendClientErrorResponse(
                    timestamp_ns=time.perf_counter_ns(),
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
            record = RequestRecord(start_perf_counter_ns=time.perf_counter_ns())

        return record

    async def _aiter_sse_chunks(
        self, response: aiohttp.ClientResponse, chunk_size: int = 8192
    ) -> typing.AsyncIterator[str]:
        """Efficiently iterate over SSE chunks from aiohttp response."""
        # Use a larger chunk size for better performance
        async for chunk in response.content.iter_chunked(chunk_size):
            if chunk:
                try:
                    # Use the fastest available decoder
                    yield chunk.decode("utf-8")
                except UnicodeDecodeError:
                    # Handle potential encoding issues gracefully
                    yield chunk.decode("utf-8", errors="replace")

    async def parse_response(
        self, response: OpenAIBaseResponse
    ) -> BackendClientResponse[OpenAIBaseResponse]:
        """Parse response (not implemented for streaming responses)."""
        raise NotImplementedError(
            "OpenAIBackendClientAioHttp does not support parsing responses"
        )

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit - cleanup connector."""
        logger.debug("Async context manager exit - cleanup connector.")
