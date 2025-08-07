# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
import asyncio
import uuid

import zmq.asyncio

from aiperf.common.comms.zmq.zmq_base_client import BaseZMQClient
from aiperf.common.constants import (
    DEFAULT_COMMS_REQUEST_TIMEOUT,
    DEFAULT_DEALER_RECV_QUEUE_SIZE,
    DEFAULT_DEALER_SEND_QUEUE_SIZE,
)
from aiperf.common.decorators import implements_protocol
from aiperf.common.enums import CommClientType
from aiperf.common.exceptions import CommunicationError
from aiperf.common.factories import CommunicationClientFactory
from aiperf.common.hooks import background_task, on_stop
from aiperf.common.messages import Message
from aiperf.common.mixins import TaskManagerMixin
from aiperf.common.protocols import RequestClientProtocol
from aiperf.common.utils import yield_to_event_loop


@implements_protocol(RequestClientProtocol)
@CommunicationClientFactory.register(CommClientType.REQUEST)
class ZMQDealerRequestClient(BaseZMQClient, TaskManagerMixin):
    """
    ZMQ DEALER socket client for asynchronous request-response communication.

    The DEALER socket connects to ROUTER sockets and can send requests asynchronously,
    receiving responses through callbacks or awaitable futures.

    ASCII Diagram:
    ┌──────────────┐                    ┌──────────────┐
    │    DEALER    │───── Request ─────>│    ROUTER    │
    │   (Client)   │                    │  (Service)   │
    │              │<─── Response ──────│              │
    └──────────────┘                    └──────────────┘

    Usage Pattern:
    - DEALER Clients send requests to ROUTER Services
    - Responses are routed back to the originating DEALER

    DEALER/ROUTER is a Many-to-One communication pattern. If you need Many-to-Many,
    use a ZMQ Proxy as well. see :class:`ZMQDealerRouterProxy` for more details.
    """

    def __init__(
        self,
        address: str,
        bind: bool,
        socket_ops: dict | None = None,
        **kwargs,
    ) -> None:
        """
        Initialize the ZMQ Dealer (Req) client class.

        Args:
            address (str): The address to bind or connect to.
            bind (bool): Whether to bind or connect the socket.
            socket_ops (dict, optional): Additional socket options to set.
        """
        super().__init__(zmq.SocketType.DEALER, address, bind, socket_ops, **kwargs)

        self._socket_lock: asyncio.Lock = asyncio.Lock()
        self._send_queue: asyncio.Queue = asyncio.Queue(
            maxsize=DEFAULT_DEALER_SEND_QUEUE_SIZE
        )
        self._receive_queue: asyncio.Queue = asyncio.Queue(
            maxsize=DEFAULT_DEALER_RECV_QUEUE_SIZE
        )

        self._request_futures_lock: asyncio.Lock = asyncio.Lock()
        self._request_futures: dict[str, asyncio.Future[Message]] = {}

        # cache this for performance (but keep in mind that it will be not be updated if the trace level is changed)
        self._trace_enabled = self.is_trace_enabled

    @background_task(immediate=True, interval=None)
    async def _request_async_task(self) -> None:
        """Task to handle incoming requests from the socket and put them in the receive queue."""
        while not self.stop_requested:
            try:
                message = await self.socket.recv_string()
                try:
                    await self._receive_queue.put(message)
                except asyncio.QueueFull:
                    self.warning(
                        f"Waiting for receive queue to be available for dealer {self.client_id}. This will cause back pressure on the router."
                    )
                    await yield_to_event_loop()
                    await self._receive_queue.put(message)

            except zmq.Again:
                self.debug("No data on dealer socket received, yielding to event loop")
                await yield_to_event_loop()
            except Exception as e:
                self.error(f"Exception receiving responses: {e}")
                await yield_to_event_loop()
            except asyncio.CancelledError:
                return

    async def _process_response(self, msg: str) -> None:
        """Process a response from the receive queue."""
        if self._trace_enabled:
            self.trace(f"Received response: {msg}")

        response_message = Message.from_json(msg)

        future = None
        async with self._request_futures_lock:
            if response_message.request_id in self._request_futures:
                future = self._request_futures.pop(response_message.request_id)

        if future:
            future.set_result(response_message)

    @background_task(immediate=True, interval=None)
    async def _process_responses_async_task(self) -> None:
        """Task to process responses from the receive queue."""
        while not self.stop_requested:
            message = await self._receive_queue.get()
            try:
                await self._process_response(message)
            except Exception as e:
                self.error(f"Exception processing response: {e}")
                await yield_to_event_loop()
            except asyncio.CancelledError:
                break
            finally:
                self._receive_queue.task_done()

        # drain the queue, and drop any messages that are not processed, since we are shutting down
        while not self._receive_queue.empty():
            await self._receive_queue.get()
            self._receive_queue.task_done()

    @background_task(immediate=True, interval=None)
    async def _send_async_task(self) -> None:
        """Task to handle outgoing requests by sending them to the socket."""
        while not self.stop_requested:
            message = await self._send_queue.get()
            try:
                await self.socket.send_string(message)
            except Exception as e:
                self.error(f"Exception sending request: {e.__class__.__qualname__} {e}")
                await yield_to_event_loop()
            except asyncio.CancelledError:
                break
            finally:
                self._send_queue.task_done()

        # drain the queue, and drop any messages that are not processed, since we are shutting down
        while not self._send_queue.empty():
            await self._send_queue.get()
            self._send_queue.task_done()

    async def _cancel_all_futures(self) -> None:
        """Cancel all futures that are not done."""
        async with self._request_futures_lock:
            for future in self._request_futures.values():
                if not future.done():
                    future.set_exception(asyncio.CancelledError("Future cancelled"))

    @on_stop
    async def _cancel_futures_and_wait_for_queues(self) -> None:
        """Cancel all futures and wait for queues to be empty."""
        await asyncio.gather(
            self._send_queue.join(),
            self._receive_queue.join(),
            self._cancel_all_futures(),
            return_exceptions=True,
        )

    async def request_async(
        self,
        message: Message,
        future: asyncio.Future[Message],
    ) -> None:
        """Send a request and be notified when the response is received."""
        if not isinstance(message, Message):
            raise TypeError(
                f"message must be an instance of Message, got {type(message).__name__}"
            )

        try:
            # Generate request ID if not provided so that responses can be matched
            if not message.request_id:
                message.request_id = str(uuid.uuid4())

            async with self._request_futures_lock:
                self._request_futures[message.request_id] = future

            request_json = message.model_dump_json()
            if self._trace_enabled:
                self.trace(f"Sending request: {request_json}")

            # put the request in the send queue, which will be processed by the send task
            try:
                self._send_queue.put_nowait(request_json)
            except asyncio.QueueFull:
                self.warning(
                    f"Waiting for send queue to be available for dealer {self.client_id}. This will cause back pressure on the router."
                )
                await yield_to_event_loop()
                await self._send_queue.put(request_json)

        except Exception as e:
            raise CommunicationError(
                f"Exception sending request: {e.__class__.__qualname__} {e}",
            ) from e

    async def request(
        self,
        message: Message,
        timeout: float = DEFAULT_COMMS_REQUEST_TIMEOUT,
    ) -> Message:
        """Send a request and wait for a response up to timeout seconds.

        Args:
            message (Message): The request message to send.
            timeout (float): Maximum time to wait for a response in seconds.

        Returns:
            Message: The response message received.

        Raises:
            CommunicationError: if the request fails, or
            asyncio.TimeoutError: if the response is not received in time.
        """
        future: asyncio.Future[Message] = asyncio.Future()
        await self.request_async(message, future)
        return await asyncio.wait_for(future, timeout=timeout)
