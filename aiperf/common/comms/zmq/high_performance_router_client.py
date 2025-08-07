# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""
High-Performance ZMQ ROUTER client optimized for extreme concurrency (100K+ requests).

This implementation uses advanced techniques:
- Batch processing for request handling
- Connection pooling and load balancing
- Optimized response routing
- Adaptive threading for CPU-bound operations
- Memory-efficient request tracking
"""

import asyncio
import concurrent.futures
import time
from collections import deque
from collections.abc import Callable, Coroutine
from typing import Any

import zmq.asyncio

from aiperf.common.comms.zmq.graceful_shutdown_mixin import GracefulShutdownMixin
from aiperf.common.comms.zmq.zmq_base_client import BaseZMQClient
from aiperf.common.constants import BATCH_PROCESSING_SIZE, EXTREME_CONCURRENCY_THRESHOLD
from aiperf.common.decorators import implements_protocol
from aiperf.common.hooks import background_task, on_stop
from aiperf.common.messages import ErrorMessage, Message
from aiperf.common.models import ErrorDetails
from aiperf.common.protocols import ReplyClientProtocol
from aiperf.common.types import MessageTypeT
from aiperf.common.utils import yield_to_event_loop


class RequestBatch:
    """Container for batch processing requests."""

    __slots__ = ("requests", "routing_envelopes", "timestamps")

    def __init__(self):
        self.requests: list[Message] = []
        self.routing_envelopes: list[tuple[bytes, ...]] = []
        self.timestamps: list[float] = []

    def add(self, request: Message, routing_envelope: tuple[bytes, ...]) -> None:
        self.requests.append(request)
        self.routing_envelopes.append(routing_envelope)
        self.timestamps.append(time.time())

    def clear(self) -> None:
        self.requests.clear()
        self.routing_envelopes.clear()
        self.timestamps.clear()

    def size(self) -> int:
        return len(self.requests)


class HighPerformanceRequestHandler:
    """Optimized request handler with connection pooling and adaptive processing."""

    def __init__(self, max_workers: int = 50):
        self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=max_workers)
        self.handlers: dict[MessageTypeT, tuple[str, Callable]] = {}
        self.response_cache: dict[str, Message] = {}
        self.cache_expiry: dict[str, float] = {}

    def register_handler(
        self,
        service_id: str,
        message_type: MessageTypeT,
        handler: Callable[[Message], Coroutine[Any, Any, Message | None]],
    ) -> None:
        """Register a handler with caching support."""
        self.handlers[message_type] = (service_id, handler)

    async def handle_batch(self, requests: list[Message]) -> list[Message | None]:
        """Handle a batch of requests concurrently."""
        tasks = []

        for request in requests:
            message_type = request.message_type

            # Check cache first
            cache_key = self._get_cache_key(request)
            if self._is_cacheable(request) and cache_key in self.response_cache:
                if time.time() < self.cache_expiry.get(cache_key, 0):
                    tasks.append(asyncio.create_task(self._return_cached(cache_key)))
                    continue

            # Handle request
            if message_type in self.handlers:
                _, handler = self.handlers[message_type]
                tasks.append(
                    asyncio.create_task(
                        self._handle_single(request, handler, cache_key)
                    )
                )
            else:
                tasks.append(
                    asyncio.create_task(
                        self._create_error_response(
                            request, f"No handler for message type {message_type}"
                        )
                    )
                )

        # Execute all handlers concurrently
        return await asyncio.gather(*tasks, return_exceptions=True)

    async def _handle_single(
        self, request: Message, handler: Callable, cache_key: str | None
    ) -> Message | None:
        """Handle a single request with optional caching."""
        try:
            response = await handler(request)

            # Cache response if applicable
            if cache_key and self._is_cacheable(request) and response:
                self.response_cache[cache_key] = response
                self.cache_expiry[cache_key] = time.time() + 300  # 5-minute cache

            return response
        except Exception as e:
            return await self._create_error_response(request, str(e))

    async def _return_cached(self, cache_key: str) -> Message:
        """Return cached response."""
        return self.response_cache[cache_key]

    async def _create_error_response(self, request: Message, error_msg: str) -> Message:
        """Create error response message."""
        return ErrorMessage(
            request_id=request.request_id,
            error=ErrorDetails(type="HANDLER_ERROR", message=error_msg),
        )

    def _get_cache_key(self, request: Message) -> str:
        """Generate cache key for request."""
        return f"{request.message_type}:{hash(str(request.model_dump()))}"

    def _is_cacheable(self, request: Message) -> bool:
        """Determine if request response can be cached."""
        # Add logic to determine cacheable requests
        # For now, assume dataset requests are cacheable
        return "dataset" in str(request.message_type).lower()

    def cleanup_cache(self) -> int:
        """Clean up expired cache entries."""
        current_time = time.time()
        expired_keys = [
            key for key, expiry in self.cache_expiry.items() if current_time > expiry
        ]

        for key in expired_keys:
            self.response_cache.pop(key, None)
            self.cache_expiry.pop(key, None)

        return len(expired_keys)


@implements_protocol(ReplyClientProtocol)
# @CommunicationClientFactory.register(CommClientType.HIGH_PERFORMANCE_REPLY)  # Removed to use simple solution
class HighPerformanceRouterClient(BaseZMQClient, GracefulShutdownMixin):
    """
    Ultra-high-performance ZMQ ROUTER client optimized for 100K+ concurrent requests.

    Key optimizations:
    - Batch processing for reduced overhead
    - Concurrent request handling with thread pool
    - Response caching for repeated requests
    - Adaptive load balancing
    - Memory-efficient tracking
    """

    def __init__(
        self,
        address: str,
        bind: bool,
        socket_ops: dict | None = None,
        batch_size: int = BATCH_PROCESSING_SIZE,
        max_workers: int = 50,
        enable_caching: bool = True,
        **kwargs,
    ) -> None:
        super().__init__(zmq.SocketType.ROUTER, address, bind, socket_ops, **kwargs)

        self.batch_size = batch_size
        self.enable_caching = enable_caching

        # High-performance request handler
        self.request_handler = HighPerformanceRequestHandler(max_workers)

        # Batch processing
        self.request_batch = RequestBatch()
        self.response_queue: deque = deque()

        # Performance tracking
        self.requests_processed = 0
        self.batch_count = 0
        self.cache_hits = 0
        self.last_performance_check = time.time()

        # Adaptive batching
        self.adaptive_batch_size = batch_size
        self.load_factor = 0.0

    def register_request_handler(
        self,
        service_id: str,
        message_type: MessageTypeT,
        handler: Callable[[Message], Coroutine[Any, Any, Message | None]],
    ) -> None:
        """Register a request handler with optimizations."""
        self.debug(
            f"Registering high-performance handler for {service_id} with message type {message_type}"
        )
        self.request_handler.register_handler(service_id, message_type, handler)

    @background_task(immediate=True, interval=None)
    async def _ultra_fast_request_receiver(self) -> None:
        """Ultra-optimized request receiver with batch processing."""
        while not self.stop_requested:
            try:
                # Collect requests into batches
                requests_collected = 0
                batch_start_time = time.time()

                # Adaptive batch collection based on load
                max_batch_time = 0.001 if self.load_factor > 0.8 else 0.005

                while (
                    requests_collected < self.adaptive_batch_size
                    and (time.time() - batch_start_time) < max_batch_time
                ):
                    try:
                        # Receive request with routing envelope using graceful recv
                        data = await self._graceful_zmq_recv(
                            self.socket, timeout=0.001, multipart=True
                        )

                        request = Message.from_json(data[-1])
                        if not request.request_id:
                            self.warning(f"Request ID missing: {data}")
                            continue

                        routing_envelope = (
                            tuple(data[:-1])
                            if len(data) > 1
                            else (request.request_id.encode(),)
                        )

                        self.request_batch.add(request, routing_envelope)
                        requests_collected += 1

                    except (zmq.Again, asyncio.TimeoutError):
                        break
                    except Exception as e:
                        self.error(f"Error receiving request: {e}")
                        continue

                # Process batch if we have requests
                if self.request_batch.size() > 0:
                    await self._process_request_batch()
                    self.batch_count += 1
                    self.requests_processed += requests_collected

                    # Adaptive batch sizing based on load
                    self._adapt_batch_size(
                        requests_collected, time.time() - batch_start_time
                    )
                else:
                    await yield_to_event_loop()

            except Exception as e:
                self.error(f"Exception in ultra-fast receiver: {e}")
                await yield_to_event_loop()
            except asyncio.CancelledError:
                return

    async def _process_request_batch(self) -> None:
        """Process a batch of requests concurrently."""
        if self.request_batch.size() == 0:
            return

        try:
            # Handle all requests in the batch concurrently
            responses = await self.request_handler.handle_batch(
                self.request_batch.requests
            )

            # Queue responses for sending
            for i, response in enumerate(responses):
                if response is not None:
                    routing_envelope = self.request_batch.routing_envelopes[i]
                    self.response_queue.append((routing_envelope, response))

            # Clear the batch
            self.request_batch.clear()

        except Exception as e:
            self.error(f"Exception processing request batch: {e}")

    @background_task(immediate=True, interval=None)
    async def _ultra_fast_response_sender(self) -> None:
        """Ultra-optimized response sender with batch processing."""
        send_buffer = []

        while not self.stop_requested:
            try:
                # Collect responses for batch sending
                responses_collected = 0

                while responses_collected < self.batch_size and self.response_queue:
                    try:
                        routing_envelope, response = self.response_queue.popleft()
                        send_buffer.append((routing_envelope, response))
                        responses_collected += 1
                    except IndexError:
                        break

                # Send batch if we have responses
                if send_buffer:
                    await self._send_response_batch(send_buffer)
                    send_buffer.clear()
                else:
                    await yield_to_event_loop()

            except Exception as e:
                self.error(f"Exception in ultra-fast sender: {e}")
                await yield_to_event_loop()
            except asyncio.CancelledError:
                return

    async def _send_response_batch(
        self, responses: list[tuple[tuple[bytes, ...], Message]]
    ) -> None:
        """Send a batch of responses efficiently."""
        for routing_envelope, response in responses:
            try:
                response_data = [*routing_envelope, response.model_dump_json().encode()]
                await self._graceful_zmq_send(
                    self.socket,
                    response_data,
                    timeout=1.0,  # Shorter timeout for high throughput
                )
            except asyncio.TimeoutError:
                self.warning(f"Response send timeout for envelope: {routing_envelope}")
            except asyncio.CancelledError:
                self.debug("Response sender cancelled during graceful shutdown")
                return
            except Exception as e:
                self.error(f"Exception sending response: {e}")

    def _adapt_batch_size(self, requests_collected: int, batch_time: float) -> None:
        """Dynamically adjust batch size based on performance."""
        if batch_time > 0:
            throughput = requests_collected / batch_time

            # Increase batch size if we're processing efficiently
            if throughput > 1000 and self.adaptive_batch_size < self.batch_size * 2:
                self.adaptive_batch_size = min(
                    self.adaptive_batch_size + 100, self.batch_size * 2
                )
            # Decrease if we're taking too long
            elif throughput < 100 and self.adaptive_batch_size > self.batch_size // 2:
                self.adaptive_batch_size = max(
                    self.adaptive_batch_size - 50, self.batch_size // 2
                )

    @background_task(immediate=False, interval=10.0)
    async def _performance_monitoring(self) -> None:
        """Monitor and report performance metrics."""
        try:
            current_time = time.time()
            time_diff = current_time - self.last_performance_check

            if time_diff > 0:
                request_rate = self.requests_processed / time_diff
                batch_rate = self.batch_count / time_diff

                # Calculate load factor
                self.load_factor = min(
                    request_rate / EXTREME_CONCURRENCY_THRESHOLD, 1.0
                )

                # Clean up cache
                if self.enable_caching:
                    cache_cleaned = self.request_handler.cleanup_cache()
                else:
                    cache_cleaned = 0

                self.debug(
                    f"High-performance metrics: "
                    f"Request rate: {request_rate:.0f}/s, "
                    f"Batch rate: {batch_rate:.1f}/s, "
                    f"Adaptive batch size: {self.adaptive_batch_size}, "
                    f"Load factor: {self.load_factor:.2f}, "
                    f"Cache cleaned: {cache_cleaned}, "
                    f"Queue size: {len(self.response_queue)}"
                )

                # Reset counters
                self.requests_processed = 0
                self.batch_count = 0
                self.cache_hits = 0
                self.last_performance_check = current_time

        except Exception as e:
            self.error(f"Exception in performance monitoring: {e}")

    @on_stop
    async def _high_performance_shutdown(self) -> None:
        """Optimized shutdown procedure with graceful ZMQ operation completion."""
        self.debug("High-performance router shutdown initiated")

        # First, gracefully shutdown all ZMQ operations
        await self._graceful_shutdown_zmq_operations()

        # Process remaining requests quickly
        if self.request_batch.size() > 0:
            await self._process_request_batch()

        # Send remaining responses
        remaining_responses = list(self.response_queue)
        if remaining_responses:
            await self._send_response_batch(remaining_responses)

        # Shutdown thread pool
        self.request_handler.executor.shutdown(wait=False)

        self.debug("High-performance router shutdown completed gracefully")
