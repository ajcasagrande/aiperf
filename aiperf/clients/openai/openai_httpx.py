# #  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# #  SPDX-License-Identifier: Apache-2.0

# import logging
# import socket
# import ssl
# import time
# import typing
# from typing import Any

# import httpx

# from aiperf.clients.openai.common import (
#     OpenAIBaseRequest,
#     OpenAIBaseResponse,
#     OpenAIChatCompletionRequest,
#     OpenAIChatResponsesRequest,
#     OpenAIClientConfig,
#     OpenAIClientConfigMixin,
#     OpenAICompletionRequest,
#     OpenAIEmbeddingsRequest,
# )
# from aiperf.clients.timers import RequestTimerKind, RequestTimers
# from aiperf.common.enums import (
#     InferenceClientType,
# )
# from aiperf.common.exceptions import InvalidPayloadError
# from aiperf.common.factories import InferenceClientFactory
# from aiperf.common.record_models import (
#     ErrorDetails,
#     InferenceServerResponse,
#     RequestRecord,
# )

# ################################################################################
# # OpenAI Inference Client - HTTPX
# ################################################################################

# logger = logging.getLogger(__name__)


# @InferenceClientFactory.register(InferenceClientType.OPENAI, override_priority=300)
# class OpenAIClientHttpx(OpenAIClientConfigMixin):
#     """A high-performance inference client for communicating with OpenAI based REST APIs using httpx.

#     This class is optimized for maximum performance, concurrent requests, and accurate timing measurements,
#     making it ideal for benchmarking scenarios. Features:
#     - HTTP/2 support for better connection multiplexing
#     - Advanced socket-level optimizations including TCP_NODELAY
#     - Connection pooling optimized for high concurrency
#     - Precise timestamp measurements
#     - SSE streaming with optimal chunk processing
#     """

#     def __init__(self, client_config: OpenAIClientConfig) -> None:
#         super().__init__(client_config)
#         self.http_client = self._create_http_client()

#     def _create_http_client(self) -> httpx.AsyncClient:
#         """Create a new httpx client with performance optimizations."""

#         # Create custom transport with socket optimizations
#         transport = self._create_transport()

#         # Configure timeout - more granular than aiohttp
#         timeout = httpx.Timeout(
#             connect=30.0,  # Connection timeout
#             read=300.0,  # Read timeout
#             write=30.0,  # Write timeout
#             pool=60.0,  # Pool timeout
#         )

#         # Configure limits for high concurrency
#         limits = httpx.Limits(
#             max_keepalive_connections=2500,  # Maximum keepalive connections
#             max_connections=2500,  # Maximum total connections
#             keepalive_expiry=300.0,  # Keepalive expiry time
#         )

#         # Default headers for performance
#         headers = {
#             "User-Agent": "aiperf-httpx/1.0",
#             "Connection": "keep-alive",
#             # "Accept-Encoding": "gzip, deflate, br",  # Enable compression
#         }

#         return httpx.AsyncClient(
#             transport=transport,
#             timeout=timeout,
#             limits=limits,
#             headers=headers,
#             http2=True,  # Enable HTTP/2
#             verify=True,  # SSL verification
#             follow_redirects=False,  # Don't follow redirects for performance
#         )

#     def _create_transport(self) -> httpx.AsyncHTTPTransport:
#         """Create a custom transport with socket-level optimizations."""

#         # Use socket options from config if provided, otherwise use optimal defaults
#         if self.client_config.socket_options:
#             socket_options = self.client_config.socket_options
#         else:
#             # Define socket options for optimal performance
#             socket_options = [
#                 # Core TCP optimizations for low latency
#                 (socket.SOL_TCP, socket.TCP_NODELAY, 1),  # Disable Nagle's algorithm
#                 (socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1),  # Enable keepalive
#             ]

#             # Add Linux-specific TCP optimizations if available
#             if hasattr(socket, "TCP_KEEPIDLE"):
#                 socket_options.extend(
#                     [
#                         (socket.SOL_TCP, socket.TCP_KEEPIDLE, 600),  # 10 min idle
#                         (socket.SOL_TCP, socket.TCP_KEEPINTVL, 60),  # 60 sec intervals
#                         (socket.SOL_TCP, socket.TCP_KEEPCNT, 3),  # 3 probes
#                     ]
#                 )

