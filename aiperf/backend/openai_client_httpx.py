#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0

import logging
import time
import typing
from typing import Any

import httpx

# Import the Rust timing module for precise measurements
from aiperf_timing import RequestTimerKind, RequestTimers  # type: ignore
from httpx._decoders import ByteChunker
from httpx._exceptions import request_context

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
from aiperf.common.enums import (
    BackendClientType,
)
from aiperf.common.exceptions import InvalidPayloadError
from aiperf.common.factories import BackendClientFactory
from aiperf.common.record_models import (
    BackendClientErrorResponse,
    BackendClientResponse,
    RequestRecord,
)

################################################################################
# OpenAI Backend Client
################################################################################

logger = logging.getLogger(__name__)


@BackendClientFactory.register(BackendClientType.OPENAI, override_priority=100000)
class OpenAIBackendClientHttpx(OpenAIClientMixin, OpenAIBackendClientProtocol):
    """A backend client for communicating with OpenAI based REST APIs.

    This class is responsible for formatting payloads, sending requests, and parsing responses for OpenAI based REST APIs.
    """

    def __init__(self, client_config: OpenAIBackendClientConfig):
        super().__init__(client_config)

        # Pre-configure httpx client for optimal performance
        self._configure_httpx_client()

    def _configure_httpx_client(self):
        """Configure httpx client with optimal performance settings."""
        # Configure connection limits and pooling for maximum performance
        limits = httpx.Limits(
            max_keepalive_connections=100,  # Keep many connections alive
            max_connections=200,  # Higher total connection limit
            keepalive_expiry=30.0,  # Keep connections alive for 30 seconds
        )

        # Configure timeouts with more granular control
        timeout = httpx.Timeout(
            connect=5.0,  # Connection timeout
            read=self.client_config.timeout_ms / 1000.0,  # Read timeout
            write=5.0,  # Write timeout
            pool=1.0,  # Pool timeout
        )

        # Create optimized client instance
        self._httpx_client = httpx.AsyncClient(
            limits=limits,
            timeout=timeout,
            http2=True,  # Enable HTTP/2 for better performance
            follow_redirects=False,  # Disable redirects for faster responses
            verify=True,  # Keep SSL verification but optimize
            trust_env=False,  # Don't read environment for faster startup
        )

    async def format_payload(
        self, endpoint: str, payload: OpenAIBaseRequest | dict[str, Any]
    ) -> OpenAIBaseRequest:
        # TODO: Is this actually an InputConverterProtocol?

        # If already formatted, return as-is
        if isinstance(payload, OpenAIBaseRequest):
            return payload

        # Otherwise, format from dict
        if not isinstance(payload, dict):
            raise ValueError("Payload must be a dict or OpenAIBaseRequest")

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
        # TODO: Is this actually an OutputConverterProtocol?

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
        """Send chat completion request using Rust-based timing for precise measurements."""

        # Initialize Rust timing metrics for precise timing
        request_timers = RequestTimers()

        # Initialize record upfront to avoid unbound variable issues
        record: RequestRecord[Any] = RequestRecord(
            start_perf_counter_ns=request_timers.capture_timestamp(
                RequestTimerKind.REQUEST_START
            ),
        )

        try:
            # Prepare request payload with performance optimizations
            request_payload = {
                "model": self.client_config.model,
                "messages": payload.messages,
                "max_tokens": self.client_config.max_tokens,
                "stream": True,
                # Uncomment for additional control parameters
                # "temperature": self.client_config.temperature,
                # "top_p": self.client_config.top_p,
                # "frequency_penalty": self.client_config.frequency_penalty,
                # "presence_penalty": self.client_config.presence_penalty,
            }

            # Add optional parameters if configured
            if self.client_config.stop:
                request_payload["stop"] = self.client_config.stop

            # Add any additional kwargs from payload
            if payload.kwargs:
                request_payload.update(payload.kwargs)

            # Prepare optimized headers
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.client_config.api_key}",
                "Accept": "text/event-stream",
                "Connection": "keep-alive",  # Explicit keep-alive for performance
                "Accept-Encoding": "gzip, deflate",  # Enable compression
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

            # Start request timing with Rust module
            request_timers.capture_timestamp(RequestTimerKind.REQUEST_START)
            record.start_perf_counter_ns = request_timers.capture_timestamp(
                RequestTimerKind.REQUEST_START
            )

            async with self._httpx_client.stream(
                "POST",
                url,
                json=request_payload,
                headers=headers,
            ) as response:
                # Check for HTTP errors
                if response.status_code != 200:
                    error_text = await response.aread()
                    record.responses.append(
                        BackendClientErrorResponse(
                            timestamp_ns=time.perf_counter_ns(),
                            error=f"HTTP {response.status_code}: {error_text.decode()}",
                        )
                    )
                    return record

                # Record first byte received (TTFT)
                first_chunk_received = False

                # Parse SSE stream with optimized buffering
                buffer = ""
                async for chunk, _, ns in self.aiter_raw_optimized(
                    response, request_timers
                ):
                    # Record first byte time on first chunk
                    if not first_chunk_received:
                        request_timers.capture_timestamp(RequestTimerKind.SEND_START)
                        first_chunk_received = True

                    # Record each chunk timing
                    request_timers.capture_timestamp(RequestTimerKind.SEND_END)

                    buffer += chunk.decode("utf-8")

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
                                break

                            # Skip empty data chunks at the start
                            if (
                                data_content.strip() == ""
                                and len(record.responses) == 0
                            ):
                                continue

                            try:
                                # Store the raw SSE data directly for most accurate timing
                                record.responses.append(
                                    BackendClientResponse[str](
                                        timestamp_ns=ns,
                                        response=data_content,  # Raw JSON string from SSE
                                    )
                                )
                            except Exception as e:
                                # Handle any response processing errors
                                record.responses.append(
                                    BackendClientErrorResponse(
                                        timestamp_ns=ns,
                                        error=str(e),
                                    )
                                )
                                continue

                        elif line.startswith("event: error"):
                            logger.error("Error event in streaming API call: %s", line)
                            record.responses.append(
                                BackendClientErrorResponse(
                                    timestamp_ns=ns,
                                    error=line,
                                )
                            )
                            break

        except Exception as e:
            logger.error("Error in optimized HTTP request: %s", str(e))
            record.responses.append(
                BackendClientErrorResponse(
                    timestamp_ns=time.perf_counter_ns(),
                    error=str(e),
                )
            )

        finally:
            # Log precise timing information from Rust module
            try:
                ttft = request_timers.duration(
                    RequestTimerKind.REQUEST_START, RequestTimerKind.SEND_START
                )
                chunk_metrics = [
                    request_timers.duration(
                        RequestTimerKind.SEND_START, RequestTimerKind.SEND_END
                    )
                    for _ in range(len(record.responses))
                ]

                if ttft is not None:
                    logger.debug(
                        "Request timing - TTFT: %.2f μs, Total chunks: %d",
                        ttft,
                        len(chunk_metrics),
                    )

                    if chunk_metrics:
                        logger.debug(
                            "Chunk timing - Min: %.2f μs, Max: %.2f μs, Avg: %.2f μs",
                            min(chunk_metrics),
                            max(chunk_metrics),
                            sum(chunk_metrics) / len(chunk_metrics),
                        )
                else:
                    logger.debug("Request completed without timing data")

            except Exception:
                # Don't fail on timing logging errors
                pass

        return record

    async def aiter_raw_optimized(
        self,
        response: httpx.Response,
        request_timers: RequestTimers,
        chunk_size: int = 1024,
    ) -> typing.AsyncIterator[tuple[bytes, int, int]]:
        """
        An optimized byte-iterator over the raw response content with larger chunk sizes.
        """
        if response.is_stream_consumed:
            raise httpx.StreamConsumed()
        if response.is_closed:
            raise httpx.StreamClosed()
        if not isinstance(response.stream, httpx.AsyncByteStream):
            raise RuntimeError("Attempted to call an async iterator on an sync stream.")

        response.is_stream_consumed = True
        response._num_bytes_downloaded = 0
        # Use larger chunk size for better performance
        chunker = ByteChunker(chunk_size=chunk_size)

        with request_context(request=response.request):
            i = 0
            async for raw_stream_bytes in response.stream:
                ns = request_timers.capture_timestamp(RequestTimerKind.RECV_CHUNK)
                response._num_bytes_downloaded += len(raw_stream_bytes)
                for chunk in chunker.decode(raw_stream_bytes):
                    yield (chunk, i, ns)
                    i += 1

        ns = request_timers.capture_timestamp(RequestTimerKind.RECV_END)
        for chunk in chunker.flush():
            yield (chunk, i, ns)
            i += 1

        await response.aclose()

    async def aiter_raw(
        self,
        response: httpx.Response,
        request_timers: RequestTimers,
        chunk_size: int | None = None,
    ) -> typing.AsyncIterator[tuple[bytes, int, int]]:
        """
        A byte-iterator over the raw response content.
        """
        # Delegate to optimized version with default chunk size
        chunk_size = chunk_size or 8192
        async for chunk, i, ns in self.aiter_raw_optimized(
            response, request_timers, chunk_size
        ):
            yield (chunk, i, ns)

    async def parse_response(
        self, response: OpenAIBaseResponse
    ) -> BackendClientResponse[OpenAIBaseResponse]:
        # TODO: Implement
        raise NotImplementedError(
            "OpenAIBackendClient does not support parsing responses"
        )

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit - cleanup httpx client."""
        if hasattr(self, "_httpx_client") and self._httpx_client:
            await self._httpx_client.aclose()
