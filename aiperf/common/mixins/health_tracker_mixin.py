# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

from aiperf.common.enums.message_enums import MessageType
from aiperf.common.health_tracker import HealthTracker
from aiperf.common.hooks import AIPerfHook, on_message, provides_hooks
from aiperf.common.messages.health_messages import ProcessHealthMessage
from aiperf.common.mixins.message_bus_mixin import MessageBusClientMixin


@provides_hooks(AIPerfHook.ON_HEALTH_UPDATE)
class HealthTrackerMixin(MessageBusClientMixin):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.health_tracker = HealthTracker()

    @on_message(MessageType.PROCESS_HEALTH)
    async def _on_process_health_message(self, message: ProcessHealthMessage):
        self.health_tracker[message.service_id] = message.process
        await self.run_hooks(
            AIPerfHook.ON_HEALTH_UPDATE,
            service_id=message.service_id,
            health=message.process,
        )
