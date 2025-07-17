#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
from collections.abc import Callable as Callable

from aiperf.common.enums import MessageType as MessageType
from aiperf.common.hooks import AIPerfHook as AIPerfHook
from aiperf.common.hooks import AIPerfHookParams as AIPerfHookParams
from aiperf.common.mixins._event_bus_client import (
    EventBusClientMixin as EventBusClientMixin,
)
from aiperf.common.mixins._hooks import HooksMixin as HooksMixin
from aiperf.common.mixins._hooks import supports_hooks as supports_hooks

class AIPerfMessageHandlerMixin(EventBusClientMixin, HooksMixin):
    def __init__(self, *args, **kwargs) -> None: ...
