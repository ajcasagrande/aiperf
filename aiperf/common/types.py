# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

from typing import TYPE_CHECKING, Any, TypeVar

from aiperf.common.enums.message_enums import MessageType
from aiperf.common.enums.service_enums import ServiceType

if TYPE_CHECKING:
    from aiperf.common.messages.base_messages import Message
    from aiperf.common.mixins.aiperf_lifecycle_mixin import AIPerfLifecycleMixin
    from aiperf.common.models import ServiceRunInfo

ConfigT = TypeVar("ConfigT", bound=Any, covariant=True)
InputT = TypeVar("InputT", bound=Any)
LifecycleMixinT = TypeVar("LifecycleMixinT", bound="AIPerfLifecycleMixin")
MessageOutputT = TypeVar("MessageOutputT", bound="Message")
MessageT = TypeVar("MessageT", bound="Message")
MessageTypeT = MessageType | str
OutputT = TypeVar("OutputT", bound=Any)
RawRequestT = TypeVar("RawRequestT", bound=Any, contravariant=True)
RawResponseT = TypeVar("RawResponseT", bound=Any, contravariant=True)
RequestInputT = TypeVar("RequestInputT", bound=Any, contravariant=True)
RequestOutputT = TypeVar("RequestOutputT", bound=Any, covariant=True)
ResponseT = TypeVar("ResponseT", bound=Any, covariant=True)
ServiceTypeT = ServiceType | str
ServiceRunInfoT = TypeVar("ServiceRunInfoT", bound="ServiceRunInfo")
