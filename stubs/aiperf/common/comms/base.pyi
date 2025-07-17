#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
import abc
from abc import ABC, abstractmethod
from collections.abc import Callable as Callable
from collections.abc import Coroutine
from typing import Any, Protocol, TypeVar

from _typeshed import Incomplete

from aiperf.common.constants import (
    DEFAULT_COMMS_REQUEST_TIMEOUT as DEFAULT_COMMS_REQUEST_TIMEOUT,
)
from aiperf.common.enums import CommunicationBackend as CommunicationBackend
from aiperf.common.enums import (
    CommunicationClientAddressType as CommunicationClientAddressType,
)
from aiperf.common.enums import CommunicationClientType as CommunicationClientType
from aiperf.common.enums import MessageType as MessageType
from aiperf.common.factories import FactoryMixin as FactoryMixin
from aiperf.common.messages import Message as Message

MessageT = TypeVar("MessageT", bound=Message)
MessageOutputT = TypeVar("MessageOutputT", bound=Message)

class CommunicationClientProtocol(Protocol):
    async def initialize(self) -> None: ...
    async def shutdown(self) -> None: ...

class CommunicationClientProtocolFactory(
    FactoryMixin[CommunicationClientType, CommunicationClientProtocol]
): ...

class PushClientProtocol(CommunicationClientProtocol, Protocol):
    async def push(self, message: Message) -> None: ...

class PullClientProtocol(CommunicationClientProtocol, Protocol):
    async def register_pull_callback(
        self,
        message_type: MessageType,
        callback: Callable[[MessageT], Coroutine[Any, Any, None]],
        max_concurrency: int | None = None,
    ) -> None: ...

class RequestClientProtocol(CommunicationClientProtocol, Protocol):
    async def request(
        self, message: MessageT, timeout: float = ...
    ) -> MessageOutputT: ...
    async def request_async(
        self,
        message: MessageT,
        callback: Callable[[MessageOutputT], Coroutine[Any, Any, None]],
    ) -> None: ...

class ReplyClientProtocol(CommunicationClientProtocol, Protocol):
    def register_request_handler(
        self,
        service_id: str,
        message_type: MessageType,
        handler: Callable[[MessageT], Coroutine[Any, Any, MessageOutputT | None]],
    ) -> None: ...

class SubClientProtocol(CommunicationClientProtocol, Protocol):
    async def subscribe(
        self,
        message_type: MessageType,
        callback: Callable[[MessageT], Coroutine[Any, Any, None]],
    ) -> None: ...
    async def subscribe_all(
        self,
        message_callback_map: dict[
            MessageType, Callable[[MessageT], Coroutine[Any, Any, None]]
        ],
    ) -> None: ...

class PubClientProtocol(CommunicationClientProtocol, Protocol):
    async def publish(self, message: MessageT) -> None: ...

class CommunicationClientFactory(
    FactoryMixin[CommunicationClientType, CommunicationClientProtocol]
): ...

ClientProtocolT = TypeVar("ClientProtocolT", bound=CommunicationClientProtocol)

class BaseCommunication(ABC, metaclass=abc.ABCMeta):
    @abstractmethod
    async def initialize(self) -> None: ...
    @property
    @abstractmethod
    def is_initialized(self) -> bool: ...
    @property
    @abstractmethod
    def stop_requested(self) -> bool: ...
    @abstractmethod
    async def shutdown(self) -> None: ...
    @abstractmethod
    def get_address(
        self, address_type: CommunicationClientAddressType | str
    ) -> str: ...
    @abstractmethod
    def create_client(
        self,
        client_type: CommunicationClientType,
        address: CommunicationClientAddressType | str,
        bind: bool = False,
        socket_ops: dict | None = None,
    ) -> CommunicationClientProtocol: ...
    create_pub_client: Incomplete
    create_sub_client: Incomplete
    create_push_client: Incomplete
    create_pull_client: Incomplete
    create_request_client: Incomplete
    create_reply_client: Incomplete

class CommunicationFactory(FactoryMixin[CommunicationBackend, BaseCommunication]): ...
