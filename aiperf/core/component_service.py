# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

from typing import cast

from aiperf.common.config.service_config import ServiceConfig
from aiperf.common.config.user_config import UserConfig
from aiperf.common.enums.service_enums import ServiceState
from aiperf.common.messages.service_messages import (
    HeartbeatMessage,
    RegistrationMessage,
)
from aiperf.core.background_tasks import background_task
from aiperf.core.base_service import BaseService


class ComponentService(BaseService):
    """A base class for all component services.

    Component services are services that are part of the system and are managed by the system controller.
    They are responsible for registering with the system controller and sending heartbeats.
    """

    def __init__(
        self,
        service_config: ServiceConfig,
        user_config: UserConfig,
        service_id: str | None = None,
        **kwargs,
    ) -> None:
        self.heartbeat_interval_seconds = service_config.heartbeat_interval_seconds
        super().__init__(
            service_id=service_id,
            service_config=service_config,
            user_config=user_config,
            **kwargs,
        )

    @background_task(
        interval=lambda self: cast(ComponentService, self).heartbeat_interval_seconds
    )
    async def _heartbeat_task(self) -> None:
        self.debug(lambda: f"Sending heartbeat: {self.service_id}")
        await self.publish(
            HeartbeatMessage(
                service_id=self.service_id,
                state=ServiceState(str(self.state)),
                service_type=self.service_type,
            )
        )

    async def _initialize(self) -> None:
        await super()._initialize()
        # Register with the system controller on initialization
        self.debug(lambda: f"Registering with the system controller: {self.service_id}")
        await self.publish(
            RegistrationMessage(
                service_id=self.service_id,
                state=ServiceState(str(self.state)),
                service_type=self.service_type,
            )
        )
