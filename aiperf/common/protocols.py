# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

import asyncio
from collections.abc import Callable, Coroutine
from typing import Any, Generic, Protocol, runtime_checkable

from aiperf.common.constants import (
    DEFAULT_COMMS_REQUEST_TIMEOUT,
    DEFAULT_PULL_CLIENT_MAX_CONCURRENCY,
)
from aiperf.common.enums import CommClientType
from aiperf.common.factories import CommunicationClientProtocolFactory
from aiperf.common.types import (
    CommAddressType,
    MessageOutputT,
    MessageT,
    MessageTypeT,
    ModelEndpointInfoT,
    ParsedResponseRecordT,
    RequestInputT,
    RequestOutputT,
    RequestRecordT,
    ResponseDataT,
    ServiceTypeT,
    TaskManagerProtocolT,
    TokenizerT,
    TurnT,
)


@runtime_checkable
class TaskManagerProtocol(Protocol):
    def execute_async(self, coro: Coroutine) -> asyncio.Task: ...

    async def cancel_all_tasks(self, timeout: float) -> None: ...

    def start_background_task(
        self,
        method: Callable,
        interval: float | Callable[[TaskManagerProtocolT], float] | None = None,
        immediate: bool = False,
        stop_on_error: bool = False,
    ) -> None: ...


@runtime_checkable
class AIPerfLifecycleProtocol(TaskManagerProtocol, Protocol):
    """Protocol for AIPerf lifecycle methods.
    see :class:`aiperf.common.mixins.aiperf_lifecycle_mixin.AIPerfLifecycleMixin` for more details.
    """

    was_initialized: bool
    was_started: bool
    was_stopped: bool
    is_running: bool

    async def initialize(self) -> None: ...
    async def start(self) -> None: ...
    async def initialize_and_start(self) -> None: ...
    async def stop(self) -> None: ...


@runtime_checkable
class DataExporterProtocol(Protocol):
    """
    Protocol for data exporters.
    Any class implementing this protocol must provide an `export` method
    that takes a list of Record objects and handles exporting them appropriately.
    """

    async def export(self) -> None: ...


class PostProcessorProtocol(Protocol):
    def process(self, records: dict) -> dict: ...


class ResponseExtractor(Protocol):
    async def extract_response_data(
        self, record: ParsedResponseRecordT
    ) -> list[ResponseDataT]: ...


@runtime_checkable
class CommunicationClientProtocol(AIPerfLifecycleProtocol, Protocol): ...


@runtime_checkable
class AIPerfLoggerProtocol(Protocol):
    def __init__(self, logger_name: str | None = None, **kwargs) -> None: ...
    def log(
        self, level: int, message: str | Callable[..., str], *args, **kwargs
    ) -> None: ...
    def trace(self, message: str | Callable[..., str], *args, **kwargs) -> None: ...
    def debug(self, message: str | Callable[..., str], *args, **kwargs) -> None: ...
    def info(self, message: str | Callable[..., str], *args, **kwargs) -> None: ...
    def notice(self, message: str | Callable[..., str], *args, **kwargs) -> None: ...
    def warning(self, message: str | Callable[..., str], *args, **kwargs) -> None: ...
    def success(self, message: str | Callable[..., str], *args, **kwargs) -> None: ...
    def error(self, message: str | Callable[..., str], *args, **kwargs) -> None: ...
    def exception(self, message: str | Callable[..., str], *args, **kwargs) -> None: ...
    def critical(self, message: str | Callable[..., str], *args, **kwargs) -> None: ...
    def is_enabled_for(self, level: int) -> bool: ...


@CommunicationClientProtocolFactory.register(CommClientType.PUSH)
class PushClientProtocol(CommunicationClientProtocol, Protocol):
    async def push(self, message: MessageT) -> None: ...


@CommunicationClientProtocolFactory.register(CommClientType.PULL)
class PullClientProtocol(CommunicationClientProtocol, Protocol):
    async def register_pull_callback(
        self,
        message_type: MessageTypeT,
        callback: Callable[[MessageT], Coroutine[Any, Any, None]],
        max_concurrency: int | None = DEFAULT_PULL_CLIENT_MAX_CONCURRENCY,
    ) -> None: ...


@CommunicationClientProtocolFactory.register(CommClientType.REQUEST)
@runtime_checkable
class RequestClientProtocol(CommunicationClientProtocol, Protocol):
    async def request(
        self,
        message: MessageT,
        timeout: float = DEFAULT_COMMS_REQUEST_TIMEOUT,
    ) -> MessageOutputT: ...

    async def request_async(
        self,
        message: MessageT,
        callback: Callable[[MessageOutputT], Coroutine[Any, Any, None]],
    ) -> None: ...


