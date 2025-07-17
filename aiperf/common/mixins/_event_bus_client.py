# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

from aiperf.common.enums._communication import CommunicationClientAddressType
from aiperf.common.hooks import AIPerfHook
from aiperf.common.mixins._comms import CommunicationsMixin
from aiperf.common.mixins._hooks import HooksMixin, supports_hooks


@supports_hooks(AIPerfHook.ON_MESSAGE)
class EventBusClientMixin(CommunicationsMixin, HooksMixin):
    """Mixin that provides clients for the event bus."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.sub_client = self.comms.create_sub_client(
            CommunicationClientAddressType.EVENT_BUS_PROXY_BACKEND
        )
        self.pub_client = self.comms.create_pub_client(
            CommunicationClientAddressType.EVENT_BUS_PROXY_FRONTEND
        )

    async def _initialize(self):
        await super()._initialize()

        await self.sub_client.initialize()
        await self.pub_client.initialize()

    async def _shutdown(self):
        await super()._shutdown()

        await self.sub_client.shutdown()
        await self.pub_client.shutdown()
