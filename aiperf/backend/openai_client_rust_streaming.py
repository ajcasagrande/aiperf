#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0

import json
import logging
from typing import Any

# Import the high-performance Rust streaming library
from aiperf_streaming import (
    PrecisionTimer,
    StreamingHttpClient,
    StreamingRequest,
    StreamingRequestModel,
    StreamingStats,
    TimingAnalysis,
)
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


class RustStreamingPerformanceConfig(BaseModel):
    """Configuration for Rust streaming performance optimizations."""

    timeout_ms: int = Field(
        default=30000, description="Total request timeout in milliseconds."
    )
    connect_timeout_ms: int = Field(
        default=5000, description="Connection timeout in milliseconds."
    )
    chunk_buffer_size: int = Field(
        default=8192, description="Buffer size for streaming chunks in bytes."
    )
    max_concurrent_requests: int = Field(
        default=10, description="Maximum concurrent requests for batch operations."
    )
    enable_gzip_compression: bool = Field(
        default=True, description="Enable gzip compression for requests."
    )
    keep_alive_timeout_ms: int = Field(
        default=30000, description="Keep-alive timeout for connections."
    )
    user_agent: str = Field(
        default="aiperf-rust-streaming/1.0",
        description="User agent string for HTTP requests.",
    )
    precision_timing: bool = Field(
        default=True, description="Enable nanosecond precision timing."
    )


