# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
import asyncio
import uuid

import zmq.asyncio

from aiperf.common.constants import DEFAULT_COMMS_REQUEST_TIMEOUT
from aiperf.common.decorators import implements_protocol
from aiperf.common.enums import CommClientType
from aiperf.common.factories import CommunicationClientFactory
from aiperf.common.hooks import background_task
from aiperf.common.messages import Message
from aiperf.common.mixins import TaskManagerMixin
from aiperf.common.protocols import RequestClientProtocol
from aiperf.common.utils import yield_to_event_loop
from aiperf.zmq.zmq_base_client import BaseZMQClient

MAX_REQUEST_QUEUE_SIZE = 1_000_000
MAX_RESPONSE_QUEUE_SIZE = 1_000_000


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


    Message Flow:
        `request` -> call `request_async` -> put request in queue, and return future to `request`
        `request` -> wait for response from future (with timeout) -> return response

        Async Tasks:
        `_request_queue_processor` -> get request from queue, and send request to socket
        `_socket_receiver_task` -> receive responses from socket, and put in response queue
        `_response_queue_processor` -> get response from queue, and set result on future
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

        self._request_futures: dict[str, asyncio.Future[Message]] = {}

        self._request_queue: asyncio.Queue[
            tuple[str, Message, asyncio.Future[Message]]
        ] = asyncio.Queue(maxsize=MAX_REQUEST_QUEUE_SIZE)
        self._response_queue: asyncio.Queue[tuple[str, Message]] = asyncio.Queue(
            maxsize=MAX_RESPONSE_QUEUE_SIZE
        )

    @background_task(immediate=True, interval=None)
    async def _request_queue_processor(self) -> None:
        """Task to process requests from the request queue."""
        _id_debug_enabled = self.is_debug_enabled
        while not self.stop_requested:
            got_request = False
            try:
                request_id, request, future = await self._request_queue.get()
                got_request = True

                if request_id in self._request_futures:
                    self.warning(
                        f"Dealer request client request queue processor task got duplicate request {request_id}. Dropping request."
                    )
                    continue

                self._request_futures[request_id] = future
                await self.socket.send_string(request.model_dump_json())
                if _id_debug_enabled:
                    self.debug(
                        f"Dealer request client request queue processor task sent request {request_id} to socket."
                    )
            except asyncio.CancelledError:
                self.debug(
                    "Dealer request client request queue processor task cancelled"
                )
                break
            except Exception as e:
                self.error(f"Exception processing request from queue: {e!r}")
                await yield_to_event_loop()
            finally:
                if got_request:
                    self._request_queue.task_done()

    @background_task(immediate=True, interval=None)
    async def _response_queue_processor(self) -> None:
        """Task to process responses from the response queue."""
        while not self.stop_requested:
            got_response = False
            try:
                request_id, response = await self._response_queue.get()
                got_response = True

                if request_id in self._request_futures:
                    future = self._request_futures.pop(request_id)
                    future.set_result(response)
                else:
                    self.warning(
                        f"Dealer request client response queue processor task got response for unknown request {request_id}. Dropping response."
                    )
            except asyncio.CancelledError:
                self.debug(
                    "Dealer request client response queue processor task cancelled"
                )
                break
            except Exception as e:
                self.error(f"Exception processing response from queue: {e!r}")
                await yield_to_event_loop()
            finally:
                if got_response:
                    self._response_queue.task_done()

    @background_task(immediate=True, interval=None)
    async def _socket_receiver_task(self) -> None:
        """Task to handle receiving responses from the socket."""
        # cache the trace enabled state to avoid re-checking it on every iteration
        _is_trace_enabled = self.is_trace_enabled
        while not self.stop_requested:
            try:
                message = await self.socket.recv_string()
                if _is_trace_enabled:
                    self.trace(f"Received response: {message}")

                response_message = Message.from_json(message)
                try:
                    self._response_queue.put_nowait(
                        (response_message.request_id, response_message)
                    )
                except asyncio.QueueFull:
                    self.warning(
                        f"Dealer request client response queue is full for request {response_message.request_id}. "
                        "Waiting for an open slot. This will cause back pressure."
                    )
                    await self._response_queue.put(
                        (response_message.request_id, response_message)
                    )
                    self.info(
                        "Dealer request client _socket_receiver_task put response in queue."
                    )

            except zmq.Again:
                self.debug("No data on dealer socket received, yielding to event loop")
                await yield_to_event_loop()
            except Exception as e:
                self.error(f"Exception receiving responses: {e!r}")
                await yield_to_event_loop()
            except asyncio.CancelledError:
                self.debug("Dealer request client receiver task cancelled")
                break

    async def request_async(self, message: Message) -> asyncio.Future[Message]:
        """Send a request and get a future for the response."""

        # Generate request ID if not provided so that responses can be matched
        if not message.request_id:
            message.request_id = str(uuid.uuid4())

        future = asyncio.Future[Message]()
        try:
            self._request_queue.put_nowait((message.request_id, message, future))
        except asyncio.QueueFull:
            self.error(
                f"Dealer request client request queue is full for request {message.request_id}. "
                "Waiting for an open slot. This will cause back pressure."
            )
            await self._request_queue.put((message.request_id, message, future))
            self.info("Dealer request client put request in queue.")
        return future

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
        future = await self.request_async(message)
        return await asyncio.wait_for(future, timeout=timeout)
