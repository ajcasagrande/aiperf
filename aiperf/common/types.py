# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

from typing import TYPE_CHECKING, Any, TypeVar

from aiperf.common.enums.communication_enums import CommAddress
from aiperf.common.enums.message_enums import MessageType

if TYPE_CHECKING:
    from aiperf.common.messages.base_messages import Message
    from aiperf.common.mixins.aiperf_lifecycle_mixin import AIPerfLifecycleMixin
    from aiperf.common.mixins.hooks_mixin import HooksMixin

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

MessageTypeT = MessageType | str
"""Alias for the MessageType being an enum or a custom string for user-defined message types."""

CommAddressType = CommAddress | str
"""Alias for the CommAddress being an enum or a custom string for user-defined addresses."""