@BackendClientFactory.register(BackendClientType.OPENAI, override_priority=3000000)
class OpenAIBackendClientRustStreaming(OpenAIClientMixin, OpenAIBackendClientProtocol):
    """
    Ultra high-performance OpenAI backend client using Rust streaming library.

    This client provides:
    - Nanosecond precision timing measurements using Rust
    - Maximum performance streaming with zero-copy operations
    - Optimized SSE (Server-Sent Events) parsing in Rust
    - Advanced performance analytics and statistics
    - Memory-efficient chunk processing
    - Concurrent request capabilities

    Performance Characteristics:
    - Timing precision: Nanosecond level (system dependent)
    - Throughput: Saturates available network bandwidth
    - Memory usage: Minimal with streaming processing
    - Concurrent requests: Configurable limits with optimal resource usage
    """

    def __init__(self, client_config: OpenAIBackendClientConfig):
        super().__init__(client_config)

        # Initialize performance configuration
        self.perf_config = RustStreamingPerformanceConfig(
            timeout_ms=client_config.timeout_ms,
            connect_timeout_ms=min(5000, client_config.timeout_ms // 6),
        )

        # Initialize high-precision timer
        self._precision_timer = PrecisionTimer()

        # Initialize the high-performance Rust streaming client
        default_headers = {
            "User-Agent": self.perf_config.user_agent,
            "Accept-Encoding": "gzip, deflate"
            if self.perf_config.enable_gzip_compression
            else "",
            "Connection": "keep-alive",
        }

        self._rust_client = StreamingHttpClient(
            timeout_ms=self.perf_config.timeout_ms,
            default_headers=default_headers,
            user_agent=self.perf_config.user_agent,
        )

        # Initialize statistics tracking
        self._stats = StreamingStats()

        logger.info(
            "Initialized RustStreamingBackendClient with precision timer at %s",
            self._precision_timer.now_iso(),
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
        """Send request using the ultra-high-performance Rust streaming client."""
        record: RequestRecord[Any] = RequestRecord(
            start_perf_counter_ns=self._precision_timer.now_ns(),
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
                    timestamp_ns=self._precision_timer.now_ns(),
                    error=str(e),
                )
            )

        return record

    async def send_chat_completion_request(
        self, payload: OpenAIChatCompletionRequest
    ) -> RequestRecord[Any]:
        """
        Send chat completion request using Rust streaming client for maximum performance.

        This method provides:
        - Nanosecond precision timing for each streaming chunk
        - Zero-copy chunk processing in Rust
        - Optimized SSE parsing
        - Advanced performance analytics
        """
        # Prepare the OpenAI API request payload
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

        # Prepare optimized headers for maximum performance
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.client_config.api_key}",
            "Accept": "text/event-stream",
            "Connection": "keep-alive",
        }

        if self.perf_config.enable_gzip_compression:
            headers["Accept-Encoding"] = "gzip, deflate"

        if self.client_config.organization:
            headers["OpenAI-Organization"] = self.client_config.organization

        # Construct the full URL
        base_url = (
            f"https://{self.client_config.url}"
            if not self.client_config.url.startswith(("http://", "https://"))
            else self.client_config.url
        )
        url = f"{base_url.rstrip('/')}/{self.client_config.endpoint}"

        try:
            # Create the high-performance streaming request
            streaming_request = StreamingRequest(
                url=url,
                method="POST",
                headers=headers,
                body=json.dumps(request_payload),
                timeout_ms=self.perf_config.timeout_ms,
            )

            # Execute the streaming request with nanosecond precision timing
            start_time_ns = self._precision_timer.now_ns()
            logger.debug(
                "Starting Rust streaming request at %s", self._precision_timer.now_iso()
            )

            # This is where the magic happens - all the heavy lifting is done in Rust
            completed_request = self._rust_client.stream_request(streaming_request)

            end_time_ns = self._precision_timer.now_ns()

            # Create the record with precise timing
            record: RequestRecord[Any] = RequestRecord(
                start_perf_counter_ns=completed_request.start_time_ns,
            )

            # Add the request to our statistics
            self._stats.add_request(completed_request)

            # Process the streaming chunks with precise timing
            chunks = completed_request.get_chunks()
            logger.debug(
                "Received %d chunks in %.2f ms",
                len(chunks),
                (end_time_ns - start_time_ns) / 1e6,
            )

            for chunk in chunks:
                # Parse SSE data format
                chunk_data = chunk.data.strip()

                if not chunk_data:
                    continue

                # Handle SSE format
                if chunk_data.startswith("data: "):
                    sse_data = chunk_data[6:]  # Remove "data: " prefix

                    # Check for stream end
                    if sse_data == "[DONE]":
                        break

                    # Skip empty chunks
                    if not sse_data.strip():
                        continue

                    try:
                        # Store the raw SSE data with nanosecond precision timing
                        record.responses.append(
                            BackendClientResponse[str](
                                timestamp_ns=chunk.timestamp_ns,
                                response=sse_data,  # Raw JSON string from SSE
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

                elif "error" in chunk_data.lower():
                    record.responses.append(
                        BackendClientErrorResponse(
                            timestamp_ns=chunk.timestamp_ns,
                            error=chunk_data,
                        )
                    )

            # Log comprehensive performance metrics
            self._log_performance_metrics(completed_request, start_time_ns, end_time_ns)

            return record

        except Exception as e:
            logger.error("Error in Rust streaming request: %s", str(e))
            record = RequestRecord(start_perf_counter_ns=self._precision_timer.now_ns())
            record.responses.append(
                BackendClientErrorResponse(
                    timestamp_ns=self._precision_timer.now_ns(),
                    error=str(e),
                )
            )
            return record

    def _log_performance_metrics(
        self, completed_request, start_time_ns: int, end_time_ns: int
    ):
        """Log comprehensive performance metrics from the Rust client."""
        try:
            total_duration_ms = (end_time_ns - start_time_ns) / 1e6
            chunk_timings = completed_request.chunk_timings()

            # Time to First Token (TTFT)
            ttft_ms = chunk_timings[0] / 1e6 if chunk_timings else 0

            # Throughput calculation
            throughput_mbps = 0
            if completed_request.throughput_bps():
                throughput_mbps = completed_request.throughput_bps() / (1024 * 1024)

            logger.info(
                "🚀 Rust Streaming Performance Metrics:\n"
                "   • Total Duration: %.2f ms\n"
                "   • Time to First Token (TTFT): %.2f ms\n"
                "   • Chunks Received: %d\n"
                "   • Total Bytes: %d\n"
                "   • Throughput: %.2f MB/s\n"
                "   • Request ID: %s",
                total_duration_ms,
                ttft_ms,
                completed_request.chunk_count,
                completed_request.total_bytes,
                throughput_mbps,
                completed_request.request_id[:8],
            )

            # Log chunk timing analysis
            if len(chunk_timings) > 1:
                avg_interval_ms = sum(chunk_timings[1:]) / len(chunk_timings[1:]) / 1e6
                max_interval_ms = max(chunk_timings[1:]) / 1e6
                min_interval_ms = min(chunk_timings[1:]) / 1e6

                logger.debug(
                    "🔍 Chunk Timing Analysis:\n"
                    "   • Average Inter-chunk Interval: %.2f ms\n"
                    "   • Maximum Inter-chunk Interval: %.2f ms\n"
                    "   • Minimum Inter-chunk Interval: %.2f ms",
                    avg_interval_ms,
                    max_interval_ms,
                    min_interval_ms,
                )

        except Exception as e:
            logger.debug("Failed to log performance metrics: %s", str(e))

    async def send_completion_request(
        self, payload: OpenAICompletionRequest
    ) -> RequestRecord[Any]:
        """Send completion request using fallback OpenAI client for non-streaming endpoints."""
        record: RequestRecord[Any] = RequestRecord(
            start_perf_counter_ns=self._precision_timer.now_ns(),
        )

        response = await self.client.completions.create(
            model=self.client_config.model,
            prompt=payload.prompt,
            max_tokens=self.client_config.max_tokens,
        )
        record.responses.append(
            BackendClientResponse(
                timestamp_ns=self._precision_timer.now_ns(),
                response=response,
            )
        )
        return record

    async def send_embeddings_request(
        self, payload: OpenAIEmbeddingsRequest
    ) -> RequestRecord[Any]:
        """Send embeddings request using fallback OpenAI client for non-streaming endpoints."""
        record: RequestRecord[Any] = RequestRecord(
            start_perf_counter_ns=self._precision_timer.now_ns(),
        )
        response = await self.client.embeddings.create(
            model=self.client_config.model,
            input=payload.input,
            dimensions=payload.dimensions,
            user=payload.user,
        )
        record.responses.append(
            BackendClientResponse(
                timestamp_ns=self._precision_timer.now_ns(),
                response=response,
            )
        )
        return record

    async def send_chat_responses_request(
        self, payload: OpenAIChatResponsesRequest
    ) -> RequestRecord[Any]:
        """Send chat responses request using fallback OpenAI client for non-streaming endpoints."""
        record: RequestRecord[Any] = RequestRecord(
            start_perf_counter_ns=self._precision_timer.now_ns(),
        )

        async for response in await self.client.responses.create(
            input=payload.input,
            model=self.client_config.model,
            stream=True,
        ):
            record.responses.append(
                BackendClientResponse(
                    timestamp_ns=self._precision_timer.now_ns(),
                    response=response,
                )
            )
        return record

    async def parse_response(
        self, response: OpenAIBaseResponse
    ) -> BackendClientResponse[OpenAIBaseResponse]:
        """Parse response - not implemented for this streaming client."""
        raise NotImplementedError(
            "OpenAIBackendClientRustStreaming does not support parsing responses"
        )

    def get_performance_statistics(self) -> dict[str, Any]:
        """Get comprehensive performance statistics from the Rust client."""
        try:
            client_stats = self._rust_client.get_stats()
            return {
                "total_requests": client_stats.total_requests
                if hasattr(client_stats, "total_requests")
                else 0,
                "total_bytes": client_stats.total_bytes
                if hasattr(client_stats, "total_bytes")
                else 0,
                "average_throughput_mbps": getattr(
                    client_stats, "avg_throughput_bps", 0
                )
                / (1024 * 1024),
                "current_timestamp_ns": self._precision_timer.now_ns(),
                "current_timestamp_iso": self._precision_timer.now_iso(),
                "performance_config": self.perf_config.model_dump(),
            }
        except Exception as e:
            logger.warning("Failed to get performance statistics: %s", str(e))
            return {
                "error": str(e),
                "current_timestamp_ns": self._precision_timer.now_ns(),
            }

    def get_advanced_timing_analysis(
        self, request_models: list[StreamingRequestModel]
    ) -> dict[str, Any]:
        """Perform advanced timing analysis using Pydantic models."""
        try:
            analysis = TimingAnalysis(requests=request_models)
            return {
                "request_duration_stats": analysis.request_duration_stats,
                "throughput_stats": analysis.throughput_stats,
                "chunk_timing_stats": analysis.chunk_timing_stats,
            }
        except Exception as e:
            logger.warning("Failed to perform advanced timing analysis: %s", str(e))
            return {"error": str(e)}

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit - cleanup resources."""
        try:
            # The Rust client handles its own cleanup automatically
            # Just log final statistics
            final_stats = self.get_performance_statistics()
            logger.info("Final Rust streaming client statistics: %s", final_stats)
        except Exception as e:
            logger.debug("Error during cleanup: %s", str(e))
