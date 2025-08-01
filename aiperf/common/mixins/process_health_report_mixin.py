# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

from aiperf.common.config.service_config import ServiceConfig
from aiperf.common.hooks import background_task
from aiperf.common.messages.health_messages import ProcessHealthMessage
from aiperf.common.mixins import MessageBusClientMixin, ProcessHealthMixin


class ProcessHealthReportMixin(MessageBusClientMixin, ProcessHealthMixin):
    """Mixin to provide process health information."""

    def __init__(self, service_config: ServiceConfig, **kwargs):
        super().__init__(service_config=service_config, **kwargs)
        self._health_check_interval: float = service_config.health_check_interval

    @background_task(
        immediate=False,
        interval=lambda self: self._health_check_interval,
    )
    async def _health_check_task(self) -> None:
        await self.publish(
            ProcessHealthMessage(service_id=self.id, process=self.get_process_health())
        )