#             # Add additional Linux-specific optimizations
#             if hasattr(socket, "TCP_QUICKACK"):
#                 socket_options.append((socket.SOL_TCP, socket.TCP_QUICKACK, 1))

#             if hasattr(socket, "TCP_USER_TIMEOUT"):
#                 socket_options.append(
#                     (socket.SOL_TCP, socket.TCP_USER_TIMEOUT, 30000)
#                 )  # 30 sec

#             # Buffer size optimizations for streaming workloads
#             socket_options.extend(
#                 [
#                     (
#                         socket.SOL_SOCKET,
#                         socket.SO_RCVBUF,
#                         1 * 1024 * 1024,
#                     ),  # 16MB receive buffer
#                     (
#                         socket.SOL_SOCKET,
#                         socket.SO_SNDBUF,
#                         1 * 1024 * 1024,
#                     ),  # 16MB send buffer
#                 ]
#             )

#         # Create SSL context optimized for performance
#         ssl_context = ssl.create_default_context()
#         ssl_context.check_hostname = True
#         ssl_context.verify_mode = ssl.CERT_REQUIRED

#         # Performance optimizations for SSL
#         ssl_context.set_ciphers(
#             "ECDHE+AESGCM:ECDHE+CHACHA20:DHE+AESGCM:DHE+CHACHA20"  # noqa
#         )
#         ssl_context.options |= (
#             ssl.OP_NO_SSLv2 | ssl.OP_NO_SSLv3 | ssl.OP_NO_TLSv1 | ssl.OP_NO_TLSv1_1
#         )

#         # Enable ALPN for HTTP/2
#         ssl_context.set_alpn_protocols(["h2", "http/1.1"])

#         return httpx.AsyncHTTPTransport(
#             verify=ssl_context,
#             http2=True,  # Enable HTTP/2
#             retries=0,  # No retries for benchmarking accuracy
#             socket_options=socket_options,  # Apply socket optimizations
#         )

#     async def format_payload(
#         self, endpoint: str, payload: OpenAIBaseRequest | dict[str, Any]
#     ) -> OpenAIBaseRequest:
#         """Format payload for the given endpoint."""
#         if isinstance(payload, dict):
#             return self._convert_dict_to_request(endpoint, payload)
#         return payload

#     def _convert_dict_to_request(
#         self, endpoint: str, payload: dict[str, Any]
#     ) -> OpenAIBaseRequest:
#         """Convert dictionary payload to proper OpenAI request object."""

#         if endpoint == "v1/chat/completions":
#             return OpenAIChatCompletionRequest(
#                 messages=payload["messages"],
#                 model=self.client_config.model,
#                 max_tokens=self.client_config.max_tokens,
#                 kwargs=payload.get("kwargs", {}),
#             )

#         elif endpoint == "v1/completions":
#             return OpenAICompletionRequest(
#                 prompt=payload["prompt"],
#                 model=self.client_config.model,
#                 max_tokens=self.client_config.max_tokens,
#                 kwargs=payload.get("kwargs", {}),
#             )

#         elif endpoint == "v1/embeddings":
#             return OpenAIEmbeddingsRequest(
#                 input=payload["input"],
#                 model=self.client_config.model,
#                 dimensions=payload["dimensions"],
#                 encoding_format=payload["encoding_format"],
#                 user=payload["user"],
#                 kwargs=payload.get("kwargs", {}),
#             )

#         elif endpoint == "v1/responses":
#             return OpenAIChatResponsesRequest(
#                 input=payload["input"],
#                 model=self.client_config.model,
#                 max_output_tokens=self.client_config.max_tokens,
#                 kwargs=payload.get("kwargs", {}),
#             )

#         else:
#             raise ValueError(f"Invalid endpoint: {endpoint}")

#     async def send_request(
#         self, endpoint: str, payload: OpenAIBaseRequest
#     ) -> RequestRecord:
#         """Send request to the specified endpoint with the given payload."""
#         record: RequestRecord[Any] = RequestRecord(
#             start_perf_ns=time.perf_counter_ns(),
#         )

