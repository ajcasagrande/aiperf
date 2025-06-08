#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0

import json
import logging
import time
from typing import Any

# Import Rust streaming module
from aiperf_streaming import StreamingHttpClient, StreamingOptions  # type: ignore
from pydantic import BaseModel, Field

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

logger = logging.getLogger(__name__)


class RustStreamingConfig(BaseModel):
    """Configuration for the Rust streaming client."""

    timeout_ms: int = Field(
        default=30000, description="Total request timeout in milliseconds."
    )
    connect_timeout_ms: int = Field(
        default=5000, description="Connection timeout in milliseconds."
    )
    chunk_size: int = Field(default=1024, description="Streaming chunk size in bytes.")
    enable_compression: bool = Field(
        default=True, description="Enable gzip compression."
    )
    max_redirects: int = Field(
        default=3, description="Maximum number of redirects to follow."
    )
    user_agent: str = Field(
        default="aiperf-rust-streaming/1.0",
        description="User agent string for requests.",
    )


@BackendClientFactory.register(BackendClientType.OPENAI, override_priority=2000000)
class RustStreamingBackendClient(OpenAIClientMixin, OpenAIBackendClientProtocol):
    """A high-performance backend client using Rust for streaming SSE requests with nanosecond precision timing.

    This client provides:
    - Ultra-precise timing measurements using Rust
    - High-performance streaming with minimal overhead
    - SSE (Server-Sent Events) parsing optimized in Rust
    - Configurable client options for performance tuning
    - Seamless integration with existing Python code
    """

    def __init__(self, client_config: OpenAIBackendClientConfig):
        if StreamingHttpClient is None:
            raise ImportError(
                "Rust streaming module not available. Please build the aiperf_streaming library."
            )

        super().__init__(client_config)

        # Initialize the Rust streaming client
        self._rust_client = StreamingHttpClient()

        # Configure streaming options based on client config
        self.streaming_config = RustStreamingConfig(
            timeout_ms=client_config.timeout_ms,
            connect_timeout_ms=min(
                5000, client_config.timeout_ms // 6
            ),  # 1/6 of total timeout
        )

    async def format_payload(
        self, endpoint: str, payload: OpenAIBaseRequest | dict[str, Any]
    ) -> OpenAIBaseRequest:
        """Format the payload for the OpenAI API."""

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
        """Send request using the Rust streaming client for maximum performance."""

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

    async def send_chat_completion_request(
        self, payload: OpenAIChatCompletionRequest
    ) -> RequestRecord[Any]:
        """Send chat completion request using Rust client for ultra-precise timing."""

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
        if hasattr(self.client_config, "temperature"):
            request_payload["temperature"] = self.client_config.temperature
        if hasattr(self.client_config, "top_p"):
            request_payload["top_p"] = self.client_config.top_p
        if hasattr(self.client_config, "frequency_penalty"):
            request_payload["frequency_penalty"] = self.client_config.frequency_penalty
        if hasattr(self.client_config, "presence_penalty"):
            request_payload["presence_penalty"] = self.client_config.presence_penalty

        # Add any additional kwargs from payload
        if payload.kwargs:
            request_payload.update(payload.kwargs)

        # Prepare headers
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.client_config.api_key}",
            "Accept": "text/event-stream",
            "Connection": "keep-alive",
            "Accept-Encoding": "gzip, deflate",
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

        # Configure streaming options
        streaming_options = StreamingOptions(
            timeout_ms=self.streaming_config.timeout_ms,
            connect_timeout_ms=self.streaming_config.connect_timeout_ms,
            chunk_size=self.streaming_config.chunk_size,
            enable_compression=self.streaming_config.enable_compression,
            max_redirects=self.streaming_config.max_redirects,
            user_agent=self.streaming_config.user_agent,
        )

        try:
            # Execute the streaming request using Rust client
            rust_response = self._rust_client.post_stream(
                url=url,
                headers=headers,
                payload={"__json__": json.dumps(request_payload)},
                options=streaming_options,
            )

            # Create record with Rust timing data
            record: RequestRecord[Any] = RequestRecord(
                start_perf_counter_ns=rust_response.start_timestamp_ns,
            )

            # Check for errors
            if rust_response.error:
                record.responses.append(
                    BackendClientErrorResponse(
                        timestamp_ns=rust_response.start_timestamp_ns,
                        error=rust_response.error,
                    )
                )
                return record

            # Convert Rust chunks to Python responses
            for chunk in rust_response.chunks:
                if chunk.is_sse_data and chunk.data.strip():
                    try:
                        # Store the raw SSE data directly for most accurate timing
                        record.responses.append(
                            BackendClientResponse[str](
                                timestamp_ns=chunk.timestamp_ns,
                                response=chunk.data,  # Raw JSON string from SSE
                            )
                        )
                    except Exception as e:
                        # Handle any response processing errors
                        record.responses.append(
                            BackendClientErrorResponse(
                                timestamp_ns=chunk.timestamp_ns,
                                error=str(e),
                            )
                        )
                        continue
                elif not chunk.is_sse_data and "error" in chunk.data.lower():
                    record.responses.append(
                        BackendClientErrorResponse(
                            timestamp_ns=chunk.timestamp_ns,
                            error=chunk.data,
                        )
                    )

            # Log timing information
            if (
                rust_response.first_chunk_timestamp_ns
                and rust_response.start_timestamp_ns
            ):
                ttft_ns = (
                    rust_response.first_chunk_timestamp_ns
                    - rust_response.start_timestamp_ns
                )
                logger.warning(
                    "Rust streaming - TTFT: %.2f ms, Total chunks: %d, Status: %d",
                    ttft_ns / 1_000_000.0,  # Convert to milliseconds
                    len(rust_response.chunks),
                    rust_response.status_code,
                )

            return record

        except Exception as e:
            logger.error("Error in Rust streaming request: %s", str(e))
            record = RequestRecord(start_perf_counter_ns=time.perf_counter_ns())
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

    async def parse_response(
        self, response: OpenAIBaseResponse
    ) -> BackendClientResponse[OpenAIBaseResponse]:
        """Parse response - not implemented for this client."""
        raise NotImplementedError(
            "RustStreamingBackendClient does not support parsing responses"
        )
