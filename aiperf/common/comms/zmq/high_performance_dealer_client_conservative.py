# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""
Conservative High-Performance ZMQ DEALER client that balances speed with stability.

This version addresses the resource exhaustion issues while maintaining high performance:
- More conservative timeouts
- Better error recovery
- Adaptive backpressure
- Resource-aware batching
"""

import asyncio
import time
import uuid

import zmq
import zmq.asyncio

from aiperf.common.comms.zmq.zmq_base_client import BaseZMQClient
from aiperf.common.constants import (
    BATCH_PROCESSING_SIZE,
    DEFAULT_COMMS_REQUEST_TIMEOUT,
)
from aiperf.common.decorators import implements_protocol
from aiperf.common.exceptions import CommunicationError
from aiperf.common.hooks import background_task, on_stop
from aiperf.common.messages import Message
from aiperf.common.mixins import TaskManagerMixin
from aiperf.common.protocols import RequestClientProtocol
from aiperf.common.utils import yield_to_event_loop


@implements_protocol(RequestClientProtocol)
# @CommunicationClientFactory.register(CommClientType.CONSERVATIVE_HIGH_PERFORMANCE_REQUEST)  # Removed to use simple solution
class ConservativeHighPerformanceDealerClient(BaseZMQClient, TaskManagerMixin):
    """
    Conservative high-performance ZMQ DEALER client optimized for stability at scale.

    Key differences from ultra-aggressive version:
    - Conservative timeouts (10ms vs 1ms)
    - Better resource management
    - Adaptive error recovery
    - Graceful degradation under load
    """

    def __init__(
        self,
        address: str,
        bind: bool,
        socket_ops: dict | None = None,
        batch_size: int = min(BATCH_PROCESSING_SIZE, 100),  # Smaller default batch
        **kwargs,
    ) -> None:
        super().__init__(zmq.SocketType.DEALER, address, bind, socket_ops, **kwargs)

        # Conservative performance settings
        self.batch_size = batch_size

        # Simple request futures tracking
        self._request_futures: dict[str, asyncio.Future] = {}
        self._futures_lock = asyncio.Lock()

        # Conservative queues - using asyncio.Queue for better flow control
        self._send_queue: asyncio.Queue = asyncio.Queue(maxsize=10000)
        self._receive_queue: asyncio.Queue = asyncio.Queue(maxsize=10000)

        # Performance tracking
        self._messages_sent = 0
        self._messages_received = 0
        self._errors_count = 0
        self._last_performance_check = time.time()

        # Adaptive parameters
        self._current_batch_size = min(batch_size, 10)  # Start small
        self._error_backoff = 0.0

        # Cache for performance
        self._trace_enabled = self.is_trace_enabled

    @background_task(immediate=True, interval=None)
    async def _conservative_receiver(self) -> None:
        """Zero-timeout receiver with infinite retry capability."""
        consecutive_errors = 0

        while not self.stop_requested:
            try:
                # Receive single message with much longer timeout to prevent timeouts
                try:
                    message = await asyncio.wait_for(
                        self.socket.recv_string(),
                        timeout=10.0,  # 10 second timeout instead of 100ms
                    )

                    if message and isinstance(message, str) and message.strip():
                        # Use infinite retry for queue insertion
                        while not self.stop_requested:
                            try:
                                await asyncio.wait_for(
                                    self._receive_queue.put(message), timeout=5.0
                                )
                                consecutive_errors = max(0, consecutive_errors - 1)
                                break  # Successfully queued
                            except asyncio.TimeoutError:
                                self.warning("Receive queue full, retrying in 0.1s...")
                                await asyncio.sleep(0.1)
                                # Continue retry loop
                    else:
                        self.debug("Received empty or invalid message")

                except asyncio.TimeoutError:
                    # Normal - no message available
                    await yield_to_event_loop()
                    continue

                except zmq.ZMQError as e:
                    consecutive_errors += 1
                    self.error(f"ZMQ error in receiver: {e}")

                    # Exponential backoff for persistent errors
                    if consecutive_errors > 5:
                        backoff_time = min(
                            2.0 ** (consecutive_errors - 5), 5.0
                        )  # Max 5s backoff
                        await asyncio.sleep(backoff_time)
                    else:
                        await yield_to_event_loop()

            except Exception as e:
                consecutive_errors += 1
                self.error(f"Unexpected error in conservative receiver: {e}")

                # Always retry with backoff
                backoff_time = min(0.1 * consecutive_errors, 2.0)  # Max 2s backoff
                await asyncio.sleep(backoff_time)

    @background_task(immediate=True, interval=None)
    async def _conservative_processor(self) -> None:
        """Conservative message processor with batching."""
        while not self.stop_requested:
            try:
                # Collect messages into batch
                batch = []
                batch_start = time.time()

                # Collect up to current batch size or timeout
                while (
                    len(batch) < self._current_batch_size
                    and (time.time() - batch_start) < 0.01
                ):
                    try:
                        message = await asyncio.wait_for(
                            self._receive_queue.get(), timeout=0.001
                        )
                        batch.append(message)
                        self._receive_queue.task_done()
                    except asyncio.TimeoutError:
                        break

                # Process batch if we have messages
                if batch:
                    await self._process_message_batch(batch)
                    self._messages_received += len(batch)

                    # Adapt batch size based on performance
                    process_time = time.time() - batch_start
                    if (
                        process_time < 0.005
                        and self._current_batch_size < self.batch_size
                    ):
                        self._current_batch_size = min(
                            self._current_batch_size + 5, self.batch_size
                        )
                    elif process_time > 0.02 and self._current_batch_size > 1:
                        self._current_batch_size = max(self._current_batch_size - 5, 1)
                else:
                    await yield_to_event_loop()

            except Exception as e:
                self.error(f"Exception in conservative processor: {e}")
                await yield_to_event_loop()
            except asyncio.CancelledError:
                return

    async def _process_message_batch(self, messages: list[str]) -> None:
        """Process a batch of messages conservatively."""
        for i, msg in enumerate(messages):
            try:
                if not msg or not msg.strip():
                    continue

                response_message = Message.from_json(msg)
                if not response_message.request_id:
                    continue

                async with self._futures_lock:
                    future = self._request_futures.pop(
                        response_message.request_id, None
                    )

                if future and not future.done():
                    future.set_result(response_message)

            except Exception as e:
                self._errors_count += 1
                self.error(f"Error processing message {i}: {e}")

    @background_task(immediate=True, interval=None)
    async def _conservative_sender(self) -> None:
        """Zero-timeout sender with infinite retry capability."""
        while not self.stop_requested:
            try:
                # Wait for message from send queue
                message = await self._send_queue.get()

                # Send message with infinite retry and longer timeout
                max_retries = 10  # Increased retries
                for attempt in range(max_retries):
                    try:
                        await asyncio.wait_for(
                            self.socket.send_string(message),
                            timeout=10.0,  # 10 second timeout instead of 1s
                        )
                        self._messages_sent += 1
                        break
                    except asyncio.TimeoutError:
                        if attempt == max_retries - 1:
                            # Even if we fail all retries, try one more time without timeout
                            try:
                                await self.socket.send_string(message)
                                self._messages_sent += 1
                                self.warning(
                                    f"Message sent after {max_retries} timeout retries"
                                )
                            except Exception as final_e:
                                self.error(f"Final send attempt failed: {final_e}")
                                self._errors_count += 1
                        else:
                            self.debug(
                                f"Send timeout attempt {attempt + 1}/{max_retries}, retrying..."
                            )
                            await asyncio.sleep(0.1 * (attempt + 1))
                    except asyncio.CancelledError:
                        # Graceful shutdown in progress
                        self.debug("Sender cancelled during shutdown")
                        return
                    except zmq.ZMQError as e:
                        self.error(f"ZMQ error sending message: {e}")
                        self._errors_count += 1
                        if "Resource temporarily unavailable" in str(e):
                            await asyncio.sleep(0.5)  # Longer backoff
                            continue  # Retry this attempt
                        break
                    except Exception as e:
                        self.error(f"Exception sending message: {e}")
                        self._errors_count += 1
                        break

            except asyncio.CancelledError:
                return
            except Exception as e:
                self.error(f"Exception in sender: {e}")
                await asyncio.sleep(0.1)
            finally:
                self._send_queue.task_done()

    async def request_async(
        self,
        message: Message,
        future: asyncio.Future[Message],
    ) -> None:
        """Send a request with zero-timeout guarantee."""
        if not isinstance(message, Message):
            raise TypeError(
                f"message must be an instance of Message, got {type(message).__name__}"
            )

        try:
            # Generate request ID if not provided
            if not message.request_id:
                message.request_id = str(uuid.uuid4())

            # Store future with infinite retry
            async with self._futures_lock:
                self._request_futures[message.request_id] = future
                # Add creation timestamp for cleanup
                future._created_at = time.time()

            request_json = message.model_dump_json()
            if not request_json or not request_json.strip():
                raise ValueError("Serialized message is empty or invalid")

            # Add to send queue with infinite retry to prevent timeouts
            while not self.stop_requested:
                try:
                    await asyncio.wait_for(
                        self._send_queue.put(request_json), timeout=5.0
                    )
                    break  # Successfully queued
                except asyncio.TimeoutError:
                    self.warning("Send queue full, retrying queue insertion...")
                    await asyncio.sleep(0.1)
                    # Continue retry loop

        except Exception as e:
            # Ensure future is cleaned up on any error
            async with self._futures_lock:
                self._request_futures.pop(message.request_id, None)
            raise CommunicationError(
                f"Exception sending request: {e.__class__.__qualname__} {e}",
            ) from e

    async def request(
        self,
        message: Message,
        timeout: float = DEFAULT_COMMS_REQUEST_TIMEOUT,
    ) -> Message:
        """Conservative request with timeout."""
        future: asyncio.Future[Message] = asyncio.Future()
        await self.request_async(message, future)
        return await asyncio.wait_for(future, timeout=timeout)

    @background_task(immediate=False, interval=30.0)
    async def _cleanup_stale_futures(self) -> None:
        """Clean up stale futures."""
        try:
            current_time = time.time()
            stale_ids = []

            async with self._futures_lock:
                for request_id, future in self._request_futures.items():
                    if (
                        future.done()
                        or hasattr(future, "_created_at")
                        and (current_time - getattr(future, "_created_at", 0)) > 300
                    ):
                        stale_ids.append(request_id)

                for request_id in stale_ids:
                    future = self._request_futures.pop(request_id, None)
                    if future and not future.done():
                        future.set_exception(asyncio.TimeoutError("Future cleaned up"))

            if stale_ids:
                self.debug(f"Cleaned up {len(stale_ids)} stale futures")
        except Exception as e:
            self.error(f"Exception during cleanup: {e}")

    @background_task(immediate=False, interval=10.0)
    async def _performance_monitoring(self) -> None:
        """Monitor performance and adapt parameters."""
        try:
            current_time = time.time()
            time_diff = current_time - self._last_performance_check

            if time_diff > 0:
                send_rate = self._messages_sent / time_diff
                receive_rate = self._messages_received / time_diff
                error_rate = self._errors_count / time_diff

                self.debug(
                    f"Conservative performance: "
                    f"Send: {send_rate:.0f}/s, "
                    f"Receive: {receive_rate:.0f}/s, "
                    f"Errors: {error_rate:.1f}/s, "
                    f"Batch size: {self._current_batch_size}, "
                    f"Queue sizes: S={self._send_queue.qsize()}, R={self._receive_queue.qsize()}"
                )

                # Reset counters
                self._messages_sent = 0
                self._messages_received = 0
                self._errors_count = 0
                self._last_performance_check = current_time

        except Exception as e:
            self.error(f"Exception in performance monitoring: {e}")

    @on_stop
    async def _conservative_shutdown(self) -> None:
        """Conservative shutdown with simple cleanup."""
        try:
            self.debug("Conservative shutdown initiated")

            # Cancel remaining futures
            async with self._futures_lock:
                for future in self._request_futures.values():
                    if not future.done():
                        future.set_exception(asyncio.CancelledError("Client shutdown"))
                self._request_futures.clear()

            # Wait for queues to drain with timeout
            try:
                await asyncio.wait_for(self._send_queue.join(), timeout=2.0)
                await asyncio.wait_for(self._receive_queue.join(), timeout=2.0)
            except asyncio.TimeoutError:
                self.debug("Queue drain timeout during shutdown")

            self.debug("Conservative shutdown completed")

        except Exception as e:
            self.error(f"Exception during conservative shutdown: {e}")