#         try:
#             if isinstance(payload, OpenAIChatCompletionRequest):
#                 record = await self.send_chat_completion_request(payload)

#             elif isinstance(payload, OpenAICompletionRequest):
#                 record = await self.send_completion_request(payload)

#             elif isinstance(payload, OpenAIEmbeddingsRequest):
#                 record = await self.send_embeddings_request(payload)

#             elif isinstance(payload, OpenAIChatResponsesRequest):
#                 record = await self.send_chat_responses_request(payload)

#             else:
#                 raise InvalidPayloadError(f"Invalid payload: {payload}")

#         except InvalidPayloadError:
#             raise  # re-raise the error to be handled by the caller

#         except Exception as e:
#             # swallow all other errors and return a generic error response
#             record.responses.append(
#                 InferenceClientErrorResponse(
#                     perf_ns=time.perf_counter_ns(),
#                     error=str(e),
#                 )
#             )

#         return record

#     async def send_completion_request(
#         self, payload: OpenAICompletionRequest
#     ) -> RequestRecord[Any]:
#         raise NotImplementedError(
#             "OpenAIClientHttpx does not support completion requests"
#         )

#     async def send_embeddings_request(
#         self, payload: OpenAIEmbeddingsRequest
#     ) -> RequestRecord[Any]:
#         raise NotImplementedError(
#             "OpenAIClientHttpx does not support embeddings requests"
#         )

#     async def send_chat_responses_request(
#         self, payload: OpenAIChatResponsesRequest
#     ) -> RequestRecord[Any]:
#         raise NotImplementedError(
#             "OpenAIClientHttpx does not support chat responses requests"
#         )

#     async def send_chat_completion_request(
#         self, payload: OpenAIChatCompletionRequest
#     ) -> RequestRecord[Any]:
#         """Send chat completion request using httpx with optimal performance."""

#         # Initialize RequestTimers for precise timing
#         timers = RequestTimers()
#         record: RequestRecord[Any] | None = None

#         try:
#             # Prepare request payload
#             request_payload = {
#                 "model": self.client_config.model,
#                 "messages": payload.messages,
#                 "max_tokens": self.client_config.max_tokens,
#                 "stream": True,
#             }

#             # Add optional parameters if configured
#             if self.client_config.stop:
#                 request_payload["stop"] = self.client_config.stop

#             # Add any additional kwargs from payload
#             if payload.kwargs:
#                 request_payload.update(payload.kwargs)

#             # Prepare headers
#             headers = {
#                 "Content-Type": "application/json",
#                 "Accept": "text/event-stream",
#             }

#             if self.client_config.api_key:
#                 headers["Authorization"] = f"Bearer {self.client_config.api_key}"

#             if self.client_config.organization:
#                 headers["OpenAI-Organization"] = self.client_config.organization

#             # Construct full URL
#             base_url = (
#                 f"https://{self.client_config.url}"
#                 if not self.client_config.url.startswith(("http://", "https://"))
#                 else self.client_config.url
#             )
#             url = f"{base_url.rstrip('/')}/{self.client_config.endpoint}"

#             # Create record and capture initial timestamp
#             record = RequestRecord(
#                 start_perf_ns=timers.capture_timestamp(RequestTimerKind.REQUEST_START),
#             )

#             timers.capture_timestamp(RequestTimerKind.SEND_START)

#             # Make the streaming request with httpx
#             async with self.http_client.stream(
#                 "POST",
#                 url,
#                 json=request_payload,
#                 headers=headers,
#             ) as response:
#                 timers.capture_timestamp(RequestTimerKind.SEND_END)

#                 # Check for HTTP errors
#                 if response.status_code != 200:
#                     error_text = await response.aread()
#                     record.responses.append(
#                         InferenceClientErrorResponse(
#                             perf_ns=time.perf_counter_ns(),
#                             error=f"HTTP {response.status_code}: {error_text.decode('utf-8', errors='replace')}",
#                         )
#                     )
#                     return record

#                 timers.capture_timestamp(RequestTimerKind.RECV_START)

#                 # Process SSE stream with optimal performance
#                 buffer = ""
#                 async for chunk in self._aiter_sse_chunks(response):
#                     chunk_timestamp = time.perf_counter_ns()

