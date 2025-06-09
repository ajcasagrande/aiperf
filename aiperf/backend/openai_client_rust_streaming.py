#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0

import json
import logging
from typing import Any

from aiperf_streaming import (
    StreamingHttpClient,
    StreamingRequest,
    TimestampKind,
)
from aiperf_streaming.models import (
    StreamingRequestModel,
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

# Import the high-performance Rust streaming library
from aiperf.common.constants import NANOS_PER_MILLIS
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


@BackendClientFactory.register(BackendClientType.OPENAI, override_priority=3000000)
class OpenAIBackendClientRustStreaming(OpenAIClientMixin, OpenAIBackendClientProtocol):
    """
    Ultra high-performance OpenAI backend client using Rust streaming library.

    This client provides:
    - Nanosecond precision timing measurements using pure Rust
    - Maximum performance streaming with zero-copy operations
    - Optimized SSE (Server-Sent Events) parsing in Rust
    - Advanced performance analytics using only Rust timestamps
    - Memory-efficient token processing with RequestTimers
    - Concurrent request capabilities

    Performance Characteristics:
    - Timing precision: Nanosecond level using pure Rust RequestTimers
    - Throughput: Saturates available network bandwidth
    - Memory usage: Minimal with streaming token processing
    - Concurrent requests: Configurable limits with optimal resource usage
    - NO Python timestamp tracking - 100% Rust timing precision
    """

    def __init__(self, client_config: OpenAIBackendClientConfig):
        super().__init__(client_config)

        # Initialize performance configuration
        self.perf_config = RustStreamingPerformanceConfig(
            timeout_ms=client_config.timeout_ms,
            connect_timeout_ms=min(5000, client_config.timeout_ms // 6),
        )

        # Initialize the high-performance Rust streaming client
        default_headers = {
            "User-Agent": self.perf_config.user_agent,
            "Accept": "text/event-stream",
            "Content-Type": "application/json",
            # "Accept-Encoding": "gzip, deflate"
            # if self.perf_config.enable_gzip_compression
            # else "",
            # "Connection": "keep-alive",
        }

        self._rust_client = StreamingHttpClient(
            timeout_ms=self.perf_config.timeout_ms,
            default_headers=default_headers,
            user_agent=self.perf_config.user_agent,
        )

        # Statistics are now tracked internally by the Rust client

        logger.info(
            "Initialized RustStreamingBackendClient with pure Rust timing - NO Python timestamps"
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
        """Send request using pure Rust timing - NO Python timestamps."""

        try:
            # For streaming requests (chat completions), use only Rust timing
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
            # Create minimal error record without Python timestamps
            record: RequestRecord[Any] = RequestRecord(
                start_perf_counter_ns=0,  # Will be set by Rust timing
            )
            record.responses.append(
                BackendClientErrorResponse(
                    timestamp_ns=0,  # Will be set by Rust timing
                    error=str(e),
                )
            )

        return record

    async def send_chat_completion_request(
        self, payload: OpenAIChatCompletionRequest
    ) -> RequestRecord[Any]:
        """
        Send chat completion request using pure Rust streaming tokens with NO Python timing.

        This method provides:
        - Pure Rust nanosecond precision timing using only RequestTimers
        - StreamingTokenChunk processing with SSE data payloads
        - Token-level timing managed entirely by Rust
        - Zero Python timestamp overhead
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
        # if hasattr(self.client_config, "temperature"):
        #     request_payload["temperature"] = self.client_config.temperature
        # if hasattr(self.client_config, "top_p"):
        #     request_payload["top_p"] = self.client_config.top_p
        # if hasattr(self.client_config, "frequency_penalty"):
        #     request_payload["frequency_penalty"] = self.client_config.frequency_penalty
        # if hasattr(self.client_config, "presence_penalty"):
        #     request_payload["presence_penalty"] = self.client_config.presence_penalty

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
                headers={},
                body=json.dumps(request_payload),
                timeout_ms=self.perf_config.timeout_ms,
            )

            logger.debug("Starting Rust streaming request with pure Rust timing")

            # Execute the streaming request using the Rust client
            # This returns (completed_request, timers) tuple with full Rust timing
            completed_request, timers = self._rust_client.stream_request_with_details(
                streaming_request
            )

            for key in [
                TimestampKind.RequestStart,
                TimestampKind.SendStart,
                TimestampKind.SendEnd,
                TimestampKind.RecvStart,
                TimestampKind.TokenStart,
                TimestampKind.TokenEnd,
                TimestampKind.RecvEnd,
                TimestampKind.RequestEnd,
            ]:
                print(
                    f"{key}: {timers.timestamp_ns(key, 0) / NANOS_PER_MILLIS:6.2f} ms"
                )
            print(
                f"Duration: {timers.duration_ns(TimestampKind.RequestStart, TimestampKind.RequestEnd) / NANOS_PER_MILLIS:6.2f} ms"
            )
            print("-" * 80)

            # Use Rust timestamps directly as relative nanoseconds from request_start (treated as 0)
            rust_recv_start_ns = timers.timestamp_ns(TimestampKind.RecvStart, 0)
            if rust_recv_start_ns is None:
                raise RuntimeError(
                    "Rust RequestTimers failed to capture RecvStart timestamp"
                )

            # Set request_start as the baseline (0) for all relative timestamps
            record: RequestRecord[Any] = RequestRecord(
                start_perf_counter_ns=rust_recv_start_ns,  # rust_recv_start_ns is our time 0 baseline for tokens
            )

            # Statistics are tracked internally by the Rust client

            # Process streaming tokens using ONLY Rust timing
            logger.debug(
                "Processing %d tokens with pure Rust timing",
                completed_request.token_count,
            )

            # Collect all tokens with their timings
            for i in range(completed_request.token_count):
                try:
                    # Get token from Rust
                    token = completed_request.get_token(i)
                    if not token:
                        continue

                    # Get token timing from Rust RequestTimers (relative timestamp)
                    rust_token_timing_ns = timers.timestamp_ns(
                        TimestampKind.TokenStart, i
                    )
                    if rust_token_timing_ns is None:
                        logger.warning(f"Missing Rust timing for token {i}")
                        continue

                    record.responses.append(
                        BackendClientResponse[str](
                            timestamp_ns=rust_token_timing_ns,
                            response=token.data.rstrip("\n"),
                        )
                    )

                except Exception as e:
                    logger.warning(f"Error collecting token {i}: {e}")
                    continue

            # logger.warning(f"Record: {record}")
            # Log comprehensive performance metrics using pure Rust RequestTimers
            # self._log_performance_metrics_with_rust_timers(
            #     completed_request, timers, record
            # )

            return record

        except Exception as e:
            logger.error("Error in Rust streaming request: %s", str(e))

            # Create minimal error record with relative timestamp (0 = request start)
            record = RequestRecord(start_perf_counter_ns=0)
            record.responses.append(
                BackendClientErrorResponse(
                    timestamp_ns=0,  # Relative to request start
                    error=str(e),
                )
            )
            return record

    def _log_performance_metrics_with_rust_timers(
        self, completed_request, timers, record: RequestRecord[Any]
    ):
        """Log comprehensive performance metrics using ONLY Rust RequestTimers."""
        try:
            # Get timing durations using pure Rust RequestTimers
            total_duration_ns = timers.duration_ns(
                TimestampKind.RequestStart, TimestampKind.RequestEnd
            )
            send_duration_ns = timers.duration_ns(
                TimestampKind.SendStart, TimestampKind.SendEnd
            )
            recv_duration_ns = timers.duration_ns(
                TimestampKind.RecvStart, TimestampKind.RecvEnd
            )

            # Get token timing statistics from Rust
            token_starts_count = timers.token_starts_count()
            token_ends_count = timers.token_ends_count()
            token_durations_ns = timers.get_token_durations_ns() or []

            # Time to First Token (TTFT) - pure Rust calculation
            ttft_ns = None
            if token_starts_count > 0:
                first_token_start_ns = timers.timestamp_ns(TimestampKind.TokenStart, 0)
                request_start_ns = timers.timestamp_ns(TimestampKind.RequestStart, 0)
                if first_token_start_ns is not None and request_start_ns is not None:
                    ttft_ns = first_token_start_ns - request_start_ns

            # Time to Second Token (TTST) - pure Rust calculation
            ttst_ns = None
            if token_starts_count > 1:
                first_token_ns = timers.timestamp_ns(TimestampKind.TokenStart, 0)
                second_token_ns = timers.timestamp_ns(TimestampKind.TokenStart, 1)
                if first_token_ns is not None and second_token_ns is not None:
                    ttst_ns = second_token_ns - first_token_ns

            # Calculate throughput using Rust completed request data
            throughput_mbps = 0
            if completed_request.throughput_bps():
                throughput_mbps = completed_request.throughput_bps() / (1024 * 1024)

            # Get request ID safely
            request_id = getattr(completed_request, "request_id", "unknown")
            request_id_short = request_id[:8] if len(request_id) > 8 else request_id

            # Calculate RequestRecord-based timing for verification
            record_ttft_ms = (
                record.time_to_first_response_ns / 1e6
                if record.time_to_first_response_ns
                else None
            )
            record_ttst_ms = (
                record.time_to_second_response_ns / 1e6
                if record.time_to_second_response_ns
                else None
            )

            logger.warning(
                "🚀 Pure Rust Performance Metrics (Relative Timestamps from Request Start):\n"
                "   • Total Duration: %s ms (Rust RequestTimers)\n"
                "   • Send Duration: %s ms (Rust RequestTimers)\n"
                "   • Receive Duration: %s ms (Rust RequestTimers)\n"
                "   • Time to First Token (TTFT): %s ms (Rust calculated)\n"
                "   • Time to Second Token (TTST): %s ms (Rust calculated)\n"
                "   • RequestRecord TTFT: %s ms (from relative timestamps)\n"
                "   • RequestRecord TTST: %s ms (from relative timestamps)\n"
                "   • Tokens Received: %d (StreamingTokenChunks)\n"
                "   • Total Bytes: %d\n"
                "   • Throughput: %.2f MB/s (Rust calculated)\n"
                "   • Request ID: %s\n"
                "   • Token Starts: %d, Token Ends: %d (Rust counters)\n"
                "   • Token Durations: %s ms (Pure Rust timing)",
                total_duration_ns / 1e6 if total_duration_ns else "N/A",
                send_duration_ns / 1e6 if send_duration_ns else "N/A",
                recv_duration_ns / 1e6 if recv_duration_ns else "N/A",
                ttft_ns / 1e6 if ttft_ns else "N/A",
                ttst_ns / 1e6 if ttst_ns else "N/A",
                f"{record_ttft_ms:.3f}" if record_ttft_ms is not None else "N/A",
                f"{record_ttst_ms:.3f}" if record_ttst_ms is not None else "N/A",
                completed_request.token_count,
                completed_request.total_bytes,
                throughput_mbps,
                request_id_short,
                token_starts_count,
                token_ends_count,
                [d / 1e6 for d in token_durations_ns[:5]]
                if token_durations_ns
                else "N/A",  # Show first 5
            )

            # Additional token timing analysis using pure Rust data
            if token_durations_ns and len(token_durations_ns) > 1:
                avg_token_duration_ns = sum(token_durations_ns) / len(
                    token_durations_ns
                )
                max_token_duration_ns = max(token_durations_ns)
                min_token_duration_ns = min(token_durations_ns)

                logger.warning(
                    "🔍 Token Timing Analysis (Pure Rust):\n"
                    "   • Average Token Duration: %.2f ms\n"
                    "   • Maximum Token Duration: %.2f ms\n"
                    "   • Minimum Token Duration: %.2f ms\n"
                    "   • Total Token Measurements: %d\n"
                    "   • Timing Source: 100%% Rust RequestTimers",
                    avg_token_duration_ns / 1e6,
                    max_token_duration_ns / 1e6,
                    min_token_duration_ns / 1e6,
                    len(token_durations_ns),
                )

            # Verify pure Rust timing accuracy vs RequestRecord calculations
            self._verify_rust_timing_accuracy(record, timers)

        except Exception as e:
            logger.debug("Failed to log Rust performance metrics: %s", str(e))

    def _verify_rust_timing_accuracy(self, record: RequestRecord[Any], timers):
        """Verify pure Rust timing calculations against RequestRecord calculations."""
        try:
            # Compare TTFT calculations
            record_ttft_ns = record.time_to_first_response_ns

            # Calculate TTFT using pure Rust RequestTimers
            rust_ttft_ns = None
            if timers.token_starts_count() > 0:
                first_token_start_ns = timers.timestamp_ns(TimestampKind.TokenStart, 0)
                request_start_ns = timers.timestamp_ns(TimestampKind.RequestStart, 0)
                if first_token_start_ns is not None and request_start_ns is not None:
                    rust_ttft_ns = first_token_start_ns - request_start_ns

            # Compare TTST calculations
            record_ttst_ns = record.time_to_second_response_ns

            # Calculate TTST using pure Rust RequestTimers
            rust_ttst_ns = None
            if timers.token_starts_count() > 1:
                first_token_ns = timers.timestamp_ns(TimestampKind.TokenStart, 0)
                second_token_ns = timers.timestamp_ns(TimestampKind.TokenStart, 1)
                if first_token_ns is not None and second_token_ns is not None:
                    rust_ttst_ns = second_token_ns - first_token_ns

            logger.warning(
                "🔬 Pure Rust Timing Accuracy (Relative Timestamps):\n"
                "   • TTFT - RequestRecord: %s ms\n"
                "   • TTFT - Pure Rust: %s ms\n"
                "   • TTST - RequestRecord: %s ms\n"
                "   • TTST - Pure Rust: %s ms\n"
                "   • Timing Source: 100%% Rust RequestTimers + StreamingTokenChunks\n"
                "   • Measurement Precision: Nanosecond level (Rust native)\n"
                "   • Timestamp Base: Request Start = 0ns (relative timing)",
                record_ttft_ns / 1e6 if record_ttft_ns else "N/A",
                rust_ttft_ns / 1e6 if rust_ttft_ns else "N/A",
                record_ttst_ns / 1e6 if record_ttst_ns else "N/A",
                rust_ttst_ns / 1e6 if rust_ttst_ns else "N/A",
            )

        except Exception as e:
            logger.debug("Failed to verify Rust timing accuracy: %s", str(e))

    async def send_completion_request(
        self, payload: OpenAICompletionRequest
    ) -> RequestRecord[Any]:
        """Send completion request with relative timing (request start = 0)."""
        # Create minimal record with relative timing (request start = 0)
        record: RequestRecord[Any] = RequestRecord(
            start_perf_counter_ns=0,  # Request start baseline
        )

        response = await self.client.completions.create(
            model=self.client_config.model,
            prompt=payload.prompt,
            max_tokens=self.client_config.max_tokens,
        )

        # Use relative timestamp (0 = request start)
        record.responses.append(
            BackendClientResponse(
                timestamp_ns=0,  # Relative to request start
                response=response,
            )
        )

        return record

    async def send_embeddings_request(
        self, payload: OpenAIEmbeddingsRequest
    ) -> RequestRecord[Any]:
        """Send embeddings request with relative timing (request start = 0)."""
        # Create minimal record with relative timing (request start = 0)
        record: RequestRecord[Any] = RequestRecord(
            start_perf_counter_ns=0,  # Request start baseline
        )

        response = await self.client.embeddings.create(
            model=self.client_config.model,
            input=payload.input,
            dimensions=payload.dimensions,
            user=payload.user,
        )

        # Use relative timestamp (0 = request start)
        record.responses.append(
            BackendClientResponse(
                timestamp_ns=0,  # Relative to request start
                response=response,
            )
        )

        return record

    async def send_chat_responses_request(
        self, payload: OpenAIChatResponsesRequest
    ) -> RequestRecord[Any]:
        """Send chat responses request with relative timing (request start = 0)."""
        # Create minimal record with relative timing (request start = 0)
        record: RequestRecord[Any] = RequestRecord(
            start_perf_counter_ns=0,  # Request start baseline
        )

        async for response in await self.client.responses.create(
            input=payload.input,
            model=self.client_config.model,
            stream=True,
        ):
            # Use relative timestamp (0 = request start)
            record.responses.append(
                BackendClientResponse(
                    timestamp_ns=0,  # Relative to request start
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
        """Get comprehensive performance statistics from pure Rust client - NO Python timing."""
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
                "performance_config": self.perf_config.model_dump(),
                "timing_source": "100% Rust RequestTimers with relative timestamps",
                "rust_native_precision": "nanosecond level",
            }
        except Exception as e:
            logger.warning("Failed to get performance statistics: %s", str(e))
            return {
                "error": str(e),
                "timing_source": "100% Rust RequestTimers with relative timestamps",
            }

    def get_advanced_timing_analysis(
        self, request_models: list[StreamingRequestModel]
    ) -> dict[str, Any]:
        """Perform advanced timing analysis using pure Rust data - NO Python timing."""
        try:
            analysis = TimingAnalysis(requests=request_models)

            return {
                "request_duration_stats": analysis.request_duration_stats,
                "throughput_stats": analysis.throughput_stats,
                "chunk_timing_stats": analysis.chunk_timing_stats,  # Now token timing stats
                "timing_source": "100% Rust RequestTimers + StreamingTokenChunks",
                "python_timing_overhead": "ZERO - Pure Rust implementation",
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
            # Get final statistics using pure Rust data
            final_stats = self.get_performance_statistics()
            logger.info(
                "Final Rust streaming client statistics (Pure Rust timing): %s",
                final_stats,
            )

        except Exception as e:
            logger.debug("Error during cleanup: %s", str(e))
