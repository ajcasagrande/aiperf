#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
from collections.abc import Generator
from typing import Any

from _typeshed import Incomplete

from aiperf.common.enums import MessageType as MessageType
from aiperf.common.enums._service import ServiceState as ServiceState
from aiperf.common.enums._service import ServiceType as ServiceType
from aiperf.common.pydantic_utils import ExcludeIfNoneMixin as ExcludeIfNoneMixin
from aiperf.common.pydantic_utils import exclude_if_none as exclude_if_none

class Message(ExcludeIfNoneMixin):
    def __init_subclass__(cls, **kwargs: dict[str, Any]): ...
    message_type: MessageType | Any
    request_ns: int
    request_id: str | None
    @classmethod
    def __get_validators__(cls) -> Generator[Incomplete]: ...
    @classmethod
    def from_json(cls, json_str: str) -> Message: ...
    def to_json(self) -> str: ...

class BaseServiceMessage(Message):
    service_id: str

class BaseStatusMessage(BaseServiceMessage):
    state: ServiceState
    service_type: ServiceType
