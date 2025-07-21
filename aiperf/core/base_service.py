# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

import uuid
from typing import ClassVar

from aiperf.common.config.service_config import ServiceConfig
from aiperf.common.config.user_config import UserConfig
from aiperf.common.enums.service_enums import ServiceType
from aiperf.core.background_tasks import BackgroundTasksMixin
from aiperf.core.communication_mixins import MessageBusMixin


class BaseService(MessageBusMixin, BackgroundTasksMixin):
    """A base class for all services."""

    service_type: ClassVar[ServiceType | str]

    def __init__(
        self,
        service_config: ServiceConfig,
        user_config: UserConfig,
        service_id: str | None = None,
        **kwargs,
    ) -> None:
        self.service_config = service_config
        self.user_config = user_config
        self.service_id = (
            service_id or f"{self.service_type}_{str(uuid.uuid4().hex)[:8]}"
        )
        super().__init__(
            service_id=self.service_id,
            id=self.service_id,
            service_config=self.service_config,
            user_config=self.user_config,
            **kwargs,
        )

    async def run_forever(self) -> None:
        await self.initialize()
        await self.start()
        await self.stopped_event.wait()

    def __str__(self) -> str:
        return f"{self.service_type} {self.service_id}"

    def __repr__(self) -> str:
        return f"<{self.service_type} {self.service_id}>"
