# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

from aiperf.common.config.service_config import ServiceConfig
from aiperf.common.enums import CommunicationClientAddressType
from aiperf.common.hooks import AIPerfHook, supports_hooks
from aiperf.common.mixins.comms_mixins import CommunicationsMixin
from aiperf.common.mixins.hooks_mixin import HooksMixin


@supports_hooks(AIPerfHook.ON_MESSAGE)
class EventBusClientMixin(CommunicationsMixin, HooksMixin):
    """Mixin that provides clients for the event bus."""

    def __init__(self, service_config: ServiceConfig, **kwargs) -> None:
        super().__init__(service_config=service_config, **kwargs)
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
