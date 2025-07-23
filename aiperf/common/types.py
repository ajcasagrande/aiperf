# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

from typing import TYPE_CHECKING, Any, TypeVar, Union

if TYPE_CHECKING:
    from aiperf.clients.model_endpoint_info import ModelEndpointInfo
    from aiperf.common.enums import (
        CaseInsensitiveStrEnum,
        CommAddress,
        MessageType,
        ServiceType,
    )
    from aiperf.common.messages.base_messages import Message
    from aiperf.common.mixins.aiperf_lifecycle_mixin import AIPerfLifecycleMixin
    from aiperf.common.mixins.hooks_mixin import HooksMixin
    from aiperf.common.models import Turn
    from aiperf.common.models.record_models import (
        ParsedResponseRecord,
        RequestRecord,
        ResponseData,
    )
    from aiperf.common.protocols import TaskManagerProtocol
    from aiperf.common.tokenizer import Tokenizer

# TypeVars

ConfigT = TypeVar("ConfigT", bound=Any, covariant=True)
RequestInputT = TypeVar("RequestInputT", bound=Any, contravariant=True)
RequestOutputT = TypeVar("RequestOutputT", bound=Any, covariant=True)
ResponseT = TypeVar("ResponseT", bound=Any, covariant=True)
RawResponseT = TypeVar("RawResponseT", bound=Any, contravariant=True)
InputT = TypeVar("InputT", bound=Any)
OutputT = TypeVar("OutputT", bound=Any)
RawRequestT = TypeVar("RawRequestT", bound=Any, contravariant=True)
MessageT = TypeVar("MessageT", bound="Message")
MessageOutputT = TypeVar("MessageOutputT", bound="Message")
LifecycleMixinT = TypeVar("LifecycleMixinT", bound="AIPerfLifecycleMixin")
HooksMixinT = TypeVar("HooksMixinT", bound="HooksMixin")
ClassEnumT = TypeVar("ClassEnumT", bound="CaseInsensitiveStrEnum")
ClassProtocolT = TypeVar("ClassProtocolT", bound=Any)
ResponseDataT = TypeVar("ResponseDataT", bound="ResponseData")
ParsedResponseRecordT = TypeVar("ParsedResponseRecordT", bound="ParsedResponseRecord")
TaskManagerProtocolT = TypeVar("TaskManagerProtocolT", bound="TaskManagerProtocol")
RequestRecordT = TypeVar("RequestRecordT", bound="RequestRecord")
ModelEndpointInfoT = TypeVar("ModelEndpointInfoT", bound="ModelEndpointInfo")
TurnT = TypeVar("TurnT", bound="Turn")
TokenizerT = TypeVar("TokenizerT", bound="Tokenizer")


# Union types

MessageTypeT = Union["MessageType", str]
"""Alias for the MessageType being an enum or a custom string for user-defined message types."""

CommAddressType = Union["CommAddress", str]
"""Alias for the CommAddress being an enum or a custom string for user-defined addresses."""

ServiceTypeT = Union["ServiceType", str]
"""Alias for the ServiceType being an enum or a custom string for user-defined service types."""
