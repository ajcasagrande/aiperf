# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""
This module defines common used alias types for AIPerf. This both helps prevent circular imports and
helps with type hinting.
"""

from collections.abc import Callable
from typing import TYPE_CHECKING, Any, TypeAlias, TypeVar, Union

from aiperf.common.enums import (
    CaseInsensitiveStrEnum,
    CommAddress,
    CommandType,
    MediaType,
    MessageType,
    ServiceType,
)

if TYPE_CHECKING:
    from aiperf.clients.model_endpoint_info import ModelEndpointInfo
    from aiperf.common.messages import Message
    from aiperf.common.mixins import HooksMixin
    from aiperf.common.models import AIPerfBaseModel, Media
    from aiperf.common.protocols import ServiceProtocol


AnyT: TypeAlias = Any
AIPerfBaseModelT = TypeVar("AIPerfBaseModelT", bound="AIPerfBaseModel")
ClassEnumT = TypeVar("ClassEnumT", bound="CaseInsensitiveStrEnum")
ClassProtocolT = TypeVar("ClassProtocolT", bound=Any)
CommAddressType: TypeAlias = Union["CommAddress", str]
CommandTypeT: TypeAlias = CommandType | str
HooksMixinT = TypeVar("HooksMixinT", bound="HooksMixin")
HookParamsT = TypeVar("HookParamsT", bound=Any)
HookCallableParamsT = HookParamsT | Callable[["SelfT"], HookParamsT]
MediaT = TypeVar("MediaT", bound="Media")
MediaTypeT = MediaType | str
MessageT = TypeVar("MessageT", bound="Message")
MessageCallbackMapT: TypeAlias = dict["MessageTypeT", Callable[["Message"], Any] | list[Callable[["Message"], Any]]]  # fmt: skip
MessageOutputT = TypeVar("MessageOutputT", bound="Message")
MessageTypeT: TypeAlias = MessageType | str
MetricTagT: TypeAlias = str
ModelEndpointInfoT = TypeVar("ModelEndpointInfoT", bound="ModelEndpointInfo")
ProtocolT = TypeVar("ProtocolT", bound=Any)
RequestInputT = TypeVar("RequestInputT", bound=Any, contravariant=True)
RequestOutputT = TypeVar("RequestOutputT", bound=Any, covariant=True)
SelfT = TypeVar("SelfT", bound=Any)
ServiceProtocolT = TypeVar("ServiceProtocolT", bound="ServiceProtocol")
ServiceTypeT: TypeAlias = ServiceType | str