@CommunicationClientProtocolFactory.register(CommClientType.REPLY)
@runtime_checkable
class ReplyClientProtocol(CommunicationClientProtocol, Protocol):
    def register_request_handler(
        self,
        service_id: str,
        message_type: MessageTypeT,
        handler: Callable[[MessageT], Coroutine[Any, Any, MessageOutputT | None]],
    ) -> None: ...


@CommunicationClientProtocolFactory.register(CommClientType.SUB)
@runtime_checkable
class SubClientProtocol(CommunicationClientProtocol, Protocol):
    async def subscribe(
        self,
        message_type: MessageTypeT,
        callback: Callable[[MessageT], Coroutine[Any, Any, None]],
    ) -> None: ...

    async def subscribe_all(
        self,
        message_callback_map: dict[
            MessageTypeT,
            Callable[[MessageT], Any] | list[Callable[[MessageT], Any]],
        ],
    ) -> None: ...


@CommunicationClientProtocolFactory.register(CommClientType.PUB)
@runtime_checkable
class PubClientProtocol(CommunicationClientProtocol, Protocol):
    async def publish(self, message: MessageT) -> None: ...


@runtime_checkable
class MessageBusClientProtocol(PubClientProtocol, SubClientProtocol, Protocol): ...


@runtime_checkable
class CommunicationProtocol(AIPerfLifecycleProtocol, Protocol):
    def get_address(self, address_type: CommAddressType) -> str: ...

    def create_client(
        self,
        address: CommAddressType,
        bind: bool = False,
        socket_ops: dict | None = None,
    ) -> CommunicationClientProtocol: ...

    def create_pub_client(
        self,
        address: CommAddressType,
        bind: bool = False,
        socket_ops: dict | None = None,
    ) -> PubClientProtocol: ...

    def create_sub_client(
        self,
        address: CommAddressType,
        bind: bool = False,
        socket_ops: dict | None = None,
    ) -> SubClientProtocol: ...

    def create_push_client(
        self,
        address: CommAddressType,
        bind: bool = False,
        socket_ops: dict | None = None,
    ) -> PushClientProtocol: ...

    def create_pull_client(
        self,
        address: CommAddressType,
        bind: bool = False,
        socket_ops: dict | None = None,
    ) -> PullClientProtocol: ...

    def create_request_client(
        self,
        address: CommAddressType,
        bind: bool = False,
        socket_ops: dict | None = None,
    ) -> RequestClientProtocol: ...

    def create_reply_client(
        self,
        address: CommAddressType,
        bind: bool = False,
        socket_ops: dict | None = None,
    ) -> ReplyClientProtocol: ...


@runtime_checkable
class InferenceClientProtocol(Protocol, Generic[RequestInputT]):
    """Protocol for an inference server client.

    This protocol defines the methods that must be implemented by any inference server client
    implementation that is compatible with the AIPerf framework.
    """

    def __init__(self, model_endpoint: ModelEndpointInfoT) -> None:
        """Create a new inference server client based on the provided configuration."""
        ...

    async def initialize(self) -> None:
        """Initialize the inference server client in an asynchronous context."""
        ...

    async def send_request(
        self,
        model_endpoint: ModelEndpointInfoT,
        payload: RequestInputT,
    ) -> RequestRecordT:
        """Send a request to the inference server.

        This method is used to send a request to the inference server.

        Args:
            model_endpoint: The endpoint to send the request to.
            payload: The payload to send to the inference server.
        Returns:
            The raw response from the inference server.
        """
        ...

    async def close(self) -> None:
        """Close the client."""
        ...


@runtime_checkable
class RequestConverterProtocol(Protocol, Generic[RequestOutputT]):
    """Protocol for a request converter that converts a raw request to a formatted request for the inference server."""

    async def format_payload(
        self, model_endpoint: ModelEndpointInfoT, turn: TurnT
    ) -> RequestOutputT:
        """Format the turn for the inference server."""
        ...


@runtime_checkable
class ResponseExtractorProtocol(Protocol):
    """Protocol for a response extractor that extracts the response data from a raw inference server
    response and converts it to a list of ResponseData objects."""

    async def extract_response_data(
        self, record: RequestRecordT, tokenizer: TokenizerT | None
    ) -> list[ResponseDataT]:
        """Extract the response data from a raw inference server response and convert it to a list of ResponseData objects."""
        ...


@runtime_checkable
class ServiceProtocol(MessageBusClientProtocol, Protocol):
    """Protocol for a service. Essentially a MessageBusClientProtocol with a service_type attribute."""

    service_type: ServiceTypeT