#                     buffer += chunk

#                     # Process complete lines efficiently
#                     while "\n" in buffer:
#                         line, buffer = buffer.split("\n", 1)
#                         line = line.strip()

#                         if not line:
#                             continue

#                         # Handle SSE format
#                         if line.startswith("data: "):
#                             data_content = line[6:]  # Remove "data: " prefix

#                             # Check for stream end
#                             if data_content == "[DONE]":
#                                 timers.capture_timestamp(RequestTimerKind.RECV_END)
#                                 break

#                             # Skip empty data chunks at the start
#                             if (
#                                 data_content.strip() == ""
#                                 and len(record.responses) == 0
#                             ):
#                                 continue

#                             try:
#                                 timers.capture_chunk_start_timestamp(chunk_timestamp)
#                                 # Store the raw SSE data directly for most accurate timing
#                                 record.responses.append(
#                                     InferenceClientResponse[str](
#                                         perf_ns=chunk_timestamp,
#                                         response=SSEDataField(data=data_content),
#                                     )
#                                 )
#                             except Exception as e:
#                                 # Handle any response processing errors
#                                 record.responses.append(
#                                     InferenceClientErrorResponse(
#                                         perf_ns=chunk_timestamp,
#                                         error=str(e),
#                                     )
#                                 )
#                                 continue

#                         elif line.startswith("event: error"):
#                             logger.error("Error event in streaming API call: %s", line)
#                             record.responses.append(
#                                 InferenceClientErrorResponse(
#                                     perf_ns=chunk_timestamp,
#                                     error=line,
#                                 )
#                             )
#                             break

#                 timers.capture_timestamp(RequestTimerKind.RECV_END)

#         except Exception as e:
#             logger.error("Error in httpx request: %s", str(e))

#             record.error = ErrorDetails(
#                 type=e.__class__.__name__,
#                 message=str(e),
#             )

#         finally:
#             timers.capture_timestamp(RequestTimerKind.REQUEST_END)

#             # Log precise timing information for debugging/monitoring
#             try:
#                 total_duration = timers.duration(
#                     RequestTimerKind.REQUEST_START, RequestTimerKind.REQUEST_END
#                 )
#                 send_duration = timers.duration(
#                     RequestTimerKind.SEND_START, RequestTimerKind.SEND_END
#                 )
#                 recv_duration = timers.duration(
#                     RequestTimerKind.RECV_START, RequestTimerKind.RECV_END
#                 )

#                 logger.debug(
#                     "HTTPX Request timing - Total: %d ns, Send: %d ns, Receive: %d ns",
#                     total_duration,
#                     send_duration,
#                     recv_duration,
#                 )
#             except Exception:
#                 # Don't fail on timing logging errors
#                 pass

#         # Ensure record is never None
#         if record is None:
#             record = RequestRecord(start_perf_ns=time.perf_counter_ns())

#         return record

#     async def _aiter_sse_chunks(
#         self, response: httpx.Response, chunk_size: int = 1024
#     ) -> typing.AsyncIterator[str]:
#         """Efficiently iterate over SSE chunks from httpx response.

#         Args:
#             response: The httpx response object
#             chunk_size: Size of chunks to read (optimized for HTTP/2)
#         """
#         # Use larger chunk size for HTTP/2 efficiency
#         async for chunk in response.aiter_bytes(chunk_size=chunk_size):
#             if chunk:
#                 try:
#                     # Use the fastest available decoder
#                     yield chunk.decode("utf-8")
#                 except UnicodeDecodeError:
#                     # Handle potential encoding issues gracefully
#                     yield chunk.decode("utf-8", errors="replace")

#     async def parse_response(
#         self, response: OpenAIBaseResponse
#     ) -> InferenceServerResponse:
#         """Parse response (not implemented for streaming responses)."""
#         raise NotImplementedError(
#             "OpenAIClientHttpx does not support parsing responses"
#         )

#     async def __aenter__(self):
#         """Async context manager entry."""
#         return self

#     async def __aexit__(self, exc_type, exc_val, exc_tb):
#         """Async context manager exit - cleanup client."""
#         logger.debug("Async context manager exit - cleanup httpx client.")
#         await self.http_client.aclose()
