#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
from _typeshed import Incomplete

from aiperf.common.enums._communication import (
    CommunicationClientAddressType as CommunicationClientAddressType,
)
from aiperf.common.hooks import AIPerfHook as AIPerfHook
from aiperf.common.mixins._comms import CommunicationsMixin as CommunicationsMixin
from aiperf.common.mixins._hooks import HooksMixin as HooksMixin
from aiperf.common.mixins._hooks import supports_hooks as supports_hooks

class EventBusClientMixin(CommunicationsMixin, HooksMixin):
    sub_client: Incomplete
    pub_client: Incomplete
    def __init__(self, **kwargs) -> None: ...
