# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

from aiperf.common.comms.base_comms import BaseCommunication, CommunicationFactory
from aiperf.common.config.service_config import ServiceConfig
from aiperf.common.hooks import on_init, on_stop
from aiperf.common.mixins.hooks_mixin import HooksMixin


class CommunicationsMixin(HooksMixin):
    """Mixin that provides a communications instance."""

    def __init__(self, service_config: ServiceConfig, **kwargs) -> None:
        self.comms: BaseCommunication = CommunicationFactory.create_instance(
            service_config.comm_backend,
            config=service_config.comm_config,
        )
        super().__init__(service_config=service_config, comms=self.comms, **kwargs)

    @on_init
    async def _initialize_comms(self) -> None:
        await self.comms.initialize()

    @on_stop
    async def _shutdown_comms(self) -> None:
        await self.comms.shutdown()
