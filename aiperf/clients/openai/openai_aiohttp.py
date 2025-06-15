#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0

import logging
import time
import typing
from typing import Any

import aiohttp

from aiperf.clients.http.aiohttp_utils import (
    AioHttpSSEStreamReader,
    create_tcp_connector,
)
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
    ErrorDetails,
    InferenceServerResponse,
    RequestRecord,
)

################################################################################
# OpenAI Inference Client
################################################################################

logger = logging.getLogger(__name__)


@InferenceClientFactory.register(InferenceClientType.OPENAI, override_priority=00)
class OpenAIClientAioHttp(OpenAIClientConfigMixin):
    """A high-performance inference client for communicating with OpenAI based REST APIs using aiohttp.

    This class is optimized for maximum performance and accurate timing measurements,
    making it ideal for benchmarking scenarios.
    """

    def __init__(self, client_config: OpenAIClientConfig) -> None:
        super().__init__(client_config)
        self.tcp_connector = create_tcp_connector()

    async def cleanup(self) -> None:
        """Cleanup the client."""
        if self.tcp_connector:
            await self.tcp_connector.close()
            self.tcp_connector = None

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
        self, endpoint: str, payload: OpenAIBaseRequest, delayed: bool = False
    ) -> RequestRecord:
        """Send request to the specified endpoint with the given payload."""
        record: RequestRecord = RequestRecord(
            start_perf_ns=time.perf_counter_ns(),
            delayed=delayed,
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
            record.error = ErrorDetails(
                type=e.__class__.__name__,
                message=str(e),
            )

        return record

    async def send_completion_request(
        self, payload: OpenAICompletionRequest
    ) -> RequestRecord:
        raise NotImplementedError(
            "OpenAIClientAioHttp does not support completion requests"
        )

    async def send_embeddings_request(
        self, payload: OpenAIEmbeddingsRequest
    ) -> RequestRecord:
        raise NotImplementedError(
            "OpenAIClientAioHttp does not support embeddings requests"
        )

    async def send_chat_responses_request(
        self, payload: OpenAIChatResponsesRequest
    ) -> RequestRecord:
        raise NotImplementedError(
            "OpenAIClientAioHttp does not support chat responses requests"
        )

    async def send_chat_completion_request(
        self, payload: OpenAIChatCompletionRequest
    ) -> RequestRecord:
        """Send chat completion request using aiohttp."""

        # Initialize RequestTimers for precise timing
        timers = RequestTimers()
        record: RequestRecord | None = None

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
                record = RequestRecord(
                    start_perf_ns=timers.capture_timestamp(
                        RequestTimerKind.REQUEST_START
                    ),
                )
                # timers.capture_timestamp(RequestTimerKind.SEND_START)
                async with session.post(
                    url,
                    json=request_payload,
                    headers=headers,
                ) as response:
                    # Check for HTTP errors
                    if response.status != 200:
                        error_text = await response.text()
                        record.error = ErrorDetails(
                            code=response.status,
                            type=response.reason,
                            message=error_text,
                        )
                        return record
                    record.status = response.status
                    # timers.capture_timestamp(RequestTimerKind.SEND_END)
                    # timers.capture_timestamp(RequestTimerKind.RECV_START)
                    # Parse SSE stream with optimal performance
                    messages = await AioHttpSSEStreamReader(
                        response
                    ).read_complete_stream()
                    record.end_perf_ns = time.perf_counter_ns()
                    # timers.capture_timestamp(RequestTimerKind.RECV_END)
                    # timers.capture_timestamp(RequestTimerKind.REQUEST_END)
                    record.responses.extend(messages)

        except Exception as e:
            logger.error("Error in aiohttp request: %s", str(e))
            if record is None:
                record = RequestRecord(
                    start_perf_ns=time.perf_counter_ns(),
                    error=ErrorDetails(type=e.__class__.__name__, message=str(e)),
                )

        # finally:
        # if not timers.has_timestamp(RequestTimerKind.REQUEST_END):
        #     timers.capture_timestamp(RequestTimerKind.REQUEST_END)

        # # Log precise timing information for debugging/monitoring
        # try:
        #     total_duration = timers.duration(
        #         RequestTimerKind.REQUEST_START, RequestTimerKind.REQUEST_END
        #     )
        #     send_duration = timers.duration(
        #         RequestTimerKind.SEND_START, RequestTimerKind.SEND_END
        #     )
        #     recv_duration = timers.duration(
        #         RequestTimerKind.RECV_START, RequestTimerKind.RECV_END
        #     )

        #     chunk_durations = [
        #         (timers.chunk_start_timestamps[0] - timers.get_timestamp(RequestTimerKind.RECV_START)) / 1_000_000
        #     ]
        #     for i in range(1, len(timers.chunk_start_timestamps)):
        #         chunk_durations.append(
        #             (timers.chunk_start_timestamps[i] - timers.chunk_start_timestamps[i - 1]) / 1_000_000
        #         )

        #     logger.error(
        #         "Request timing - Total: %.3f ms, Send: %.3f ms, Receive: %.3f ms, Chunks: %s",
        #         total_duration / 1000000,
        #         send_duration / 1000000,
        #         recv_duration / 1000000,
        #         str(chunk_durations),
        #     )
        # except Exception:
        #     # Don't fail on timing logging errors
        #     logger.error("Error in timing logging: %s %s", e.__class__.__name__, str(e))
        #     pass

        return record

    # @staticmethod
    # async def _aiter_raw_sse_messages(
    #     response: aiohttp.ClientResponse,
    # ) -> typing.AsyncIterator[tuple[str, int]]:
    #     """Efficiently iterate over raw SSE messages from aiohttp response.

    #     Returns a tuple of the raw SSE message and the perf_counter_ns of the chunk.
    #     """

    #     while not response.content.at_eof():
    #         chunk = await response.content.readuntil(b"\n\n")
    #         chunk_ns = time.perf_counter_ns()
    #         if chunk:
    #             try:
    #                 # Use the fastest available decoder
    #                 yield chunk.decode("utf-8").strip(), chunk_ns
    #             except UnicodeDecodeError:
    #                 # Handle potential encoding issues gracefully
    #                 yield chunk.decode("utf-8", errors="replace").strip(), chunk_ns

    @staticmethod
    async def _aiter_raw_sse_messages(
        response: aiohttp.ClientResponse, chunk_size: int = 8192
    ) -> typing.AsyncIterator[tuple[str, int]]:
        """Efficiently iterate over raw SSE messages from aiohttp response.

        Returns a tuple of the raw SSE message and the perf_counter_ns of the chunk.

        Args:
            response: The aiohttp client response.
            chunk_size: The chunk size to use after the initial chunk has been read.
        """

        if response.content.at_eof():
            return

        # Read the initial chunk of the SSE stream
        chunk = await response.content.readuntil(b"\n\n")
        chunk_ns = time.perf_counter_ns()
        if chunk:
            try:
                # Use the fastest available decoder
                yield chunk.decode("utf-8").strip(), chunk_ns
            except UnicodeDecodeError:
                # Handle potential encoding issues gracefully
                yield chunk.decode("utf-8", errors="replace").strip(), chunk_ns

        # Iterate over the SSE stream in larger chunks
        async for chunk, chunk_ns in OpenAIClientAioHttp._aiter_sse_chunks(
            response, chunk_size
        ):
            yield chunk, chunk_ns

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
