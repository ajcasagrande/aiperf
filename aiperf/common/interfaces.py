# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

import asyncio
from collections.abc import Callable, Coroutine
from typing import Any, Protocol, runtime_checkable

from aiperf.common.enums import (
    CommClientType,
    CommunicationBackend,
    ComposerType,
    CustomDatasetType,
    DataExporterType,
    PostProcessorType,
    ServiceType,
    StreamingPostProcessorType,
)
from aiperf.common.mixins.factory_mixin import FactoryMixin
from aiperf.common.types import (
    CommAddressType,
    MessageOutputT,
    MessageT,
    MessageTypeT,
    ParsedResponseRecordT,
    ResponseDataT,
)

# if TYPE_CHECKING:
#     from aiperf.common.enums import (
#         CommClientType,
#         CommunicationBackend,
#         ComposerType,
#         CustomDatasetType,
#         DataExporterType,
#         MessageType,
#         PostProcessorType,
#         ServiceType,
#         StreamingPostProcessorType,
#     )
#     from aiperf.common.messages import Message
#     from aiperf.common.models import ParsedResponseRecord, ResponseData
#     from aiperf.common.service.base_service import BaseService
#     from aiperf.common.types import (
#         CommAddressType,
#         MessageOutputT,
#         MessageT,
#         MessageTypeT,
#     )
#     from aiperf.services.dataset.composer.base import BaseDatasetComposer
#     from aiperf.services.dataset.loader.protocol import CustomDatasetLoaderProtocol
#     from aiperf.services.records_manager.post_processors.streaming_post_processor import (
#         BaseStreamingPostProcessor,
#     )


class CommunicationFactory(
    FactoryMixin[CommunicationBackend, "CommunicationProtocol"]
): ...


class ServiceFactory(FactoryMixin[ServiceType, "BaseService"]): ...


class DataExporterFactory(FactoryMixin[DataExporterType, "DataExporterProtocol"]): ...


class PostProcessorFactory(
    FactoryMixin[PostProcessorType, "PostProcessorProtocol"]
): ...


class ComposerFactory(FactoryMixin[ComposerType, "BaseDatasetComposer"]): ...


class CustomDatasetFactory(
    FactoryMixin[CustomDatasetType, "CustomDatasetLoaderProtocol"]
): ...


class StreamingPostProcessorFactory(
    FactoryMixin[StreamingPostProcessorType, "BaseStreamingPostProcessor"]
): ...


class CommunicationClientFactory(
    FactoryMixin[CommClientType, "CommunicationClientProtocol"]
): ...


class CommunicationClientProtocolFactory(
    FactoryMixin[CommClientType, "CommunicationClientProtocol"]
): ...


@runtime_checkable
class TaskManagerProtocol(Protocol):
    def execute_async(self, coro: Coroutine) -> asyncio.Task: ...

    async def cancel_all_tasks(self, timeout: float) -> None: ...

    def start_background_task(
        self,
        method: Callable,
        interval: float | Callable[["TaskManagerProtocol"], float] | None = None,
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
    async def push(self, message: "MessageT") -> None: ...


@CommunicationClientProtocolFactory.register(CommClientType.PULL)
class PullClientProtocol(CommunicationClientProtocol, Protocol):
    async def register_pull_callback(
        self,
        message_type: "MessageTypeT",
        callback: Callable[["MessageT"], Coroutine[Any, Any, None]],
        max_concurrency: int | None,
    ) -> None: ...


@CommunicationClientProtocolFactory.register(CommClientType.REQUEST)
@runtime_checkable
class RequestClientProtocol(CommunicationClientProtocol, Protocol):
    async def request(
        self,
        message: "MessageT",
        timeout: float,
    ) -> "MessageOutputT": ...

    async def request_async(
        self,
        message: "MessageT",
        callback: Callable[["MessageOutputT"], Coroutine[Any, Any, None]],
    ) -> None: ...


@CommunicationClientProtocolFactory.register(CommClientType.REPLY)
@runtime_checkable
class ReplyClientProtocol(CommunicationClientProtocol, Protocol):
    def register_request_handler(
        self,
        service_id: str,
        message_type: "MessageTypeT",
        handler: Callable[["MessageT"], Coroutine[Any, Any, "MessageOutputT | None"]],
    ) -> None: ...


@CommunicationClientProtocolFactory.register(CommClientType.SUB)
@runtime_checkable
class SubClientProtocol(CommunicationClientProtocol, Protocol):
    async def subscribe(
        self,
        message_type: "MessageTypeT",
        callback: Callable[["MessageT"], Coroutine[Any, Any, None]],
    ) -> None: ...

    async def subscribe_all(
        self,
        message_callback_map: dict[
            "MessageTypeT",
            Callable[["MessageT"], Any] | list[Callable[["MessageT"], Any]],
        ],
    ) -> None: ...


@CommunicationClientProtocolFactory.register(CommClientType.PUB)
@runtime_checkable
class PubClientProtocol(CommunicationClientProtocol, Protocol):
    async def publish(self, message: "MessageT") -> None: ...


@runtime_checkable
class MessageBusProtocol(PubClientProtocol, SubClientProtocol, Protocol): ...


@runtime_checkable
class CommunicationProtocol(AIPerfLifecycleProtocol, Protocol):
    def get_address(self, address_type: "CommAddressType") -> str: ...

    def create_client(
        self, address: "CommAddressType", bind: bool, socket_ops: dict | None
    ) -> CommunicationClientProtocol: ...

    def create_pub_client(
        self, address: "CommAddressType", bind: bool, socket_ops: dict | None
    ) -> PubClientProtocol: ...

    def create_sub_client(
        self, address: "CommAddressType", bind: bool, socket_ops: dict | None
    ) -> SubClientProtocol: ...

    def create_push_client(
        self, address: "CommAddressType", bind: bool, socket_ops: dict | None
    ) -> PushClientProtocol: ...

    def create_pull_client(
        self, address: "CommAddressType", bind: bool, socket_ops: dict | None
    ) -> PullClientProtocol: ...

    def create_request_client(
        self, address: "CommAddressType", bind: bool, socket_ops: dict | None
    ) -> RequestClientProtocol: ...

    def create_reply_client(
        self, address: "CommAddressType", bind: bool, socket_ops: dict | None
    ) -> ReplyClientProtocol: ...
