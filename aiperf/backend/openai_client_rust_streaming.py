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
        default=200, description="Maximum concurrent requests for batch operations."
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
        """Send request using the ultra-high-performance Rust streaming client with pure Rust timing."""

        try:
            # For streaming requests (chat completions), use pure Rust timing
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
            # Fallback record with Python timing only in error cases
            record: RequestRecord[Any] = RequestRecord(
                start_perf_counter_ns=self._precision_timer.now_ns(),
            )
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
        - Pure Rust nanosecond precision timing for each streaming chunk
        - Zero-copy chunk processing in Rust
        - Optimized SSE parsing
        - Advanced performance analytics using only Rust timing data
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

            logger.debug("Starting Rust streaming request")

            # This is where the magic happens - ALL timing is done in Rust with nanosecond precision
            completed_request = self._rust_client.stream_request(streaming_request)

            # Use ONLY Rust timing data - no Python timing mixed in
            # Create the record with precise Rust timing
            record: RequestRecord[Any] = RequestRecord(
                start_perf_counter_ns=completed_request.start_time_ns,
            )

            # Add the request to our statistics
            self._stats.add_request(completed_request)

            # Process the streaming chunks with precise Rust timing
            chunks = completed_request.get_chunks()

            # Use pure Rust timing for logging
            rust_total_duration_ns = (
                completed_request.end_time_ns - completed_request.start_time_ns
                if hasattr(completed_request, "end_time_ns")
                and completed_request.end_time_ns
                else 0
            )
            logger.debug(
                "Received %d chunks in %.2f ms (pure Rust timing)",
                len(chunks),
                rust_total_duration_ns / 1e6,
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
                        # Store the raw SSE data with PURE Rust nanosecond precision timing
                        record.responses.append(
                            BackendClientResponse[str](
                                timestamp_ns=chunk.timestamp_ns,  # This is pure Rust timing
                                response=sse_data,  # Raw JSON string from SSE
                            )
                        )
                    except Exception as e:
                        # Handle any response processing errors
                        record.responses.append(
                            BackendClientErrorResponse(
                                timestamp_ns=chunk.timestamp_ns,  # Pure Rust timing
                                error=str(e),
                            )
                        )
                        continue

                elif "error" in chunk_data.lower():
                    record.responses.append(
                        BackendClientErrorResponse(
                            timestamp_ns=chunk.timestamp_ns,  # Pure Rust timing
                            error=chunk_data,
                        )
                    )

            # # Log comprehensive performance metrics using ONLY Rust timing
            # self._log_performance_metrics_rust_only(completed_request)

            # # Log additional accuracy verification
            # self._verify_rust_timing_accuracy(record, completed_request)

            return record

        except Exception as e:
            logger.error("Error in Rust streaming request: %s", str(e))
            # Fallback to Python timing only in error cases
            record = RequestRecord(start_perf_counter_ns=self._precision_timer.now_ns())
            record.responses.append(
                BackendClientErrorResponse(
                    timestamp_ns=self._precision_timer.now_ns(),
                    error=str(e),
                )
            )
            return record

    def _log_performance_metrics_rust_only(self, completed_request):
        """Log comprehensive performance metrics using ONLY pure Rust timing data."""
        try:
            # Get pure Rust timing data
            rust_start_time_ns = completed_request.start_time_ns
            rust_end_time_ns = getattr(completed_request, "end_time_ns", None)

            # Calculate total duration using pure Rust timing
            if rust_end_time_ns:
                total_duration_ns = rust_end_time_ns - rust_start_time_ns
                total_duration_ms = total_duration_ns / 1e6
            else:
                total_duration_ms = 0

            # Get chunk timings directly from Rust
            chunk_timings = completed_request.chunk_timings()

            # Time to First Token (TTFT) - pure Rust calculation
            ttft_ns = chunk_timings[0] if chunk_timings else 0
            ttft_ms = ttft_ns / 1e6

            # Throughput calculation from Rust
            throughput_mbps = 0
            if (
                hasattr(completed_request, "throughput_bps")
                and completed_request.throughput_bps()
            ):
                throughput_mbps = completed_request.throughput_bps() / (1024 * 1024)

            # Get request ID safely
            request_id = getattr(completed_request, "request_id", "unknown")
            request_id_short = request_id[:8] if len(request_id) > 8 else request_id

            logger.warning(
                "🚀 Pure Rust Streaming Performance Metrics:\n"
                "   • Total Duration: %.2f ms (Rust timing)\n"
                "   • Time to First Token (TTFT): %.2f ms (Rust timing)\n"
                "   • Chunks Received: %d\n"
                "   • Total Bytes: %d\n"
                "   • Throughput: %.2f MB/s (Rust calculated)\n"
                "   • Request ID: %s\n"
                "   • Rust Start Time: %d ns\n"
                "   • Rust End Time: %s ns",
                total_duration_ms,
                ttft_ms,
                completed_request.chunk_count,
                completed_request.total_bytes,
                throughput_mbps,
                request_id_short,
                rust_start_time_ns,
                rust_end_time_ns if rust_end_time_ns else "N/A",
            )

            # Log chunk timing analysis using pure Rust data
            if len(chunk_timings) > 1:
                # All intervals calculated by Rust
                interval_timings_ns = chunk_timings[1:]  # Skip first (TTFT)
                avg_interval_ns = sum(interval_timings_ns) / len(interval_timings_ns)
                max_interval_ns = max(interval_timings_ns)
                min_interval_ns = min(interval_timings_ns)

                logger.warning(
                    "🔍 Pure Rust Chunk Timing Analysis:\n"
                    "   • Average Inter-chunk Interval: %.2f ms (Rust)\n"
                    "   • Maximum Inter-chunk Interval: %.2f ms (Rust)\n"
                    "   • Minimum Inter-chunk Interval: %.2f ms (Rust)\n"
                    "   • Total Timing Points: %d",
                    avg_interval_ns / 1e6,
                    max_interval_ns / 1e6,
                    min_interval_ns / 1e6,
                    len(chunk_timings),
                )

        except Exception as e:
            logger.debug("Failed to log pure Rust performance metrics: %s", str(e))

    def _verify_rust_timing_accuracy(
        self, record: RequestRecord[Any], completed_request
    ):
        """Verify that we're using pure Rust timing with maximum accuracy."""
        try:
            # Verify that the record's timing calculations use pure Rust data
            rust_ttft_ns = None
            rust_ttst_ns = None

            if record.responses and len(record.responses) >= 1:
                # Time to First Token: first response timestamp - start time (both from Rust)
                rust_ttft_ns = record.time_to_first_response_ns

            if record.responses and len(record.responses) >= 2:
                # Time to Second Token: second response timestamp - first response timestamp (both from Rust)
                rust_ttst_ns = record.time_to_second_response_ns

            # Compare with Rust's own chunk timing calculations
            rust_chunk_timings = completed_request.chunk_timings()

            logger.warning(
                "🔬 Rust Timing Accuracy Verification:\n"
                "   • Record TTFT (via RequestRecord): %s ns\n"
                "   • Rust TTFT (direct calculation): %s ns\n"
                "   • Record TTST (via RequestRecord): %s ns\n"
                "   • Rust TTST (direct calculation): %s ns\n"
                "   • Record Start Time (Rust): %d ns\n"
                "   • First Response Timestamp (Rust): %s ns\n"
                "   • Second Response Timestamp (Rust): %s ns\n"
                "   • Total Rust Chunk Timings: %d\n"
                "   • Timing Source: 100%% Pure Rust (Zero Python timing)",
                rust_ttft_ns,
                completed_request.start_time_ns - rust_chunk_timings[0]
                if rust_chunk_timings
                else "N/A",
                rust_ttst_ns,
                rust_chunk_timings[1] - rust_chunk_timings[0]
                if rust_chunk_timings
                else "N/A",
                record.start_perf_counter_ns,
                record.responses[0].timestamp_ns if record.responses else "N/A",
                record.responses[1].timestamp_ns
                if len(record.responses) > 1
                else "N/A",
                len(rust_chunk_timings),
            )

            # Verify accuracy by comparing our calculations with Rust calculations
            if rust_ttft_ns and rust_chunk_timings:
                rust_direct_ttft = rust_chunk_timings[0]
                accuracy_diff_ns = (
                    abs(rust_ttft_ns - rust_direct_ttft) if rust_direct_ttft else 0
                )
                logger.debug(
                    "🎯 Timing Accuracy: %s nanosecond precision (diff: %d ns)",
                    "Perfect"
                    if accuracy_diff_ns == 0
                    else f"High ({accuracy_diff_ns}ns diff)",
                    accuracy_diff_ns,
                )

        except Exception as e:
            logger.debug("Failed to verify Rust timing accuracy: %s", str(e))

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
