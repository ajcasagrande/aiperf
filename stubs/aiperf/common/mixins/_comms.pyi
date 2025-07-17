#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
from aiperf.common.comms.base import BaseCommunication as BaseCommunication
from aiperf.common.comms.base import CommunicationFactory as CommunicationFactory
from aiperf.common.hooks import AIPerfHook as AIPerfHook
from aiperf.common.mixins._hooks import HooksMixin as HooksMixin
from aiperf.common.mixins._hooks import supports_hooks as supports_hooks

class CommunicationsMixin(HooksMixin):
    comms: BaseCommunication
    def __init__(self, **kwargs) -> None: ...
